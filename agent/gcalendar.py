import json
import logging
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from googleapiclient.discovery import build
from agent.google_auth import get_credentials

logger = logging.getLogger(__name__)
TZ = ZoneInfo("Europe/Rome")


def _cal_service():
    creds = get_credentials()
    return build("calendar", "v3", credentials=creds, cache_discovery=False) if creds else None


def _tasks_service():
    creds = get_credentials()
    return build("tasks", "v1", credentials=creds, cache_discovery=False) if creds else None


def _not_auth():
    return "❌ Non autenticato con Google. Usa /auth_google nel bot."


def _fmt_dt(dt_str: str) -> str:
    """Parse and format a Google Calendar dateTime string."""
    try:
        dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00")).astimezone(TZ)
        return dt.strftime("%H:%M")
    except Exception:
        return dt_str[:10]


# ── Internal: for scheduler ────────────────────────────────────────────────────

def get_today_events_and_tasks() -> str:
    """Return a formatted string of today's calendar events and tasks."""
    result = {}

    cal = _cal_service()
    tasks_svc = _tasks_service()

    if not cal:
        return _not_auth()

    today = date.today()
    day_start = datetime(today.year, today.month, today.day, 0, 0, tzinfo=TZ).isoformat()
    day_end = datetime(today.year, today.month, today.day, 23, 59, 59, tzinfo=TZ).isoformat()

    # Calendar events
    try:
        events_res = cal.events().list(
            calendarId="primary",
            timeMin=day_start,
            timeMax=day_end,
            singleEvents=True,
            orderBy="startTime",
        ).execute()
        events = []
        for e in events_res.get("items", []):
            start = e["start"].get("dateTime", e["start"].get("date", ""))
            end = e["end"].get("dateTime", e["end"].get("date", ""))
            events.append({
                "titolo": e.get("summary", "Senza titolo"),
                "inizio": _fmt_dt(start) if "T" in start else "tutto il giorno",
                "fine": _fmt_dt(end) if "T" in end else "",
                "luogo": e.get("location", ""),
                "descrizione": e.get("description", "")[:200],
            })
        result["eventi_calendario"] = events
    except Exception as e:
        result["eventi_calendario"] = f"Errore: {e}"

    # Tasks
    if tasks_svc:
        try:
            lists_res = tasks_svc.tasklists().list().execute()
            all_tasks = []
            for tl in lists_res.get("items", []):
                tasks_res = tasks_svc.tasks().list(
                    tasklist=tl["id"], showCompleted=False
                ).execute()
                for t in tasks_res.get("items", []):
                    due = t.get("due", "")
                    # Include tasks due today or with no due date
                    if not due or due[:10] == str(today):
                        all_tasks.append({
                            "titolo": t.get("title", ""),
                            "lista": tl.get("title", ""),
                            "scadenza": due[:10] if due else "nessuna",
                            "note": t.get("notes", "")[:200],
                        })
            result["tasks"] = all_tasks
        except Exception as e:
            result["tasks"] = f"Errore: {e}"

    return json.dumps(result, ensure_ascii=False, indent=2)


# ── Tools exposed to Claude ────────────────────────────────────────────────────

def calendar_get_events(date_str: str = "oggi") -> str:
    """Recupera gli eventi del calendario per una data specifica.

    Args:
        date_str: Data in formato YYYY-MM-DD oppure 'oggi', 'domani', 'questa settimana'
    """
    cal = _cal_service()
    if not cal:
        return _not_auth()

    today = date.today()
    if date_str in ("oggi", "today", ""):
        target = today
    elif date_str in ("domani", "tomorrow"):
        target = today + timedelta(days=1)
    elif date_str == "questa settimana":
        # Return full week
        day_start = datetime(today.year, today.month, today.day, 0, 0, tzinfo=TZ).isoformat()
        day_end = datetime(today.year, today.month, today.day + 6, 23, 59, 59, tzinfo=TZ).isoformat()
    else:
        try:
            target = date.fromisoformat(date_str)
        except ValueError:
            return f"Formato data non valido: {date_str}. Usa YYYY-MM-DD."

    if date_str not in ("questa settimana",):
        day_start = datetime(target.year, target.month, target.day, 0, 0, tzinfo=TZ).isoformat()
        day_end = datetime(target.year, target.month, target.day, 23, 59, 59, tzinfo=TZ).isoformat()

    try:
        res = cal.events().list(
            calendarId="primary",
            timeMin=day_start,
            timeMax=day_end,
            singleEvents=True,
            orderBy="startTime",
        ).execute()
        items = res.get("items", [])
        if not items:
            return f"Nessun evento per {date_str}."
        events = []
        for e in items:
            start = e["start"].get("dateTime", e["start"].get("date", ""))
            end = e["end"].get("dateTime", e["end"].get("date", ""))
            events.append({
                "id": e["id"],
                "titolo": e.get("summary", "Senza titolo"),
                "inizio": _fmt_dt(start) if "T" in start else "tutto il giorno",
                "fine": _fmt_dt(end) if "T" in end else "",
                "luogo": e.get("location", ""),
                "descrizione": e.get("description", ""),
                "colorId": e.get("colorId", ""),  # 10=verde/fatto, 11=rosso/non fatto, 3=viola/rimandato
            })
        return json.dumps(events, ensure_ascii=False, indent=2)
    except Exception as e:
        return f"Errore calendario: {e}"


