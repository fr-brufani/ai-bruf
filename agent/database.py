"""
Layer Supabase per persistenza dati.
Se SUPABASE_URL/SUPABASE_KEY non sono impostati, tutte le funzioni degradano gracefully.
"""
import os
import logging

logger = logging.getLogger(__name__)

_client = None


def _available() -> bool:
    return bool(os.environ.get("SUPABASE_URL") and
                (os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get("SUPABASE_KEY")))


def _get_client():
    """Usa la service_role key se disponibile (bypassa RLS), altrimenti la anon key."""
    global _client
    if _client is None:
        from supabase import create_client
        key = os.environ.get("SUPABASE_SERVICE_KEY") or os.environ["SUPABASE_KEY"]
        _client = create_client(os.environ["SUPABASE_URL"], key)
    return _client


# ── Memoria agente ─────────────────────────────────────────────────────────────

def memory_read() -> str:
    if not _available():
        return ""
    try:
        res = _get_client().table("agent_memory").select("content").eq("id", 1).execute()
        return res.data[0]["content"] if res.data else ""
    except Exception as e:
        logger.error(f"DB memory_read: {e}")
        return ""


def memory_write(content: str) -> str:
    if not _available():
        return "DB non configurato — memoria non salvata"
    try:
        _get_client().table("agent_memory").upsert({
            "id": 1,
            "content": content,
        }).execute()
        return f"Memoria aggiornata ({len(content)} caratteri)"
    except Exception as e:
        logger.error(f"DB memory_write: {e}")
        return f"Errore DB: {e}"


# ── Cronologia conversazione ───────────────────────────────────────────────────

def messages_load(limit: int = 20) -> list:
    """Carica gli ultimi N scambi puliti (solo user-text e assistant-text)."""
    if not _available():
        return []
    try:
        res = (
            _get_client()
            .table("conversation_messages")
            .select("role, content")
            .order("id", desc=True)
            .limit(limit)
            .execute()
        )
        return [{"role": r["role"], "content": r["content"]} for r in reversed(res.data)]
    except Exception as e:
        logger.error(f"DB messages_load: {e}")
        return []


def messages_load_today() -> list:
    """Carica i messaggi di OGGI per l'audit notturno."""
    if not _available():
        return []
    try:
        from datetime import datetime
        from zoneinfo import ZoneInfo
        tz = ZoneInfo("Europe/Rome")
        today_start = datetime.now(tz).replace(hour=0, minute=0, second=0, microsecond=0)
        today_start_utc = today_start.astimezone(ZoneInfo("UTC")).isoformat()
        res = (
            _get_client()
            .table("conversation_messages")
            .select("role, content")
            .gte("created_at", today_start_utc)
            .order("id", desc=False)
            .execute()
        )
        return [{"role": r["role"], "content": r["content"]} for r in res.data]
    except Exception as e:
        logger.error(f"DB messages_load_today: {e}")
        return []


def messages_append(role: str, content: str) -> None:
    if not _available():
        return
    try:
        _get_client().table("conversation_messages").insert({
            "role": role,
            "content": content,
        }).execute()
    except Exception as e:
        logger.error(f"DB messages_append: {e}")


def messages_clear() -> None:
    if not _available():
        return
    try:
        _get_client().table("conversation_messages").delete().gte("id", 0).execute()
    except Exception as e:
        logger.error(f"DB messages_clear: {e}")


# ── Job applications ───────────────────────────────────────────────────────────

def job_application_save(
    company: str, role_title: str, url: str, cv_type: str, notes: str = ""
) -> None:
    if not _available():
        return
    try:
        _get_client().table("job_applications").insert({
            "company": company,
            "role_title": role_title,
            "url": url,
            "cv_type": cv_type,
            "notes": notes,
        }).execute()
        logger.info(f"Application salvata: {company} — {role_title}")
    except Exception as e:
        logger.error(f"DB job_application_save: {e}")


def job_application_update_status(app_id: int, status: str, notes: str = "") -> str:
    if not _available():
        return "DB non configurato"
    try:
        data = {"status": status}
        if notes:
            data["notes"] = notes
        _get_client().table("job_applications").update(data).eq("id", app_id).execute()
        return f"✅ Application #{app_id} → {status}"
    except Exception as e:
        logger.error(f"DB job_application_update: {e}")
        return f"Errore: {e}"


