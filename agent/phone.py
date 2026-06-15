"""
Integrazione Vapi.ai per chiamate telefoniche AI in italiano.

Variabili d'ambiente necessarie:
  VAPI_API_KEY         — Private Key dal dashboard Vapi
  VAPI_PHONE_NUMBER_ID — ID del numero acquistato/importato in Vapi
"""
import os
import logging

logger = logging.getLogger(__name__)

VAPI_BASE = "https://api.vapi.ai"


def _available() -> bool:
    return bool(os.environ.get("VAPI_API_KEY"))


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {os.environ.get('VAPI_API_KEY', '')}",
        "Content-Type": "application/json",
    }


def _normalize_number(number: str) -> str:
    """Normalizza un numero italiano in E.164 (+39...)."""
    n = number.strip().replace(" ", "").replace("-", "").replace(".", "")
    if n.startswith("00"):
        n = "+" + n[2:]
    elif not n.startswith("+"):
        n = "+39" + n
    return n


def call_make(phone_number: str, task: str, max_duration: int = 5) -> str:
    """Avvia una chiamata AI tramite Vapi.ai."""
    import httpx

    if not _available():
        return "❌ VAPI_API_KEY non configurata"

    phone_number_id = os.environ.get("VAPI_PHONE_NUMBER_ID")
    if not phone_number_id:
        return (
            "❌ VAPI_PHONE_NUMBER_ID non configurato.\n"
            "Vai su dashboard Vapi → Phone Numbers → acquista un numero → copia l'ID."
        )

    number = _normalize_number(phone_number)

    # Costruisce il primo messaggio dall'istruzione
    first_message = f"Buongiorno, chiamo per conto di Francesco. {task.split('.')[0]}."

    payload = {
        "phoneNumberId": phone_number_id,
        "customer": {"number": number},
        "maxDurationSeconds": max_duration * 60,
        "assistant": {
            "transcriber": {
                "provider": "deepgram",
                "language": "it",
            },
            "model": {
                "provider": "anthropic",
                "model": "claude-haiku-4-5-20251001",
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            f"Sei un assistente personale che chiama per conto di Francesco.\n"
                            f"Il tuo compito è: {task}\n\n"
                            "Regole:\n"
                            "- Parla SOLO in italiano\n"
                            "- Sii professionale e conciso\n"
                            "- Se il tuo compito è completato, ringrazia e chiudi la chiamata\n"
                            "- Se ti viene chiesto qualcosa che non sai, di' che riferirai a Francesco\n"
                            "- Non inventare informazioni"
                        ),
                    }
                ],
            },
            "voice": {
                "provider": "azure",
                "voiceId": "it-IT-DiegoNeural",
            },
            "firstMessage": first_message,
            "endCallPhrases": ["grazie arrivederci", "arrivederci", "buona giornata"],
        },
    }

    try:
        resp = httpx.post(
            f"{VAPI_BASE}/call/phone",
            json=payload,
            headers=_headers(),
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        call_id = data.get("id", "")

        if not call_id:
            return f"❌ Risposta inattesa da Vapi: {data}"

        from agent.database import calls_save_pending
        calls_save_pending(call_id, number, task)

        return f"📞 Chiamata avviata verso {number}\nTi avviso quando è completata."

    except httpx.HTTPStatusError as e:
        logger.error(f"call_make HTTP error: {e.response.text}")
        return f"❌ Errore API Vapi ({e.response.status_code}): {e.response.text[:300]}"
    except Exception as e:
        logger.error(f"call_make error: {e}")
        return f"❌ Errore: {e}"


def call_check_status(call_id: str) -> str:
    """Controlla stato e trascrizione di una chiamata."""
    import httpx

    if not _available():
        return "❌ VAPI_API_KEY non configurata"

    try:
        resp = httpx.get(
            f"{VAPI_BASE}/call/{call_id}",
            headers=_headers(),
            timeout=15,
        )
        resp.raise_for_status()
        return _format_call_result(resp.json())
    except Exception as e:
        logger.error(f"call_check_status error: {e}")
        return f"❌ Errore: {e}"


def call_list_recent() -> str:
    """Lista le ultime 10 chiamate effettuate."""
    import httpx

    if not _available():
        return "❌ VAPI_API_KEY non configurata"

    try:
        resp = httpx.get(
            f"{VAPI_BASE}/call?limit=10",
            headers=_headers(),
            timeout=15,
        )
        resp.raise_for_status()
        calls = resp.json()

        if not calls:
            return "Nessuna chiamata recente."

        status_emoji = {
            "ended": "✅", "failed": "❌", "in-progress": "📞", "queued": "⏳", "ringing": "🔔",
        }
        lines = ["📋 *Ultime chiamate:*\n"]
        for c in calls:
            status = c.get("status", "?")
            number = c.get("customer", {}).get("number", "?")
            duration = int(c.get("endedAt", 0) and c.get("startedAt", 0) and 0)
            ended_reason = c.get("endedReason", "")
            e = status_emoji.get(status, "•")
            lines.append(f"{e} {number} — {status} {f'({ended_reason})' if ended_reason else ''}")
        return "\n".join(lines)

    except Exception as e:
        return f"❌ Errore: {e}"


def calls_check_pending() -> list:
    """Controlla le chiamate pending e restituisce quelle completate."""
    import httpx
    from agent.database import calls_get_pending, calls_remove_pending

    if not _available():
        return []

    pending = calls_get_pending()
    completed = []

    for call in pending:
        call_id = call.get("call_id")
        if not call_id:
            continue
        try:
            resp = httpx.get(
                f"{VAPI_BASE}/call/{call_id}",
                headers=_headers(),
                timeout=15,
            )
            data = resp.json()
            status = data.get("status", "")
            if status == "ended" or data.get("endedAt"):
                calls_remove_pending(call_id)
                completed.append({"call": call, "data": data, "status": status})
        except Exception as e:
            logger.error(f"calls_check_pending error for {call_id}: {e}")

    return completed


def _format_call_result(data: dict) -> str:
    """Formatta il risultato di una chiamata per Telegram."""
    status = data.get("status", "unknown")
    ended_reason = data.get("endedReason", "")
    summary = data.get("summary", "")
    transcript = data.get("transcript", "")
    number = data.get("customer", {}).get("number", "")

    status_emoji = {
        "ended": "✅", "failed": "❌", "in-progress": "📞", "queued": "⏳",
    }.get(status, "⏳")

    lines = [f"{status_emoji} *Chiamata — {number}*"]
    if ended_reason:
        lines.append(f"Esito: {ended_reason}")

    if summary:
        lines.append(f"\n📋 *Riepilogo:*\n{summary}")

    if transcript:
        lines.append(f"\n💬 *Trascrizione:*\n{transcript[:1500]}")

    return "\n".join(lines)
