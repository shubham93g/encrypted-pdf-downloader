# Payslip Downloader

A Python script that fetches your payslip emails from Gmail, decrypts the password-protected PDF attachments, and saves them locally in reverse chronological order.

## How it works

1. Authenticates with your Gmail account via OAuth2 (read-only access)
2. Searches for emails from a specific sender address that contain a subject keyword and a PDF attachment
3. Downloads and decrypts the PDFs using a shared password
4. Saves them as `01-Month-Year.pdf`, `02-Month-Year.pdf`, etc. — most recent first

## Prerequisites

- Python 3.9 or later
- A Google account with Gmail
- A Google Cloud project with the Gmail API enabled

## Setup

### 1. Google Cloud — enable Gmail API and get credentials

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project (or select an existing one)
3. Navigate to **APIs & Services > Library**, search for **Gmail API**, and click **Enable**
4. Go to **APIs & Services > Credentials**
5. Click **Create Credentials > OAuth client ID**
6. Choose **Desktop app** as the application type
7. Download the JSON file and rename it to `credentials.json`
8. Place `credentials.json` in the project root directory

> Note: On first run the script will open a browser window asking you to authorize access. After authorization, a `token.json` file is saved so you won't need to authorize again.

### 2. Install dependencies

```bash
./setup.sh
```

This will:
- Create a `.venv` virtual environment
- Install all Python dependencies
- Copy `.env.example` to `.env` for you to fill in

### 3. Configure

Edit the `.env` file created by `setup.sh`:

```env
SENDER_EMAIL=payroll@yourcompany.com   # Who sends the payslip emails
SUBJECT_KEYWORD=payslip                # Keyword that appears in the subject
PDF_PASSWORD=your_pdf_password         # Password to unlock the PDFs
OUTPUT_DIR=./payslips                  # Where to save the decrypted PDFs
MAX_PAYSLIPS=6                         # How many recent payslips to fetch
```

> `OUTPUT_DIR` can be an absolute path (e.g. `/Users/you/Documents/payslips`) or a path relative to the project root.

### 4. Run

```bash
./run.sh
```

On the first run, your browser will open for Gmail authorization. Once authorized, subsequent runs will proceed without a browser prompt.

## Output

PDFs are saved in the output directory with filenames based on when the email was received:

```
payslips/
├── 01-March-2026.pdf     ← most recent
├── 02-February-2026.pdf
├── 03-January-2026.pdf
├── 04-December-2025.pdf
├── 05-November-2025.pdf
└── 06-October-2025.pdf   ← oldest
```

## Security

- `credentials.json`, `token.json`, and `.env` are all listed in `.gitignore` and will never be committed
- The `.env.example` file (safe to commit) contains only placeholder values
- Gmail access uses the `gmail.readonly` scope — the script cannot send, delete, or modify emails

## Troubleshooting

**"credentials.json not found"**
Download your OAuth credentials from Google Cloud Console and place them in the project root. See step 1 above.

**"incorrect PDF password"**
Double-check the `PDF_PASSWORD` value in your `.env` file.

**"No payslip emails found"**
Verify that `SENDER_EMAIL` exactly matches the sender's address and that `SUBJECT_KEYWORD` appears in the subject of those emails. You can confirm by searching Gmail directly with `from:sender@example.com subject:keyword`.

**Token expired / authorization error**
Delete `token.json` and run `./run.sh` again to re-authorize.

**Permission denied running scripts**
```bash
chmod +x setup.sh run.sh
```
