"""One-time helper: authorise brio4edits@gmail.com to send mail and save the refresh token locally.

Usage:  python scripts/get_gmail_refresh_token.py path/to/client_secret.json
Writes .env.gmail (git-ignored) with GMAIL_CLIENT_ID, GMAIL_CLIENT_SECRET and GMAIL_REFRESH_TOKEN.
Nothing secret is printed.
"""

import http.server
import json
import secrets
import sys
import urllib.parse
import webbrowser
from pathlib import Path

import requests

SCOPE = "https://www.googleapis.com/auth/gmail.send"
PORT = 8765
REDIRECT = f"http://127.0.0.1:{PORT}/"


def main(client_file):
    client = json.loads(Path(client_file).read_text(encoding="utf-8"))
    client = client.get("installed") or client.get("web")
    state = secrets.token_urlsafe(24)
    result = {}

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            query = dict(urllib.parse.parse_qsl(urllib.parse.urlparse(self.path).query))
            if query.get("state") == state:
                result.update(query)
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"Done. You can close this tab and return to the terminal.")

        def log_message(self, *args):
            pass

    url = "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode({
        "client_id": client["client_id"], "redirect_uri": REDIRECT, "response_type": "code",
        "scope": SCOPE, "access_type": "offline", "prompt": "consent", "state": state,
        "login_hint": "brio4edits@gmail.com",
    })
    print("Opening Google sign-in. Sign in as brio4edits@gmail.com and allow 'Send email on your behalf'.")
    webbrowser.open(url)
    server = http.server.HTTPServer(("127.0.0.1", PORT), Handler)
    while not result:
        server.handle_request()
    if "code" not in result:
        sys.exit(f"Google did not grant access: {result.get('error', 'unknown error')}")
    token = requests.post("https://oauth2.googleapis.com/token", data={
        "code": result["code"], "client_id": client["client_id"], "client_secret": client["client_secret"],
        "redirect_uri": REDIRECT, "grant_type": "authorization_code",
    }, timeout=20)
    token.raise_for_status()
    refresh = token.json().get("refresh_token")
    if not refresh:
        sys.exit("No refresh token returned. Remove the app's access in your Google Account and run again.")
    out = Path(__file__).resolve().parent.parent / ".env.gmail"
    out.write_text(
        f"GMAIL_CLIENT_ID={client['client_id']}\nGMAIL_CLIENT_SECRET={client['client_secret']}\n"
        f"GMAIL_REFRESH_TOKEN={refresh}\n", encoding="utf-8",
    )
    print(f"Saved to {out} (not committed). Add these three values to Vercel Production as Sensitive.")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
