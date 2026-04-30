from __future__ import annotations

import argparse
from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow


SCOPES = ["https://www.googleapis.com/auth/gmail.send"]


def main() -> None:
    parser = argparse.ArgumentParser(description="Create Gmail API OAuth token for the bot.")
    parser.add_argument(
        "--credentials",
        default="./secrets/gmail_credentials.json",
        help="Path to OAuth client credentials JSON from Google Cloud Console.",
    )
    parser.add_argument(
        "--token",
        default="./secrets/gmail_token.json",
        help="Path where the authorized token JSON will be written.",
    )
    parser.add_argument(
        "--host",
        default="localhost",
        help="Host for the temporary local OAuth callback server.",
    )
    parser.add_argument(
        "--port",
        default=8080,
        type=int,
        help="Port for the temporary local OAuth callback server.",
    )
    args = parser.parse_args()

    credentials_path = Path(args.credentials)
    token_path = Path(args.token)
    token_path.parent.mkdir(parents=True, exist_ok=True)

    flow = InstalledAppFlow.from_client_secrets_file(str(credentials_path), SCOPES)
    creds = flow.run_local_server(host=args.host, port=args.port)
    token_path.write_text(creds.to_json(), encoding="utf-8")
    print(f"Wrote Gmail token to {token_path}")


if __name__ == "__main__":
    main()
