# Project: Encrypted PDF Downloader

Single-file Python script that fetches password-protected PDFs from Gmail and saves them locally.

## Stack
- Python 3.9+, single script (`main.py`)
- Gmail API via OAuth2 (`google-api-python-client`, `google-auth-oauthlib`)
- PDF decryption: `pikepdf`
- Config: `python-dotenv` loading from `.env`
- Venv: `.venv/` managed by `setup.sh`

## Key files
- `main.py` — all logic (auth, search, download, decrypt, save)
- `.env` — secrets (gitignored); `.env.example` is the committed template
- `credentials.json` — OAuth2 credentials from Google Cloud (gitignored, user-provided)
- `token.json` — saved OAuth2 token after first auth (gitignored, auto-generated)
- `setup.sh` — creates venv, installs deps, copies .env.example
- `run.sh` — activates venv and runs main.py

## Config variables (all in .env)
- `SENDER_EMAIL` — sender address to filter by
- `SUBJECT_PREFIX` — literal string the subject must start with (case-insensitive)
- `PDF_PASSWORD` — shared PDF decryption password
- `OUTPUT_DIR` — where to save PDFs (default: `./pdfs`)
- `MAX_PDFS` — how many recent PDFs to fetch (default: 6)

## Output filename format
`{index:02d}_{YYYY}-{Mon}-{DD}_{OriginalFileStem}.pdf` — e.g. `01_2026-Mar-05_Payslip.pdf`. Index 01 = most recent email by received date.

## Gmail OAuth2 scope
`gmail.readonly` — read-only, minimal privilege.
