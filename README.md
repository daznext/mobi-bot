# Kindle Converter Telegram Bot

Telegram bot that accepts `fb2`, `fb2.zip`, and `epub` books, converts them to `mobi` with Calibre, sends the converted file back, and can email it to a saved Kindle address.

## Requirements

- Python from `./venv`
- Calibre CLI (`ebook-convert`) installed and available in `PATH`
- Telegram bot token
- SMTP account approved in Amazon Kindle personal document settings

## Setup

```bash
cp .env.example .env
./venv/bin/pip install -r requirements.txt
```

Fill `.env`, then export it before running:

```bash
set -a
source .env
set +a
./venv/bin/python -m kindle_bot
```

If `ebook-convert` is not in `PATH`, set `EBOOK_CONVERT_BIN`, for example:

```bash
export EBOOK_CONVERT_BIN=/opt/homebrew/bin/ebook-convert
```

## Bot Commands

- `/start` - show help
- `/setemail name@kindle.com` - save or replace Kindle email
- `/email` - show saved Kindle email
- `/deleteemail` - delete saved Kindle email
- `/help` - show help

Send a book as a Telegram document. The bot converts it to `mobi` and returns the file. If you have a saved Kindle email, the bot also shows a button to email the converted book to that address.

