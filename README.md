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

### 1. Google Cloud — enable Gmail API and create OAuth credentials

#### 1a. Create a project and enable the Gmail API

1. Open [Google Cloud Console — Create Project](https://console.cloud.google.com/projectcreate), give it a name (e.g. `payslip-downloader`), and click **Create**
2. Open [Gmail API — Enable](https://console.cloud.google.com/apis/library/gmail.googleapis.com), make sure your new project is selected in the top bar, and click **Enable**

#### 1b. Configure the OAuth consent screen

Before creating credentials, Google requires a consent screen to be set up.

1. Open [OAuth consent screen](https://console.cloud.google.com/apis/credentials/consent)
2. Select **External** and click **Create**
3. Fill in the required fields:
   - **App name**: anything (e.g. `Payslip Downloader`)
   - **User support email**: your Gmail address
   - **Developer contact email**: your Gmail address
4. Click **Save and Continue** through the remaining screens (Scopes, Test users, Summary) — no changes needed on those pages

#### 1c. Create an OAuth client ID

1. Open [Credentials](https://console.cloud.google.com/apis/credentials) and click **+ Create Credentials > OAuth client ID**
2. Set **Application type** to **Desktop app**
3. Give it any name (e.g. `Payslip Downloader`) and click **Create**
4. In the confirmation dialog, click **Download JSON**
5. Rename the downloaded file to `credentials.json` and place it in the project root

#### What happens on first run

The first time you run the script, a browser window opens asking you to sign in and grant read-only Gmail access. After you approve, a `token.json` file is saved automatically — subsequent runs skip the browser step entirely.

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
