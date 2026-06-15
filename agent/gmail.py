import base64
import json
import logging
from datetime import date, datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from googleapiclient.discovery import build
from agent.google_auth import get_credentials

logger = logging.getLogger(__name__)

_PROMO_LABELS = {"CATEGORY_PROMOTIONS", "CATEGORY_UPDATES", "CATEGORY_SOCIAL", "CATEGORY_FORUMS"}


def _service():
    creds = get_credentials()
    if not creds:
        return None
    return build("gmail", "v1", credentials=creds, cache_discovery=False)


def _not_auth():
    return "❌ Non autenticato con Google. Usa /auth_google nel bot."


# ── Internal: for scheduler ────────────────────────────────────────────────────

def get_today_emails_summary() -> str:
    svc = _service()
    if not svc:
        return _not_auth()
    today = date.today().strftime("%Y/%m/%d")
    try:
        res = svc.users().messages().list(
            userId="me", q=f"after:{today} in:inbox", maxResults=50
        ).execute()
        msgs = res.get("messages", [])
        if not msgs:
            return "Nessuna email ricevuta oggi nella inbox."

        emails = []
        for m in msgs[:40]:
            detail = svc.users().messages().get(
                userId="me", id=m["id"], format="metadata",
                metadataHeaders=["From", "Subject", "Date"]
            ).execute()
            headers = {h["name"]: h["value"] for h in detail["payload"]["headers"]}
            labels = set(detail.get("labelIds", []))
            emails.append({
                "da": headers.get("From", ""),
                "oggetto": headers.get("Subject", ""),
                "anteprima": detail.get("snippet", "")[:200],
                "promozionale": bool(labels & _PROMO_LABELS),
            })
        return json.dumps(emails, ensure_ascii=False, indent=2)
    except Exception as e:
        return f"Errore Gmail: {e}"


# ── Tools exposed to Claude ────────────────────────────────────────────────────

def gmail_get_today_emails() -> str:
    """Recupera tutte le email ricevute oggi nella inbox."""
    return get_today_emails_summary()


def gmail_search(query: str) -> str:
    """Cerca email o contatti in Gmail.

    Args:
        query: Query Gmail (es. 'from:mario@example.com', 'subject:fattura', 'mario rossi')
    """
    svc = _service()
    if not svc:
        return _not_auth()
    try:
        res = svc.users().messages().list(
            userId="me", q=query, maxResults=10
        ).execute()
        msgs = res.get("messages", [])
        if not msgs:
            return "Nessun risultato trovato."

        results = []
        for m in msgs:
            detail = svc.users().messages().get(
                userId="me", id=m["id"], format="metadata",
                metadataHeaders=["From", "To", "Subject", "Date"]
            ).execute()
            headers = {h["name"]: h["value"] for h in detail["payload"]["headers"]}
            results.append({
                "id": m["id"],
                "thread_id": m["threadId"],
                "da": headers.get("From", ""),
                "a": headers.get("To", ""),
                "oggetto": headers.get("Subject", ""),
                "data": headers.get("Date", ""),
                "anteprima": detail.get("snippet", "")[:200],
            })
        return json.dumps(results, ensure_ascii=False, indent=2)
    except Exception as e:
        return f"Errore ricerca Gmail: {e}"


def gmail_read_email(message_id: str) -> str:
    """Legge il testo completo di un'email dato il suo ID.

    Args:
        message_id: ID del messaggio Gmail
    """
    svc = _service()
    if not svc:
        return _not_auth()
    try:
        detail = svc.users().messages().get(
            userId="me", id=message_id, format="full"
        ).execute()
        headers = {h["name"]: h["value"] for h in detail["payload"]["headers"]}

        # Extract text body
        body = ""
        payload = detail["payload"]
        if "parts" in payload:
            for part in payload["parts"]:
                if part.get("mimeType") == "text/plain":
                    data = part["body"].get("data", "")
                    body = base64.urlsafe_b64decode(data + "==").decode("utf-8", errors="replace")
                    break
        elif payload["body"].get("data"):
            body = base64.urlsafe_b64decode(
                payload["body"]["data"] + "=="
            ).decode("utf-8", errors="replace")

        return (
            f"Da: {headers.get('From', '')}\n"
            f"A: {headers.get('To', '')}\n"
            f"Oggetto: {headers.get('Subject', '')}\n"
            f"Data: {headers.get('Date', '')}\n"
            f"\n{body[:5000]}"
        )
    except Exception as e:
        return f"Errore lettura email: {e}"


def gmail_create_draft(to: str, subject: str, body: str) -> str:
    """Crea una bozza email in Gmail e mostrala all'utente per revisione.

    Args:
        to: Indirizzo email del destinatario
        subject: Oggetto dell'email
        body: Testo del corpo dell'email
    """
    svc = _service()
    if not svc:
        return _not_auth()
    try:
        msg = MIMEText(body, "plain", "utf-8")
        msg["to"] = to
        msg["subject"] = subject

        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        draft = svc.users().drafts().create(
            userId="me", body={"message": {"raw": raw}}
        ).execute()

        return (
            f"✅ Bozza creata (ID: {draft['id']})\n\n"
            f"**A:** {to}\n"
            f"**Oggetto:** {subject}\n"
            f"**Testo:**\n{body}\n\n"
            f"Dimmi 'invia la bozza {draft['id']}' oppure 'modifica' per cambiarla."
        )
    except Exception as e:
        return f"Errore creazione bozza: {e}"


def gmail_send_draft(draft_id: str) -> str:
    """Invia una bozza Gmail esistente.

    Args:
        draft_id: ID della bozza da inviare (ottenuto da gmail_create_draft)
    """
    svc = _service()
    if not svc:
        return _not_auth()
    try:
        svc.users().drafts().send(userId="me", body={"id": draft_id}).execute()
        return f"✅ Email inviata con successo! (bozza {draft_id})"
    except Exception as e:
        return f"Errore invio bozza: {e}"


def gmail_send_email(to: str, subject: str, body: str) -> str:
    """Invia un'email direttamente senza passare per le bozze.

    Args:
        to: Indirizzo email del destinatario
        subject: Oggetto dell'email
        body: Testo del corpo dell'email
    """
    svc = _service()
    if not svc:
        return _not_auth()
    try:
        msg = MIMEText(body, "plain", "utf-8")
        msg["to"] = to
        msg["subject"] = subject
        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        svc.users().messages().send(
            userId="me", body={"raw": raw}
        ).execute()
        return f"✅ Email inviata a {to} con oggetto '{subject}'"
    except Exception as e:
        return f"Errore invio email: {e}"
