import base64
import io
import logging
import os
import sys
from datetime import datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any, Optional

log = logging.getLogger(__name__)

from pypdf import PdfReader, PdfWriter
from pypdf.errors import FileNotDecryptedError
from dotenv import load_dotenv
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
TOKEN_FILE = "token.json"
CREDENTIALS_FILE = "credentials.json"


def load_config() -> dict[str, Any]:
    load_dotenv()
    required = ["SENDER_EMAIL", "SUBJECT_PREFIX", "PDF_PASSWORD"]
    missing = [k for k in required if not os.getenv(k)]
    if missing:
        sys.exit(f"Error: missing required environment variables: {', '.join(missing)}")

    return {
        "sender_email": os.getenv("SENDER_EMAIL"),
        "subject_prefix": os.getenv("SUBJECT_PREFIX"),
        "pdf_password": os.getenv("PDF_PASSWORD"),
        "output_dir": os.getenv("OUTPUT_DIR", "./pdfs"),
        "max_pdfs": int(os.getenv("MAX_PDFS", "6")),
        "overwrite_files": os.getenv("OVERWRITE_FILES", "false").strip().lower() == "true",
    }


def get_gmail_service() -> Any:
    creds = None

    if Path(TOKEN_FILE).exists():
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not Path(CREDENTIALS_FILE).exists():
                sys.exit(
                    f"Error: '{CREDENTIALS_FILE}' not found. "
                    "Download it from Google Cloud Console and place it in the project root. "
                    "See README.md for instructions."
                )
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)

        with open(TOKEN_FILE, "w") as f:
            f.write(creds.to_json())

    return build("gmail", "v1", credentials=creds)


def search_pdf_emails(service: Any, sender_email: str, subject_prefix: str, max_results: int) -> list[dict]:
    # Use the first word of the prefix as the Gmail search term (broad pre-filter)
    search_word = subject_prefix.split()[0]
    query = f"from:{sender_email} subject:{search_word}"
    log.info("  Gmail query: %s", query)
    result = (
        service.users()
        .messages()
        .list(userId="me", q=query, maxResults=max_results)
        .execute()
    )
    return result.get("messages", [])


def get_email_metadata(service: Any, message_id: str) -> tuple[Optional[datetime], str]:
    msg = (
        service.users()
        .messages()
        .get(userId="me", id=message_id, format="metadata", metadataHeaders=["Date", "Subject"])
        .execute()
    )
    headers = msg.get("payload", {}).get("headers", [])
    date = None
    subject = ""
    for header in headers:
        if header["name"] == "Date":
            try:
                date = parsedate_to_datetime(header["value"].strip())
            except (ValueError, TypeError):
                date = None
        elif header["name"] == "Subject":
            subject = header["value"]
    return date, subject


def find_pdf_attachment(service: Any, message_id: str) -> tuple[Optional[str], Optional[str]]:
    msg = (
        service.users()
        .messages()
        .get(userId="me", id=message_id, format="full")
        .execute()
    )

    def find_in_parts(parts):
        for part in parts:
            mime = part.get("mimeType", "")
            filename = part.get("filename", "")
            if mime == "application/pdf" or filename.lower().endswith(".pdf"):
                attachment_id = part.get("body", {}).get("attachmentId")
                if attachment_id:
                    return attachment_id, filename
            sub_parts = part.get("parts", [])
            if sub_parts:
                result = find_in_parts(sub_parts)
                if result:
                    return result
        return None, None

    parts = msg.get("payload", {}).get("parts", [])
    return find_in_parts(parts)


def download_attachment(service: Any, message_id: str, attachment_id: str) -> bytes:
    attachment = (
        service.users()
        .messages()
        .attachments()
        .get(userId="me", messageId=message_id, id=attachment_id)
        .execute()
    )
    data = attachment["data"]
    return base64.urlsafe_b64decode(data)


def decrypt_pdf(pdf_bytes: bytes, password: str) -> bytes:
    reader = PdfReader(io.BytesIO(pdf_bytes))
    if reader.decrypt(password) == 0:
        raise FileNotDecryptedError("Incorrect password")
    writer = PdfWriter()
    for page in reader.pages:
        writer.add_page(page)
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


def save_pdf(pdf_bytes: bytes, output_dir: Path, index: int, date: datetime, original_filename: str, overwrite: bool = False) -> Path:
    year = date.strftime("%Y")
    month = date.strftime("%b")
    day = date.strftime("%d")
    stem = Path(original_filename).stem
    base = f"{index:02d}_{year}-{month}-{day}_{stem}"
    output_path = Path(output_dir) / f"{base}.pdf"
    if output_path.exists():
        if overwrite:
            log.warning("       Warning: overwriting existing file %s", output_path.name)
        else:
            counter = 2
            while output_path.exists():
                output_path = Path(output_dir) / f"{base} ({counter}).pdf"
                counter += 1
            log.warning("       Warning: file already exists, saving as %s", output_path.name)
    output_path.write_bytes(pdf_bytes)
    return output_path


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    config = load_config()

    output_dir = Path(config["output_dir"])
    output_dir.mkdir(parents=True, exist_ok=True)

    log.info("Authenticating with Gmail...")
    service = get_gmail_service()

    log.info(
        "Searching for up to %d matching emails from %s with subject starting with '%s'...",
        config["max_pdfs"],
        config["sender_email"],
        config["subject_prefix"],
    )
    messages = search_pdf_emails(
        service,
        config["sender_email"],
        config["subject_prefix"],
        config["max_pdfs"],
    )

    if not messages:
        log.warning("No matching emails found. Check your SENDER_EMAIL and SUBJECT_PREFIX settings.")
        return

    log.info("Found %d candidate email(s). Fetching metadata...", len(messages))

    # Fetch metadata, apply prefix filter, sort descending (most recent first)
    emails_with_dates = []
    for msg in messages:
        date, subject = get_email_metadata(service, msg["id"])
        if not date:
            log.warning("  Warning: could not parse date for message %s, skipping.", msg["id"])
            continue
        if not subject.lower().startswith(config["subject_prefix"].lower()):
            log.info("  Skipping: subject does not start with prefix — \"%s\"", subject)
            continue
        emails_with_dates.append((msg["id"], date))

    emails_with_dates.sort(key=lambda x: x[1], reverse=True)

    log.info("Processing %d PDF(s)...\n", len(emails_with_dates))

    for index, (message_id, date) in enumerate(emails_with_dates, start=1):
        label = date.strftime("%B %Y")
        log.info("  [%02d] %s — downloading attachment...", index, label)

        attachment_id, filename = find_pdf_attachment(service, message_id)
        if not attachment_id:
            log.warning("       Warning: no PDF attachment found in email dated %s, skipping.", label)
            continue

        pdf_bytes = download_attachment(service, message_id, attachment_id)

        log.info("       Decrypting PDF...")
        try:
            decrypted_bytes = decrypt_pdf(pdf_bytes, config["pdf_password"])
        except FileNotDecryptedError:
            log.warning(
                "       Warning: incorrect PDF password for email dated %s, skipping. "
                "Check PDF_PASSWORD in your .env file.",
                label,
            )
            continue

        output_path = save_pdf(decrypted_bytes, output_dir, index, date, filename, config["overwrite_files"])
        log.info("       Saved: %s\n", output_path)

    log.info("Done. %d PDF(s) saved to '%s/'.", len(emails_with_dates), output_dir)


if __name__ == "__main__":
    main()