# Color IDs per stati task
TASK_COLOR_DONE       = "10"   # Basil — verde scuro
TASK_COLOR_NOT_DONE   = "11"   # Tomato — rosso
TASK_COLOR_RESCHEDULED = "3"   # Grape — viola


def calendar_create_task(
    title: str,
    date_str: str,
    start_time: str = "",
    end_time: str = "",
    description: str = "",
    domain: str = "",
) -> dict:
    """Crea un evento-task sul Calendar e restituisce event_id + link.
    Se start_time è vuoto crea un evento tutto il giorno.
    """
    cal = _cal_service()
    if not cal:
        return {"error": _not_auth()}
    try:
        if domain:
            description = f"[{domain}]\n{description}".strip()

        if start_time:
            if not end_time:
                # Default: 30 minuti
                s = datetime.fromisoformat(f"{date_str}T{start_time}:00").replace(tzinfo=TZ)
                e = s + timedelta(minutes=30)
                end_time = e.strftime("%H:%M")
            start_dt = datetime.fromisoformat(f"{date_str}T{start_time}:00").replace(tzinfo=TZ)
            end_dt   = datetime.fromisoformat(f"{date_str}T{end_time}:00").replace(tzinfo=TZ)
            start_body = {"dateTime": start_dt.isoformat(), "timeZone": "Europe/Rome"}
            end_body   = {"dateTime": end_dt.isoformat(),   "timeZone": "Europe/Rome"}
        else:
            # Evento tutto il giorno
            start_body = {"date": date_str}
            end_body   = {"date": date_str}

        event = {
            "summary": title,
            "description": description,
            "start": start_body,
            "end": end_body,
        }
        created = cal.events().insert(calendarId="primary", body=event).execute()
        return {
            "event_id": created["id"],
            "link": created.get("htmlLink", ""),
            "message": f"✅ Task creata sul calendario: '{title}' — {date_str}" + (f" alle {start_time}" if start_time else ""),
        }
    except Exception as e:
        return {"error": f"Errore creazione task calendario: {e}"}


def calendar_update_task_color(event_id: str, color_id: str) -> bool:
    """Aggiorna il colore di un evento Calendar. Restituisce True se ok."""
    cal = _cal_service()
    if not cal:
        return False
    try:
        cal.events().patch(
            calendarId="primary",
            eventId=event_id,
            body={"colorId": color_id},
        ).execute()
        return True
    except Exception as e:
        logger.error(f"calendar_update_task_color: {e}")
        return False


def calendar_move_task(
    event_id: str, new_date: str, new_start_time: str = "", new_end_time: str = ""
) -> bool:
    """Sposta un evento a nuova data/ora e lo colora di viola (rischedulato). Restituisce True se ok."""
    cal = _cal_service()
    if not cal:
        return False
    try:
        # Leggi l'evento attuale per preservare la durata
        existing = cal.events().get(calendarId="primary", eventId=event_id).execute()
        body: dict = {"colorId": TASK_COLOR_RESCHEDULED}

        if new_start_time:
            if not new_end_time:
                s = datetime.fromisoformat(f"{new_date}T{new_start_time}:00").replace(tzinfo=TZ)
                e = s + timedelta(minutes=30)
                new_end_time = e.strftime("%H:%M")
            body["start"] = {"dateTime": datetime.fromisoformat(f"{new_date}T{new_start_time}:00").replace(tzinfo=TZ).isoformat(), "timeZone": "Europe/Rome"}
            body["end"]   = {"dateTime": datetime.fromisoformat(f"{new_date}T{new_end_time}:00").replace(tzinfo=TZ).isoformat(),   "timeZone": "Europe/Rome"}
        else:
            body["start"] = {"date": new_date}
            body["end"]   = {"date": new_date}

        cal.events().patch(
            calendarId="primary", eventId=event_id, body=body
        ).execute()
        return True
    except Exception as e:
        logger.error(f"calendar_move_task: {e}")
        return False


