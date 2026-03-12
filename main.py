import base64
import io
import logging
import os
import sys
from datetime import datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any, Optional

_LEVEL_ABBREV = {
    logging.DEBUG: "DEBG",
    logging.INFO: "INFO",
    logging.WARNING: "WARN",
    logging.ERROR: "ERRO",
    logging.CRITICAL: "CRIT",
}


class _BriefFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        record.levelname = _LEVEL_ABBREV.get(record.levelno, record.levelname[:4])
        return super().format(record)


log = logging.getLogger(__name__)

from pypdf import PdfReader, PdfWriter
from pypdf.errors import FileNotDecryptedError
from dotenv import load_dotenv
from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
TOKEN_FILE = "token.json"
CREDENTIALS_FILE = "credentials.json"


def load_config() -> dict[str, Any]:
    load_dotenv()
    required = ["SENDER_EMAIL", "SUBJECT_KEYWORD"]
    missing = [k for k in required if not os.getenv(k)]
    if missing:
        sys.exit(f"Error: missing required environment variables: {', '.join(missing)}")

    return {
        "sender_email": os.getenv("SENDER_EMAIL"),
        "subject_keyword": os.getenv("SUBJECT_KEYWORD"),
        "pdf_passwords": [p.strip() for p in os.getenv("PDF_PASSWORDS", "").split(",") if p.strip()],
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
            try:
                creds.refresh(Request())
            except RefreshError:
                log.warning(
                    "OAuth token has expired or been revoked — re-authorizing. "
                    "A browser window will open."
                )
                Path(TOKEN_FILE).unlink(missing_ok=True)
                creds = None
        if not creds:
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


def search_pdf_emails(service: Any, sender_email: str, subject_keyword: str, max_results: int) -> list[dict]:
    query = f"from:{sender_email} subject:{subject_keyword} has:attachment"
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
                attachment_id, filename = find_in_parts(sub_parts)
                if attachment_id:
                    return attachment_id, filename
        return None, None

    payload = msg.get("payload", {})
    parts = payload.get("parts", [])
    if parts:
        return find_in_parts(parts)
    # Single-part message — check the payload itself
    return find_in_parts([payload])


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


def decrypt_pdf(pdf_bytes: bytes, passwords: list[str]) -> bytes:
    reader = PdfReader(io.BytesIO(pdf_bytes))
    if not reader.is_encrypted:
        log.info("       PDF is not encrypted — saving as-is.")
        return pdf_bytes
    for password in passwords:
        if reader.decrypt(password) != 0:
            writer = PdfWriter()
            for page in reader.pages:
                writer.add_page(page)
            out = io.BytesIO()
            writer.write(out)
            return out.getvalue()
        # decrypt() mutates reader state — re-open for next attempt
        reader = PdfReader(io.BytesIO(pdf_bytes))
    raise FileNotDecryptedError("No password matched")


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
    load_dotenv()
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    handler = logging.StreamHandler()
    handler.setFormatter(_BriefFormatter("%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"))
    logging.basicConfig(level=getattr(logging, log_level, logging.INFO), handlers=[handler])

    config = load_config()

    output_dir = Path(config["output_dir"])
    output_dir.mkdir(parents=True, exist_ok=True)

    log.info("Authenticating with Gmail...")
    service = get_gmail_service()

    log.info(
        "Searching for up to %d matching emails from %s with subject containing '%s'...",
        config["max_pdfs"],
        config["sender_email"],
        config["subject_keyword"],
    )
    messages = search_pdf_emails(
        service,
        config["sender_email"],
        config["subject_keyword"],
        config["max_pdfs"],
    )

    if not messages:
        log.warning("No matching emails found. Check your SENDER_EMAIL and SUBJECT_KEYWORD settings.")
        return

    log.info("Found %d candidate email(s). Fetching metadata...", len(messages))

    # Fetch metadata and sort descending (most recent first)
    emails = []
    for msg in messages:
        date, subject = get_email_metadata(service, msg["id"])
        if not date:
            log.warning("  Warning: could not parse date for message %s, skipping.", msg["id"])
            continue
        emails.append((msg["id"], date, subject))

    emails.sort(key=lambda x: x[1], reverse=True)

    log.info("Processing %d PDF(s)...", len(emails))

    for index, (message_id, date, subject) in enumerate(emails, start=1):
        log.info("  [%02d] %s — downloading attachment...", index, subject)

        attachment_id, filename = find_pdf_attachment(service, message_id)
        if not attachment_id:
            log.warning("       Warning: no PDF attachment found in email \"%s\", skipping.", subject)
            continue

        pdf_bytes = download_attachment(service, message_id, attachment_id)

        try:
            decrypted_bytes = decrypt_pdf(pdf_bytes, config["pdf_passwords"])
        except FileNotDecryptedError:
            log.warning(
                "       Warning: no PDF password matched for email \"%s\", skipping. "
                "Check PDF_PASSWORDS in your .env file.",
                subject,
            )
            continue

        output_path = save_pdf(decrypted_bytes, output_dir, index, date, filename, config["overwrite_files"])
        log.info("       Saved: %s", output_path)

    log.info("Done. %d PDF(s) saved to '%s/'.", len(emails), output_dir)


if __name__ == "__main__":
    main()
