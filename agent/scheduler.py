import asyncio
import json
import logging
import os
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

import anthropic
from telegram.ext import Application

logger = logging.getLogger(__name__)
ROME_TZ = ZoneInfo("Europe/Rome")
MODEL = "claude-haiku-4-5-20251001"

# Traccia gli event_id per cui abbiamo già mandato il reminder (resettato ogni notte)
_reminded_today: set = set()


def _claude(system: str, user: str) -> str:
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    resp = client.messages.create(
        model=MODEL,
        max_tokens=2000,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return resp.content[0].text


# ── Job callbacks ──────────────────────────────────────────────────────────────

async def send_email_recap(context):
    """12:30 — Daily email recap."""
    from agent.gmail import get_today_emails_summary

    owner_id = int(os.environ.get("OWNER_TELEGRAM_ID", 0))
    if not owner_id:
        return

    try:
        emails_data = await asyncio.to_thread(get_today_emails_summary)
        today_str = datetime.now(ROME_TZ).strftime("%d/%m/%Y")

        text = await asyncio.to_thread(
            _claude,
            (
                "Sei l'assistente email personale. Presenta le email in modo chiaro e conciso. "
                "Usa la formattazione Telegram (grassetto con *testo*, liste con -). "
                "NON aggiungere preamboli tipo 'Ecco il recap'."
            ),
            (
                f"Fai un recap delle email di oggi ({today_str}).\n"
                "Dividile in due sezioni NETTE:\n"
                "📢 *Promozionali/Newsletter* — non richiedono azione\n"
                "📬 *Da leggere/rispondere* — richiedono attenzione\n\n"
                f"Email:\n{emails_data}"
            ),
        )

        header = f"📧 *Recap Email — {today_str}*\n\n"
        await context.bot.send_message(
            chat_id=owner_id,
            text=header + text,
            parse_mode="Markdown",
        )
    except Exception as e:
        logger.error(f"send_email_recap error: {e}")


async def send_calendar_briefing(context):
    """08:00 — Briefing mattutino: eventi del giorno dal Calendar."""
    owner_id = int(os.environ.get("OWNER_TELEGRAM_ID", 0))
    if not owner_id:
        return

    try:
        from agent.gcalendar import calendar_get_events
        today_str = datetime.now(ROME_TZ).strftime("%A %d/%m/%Y")
        events_json = await asyncio.to_thread(calendar_get_events, "oggi")

        try:
            events = json.loads(events_json)
        except Exception:
            events = []

        if not events:
            await context.bot.send_message(
                chat_id=owner_id,
                text=f"🌅 *Buongiorno! — {today_str}*\n\nNessun evento in calendario per oggi. Buona giornata! 💪",
                parse_mode="Markdown",
            )
            return

        lines = [f"🌅 *Buongiorno! — {today_str}*\n"]
        lines.append("📅 *Programma di oggi:*")
        for e in events:
            orario = e.get("inizio", "")
            titolo = e.get("titolo", "")
            luogo = f" 📍 {e['luogo']}" if e.get("luogo") else ""
            if orario == "tutto il giorno":
                lines.append(f"  • {titolo}{luogo}")
            else:
                fine = e.get("fine", "")
                time_range = f"{orario}–{fine}" if fine else orario
                lines.append(f"  ⏰ {time_range} *{titolo}*{luogo}")

        lines.append("\nBuona giornata! 💪")
        await context.bot.send_message(
            chat_id=owner_id,
            text="\n".join(lines),
            parse_mode="Markdown",
        )
    except Exception as e:
        logger.error(f"send_calendar_briefing error: {e}")


async def send_event_reminders(context):
    """Ogni minuto — manda reminder 10 minuti prima di ogni evento del giorno."""
    global _reminded_today
    owner_id = int(os.environ.get("OWNER_TELEGRAM_ID", 0))
    if not owner_id:
        return

    try:
        from agent.gcalendar import _cal_service, _fmt_dt, TZ
        now = datetime.now(ROME_TZ)

        # Reset set a mezzanotte
        if now.hour == 0 and now.minute < 2:
            _reminded_today.clear()

        # Finestra: eventi che iniziano tra 8 e 12 minuti da adesso
        window_start = now + timedelta(minutes=8)
        window_end   = now + timedelta(minutes=12)

        cal = _cal_service()
        if not cal:
            return

        res = cal.events().list(
            calendarId="primary",
            timeMin=window_start.isoformat(),
            timeMax=window_end.isoformat(),
            singleEvents=True,
            orderBy="startTime",
        ).execute()

        for e in res.get("items", []):
            event_id = e["id"]
            if event_id in _reminded_today:
                continue  # già inviato oggi

            start = e["start"].get("dateTime", "")
            if not start:
                continue  # evento tutto il giorno, skip reminder

            titolo = e.get("summary", "Evento")
            orario = _fmt_dt(start)
            luogo = f"\n📍 {e['luogo']}" if e.get("location") else ""
            descrizione = f"\n📝 {e['description'][:100]}" if e.get("description") else ""

            await context.bot.send_message(
                chat_id=owner_id,
                text=(
                    f"⏰ *Tra ~10 minuti:* *{titolo}*\n"
                    f"🕐 Ore {orario}{luogo}{descrizione}"
                ),
                parse_mode="Markdown",
            )
            _reminded_today.add(event_id)

    except Exception as e:
        logger.error(f"send_event_reminders error: {e}")


async def send_planning_reminder(context):
    """22:00 — Mostra il programma di domani e chiede di aggiungere/modificare eventi."""
    owner_id = int(os.environ.get("OWNER_TELEGRAM_ID", 0))
    if not owner_id:
        return
    try:
        from agent.gcalendar import calendar_get_events
        events_json = await asyncio.to_thread(calendar_get_events, "domani")

        try:
            events = json.loads(events_json)
        except Exception:
            events = []

        tomorrow_str = (datetime.now(ROME_TZ) + timedelta(days=1)).strftime("%A %d/%m/%Y")
        lines = [f"🗓 *Pianifica domani — {tomorrow_str}*\n"]

        if events:
            lines.append("Hai già questi eventi:")
            for e in events:
                orario = e.get("inizio", "")
                titolo = e.get("titolo", "")
                if orario == "tutto il giorno":
                    lines.append(f"  • {titolo}")
                else:
                    lines.append(f"  ⏰ {orario} *{titolo}*")
        else:
            lines.append("Nessun evento in calendario per domani.")

        lines.append("\nVuoi aggiungere qualcosa? Dimmi cosa devi fare domani.")

        await context.bot.send_message(
            chat_id=owner_id,
            text="\n".join(lines),
            parse_mode="Markdown",
        )
    except Exception as e:
        logger.error(f"send_planning_reminder error: {e}")


async def send_evening_recap(context):
    """22:30 — Recap della giornata: fatto/non fatto/rimandato (da Calendar colorId)."""
    owner_id = int(os.environ.get("OWNER_TELEGRAM_ID", 0))
    if not owner_id:
        return
    try:
        from agent.gcalendar import get_today_events_for_recap
        today_str = datetime.now(ROME_TZ).strftime("%d/%m/%Y")
        data = await asyncio.to_thread(get_today_events_for_recap)

        if "error" in data:
            await context.bot.send_message(chat_id=owner_id, text=f"❌ Errore recap: {data['error']}")
            return

        done        = data.get("done", [])
        not_done    = data.get("not_done", [])
        rescheduled = data.get("rescheduled", [])
        pending     = data.get("pending", [])

        lines = [f"📊 *Recap giornata — {today_str}*\n"]

        if done:
            lines.append(f"✅ *Fatto ({len(done)}):*")
            for t in done:
                lines.append(f"  • {t['titolo']}")
            lines.append("")

        if not_done:
            lines.append(f"❌ *Non fatto ({len(not_done)}):*")
            for t in not_done:
                lines.append(f"  • {t['titolo']}")
            lines.append("")

        if rescheduled:
            lines.append(f"🔄 *Rimandato ({len(rescheduled)}):*")
            for t in rescheduled:
                lines.append(f"  • {t['titolo']}")
            lines.append("")

        if pending:
            lines.append(f"⏳ *Non aggiornato ({len(pending)}):*")
            for t in pending:
                orario = f" {t['orario']}" if t.get("orario") and t["orario"] != "tutto il giorno" else ""
                lines.append(f"  • {t['titolo']}{orario}")
            lines.append("")
            lines.append("_Vuoi segnare qualcosa come fatto, non fatto o rimandarlo?_")

        total = len(done) + len(not_done) + len(rescheduled) + len(pending)
        if total == 0:
            lines.append("Nessun evento oggi.")

        await context.bot.send_message(
            chat_id=owner_id,
            text="\n".join(lines),
            parse_mode="Markdown",
        )
    except Exception as e:
        logger.error(f"send_evening_recap error: {e}")
        await context.bot.send_message(
            chat_id=int(os.environ.get("OWNER_TELEGRAM_ID", 0)),
            text=f"❌ Errore recap serale: {e}",
        )


async def send_diet_planning_reminder(context):
    """Domenica 12:00 — Ricorda di registrare la spesa per pianificare la dieta."""
    owner_id = int(os.environ.get("OWNER_TELEGRAM_ID", 0))
    if not owner_id:
        return
    try:
        from agent.database import diet_get_shopping
        shopping = await asyncio.to_thread(diet_get_shopping)
        text = (
            "🥗 *Programmiamo la dieta per la settimana!*\n\n"
            "Dimmi cosa hai comprato — mandami la lista della spesa "
            "e preparo le proposte pasto personalizzate per tutta la settimana 🎯"
        )
        if shopping:
            preview = shopping.split("\n")[1][:120] if "\n" in shopping else shopping[:120]
            text += f"\n\n_Settimana scorsa: {preview}_"
        await context.bot.send_message(chat_id=owner_id, text=text, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"send_diet_planning_reminder error: {e}")


_NUTRITION_SYSTEM = (
    "Sei un nutrizionista preciso. Calcola macro e calorie accuratamente usando questi valori "
    "di riferimento per 100g: pollo/tacchino 165kcal P23 C0 G7 | salmone 208kcal P20 C0 G13 | "
    "uovo intero 155kcal P13 C1 G11 (1 uovo≈60g) | fiocchi di latte 72kcal P11 C3 G1 | "
    "yogurt greco 59kcal P10 C4 G0 | avena 389kcal P17 C66 G7 | albume 52kcal P11 C1 G0 | "
    "whey proteine 400kcal P80 C8 G5 | riso crudo 360kcal P7 C79 G1 | "
    "pasta cruda 357kcal P13 C72 G2 | patate 77kcal P2 C17 G0 | olio 900kcal P0 C0 G100 | "
    "parmigiano 431kcal P38 C0 G29 | latte 61kcal P3 C5 G3."
)

_MEAL_FORMAT = (
    "Formato OBBLIGATORIO per ogni opzione:\n"
    "[n]️⃣ **[nome breve]**\n"
    "- [quantità]g/ml [ingrediente]\n"
    "📊 ~[kcal] kcal | P: [g]g | C: [g]g | G: [g]g"
)


def _build_all_meal_proposals() -> dict:
    """Genera proposte per TUTTI e 4 i pasti in una sola chiamata Claude (batch 07:00)."""
    import re
    from agent.database import diet_get_base, diet_get_shopping

    diet_base = diet_get_base()
    shopping  = diet_get_shopping()

    now      = datetime.now(ROME_TZ)
    weekday  = now.weekday()
    day_name = ["lunedì","martedì","mercoledì","giovedì","venerdì","sabato","domenica"][weekday]
    is_rice  = weekday in (4, 5, 6, 0)

    shopping_block = (
        f"Lista spesa questa settimana:\n{shopping}"
        if shopping else
        "Spesa non registrata — usa ingredienti tipici dello schema."
    )
    rice_note = "\nNOTA PRANZO: oggi è giorno di riso (ven→lun) — includi 60g riso." if is_rice else ""

    prompt = (
        f"Oggi è {day_name}. Genera 3 opzioni per OGNUNO dei 4 pasti.\n\n"
        f"Schema dieta:\n{diet_base}\n\n"
        f"{shopping_block}{rice_note}\n\n"
        f"{_MEAL_FORMAT}\n\n"
        "Struttura la risposta esattamente così (usa i separatori):\n\n"
        "===COLAZIONE===\n[3 opzioni]\n\n"
        "===PRANZO===\n[3 opzioni]\n\n"
        "===MERENDA===\n[3 opzioni]\n\n"
        "===CENA===\n[3 opzioni]\n\n"
        "Niente preamboli. Solo i 4 blocchi."
    )

    raw = _claude(_NUTRITION_SYSTEM, prompt)

    # Parsing: estrai i 4 blocchi
    result = {}
    for meal in ("colazione", "pranzo", "merenda", "cena"):
        pattern = rf"==={meal.upper()}===\s*(.*?)(?====|$)"
        match = re.search(pattern, raw, re.DOTALL | re.IGNORECASE)
        result[meal] = match.group(1).strip() if match else ""

    return result


def _build_meal_proposals(meal_type: str) -> str:
    """Genera 3 proposte per il pasto — usa cache giornaliera se disponibile."""
    from agent.database import diet_get_daily_meals

    # ── Usa cache batch se disponibile ──
    cached = diet_get_daily_meals()
    if cached and cached.get(meal_type):
        logger.info(f"meal_proposals({meal_type}): uso cache giornaliera")
        return cached[meal_type]

    # ── Fallback: genera on-demand (singola chiamata) ──
    logger.info(f"meal_proposals({meal_type}): cache mancante, genero on-demand")
    from agent.database import diet_get_base, diet_get_shopping
    diet_base = diet_get_base()
    shopping  = diet_get_shopping()

    now      = datetime.now(ROME_TZ)
    weekday  = now.weekday()
    day_name = ["lunedì","martedì","mercoledì","giovedì","venerdì","sabato","domenica"][weekday]
    is_rice  = weekday in (4, 5, 6, 0)

    shopping_block = (
        f"Lista spesa disponibile questa settimana:\n{shopping}"
        if shopping else
        "Lista spesa non ancora registrata — usa ingredienti tipici dello schema."
    )
    rice_note = (
        "\nNOTA: Oggi è giorno di riso (ven→lun) — includi 60g riso nel pranzo."
        if is_rice and meal_type == "pranzo" else ""
    )

    prompt = (
        f"Proponi esattamente 3 opzioni per la {meal_type} di {day_name}.\n\n"
        f"Schema dieta:\n{diet_base}\n\n"
        f"{shopping_block}{rice_note}\n\n"
        f"{_MEAL_FORMAT}\n\n"
        "Numera le opzioni con 1️⃣ 2️⃣ 3️⃣. Niente preamboli."
    )
    return _claude(_NUTRITION_SYSTEM, prompt)


async def _send_meal(context, meal_type: str, emoji: str):
    owner_id = int(os.environ.get("OWNER_TELEGRAM_ID", 0))
    if not owner_id:
        return
    try:
        proposals = await asyncio.to_thread(_build_meal_proposals, meal_type)
        await context.bot.send_message(
            chat_id=owner_id,
            text=f"{emoji} *{meal_type.capitalize()} — proposte di oggi:*\n\n{proposals}",
            parse_mode="Markdown",
        )
    except Exception as e:
        logger.error(f"_send_meal({meal_type}) error: {e}")


async def send_meal_daily_prep(context):
    """07:00 — Genera e salva le proposte per tutti i 4 pasti del giorno in una sola chiamata."""
    owner_id = int(os.environ.get("OWNER_TELEGRAM_ID", 0))
    try:
        proposals = await asyncio.to_thread(_build_all_meal_proposals)
        from agent.database import diet_save_daily_meals
        await asyncio.to_thread(diet_save_daily_meals, proposals)
        logger.info("Proposte pasto giornaliere generate e salvate (batch)")
    except Exception as e:
        logger.error(f"send_meal_daily_prep error: {e}")


async def send_meal_colazione(context): await _send_meal(context, "colazione", "☀️")
async def send_meal_pranzo(context):    await _send_meal(context, "pranzo",    "🍽️")
async def send_meal_merenda(context):   await _send_meal(context, "merenda",   "🍎")
async def send_meal_cena(context):      await _send_meal(context, "cena",      "🌙")


async def check_pending_calls(context):
    """Ogni 2 minuti — controlla chiamate Bland.ai in corso e notifica se completate."""
    owner_id = int(os.environ.get("OWNER_TELEGRAM_ID", 0))
    if not owner_id or not os.environ.get("VAPI_API_KEY"):
        return
    try:
        from agent.phone import calls_check_pending, _format_call_result
        completed = await asyncio.to_thread(calls_check_pending)
        for item in completed:
            call = item["call"]
            data = item["data"]
            status = item["status"]

            status_emoji = {
                "completed": "✅", "failed": "❌", "voicemail": "📬",
                "busy": "🔴", "no-answer": "📵",
            }.get(status, "⏳")

            summary = data.get("summary", "")
            transcripts = data.get("transcripts", [])
            duration = int(data.get("call_length", 0))
            number = call.get("phone_number", "")

            lines = [
                f"{status_emoji} *Chiamata completata — {number}*",
                f"Durata: {duration}s | Stato: {status}",
            ]
            if summary:
                lines.append(f"\n📋 *Riepilogo:*\n{summary}")
            if transcripts:
                lines.append("\n💬 *Trascrizione:*")
                for t in transcripts[-8:]:
                    role = "🤖" if t.get("user") == "assistant" else "☎️"
                    text = (t.get("text") or "").strip()
                    if text:
                        lines.append(f"{role} {text[:250]}")

            await context.bot.send_message(
                chat_id=owner_id,
                text="\n".join(lines),
                parse_mode="Markdown",
            )
    except Exception as e:
        logger.error(f"check_pending_calls error: {e}")


async def run_daily_audit(context):
    """23:55 — Audit notturno: estrae learnings dalla conversazione del giorno e aggiorna la memoria."""
    from agent.database import messages_load_today, memory_read, memory_write

    try:
        messages = await asyncio.to_thread(messages_load_today)
        user_messages = [m for m in messages if m["role"] == "user"]

        if not user_messages:
            logger.info("daily_audit: nessuna interazione oggi, skip")
            return

        current_memory = await asyncio.to_thread(memory_read)

        transcript = "\n".join([
            f"{'Francesco' if m['role'] == 'user' else 'Bot'}: {m['content'][:600]}"
            for m in messages
        ])

        audit_system = (
            "Sei un analista che revisiona conversazioni per estrarre apprendimenti utili per sessioni future.\n\n"
            "Analizza la conversazione di oggi e identifica SOLO informazioni NUOVE che:\n"
            "1. Non sono già presenti nella memoria attuale\n"
            "2. Saranno utili in future interazioni\n\n"
            "Cerca:\n"
            "- Preferenze esplicite ('preferisco', 'voglio sempre', 'non mi piace')\n"
            "- Correzioni fatte ('no non così', 'in futuro fai X')\n"
            "- Nuovi fatti rilevanti su Francesco (abitudini, contesti, preferenze)\n"
            "- Pattern utili da ricordare\n\n"
            "NON salvare:\n"
            "- Task specifici già completati\n"
            "- Info temporanee o di una sola volta\n"
            "- Cose già in memoria\n"
            "- Interazioni banali senza learning\n\n"
            "Se non trovi nulla di nuovo, rispondi esattamente: NESSUN_LEARNING\n\n"
            "Altrimenti scrivi SOLO il testo aggiornato della memoria completa "
            "(memoria attuale + nuovi apprendimenti aggiunti in fondo, formato: [DATA] CATEGORIA: apprendimento)."
        )

        audit_prompt = (
            f"MEMORIA ATTUALE:\n{current_memory or '(vuota)'}\n\n"
            f"CONVERSAZIONE DI OGGI:\n{transcript[:4000]}"
        )

        result = await asyncio.to_thread(_claude, audit_system, audit_prompt)

        if result.strip() == "NESSUN_LEARNING":
            logger.info("daily_audit: nessun nuovo learning trovato")
            return

        await asyncio.to_thread(memory_write, result)
        logger.info(f"daily_audit: memoria aggiornata ({len(result)} chars)")

    except Exception as e:
        logger.error(f"run_daily_audit error: {e}")


async def send_revolut_reminder(context):
    """1° del mese, 13:00 — Chiede l'estratto conto Revolut."""
    owner_id = int(os.environ.get("OWNER_TELEGRAM_ID", 0))
    if not owner_id:
        return
    month_str = datetime.now(ROME_TZ).strftime("%B %Y")
    await context.bot.send_message(
        chat_id=owner_id,
        text=(
            f"💳 *Analisi spese mensili — {month_str}*\n\n"
            "È il momento di analizzare le spese del mese scorso!\n\n"
            "Esporta il CSV da Revolut:\n"
            "Profilo → Estratto conto → seleziona il mese → Esporta CSV\n\n"
            "Poi mandamelo qui e lo analizzo subito 📊"
        ),
        parse_mode="Markdown",
    )


# ── Registration ───────────────────────────────────────────────────────────────

def setup_scheduler(app: Application) -> None:
    from apscheduler.triggers.cron import CronTrigger

    jq = app.job_queue

    # 08:00 Rome — Briefing mattutino
    jq.run_daily(
        callback=send_calendar_briefing,
        time=time(8, 0, tzinfo=ROME_TZ),
        name="calendar_briefing",
    )

    # 12:30 Rome — Recap email
    jq.run_daily(
        callback=send_email_recap,
        time=time(12, 30, tzinfo=ROME_TZ),
        name="email_recap",
    )

    # Ogni minuto — reminder 10 minuti prima degli eventi
    jq.run_repeating(
        callback=send_event_reminders,
        interval=60,
        first=15,
        name="event_reminders",
    )

    # 22:00 Rome — Pianificazione giornata successiva
    jq.run_daily(
        callback=send_planning_reminder,
        time=time(22, 0, tzinfo=ROME_TZ),
        name="planning_reminder",
    )

    # 22:30 Rome — Recap della giornata
    jq.run_daily(
        callback=send_evening_recap,
        time=time(22, 30, tzinfo=ROME_TZ),
        name="evening_recap",
    )

    # 13:00 il 1° di ogni mese — Reminder estratto conto Revolut
    jq.run_custom(
        callback=send_revolut_reminder,
        job_kwargs={"trigger": CronTrigger(day=1, hour=13, minute=0, timezone=ROME_TZ)},
        name="revolut_reminder",
    )

    # Domenica 12:00 — Pianificazione dieta settimanale
    jq.run_custom(
        callback=send_diet_planning_reminder,
        job_kwargs={"trigger": CronTrigger(day_of_week="sun", hour=12, minute=0, timezone=ROME_TZ)},
        name="diet_planning",
    )

    # Ogni 2 minuti — controlla chiamate Bland.ai completate e notifica
    jq.run_repeating(
        callback=check_pending_calls,
        interval=120,
        first=30,
        name="calls_checker",
    )

    # 23:55 — Audit notturno: impara dalle interazioni del giorno
    jq.run_daily(
        callback=run_daily_audit,
        time=time(23, 55, tzinfo=ROME_TZ),
        name="daily_audit",
    )


    logger.info(
        "Scheduler attivo: briefing 08:00 | email recap 12:30 | "
        "reminder eventi ogni minuto | planning 22:00 | recap 22:30 | "
        "audit 23:55 | revolut 1° mese 13:00 | dieta dom 12:00 (Europe/Rome)"
    )