def calendar_add_event(
    title: str,
    date_str: str,
    start_time: str = "",
    end_time: str = "",
    description: str = "",
    location: str = "",
    recurrence: str = "",
) -> str:
    """Aggiunge un evento/task al Google Calendar.

    Args:
        title: Titolo dell'evento
        date_str: Data in formato YYYY-MM-DD
        start_time: Orario di inizio HH:MM (ometti per evento tutto il giorno)
        end_time: Orario di fine HH:MM (ometti per evento tutto il giorno o durata default 1h)
        description: Descrizione opzionale
        location: Luogo opzionale
        recurrence: 'daily', 'weekly', 'monthly', o RRULE completa (opzionale)
    """
    cal = _cal_service()
    if not cal:
        return _not_auth()

    try:
        if start_time:
            if not end_time:
                s = datetime.fromisoformat(f"{date_str}T{start_time}:00").replace(tzinfo=TZ)
                e = s + timedelta(hours=1)
                end_time = e.strftime("%H:%M")
            start_dt = datetime.fromisoformat(f"{date_str}T{start_time}:00").replace(tzinfo=TZ)
            end_dt   = datetime.fromisoformat(f"{date_str}T{end_time}:00").replace(tzinfo=TZ)
            event = {
                "summary": title,
                "description": description,
                "location": location,
                "start": {"dateTime": start_dt.isoformat(), "timeZone": "Europe/Rome"},
                "end":   {"dateTime": end_dt.isoformat(),   "timeZone": "Europe/Rome"},
            }
            time_info = f" dalle {start_time} alle {end_time}"
        else:
            # Evento tutto il giorno
            next_day = (date.fromisoformat(date_str) + timedelta(days=1)).isoformat()
            event = {
                "summary": title,
                "description": description,
                "location": location,
                "start": {"date": date_str},
                "end":   {"date": next_day},
            }
            time_info = " (tutto il giorno)"

        _recurrence_map = {
            "daily": "RRULE:FREQ=DAILY",
            "weekly": "RRULE:FREQ=WEEKLY",
            "monthly": "RRULE:FREQ=MONTHLY",
        }
        if recurrence:
            rule = _recurrence_map.get(recurrence.lower(), recurrence)
            event["recurrence"] = [rule]

        created = cal.events().insert(calendarId="primary", body=event).execute()
        link = created.get("htmlLink", "")
        return f"✅ Evento creato: '{title}' il {date_str}{time_info}\n{link}"
    except Exception as e:
        return f"Errore creazione evento: {e}"


def calendar_mark_done(event_id: str) -> str:
    """Segna un evento come completato: lo colora di verde sul Calendar e salva su DB.

    Args:
        event_id: ID dell'evento (da calendar_get_events, campo 'id')
    """
    cal = _cal_service()
    if not cal:
        return _not_auth()
    try:
        event = cal.events().get(calendarId="primary", eventId=event_id).execute()
        cal.events().patch(
            calendarId="primary", eventId=event_id, body={"colorId": TASK_COLOR_DONE}
        ).execute()
        title = event.get("summary", "evento")
        # Salva su DB
        try:
            from agent.database import task_upsert_status
            task_upsert_status(event_id, title, "done")
        except Exception:
            pass
        return f"✅ '{title}' segnato come fatto (verde sul calendario)"
    except Exception as e:
        return f"Errore: {e}"


def calendar_mark_not_done(event_id: str) -> str:
    """Segna un evento come non completato: lo colora di rosso sul Calendar e salva su DB.

    Args:
        event_id: ID dell'evento (da calendar_get_events, campo 'id')
    """
    cal = _cal_service()
    if not cal:
        return _not_auth()
    try:
        event = cal.events().get(calendarId="primary", eventId=event_id).execute()
        cal.events().patch(
            calendarId="primary", eventId=event_id, body={"colorId": TASK_COLOR_NOT_DONE}
        ).execute()
        title = event.get("summary", "evento")
        try:
            from agent.database import task_upsert_status
            task_upsert_status(event_id, title, "not_done")
        except Exception:
            pass
        return f"❌ '{title}' segnato come non fatto (rosso sul calendario)"
    except Exception as e:
        return f"Errore: {e}"


