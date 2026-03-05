import base64
import io
import os
import sys
from datetime import datetime
from pathlib import Path

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


def load_config():
    load_dotenv()
    required = ["SENDER_EMAIL", "SUBJECT_PREFIX", "PDF_PASSWORD"]
    missing = [k for k in required if not os.getenv(k)]
    if missing:
        sys.exit(f"Error: missing required environment variables: {', '.join(missing)}")

    return {
        "sender_email": os.environ["SENDER_EMAIL"],
        "subject_prefix": os.environ["SUBJECT_PREFIX"],
        "pdf_password": os.environ["PDF_PASSWORD"],
        "output_dir": os.getenv("OUTPUT_DIR", "./pdfs"),
        "max_pdfs": int(os.getenv("MAX_PDFS", "6")),
        "overwrite_files": os.getenv("OVERWRITE_FILES", "false").strip().lower() == "true",
    }


def get_gmail_service():
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


def search_pdf_emails(service, sender_email, subject_prefix, max_results):
    # Use the first word of the prefix as the Gmail search term (broad pre-filter)
    search_word = subject_prefix.split()[0]
    query = f"from:{sender_email} subject:{search_word}"
    print(f"  Gmail query: {query}")
    result = (
        service.users()
        .messages()
        .list(userId="me", q=query, maxResults=max_results)
        .execute()
    )
    return result.get("messages", [])


def get_email_metadata(service, message_id):
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
            date_str = header["value"]
            # Parse various RFC 2822 date formats
            for fmt in (
                "%a, %d %b %Y %H:%M:%S %z",
                "%a, %d %b %Y %H:%M:%S %Z",
                "%d %b %Y %H:%M:%S %z",
                "%d %b %Y %H:%M:%S %Z",
            ):
                try:
                    date = datetime.strptime(date_str.strip(), fmt)
                    break
                except ValueError:
                    continue
            if date is None:
                # Fallback: strip timezone name/offset and retry
                parts = date_str.strip().rsplit(" ", 1)
                if len(parts) == 2:
                    for fmt in ("%a, %d %b %Y %H:%M:%S", "%d %b %Y %H:%M:%S"):
                        try:
                            date = datetime.strptime(parts[0].strip(), fmt)
                            break
                        except ValueError:
                            continue
        elif header["name"] == "Subject":
            subject = header["value"]
    return date, subject


def find_pdf_attachment(service, message_id):
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


def download_attachment(service, message_id, attachment_id):
    attachment = (
        service.users()
        .messages()
        .attachments()
        .get(userId="me", messageId=message_id, id=attachment_id)
        .execute()
    )
    data = attachment["data"]
    return base64.urlsafe_b64decode(data)


def decrypt_pdf(pdf_bytes, password):
    reader = PdfReader(io.BytesIO(pdf_bytes))
    reader.decrypt(password)
    writer = PdfWriter()
    for page in reader.pages:
        writer.add_page(page)
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


def save_pdf(pdf_bytes, output_dir, index, date, original_filename, overwrite=False):
    year = date.strftime("%Y")
    month = date.strftime("%b")
    day = date.strftime("%d")
    stem = Path(original_filename).stem
    base = f"{index:02d}_{year}-{month}-{day}_{stem}"
    output_path = Path(output_dir) / f"{base}.pdf"
    if output_path.exists() and not overwrite:
        counter = 2
        while output_path.exists():
            output_path = Path(output_dir) / f"{base} ({counter}).pdf"
            counter += 1
        print(f"       Warning: file already exists, saving as {output_path.name}")
    output_path.write_bytes(pdf_bytes)
    return output_path


def main():
    config = load_config()

    output_dir = Path(config["output_dir"])
    output_dir.mkdir(parents=True, exist_ok=True)

    print("Authenticating with Gmail...")
    service = get_gmail_service()

    print(
        f"Searching for up to {config['max_pdfs']} matching emails "
        f"from {config['sender_email']} with subject starting with '{config['subject_prefix']}'..."
    )
    messages = search_pdf_emails(
        service,
        config["sender_email"],
        config["subject_prefix"],
        config["max_pdfs"],
    )

    if not messages:
        print("No matching emails found. Check your SENDER_EMAIL and SUBJECT_PREFIX settings.")
        return

    print(f"Found {len(messages)} candidate email(s). Fetching metadata...")

    # Fetch metadata, apply prefix filter, sort descending (most recent first)
    emails_with_dates = []
    for msg in messages:
        date, subject = get_email_metadata(service, msg["id"])
        if not date:
            print(f"  Warning: could not parse date for message {msg['id']}, skipping.")
            continue
        if not subject.lower().startswith(config["subject_prefix"].lower()):
            print(f"  Skipping: subject does not start with prefix — \"{subject}\"")
            continue
        emails_with_dates.append((msg["id"], date))

    emails_with_dates.sort(key=lambda x: x[1], reverse=True)

    print(f"Processing {len(emails_with_dates)} PDF(s)...\n")

    for index, (message_id, date) in enumerate(emails_with_dates, start=1):
        label = date.strftime("%B %Y")
        print(f"  [{index:02d}] {label} — downloading attachment...")

        attachment_id, filename = find_pdf_attachment(service, message_id)
        if not attachment_id:
            print(f"       Warning: no PDF attachment found in email dated {label}, skipping.")
            continue

        pdf_bytes = download_attachment(service, message_id, attachment_id)

        print(f"       Decrypting PDF...")
        try:
            decrypted_bytes = decrypt_pdf(pdf_bytes, config["pdf_password"])
        except FileNotDecryptedError:
            sys.exit(
                f"Error: incorrect PDF password for email dated {label}. "
                "Check PDF_PASSWORD in your .env file."
            )

        output_path = save_pdf(decrypted_bytes, output_dir, index, date, filename, config["overwrite_files"])
        print(f"       Saved: {output_path}\n")

    print(f"Done. {len(emails_with_dates)} PDF(s) saved to '{output_dir}/'.")


if __name__ == "__main__":
    main()