def job_applications_list() -> str:
    if not _available():
        return "DB non configurato"
    try:
        res = (
            _get_client()
            .table("job_applications")
            .select("id, company, role_title, status, cv_type, applied_at, url")
            .order("applied_at", desc=True)
            .execute()
        )
        if not res.data:
            return "Nessuna application registrata."
        lines = ["📋 *Job Applications*\n"]
        for a in res.data:
            date = a["applied_at"][:10] if a.get("applied_at") else "?"
            status_emoji = {
                "applied": "📤", "interviewing": "🗣️",
                "offer": "🎉", "rejected": "❌", "withdrawn": "↩️",
            }.get(a.get("status", ""), "•")
            lines.append(
                f"{status_emoji} *#{a['id']}* {a['company']} — {a.get('role_title','?')}\n"
                f"   {date} | {a.get('cv_type','?')} CV | {a.get('url','')}"
            )
        return "\n\n".join(lines)
    except Exception as e:
        logger.error(f"DB job_applications_list: {e}")
        return f"Errore: {e}"


# ── Expense reports ────────────────────────────────────────────────────────────

def expense_report_save(
    period: str, csv_raw: str, analysis_text: str, total_spent: float = None
) -> None:
    if not _available():
        return
    try:
        _get_client().table("expense_reports").upsert({
            "period": period,
            "csv_raw": csv_raw,
            "analysis_text": analysis_text,
            "total_spent": total_spent,
        }).execute()
        logger.info(f"Expense report salvato: {period}")
    except Exception as e:
        logger.error(f"DB expense_report_save: {e}")


def expense_report_get(period: str) -> object:
    if not _available():
        return None
    try:
        res = (
            _get_client()
            .table("expense_reports")
            .select("period, analysis_text, total_spent, created_at")
            .eq("period", period)
            .execute()
        )
        return res.data[0] if res.data else None
    except Exception as e:
        logger.error(f"DB expense_report_get: {e}")
        return None


# ── Wedding contacts ───────────────────────────────────────────────────────────

def wedding_contact_add(
    name: str, category: str, email: str = "", website: str = "",
    location: str = "Umbria", notes: str = ""
) -> str:
    if not _available():
        return "DB non configurato"
    try:
        _get_client().table("wedding_contacts").insert({
            "name": name, "category": category, "email": email or None,
            "website": website or None, "location": location, "notes": notes or None,
        }).execute()
        return f"✅ Contatto aggiunto: {name} ({category})"
    except Exception as e:
        logger.error(f"DB wedding_contact_add: {e}")
        return f"Errore: {e}"


def wedding_contact_list(status: str = "", category: str = "") -> str:
    if not _available():
        return "DB non configurato"
    try:
        q = _get_client().table("wedding_contacts").select("*").order("created_at", desc=True)
        if status:
            q = q.eq("status", status)
        if category:
            q = q.eq("category", category)
        res = q.execute()
        if not res.data:
            return "Nessun contatto trovato."
        status_emoji = {"new": "🆕", "contacted": "📤", "replied": "💬",
                        "negotiating": "🤝", "archived": "📁"}
        lines = [f"📋 *Contatti Wedding* ({len(res.data)} totali)\n"]
        for c in res.data:
            e = status_emoji.get(c.get("status", ""), "•")
            email_str = f" | {c['email']}" if c.get("email") else ""
            lines.append(
                f"{e} *#{c['id']} {c['name']}* — {c['category']}{email_str}\n"
                f"   {c.get('website','') or 'no sito'}"
            )
        return "\n\n".join(lines)
    except Exception as e:
        logger.error(f"DB wedding_contact_list: {e}")
        return f"Errore: {e}"


def wedding_contact_update(
    contact_id: int, status: str = "", notes: str = "", email: str = ""
) -> str:
    if not _available():
        return "DB non configurato"
    try:
        from datetime import datetime, timezone
        data: dict = {"updated_at": datetime.now(timezone.utc).isoformat()}
        if status:
            data["status"] = status
        if notes:
            data["notes"] = notes
        if email:
            data["email"] = email
        if status in ("contacted", "replied", "negotiating"):
            data["last_contact"] = datetime.now(timezone.utc).isoformat()
        _get_client().table("wedding_contacts").update(data).eq("id", contact_id).execute()
        return f"✅ Contatto #{contact_id} aggiornato"
    except Exception as e:
        logger.error(f"DB wedding_contact_update: {e}")
        return f"Errore: {e}"


