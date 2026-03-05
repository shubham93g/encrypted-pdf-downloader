#!/usr/bin/env bash
set -e

echo "Setting up payslip-downloader..."

python3 -m venv .venv
source .venv/bin/activate

pip install --upgrade pip --quiet
pip install -r requirements.txt --quiet

if [ ! -f .env ]; then
  cp .env.example .env
  echo ""
  echo ".env created from .env.example — fill in your values before running:"
  echo "  SENDER_EMAIL    — email address that sends your payslips"
  echo "  SUBJECT_KEYWORD — keyword in the subject line (e.g. payslip)"
  echo "  PDF_PASSWORD    — password to decrypt the PDF attachments"
  echo "  OUTPUT_DIR      — where to save PDFs (default: ./payslips)"
  echo "  MAX_PAYSLIPS    — how many recent payslips to fetch (default: 6)"
else
  echo ".env already exists, skipping."
fi

echo ""
echo "Setup complete."
echo ""
echo "Next steps:"
echo "  1. Place your credentials.json in this directory (see README.md)"
echo "  2. Edit .env with your settings"
echo "  3. Run: ./run.sh"