def calendar_reschedule_event(event_id: str, new_date: str, new_time: str = "") -> str:
    """Rimanda un evento a una nuova data/ora: lo colora di viola e lo sposta sul Calendar.

    Args:
        event_id: ID dell'evento (da calendar_get_events)
        new_date: Nuova data YYYY-MM-DD
        new_time: Nuovo orario HH:MM (opzionale — ometti per tutto il giorno)
    """
    cal = _cal_service()
    if not cal:
        return _not_auth()
    try:
        event = cal.events().get(calendarId="primary", eventId=event_id).execute()
        title = event.get("summary", "evento")
        body: dict = {"colorId": TASK_COLOR_RESCHEDULED}

        if new_time:
            end_dt = (datetime.fromisoformat(f"{new_date}T{new_time}:00").replace(tzinfo=TZ)
                      + timedelta(hours=1))
            body["start"] = {"dateTime": datetime.fromisoformat(f"{new_date}T{new_time}:00").replace(tzinfo=TZ).isoformat(), "timeZone": "Europe/Rome"}
            body["end"]   = {"dateTime": end_dt.isoformat(), "timeZone": "Europe/Rome"}
            time_str = f" alle {new_time}"
        else:
            next_day = (date.fromisoformat(new_date) + timedelta(days=1)).isoformat()
            body["start"] = {"date": new_date}
            body["end"]   = {"date": next_day}
            time_str = " (tutto il giorno)"

        cal.events().patch(calendarId="primary", eventId=event_id, body=body).execute()
        try:
            from agent.database import task_upsert_status
            task_upsert_status(event_id, title, "rescheduled", new_date=new_date, new_time=new_time)
        except Exception:
            pass
        return f"🔄 '{title}' rimandato al {new_date}{time_str} (viola sul calendario)"
    except Exception as e:
        return f"Errore: {e}"


def get_today_events_for_recap() -> dict:
    """Restituisce gli eventi di oggi raggruppati per stato (per recap serale)."""
    cal = _cal_service()
    if not cal:
        return {"error": _not_auth()}
    today = date.today()
    day_start = datetime(today.year, today.month, today.day, 0, 0, tzinfo=TZ).isoformat()
    day_end   = datetime(today.year, today.month, today.day, 23, 59, 59, tzinfo=TZ).isoformat()
    try:
        res = cal.events().list(
            calendarId="primary", timeMin=day_start, timeMax=day_end,
            singleEvents=True, orderBy="startTime",
        ).execute()
        done, not_done, rescheduled, pending = [], [], [], []
        for e in res.get("items", []):
            start = e["start"].get("dateTime", e["start"].get("date", ""))
            color = e.get("colorId", "")
            entry = {
                "id": e["id"],
                "titolo": e.get("summary", ""),
                "orario": _fmt_dt(start) if "T" in start else "tutto il giorno",
            }
            if color == TASK_COLOR_DONE:
                done.append(entry)
            elif color == TASK_COLOR_NOT_DONE:
                not_done.append(entry)
            elif color == TASK_COLOR_RESCHEDULED:
                rescheduled.append(entry)
            else:
                pending.append(entry)
        return {"done": done, "not_done": not_done, "rescheduled": rescheduled, "pending": pending}
    except Exception as e:
        return {"error": str(e)}


def calendar_delete_event(event_id: str) -> str:
    """Cancella un evento dal Google Calendar dato il suo ID.

    Args:
        event_id: ID dell'evento (ottenuto da calendar_get_events)
    """
    cal = _cal_service()
    if not cal:
        return _not_auth()
    try:
        cal.events().delete(calendarId="primary", eventId=event_id).execute()
        return f"🗑️ Evento cancellato."
    except Exception as e:
        return f"Errore cancellazione evento: {e}"


