"""
Esegui questo script UNA VOLTA per autenticarti con Google.
Genera il file token.json usato dal bot.

Uso: python3 auth_setup.py
"""

from pathlib import Path
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.compose",
    "https://www.googleapis.com/auth/contacts.readonly",
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/tasks",
]

CREDENTIALS_FILE = Path(__file__).parent / "google_credentials.json"
TOKEN_FILE = Path(__file__).parent / "token.json"

if not CREDENTIALS_FILE.exists():
    print("❌ google_credentials.json non trovato!")
    exit(1)

print("Apertura browser per autenticazione Google...")
print("(Si aprirà automaticamente. Se non si apre, copia il link dal terminale)\n")

flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_FILE), SCOPES)
creds = flow.run_local_server(port=0, open_browser=True)

TOKEN_FILE.write_text(creds.to_json())
print(f"\n✅ Autenticazione completata! Token salvato in: {TOKEN_FILE}")
print("Ora puoi riavviare il bot con: python3 main.py")
