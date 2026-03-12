#!/usr/bin/env bash
set -e

echo "Setting up encrypted-pdf-downloader..."

REQUIRED_VERSION=$(cat .python-version | tr -d '[:space:]')

if command -v pyenv &>/dev/null; then
  if ! pyenv versions --bare | grep -q "^${REQUIRED_VERSION}"; then
    echo "Installing Python $REQUIRED_VERSION via pyenv..."
    pyenv install "$REQUIRED_VERSION"
  fi
  pyenv local "$REQUIRED_VERSION"
  export PATH="$(pyenv prefix)/bin:$PATH"
else
  PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
  PYTHON_MAJOR_MINOR=$(echo "$PYTHON_VERSION" | cut -d. -f1,2)
  if [ "$PYTHON_MAJOR_MINOR" != "$REQUIRED_VERSION" ]; then
    echo "Error: Python $REQUIRED_VERSION is required (found $PYTHON_VERSION)."
    echo "Install pyenv for automatic version management: https://github.com/pyenv/pyenv"
    exit 1
  fi
fi

python3 -m venv .venv
source .venv/bin/activate

pip install --upgrade pip --quiet
pip install -r requirements.txt --quiet

if [ ! -f .env ]; then
  cp .env.example .env
  echo ""
  echo ".env created from .env.example — fill in your values before running:"
  echo "  SENDER_EMAIL    — email address that sends the PDFs"
  echo "  SUBJECT_PREFIX  — subject line prefix to filter emails"
  echo "  PDF_PASSWORDS   — comma-separated passwords to decrypt the PDF attachments"
  echo "  OUTPUT_DIR      — where to save PDFs (default: ./pdfs)"
  echo "  MAX_PDFS        — how many recent PDFs to fetch (default: 6)"
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
