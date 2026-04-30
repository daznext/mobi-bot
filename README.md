# Kindle Converter Telegram Bot

Telegram bot that accepts `fb2`, `fb2.zip`, and `epub` books, converts them to `mobi` with Calibre, sends the converted file back, and can email it to a saved Kindle address.

## Requirements

- Python from `./venv`
- Calibre CLI (`ebook-convert`) installed and available in `PATH`
- Telegram bot token
- SMTP account or Gmail API sender approved in Amazon Kindle personal document settings

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

The address from `SMTP_FROM` must be added to Amazon's approved sender list:
Amazon account settings -> Content Library / Devices -> Preferences -> Personal Document Settings -> Approved Personal Document E-mail List.

## Access Control

By default, anyone who finds the bot can use it. To restrict access, set `ALLOWED_USER_IDS` to a comma-separated list of Telegram user ids:

```env
ALLOWED_USER_IDS=123456789,987654321
```

You can find your id by sending `/whoami` to the bot while `ALLOWED_USER_IDS` is empty. After setting the allowlist, restart the bot.

## Mail Backend

### SMTP

Use SMTP when your server provider allows outbound SMTP ports:

```env
MAIL_BACKEND=smtp
SMTP_FROM=bot@example.com
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USERNAME=bot@example.com
SMTP_PASSWORD=replace-me
SMTP_USE_TLS=true
SMTP_USE_SSL=false
```

### Gmail API

Use Gmail API when SMTP is blocked by the hosting provider. It sends through HTTPS.

1. In Google Cloud Console, create an OAuth client for a Desktop app and download its JSON.
2. Save it as `./secrets/gmail_credentials.json`.
3. Generate the token on a machine where you can open a browser:

```bash
./venv/bin/python tools/create_gmail_token.py
```

4. Copy `./secrets/gmail_token.json` to the server.
5. Configure `.env`:

```env
MAIL_BACKEND=gmail_api
SMTP_FROM=your-gmail-address@gmail.com
GMAIL_CREDENTIALS_PATH=./secrets/gmail_credentials.json
GMAIL_TOKEN_PATH=./secrets/gmail_token.json
```

Add the `SMTP_FROM` Gmail address to Amazon's approved sender list.

## Bot Commands

- `/start` - show help
- `/setemail name@kindle.com` - save or replace Kindle email
- `/email` - show saved Kindle email
- `/deleteemail` - delete saved Kindle email
- `/whoami` - show your Telegram user id
- `/help` - show help

Send a book as a Telegram document. The bot converts it to `mobi` and returns the file. If you have a saved Kindle email, the bot also shows a button to email an `epub` copy to that address.