def wedding_contact_get(contact_id: int) -> object:
    if not _available():
        return None
    try:
        res = _get_client().table("wedding_contacts").select("*").eq("id", contact_id).execute()
        return res.data[0] if res.data else None
    except Exception as e:
        logger.error(f"DB wedding_contact_get: {e}")
        return None


# ── User tasks (Calendar = source of truth, DB = status log) ──────────────────

def task_upsert_status(
    calendar_event_id: str,
    title: str,
    status: str,
    new_date: str = "",
    new_time: str = "",
) -> None:
    """Salva/aggiorna lo stato di un evento nel DB. Chiamata dai tool calendar_mark_*."""
    if not _available():
        return
    try:
        from datetime import datetime, timezone
        data: dict = {
            "calendar_event_id": calendar_event_id,
            "title": title,
            "status": status,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        if new_date:
            data["event_date"] = new_date
        if new_time:
            data["event_time"] = new_time
        _get_client().table("user_tasks").upsert(data, on_conflict="calendar_event_id").execute()
        logger.info(f"task_upsert_status: {title} → {status}")
    except Exception as e:
        logger.error(f"DB task_upsert_status: {e}")


def task_get_today_db_summary() -> dict:
    """Recupera il riepilogo di oggi dal DB (backup al Calendar colorId)."""
    if not _available():
        return {}
    try:
        from datetime import datetime
        from zoneinfo import ZoneInfo
        today = str(datetime.now(ZoneInfo("Europe/Rome")).date())
        res = (
            _get_client()
            .table("user_tasks")
            .select("calendar_event_id, title, status, event_time")
            .eq("event_date", today)
            .execute()
        )
        result: dict = {"done": [], "not_done": [], "rescheduled": [], "pending": []}
        for t in (res.data or []):
            bucket = result.get(t.get("status", "pending"), result["pending"])
            bucket.append({"title": t["title"], "orario": (t.get("event_time") or "")[:5]})
        return result
    except Exception as e:
        logger.error(f"DB task_get_today_db_summary: {e}")
        return {}


def task_get(task_id: int) -> object:
    if not _available():
        return None
    try:
        res = _get_client().table("user_tasks").select("*").eq("id", task_id).execute()
        return res.data[0] if res.data else None
    except Exception as e:
        logger.error(f"DB task_get: {e}")
        return None


def task_add(
    title: str, due_date: str = "", due_time: str = "",
    domain: str = "generale", notes: str = "", recurring: str = "",
    calendar_event_id: str = ""
) -> str:
    if not _available():
        return "DB non configurato"
    try:
        _get_client().table("user_tasks").insert({
            "title": title,
            "due_date": due_date or None,
            "due_time": due_time or None,
            "domain": domain,
            "notes": notes or None,
            "recurring": recurring or None,
            "calendar_event_id": calendar_event_id or None,
        }).execute()
        time_str = f" alle {due_time}" if due_time else ""
        date_str = f" il {due_date}" if due_date else ""
        return f"✅ Task aggiunta: *{title}*{date_str}{time_str} [{domain}]"
    except Exception as e:
        logger.error(f"DB task_add: {e}")
        return f"Errore: {e}"


def task_list(date: str = "", status: str = "pending", domain: str = "") -> str:
    if not _available():
        return "DB non configurato"
    try:
        from datetime import datetime, timedelta
        from zoneinfo import ZoneInfo
        TZ = ZoneInfo("Europe/Rome")
        today = datetime.now(TZ).date()

        q = _get_client().table("user_tasks").select("*").order("due_time", desc=False, nullsfirst=False)

        if date in ("oggi", "today", ""):
            q = q.eq("due_date", str(today))
        elif date in ("domani", "tomorrow"):
            q = q.eq("due_date", str(today + timedelta(days=1)))
        elif date:
            q = q.eq("due_date", date)

        if status:
            q = q.eq("status", status)
        if domain:
            q = q.eq("domain", domain)

        res = q.execute()
        if not res.data:
            return "Nessuna task trovata."

        label = date or "oggi"
        lines = [f"📋 *Task — {label}* ({len(res.data)})\n"]
        for t in res.data:
            icon = "✅" if t["status"] == "done" else ("❌" if t["status"] == "not_done" else "⏰" if t.get("due_time") else "•")
            time_str = f" {t['due_time'][:5]}" if t.get("due_time") else ""
            lines.append(f"{icon} *#{t['id']}*{time_str} {t['title']} `[{t['domain']}]`")
        return "\n".join(lines)
    except Exception as e:
        logger.error(f"DB task_list: {e}")
        return f"Errore: {e}"


def task_update_status(task_id: int, status: str, notes: str = "") -> str:
    if not _available():
        return "DB non configurato"
    try:
        from datetime import datetime, timezone
        data = {"status": status, "updated_at": datetime.now(timezone.utc).isoformat()}
        if notes:
            data["notes"] = notes
        _get_client().table("user_tasks").update(data).eq("id", task_id).execute()
        emoji = "✅" if status == "done" else "❌"
        return f"{emoji} Task #{task_id} → {status}"
    except Exception as e:
        logger.error(f"DB task_update_status: {e}")
        return f"Errore: {e}"


def task_reschedule(task_id: int, new_date: str, new_time: str = "") -> str:
    if not _available():
        return "DB non configurato"
    try:
        from datetime import datetime, timezone
        data = {
            "due_date": new_date,
            "status": "pending",
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        if new_time:
            data["due_time"] = new_time
        _get_client().table("user_tasks").update(data).eq("id", task_id).execute()
        time_str = f" alle {new_time}" if new_time else ""
        return f"🔄 Task #{task_id} rischedulata al {new_date}{time_str}"
    except Exception as e:
        logger.error(f"DB task_reschedule: {e}")
        return f"Errore: {e}"


def task_get_today_summary() -> dict:
    """Usata dallo scheduler per briefing e tracker serale."""
    if not _available():
        return {"done": [], "not_done": [], "pending": [], "date": ""}
    try:
        from datetime import datetime
        from zoneinfo import ZoneInfo
        today = str(datetime.now(ZoneInfo("Europe/Rome")).date())
        res = _get_client().table("user_tasks").select("*").eq("due_date", today).execute()
        done = [t for t in res.data if t["status"] == "done"]
        not_done = [t for t in res.data if t["status"] == "not_done"]
        pending = [t for t in res.data if t["status"] == "pending"]
        return {"done": done, "not_done": not_done, "pending": pending, "date": today}
    except Exception as e:
        logger.error(f"DB task_get_today_summary: {e}")
        return {"done": [], "not_done": [], "pending": [], "date": ""}


# ── Dieta ──────────────────────────────────────────────────────────────────────
# Usa agent_memory con id speciali per non creare nuove tabelle:
#   id=2  → schema dieta base
#   id=3  → spesa settimanale (JSON: {week_start, items, notes, saved_at})

_DIET_BASE_ID        = 2
_DIET_SHOPPING_ID    = 3
_DIET_DAILY_MEALS_ID = 4
_CALLS_PENDING_ID    = 5

DIET_BASE_DEFAULT = """COLAZIONE (scegli una opzione):
• 150g fiocchi di latte + 3 uova
• 50g avena + 30g proteine whey + 200ml latte
• 40g avena + 50ml albume + 150ml latte + 30g proteine whey
• Pancake: 50g avena + 200ml albume + marmellata
• 250g yogurt greco + 30g proteine whey + 1 mela o pera
• 4 uova + 150ml albume

PRANZO:
- Verdure: 1 busta surgelata (broccoli / verdure miste / spinaci)
- Proteina: 200g pollo o tacchino  OPPURE  150g pesce grasso/250g pesce magro  OPPURE  200g vitello
- Condimento: 10g olio
- VENERDÌ→LUNEDÌ: aggiungi 60g riso

MERENDA (scegli una opzione):
• 200g fiocchi di latte
• 200g budino proteico
• 250g yogurt greco + stevia

CENA:
- Verdura: insalata normale / radicchio / minestrone 300g / zuppa di verdure + 10g olio
- Carboidrati (scegli uno):
  • 80-100g pasta al pomodoro/verdure
  • 300g patate + 2 uova/carne/pesce
  • 80-100g risotto (verdure o altro)
  • 80-100g legumi
- Condimento: 10g olio + 2 cucchiai parmigiano"""


def diet_get_base() -> str:
    """Legge lo schema dieta base dal DB. Fallback al default se non trovato."""
    if not _available():
        return DIET_BASE_DEFAULT
    try:
        res = _get_client().table("agent_memory").select("content").eq("id", _DIET_BASE_ID).execute()
        return res.data[0]["content"] if res.data else DIET_BASE_DEFAULT
    except Exception as e:
        logger.error(f"DB diet_get_base: {e}")
        return DIET_BASE_DEFAULT


def diet_save_base(content: str) -> str:
    """Salva/aggiorna lo schema dieta base."""
    if not _available():
        return "DB non configurato"
    try:
        _get_client().table("agent_memory").upsert({"id": _DIET_BASE_ID, "content": content}).execute()
        return "✅ Schema dieta aggiornato"
    except Exception as e:
        logger.error(f"DB diet_save_base: {e}")
        return f"Errore: {e}"


def diet_save_shopping(items_text: str, notes: str = "") -> str:
    """Salva la lista spesa della settimana corrente."""
    if not _available():
        return "DB non configurato"
    try:
        import json
        from datetime import datetime, timedelta
        from zoneinfo import ZoneInfo
        today = datetime.now(ZoneInfo("Europe/Rome")).date()
        monday = today - timedelta(days=today.weekday())
        payload = json.dumps({
            "week_start": str(monday),
            "items": items_text.strip(),
            "notes": notes.strip(),
            "saved_at": str(today),
        }, ensure_ascii=False)
        _get_client().table("agent_memory").upsert({"id": _DIET_SHOPPING_ID, "content": payload}).execute()
        return f"✅ Spesa salvata per la settimana del {monday}"
    except Exception as e:
        logger.error(f"DB diet_save_shopping: {e}")
        return f"Errore: {e}"


def diet_get_shopping() -> str:
    """Legge la lista spesa della settimana corrente (testo formattato)."""
    if not _available():
        return ""
    try:
        import json
        res = _get_client().table("agent_memory").select("content").eq("id", _DIET_SHOPPING_ID).execute()
        if not res.data:
            return ""
        data = json.loads(res.data[0]["content"])
        return f"Settimana dal {data.get('week_start','?')}:\n{data.get('items','')}"
    except Exception as e:
        logger.error(f"DB diet_get_shopping: {e}")
        return ""


def diet_save_daily_meals(proposals: dict) -> str:
    """Salva le proposte pasto pre-generate per oggi (batch mattutino)."""
    if not _available():
        return "DB non configurato"
    try:
        import json
        from datetime import datetime
        from zoneinfo import ZoneInfo
        today = str(datetime.now(ZoneInfo("Europe/Rome")).date())
        payload = json.dumps({"date": today, **proposals}, ensure_ascii=False)
        _get_client().table("agent_memory").upsert(
            {"id": _DIET_DAILY_MEALS_ID, "content": payload}
        ).execute()
        logger.info(f"Proposte pasto giornaliere salvate per {today}")
        return f"✅ Proposte salvate per {today}"
    except Exception as e:
        logger.error(f"DB diet_save_daily_meals: {e}")
        return f"Errore: {e}"


def diet_get_daily_meals():
    """Legge le proposte pasto pre-generate per OGGI. Ritorna None se assenti o stantie."""
    if not _available():
        return None
    try:
        import json
        from datetime import datetime
        from zoneinfo import ZoneInfo
        today = str(datetime.now(ZoneInfo("Europe/Rome")).date())
        res = (
            _get_client()
            .table("agent_memory")
            .select("content")
            .eq("id", _DIET_DAILY_MEALS_ID)
            .execute()
        )
        if not res.data:
            return None
        data = json.loads(res.data[0]["content"])
        if data.get("date") != today:
            return None  # proposte di ieri, rigenera
        return data
    except Exception as e:
        logger.error(f"DB diet_get_daily_meals: {e}")
        return None


def diet_initialize_if_empty() -> None:
    """Chiamata allo startup: pre-popola lo schema dieta se vuoto."""
    if not _available():
        return
    try:
        res = _get_client().table("agent_memory").select("id").eq("id", _DIET_BASE_ID).execute()
        if not res.data:
            _get_client().table("agent_memory").upsert({"id": _DIET_BASE_ID, "content": DIET_BASE_DEFAULT}).execute()
            logger.info("Schema dieta inizializzato nel DB")
    except Exception as e:
        logger.error(f"DB diet_initialize_if_empty: {e}")


# ── Chiamate telefoniche (Bland.ai) ───────────────────────────────────────────

def calls_save_pending(call_id: str, phone_number: str, task: str) -> None:
    """Aggiunge una chiamata alla lista pending in agent_memory id=5."""
    if not _available():
        return
    try:
        import json
        from datetime import datetime, timezone
        pending = calls_get_pending()
        pending.append({
            "call_id": call_id,
            "phone_number": phone_number,
            "task": task[:300],
            "started_at": datetime.now(timezone.utc).isoformat(),
        })
        _get_client().table("agent_memory").upsert(
            {"id": _CALLS_PENDING_ID, "content": json.dumps(pending, ensure_ascii=False)}
        ).execute()
    except Exception as e:
        logger.error(f"DB calls_save_pending: {e}")


def calls_get_pending() -> list:
    """Legge la lista delle chiamate in attesa."""
    if not _available():
        return []
    try:
        import json
        res = (
            _get_client()
            .table("agent_memory")
            .select("content")
            .eq("id", _CALLS_PENDING_ID)
            .execute()
        )
        if not res.data:
            return []
        return json.loads(res.data[0]["content"])
    except Exception as e:
        logger.error(f"DB calls_get_pending: {e}")
        return []


def calls_remove_pending(call_id: str) -> None:
    """Rimuove una chiamata completata dalla lista pending."""
    if not _available():
        return
    try:
        import json
        pending = [c for c in calls_get_pending() if c.get("call_id") != call_id]
        _get_client().table("agent_memory").upsert(
            {"id": _CALLS_PENDING_ID, "content": json.dumps(pending, ensure_ascii=False)}
        ).execute()
    except Exception as e:
        logger.error(f"DB calls_remove_pending: {e}")


# ── CRUD generici ──────────────────────────────────────────────────────────────

def db_select(table: str, filters: object = None) -> str:
    """SELECT generico su qualsiasi tabella con filtri opzionali."""
    if not _available():
        return "DB non configurato"
    try:
        import json
        q = _get_client().table(table).select("*")
        for col, val in (filters or {}).items():
            q = q.eq(col, val)
        res = q.execute()
        if not res.data:
            return f"Nessun record trovato in '{table}'."
        return json.dumps(res.data, ensure_ascii=False, default=str, indent=2)
    except Exception as e:
        logger.error(f"DB db_select: {e}")
        return f"Errore: {e}"


def db_insert(table: str, data: object) -> str:
    """INSERT generico su qualsiasi tabella."""
    if not _available():
        return "DB non configurato"
    try:
        import json
        res = _get_client().table(table).insert(data).execute()
        inserted = res.data[0] if res.data else {}
        return f"✅ Inserito in '{table}': {json.dumps(inserted, ensure_ascii=False, default=str)}"
    except Exception as e:
        logger.error(f"DB db_insert: {e}")
        return f"Errore: {e}"


def db_update(table: str, filters: object, updates: object) -> str:
    """UPDATE generico su qualsiasi tabella."""
    if not _available():
        return "DB non configurato"
    if not filters:
        return "❌ Sicurezza: specifica almeno un filtro per non aggiornare tutta la tabella"
    try:
        q = _get_client().table(table).update(updates)
        for col, val in (filters or {}).items():
            q = q.eq(col, val)
        res = q.execute()
        return f"✅ Aggiornati {len(res.data or [])} record in '{table}'"
    except Exception as e:
        logger.error(f"DB db_update: {e}")
        return f"Errore: {e}"


def db_delete(table: str, filters: object) -> str:
    """DELETE generico su qualsiasi tabella. Richiede almeno un filtro per sicurezza."""
    if not _available():
        return "DB non configurato"
    if not filters:
        return "❌ Sicurezza: specifica almeno un filtro per la DELETE (altrimenti si svuota l'intera tabella)"
    try:
        q = _get_client().table(table).delete()
        for col, val in (filters or {}).items():
            q = q.eq(col, val)
        res = q.execute()
        return f"✅ Eliminati {len(res.data or [])} record da '{table}'"
    except Exception as e:
        logger.error(f"DB db_delete: {e}")
        return f"Errore: {e}"
