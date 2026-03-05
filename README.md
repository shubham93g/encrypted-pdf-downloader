# Encrypted PDF Downloader

A Python script that fetches emails from Gmail, decrypts the password-protected PDF attachments, and saves them locally in reverse chronological order.

## How it works

1. Authenticates with your Gmail account via OAuth2 (read-only access)
2. Searches for emails from a specific sender address that contain a subject keyword and a PDF attachment
3. Downloads and decrypts the PDFs using a shared password
4. Saves them as `01_2026-Mar-05_Document.pdf`, `02_2026-Feb-03_Document.pdf`, etc. — most recent first

## Prerequisites

- Python 3.9 or later
- A Google account with Gmail
- A Google Cloud project with the Gmail API enabled

## Setup

### 1. Google Cloud — enable Gmail API and create OAuth credentials

#### 1a. Create a project and enable the Gmail API

1. Open [Google Cloud Console — Create Project](https://console.cloud.google.com/projectcreate), give it a name (e.g. `encrypted-pdf-downloader`), and click **Create**
2. After the project is created, Google will show a notification — click **Select Project** to switch to it (or select it from the project dropdown in the top bar)
3. Open [Gmail API — Enable](https://console.cloud.google.com/apis/library/gmail.googleapis.com) and click **Enable**

> **Important:** All steps in section 1 (API, consent screen, and credentials) must be done in the same project. Confirm the correct project name is shown in the top-left dropdown before proceeding.

#### 1b. Configure the OAuth consent screen

Before creating credentials, Google requires a consent screen to be set up.

1. Open [OAuth consent screen](https://console.cloud.google.com/apis/credentials/consent)
2. Select **External** and click **Create**
3. Fill in the required fields:
   - **App name**: anything (e.g. `Encrypted PDF Downloader`)
   - **User support email**: your Gmail address
   - **Developer contact email**: your Gmail address
4. Click **Save and Continue** through the **Scopes** and **Test users** screens
5. On the **Test users** screen, click **+ Add Users**, enter your Gmail address, and click **Add**
6. Click **Save and Continue** through to the Summary, then **Back to Dashboard**

#### 1c. Create an OAuth client ID

1. Open [Credentials](https://console.cloud.google.com/apis/credentials) and click **+ Create Credentials > OAuth client ID**
2. Set **Application type** to **Desktop app**
3. Give it any name (e.g. `Encrypted PDF Downloader`) and click **Create**
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
SENDER_EMAIL=sender@example.com            # Who sends the emails with PDF attachments
SUBJECT_PREFIX=Your subject prefix here    # Subject must start with this (case-insensitive)
PDF_PASSWORD=your_pdf_password             # Password to unlock the PDFs
OUTPUT_DIR=./pdfs                          # Where to save the decrypted PDFs
MAX_PDFS=6                                 # How many recent PDFs to fetch
```

> `OUTPUT_DIR` can be an absolute path (e.g. `/Users/you/Documents/pdfs`) or a path relative to the project root.

### 4. Run

```bash
./run.sh
```

On the first run, your browser will open for Gmail authorization. Once authorized, subsequent runs will proceed without a browser prompt.

## Output

PDFs are saved in the output directory with filenames in the format `{index}_{YYYY}-{Mon}-{DD}_{OriginalName}.pdf`:

```
pdfs/
├── 01_2026-Mar-05_Document.pdf     ← most recent
├── 02_2026-Feb-03_Document.pdf
├── 03_2026-Jan-06_Document.pdf
├── 04_2025-Dec-04_Document.pdf
├── 05_2025-Nov-05_Document.pdf
└── 06_2025-Oct-03_Document.pdf     ← oldest
```

If a file with the same name already exists, the script appends a numeric suffix (macOS-style) rather than overwriting, and prints a warning:

```
Warning: file already exists, saving as 01_2026-Mar-05_Document (2).pdf
```

## Security

- `credentials.json`, `token.json`, and `.env` are all listed in `.gitignore` and will never be committed
- The `.env.example` file (safe to commit) contains only placeholder values
- Gmail access uses the `gmail.readonly` scope — the script cannot send, delete, or modify emails

## Troubleshooting

**"Gmail API has not been used in project"**
The Gmail API is not enabled in the project your credentials belong to. Open [Gmail API — Enable](https://console.cloud.google.com/apis/library/gmail.googleapis.com), make sure the correct project is selected in the top-left dropdown, and click **Enable**. Then delete `token.json` and re-run `./run.sh`.

**"credentials.json not found"**
Download your OAuth credentials from Google Cloud Console and place them in the project root. See step 1 above.

**"incorrect PDF password"**
Double-check the `PDF_PASSWORD` value in your `.env` file.

**"No matching emails found"**
Verify that `SENDER_EMAIL` exactly matches the sender's address and that `SUBJECT_PREFIX` matches the beginning of the subject line. You can confirm by searching Gmail directly with `from:sender@example.com subject:firstword`.

**"App has not completed Google verification"**
Your OAuth app is in Testing mode — only approved test users can authorize it. Open the [OAuth consent screen](https://console.cloud.google.com/apis/credentials/consent), scroll to **Test users**, click **+ Add Users**, and add your Gmail address.

**Token expired / authorization error**
Delete `token.json` and run `./run.sh` again to re-authorize.

**Permission denied running scripts**
```bash
chmod +x setup.sh run.sh
```