def tasks_get_list() -> str:
    """Recupera tutti i task non completati da Google Tasks."""
    svc = _tasks_service()
    if not svc:
        return _not_auth()
    try:
        lists_res = svc.tasklists().list().execute()
        all_tasks = []
        for tl in lists_res.get("items", []):
            tasks_res = svc.tasks().list(
                tasklist=tl["id"], showCompleted=False
            ).execute()
            for t in tasks_res.get("items", []):
                all_tasks.append({
                    "id": t["id"],
                    "lista": tl.get("title", ""),
                    "lista_id": tl["id"],
                    "titolo": t.get("title", ""),
                    "scadenza": t.get("due", "")[:10] if t.get("due") else "",
                    "note": t.get("notes", ""),
                    "stato": t.get("status", ""),
                })
        return json.dumps(all_tasks, ensure_ascii=False, indent=2) if all_tasks else "Nessun task pendente."
    except Exception as e:
        return f"Errore tasks: {e}"


def get_today_tracker() -> dict:
    """Return today's tasks split by completed/not completed. Used by scheduler."""
    svc = _tasks_service()
    if not svc:
        return {"errore": _not_auth()}

    today = str(date.today())
    completed, pending = [], []

    try:
        lists_res = svc.tasklists().list().execute()
        for tl in lists_res.get("items", []):
            # Pending tasks due today or earlier
            pending_res = svc.tasks().list(
                tasklist=tl["id"], showCompleted=False, showHidden=False
            ).execute()
            for t in pending_res.get("items", []):
                due = (t.get("due") or "")[:10]
                if not due or due <= today:
                    pending.append({
                        "id": t["id"],
                        "lista_id": tl["id"],
                        "titolo": t.get("title", ""),
                        "scadenza": due,
                    })

            # Completed today
            completed_res = svc.tasks().list(
                tasklist=tl["id"], showCompleted=True, showHidden=True
            ).execute()
            for t in completed_res.get("items", []):
                if t.get("status") == "completed":
                    comp_time = (t.get("completed") or "")[:10]
                    if comp_time == today:
                        completed.append({"titolo": t.get("title", ""), "lista_id": tl["id"]})

    except Exception as e:
        return {"errore": str(e)}

    return {"completate": completed, "non_completate": pending, "data": today}


def tasks_complete(task_id: str, tasklist_id: str = "") -> str:
    """Segna un task come completato.

    Args:
        task_id: ID del task (ottenuto da tasks_get_list)
        tasklist_id: ID della lista (ottenuto da tasks_get_list, opzionale)
    """
    svc = _tasks_service()
    if not svc:
        return _not_auth()
    try:
        if not tasklist_id:
            lists_res = svc.tasklists().list().execute()
            tasklist_id = lists_res["items"][0]["id"]

        svc.tasks().update(
            tasklist=tasklist_id,
            task=task_id,
            body={"id": task_id, "status": "completed"},
        ).execute()
        return "✅ Task segnato come completato."
    except Exception as e:
        return f"Errore: {e}"


def tasks_update_due(task_id: str, new_due_date: str, tasklist_id: str = "") -> str:
    """Cambia la data di scadenza di un task (per rischedularlo).

    Args:
        task_id: ID del task (ottenuto da tasks_get_list)
        new_due_date: Nuova data di scadenza in formato YYYY-MM-DD
        tasklist_id: ID della lista (ottenuto da tasks_get_list, opzionale)
    """
    svc = _tasks_service()
    if not svc:
        return _not_auth()
    try:
        if not tasklist_id:
            lists_res = svc.tasklists().list().execute()
            tasklist_id = lists_res["items"][0]["id"]

        svc.tasks().update(
            tasklist=tasklist_id,
            task=task_id,
            body={"id": task_id, "due": f"{new_due_date}T00:00:00.000Z"},
        ).execute()
        return f"📅 Task rischedulato al {new_due_date}."
    except Exception as e:
        return f"Errore: {e}"


def tasks_add(title: str, due_date: str = "", notes: str = "") -> str:
    """Aggiunge un task a Google Tasks.

    Args:
        title: Titolo del task
        due_date: Data di scadenza in formato YYYY-MM-DD (opzionale)
        notes: Note aggiuntive (opzionale)
    """
    svc = _tasks_service()
    if not svc:
        return _not_auth()
    try:
        # Get default task list
        lists_res = svc.tasklists().list().execute()
        default_list = lists_res["items"][0]["id"]

        task = {"title": title, "notes": notes}
        if due_date:
            task["due"] = f"{due_date}T00:00:00.000Z"

        created = svc.tasks().insert(tasklist=default_list, body=task).execute()
        due_info = f" (scadenza: {due_date})" if due_date else ""
        return f"✅ Task aggiunto: '{title}'{due_info}"
    except Exception as e:
        return f"Errore aggiunta task: {e}"
