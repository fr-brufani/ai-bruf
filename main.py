import os
import asyncio
import logging
from dotenv import load_dotenv

load_dotenv()

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
import os
from agent.core import process_message, reset_chat
from agent.memory import read_memory
from agent.scheduler import setup_scheduler

logging.basicConfig(
    format="%(asctime)s — %(name)s — %(levelname)s — %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
OWNER_ID = int(os.environ.get("OWNER_TELEGRAM_ID") or 0)


def is_authorized(user_id: int) -> bool:
    return OWNER_ID == 0 or user_id == OWNER_ID


# ── Commands ──────────────────────────────────────────────────────────────────

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id):
        return
    from agent.google_auth import is_authenticated
    google_status = "✅ Google connesso" if is_authenticated() else "❌ Google non connesso (esegui auth\\_setup.py)"
    await update.message.reply_text(
        "Ciao! Sono il tuo agente AI personale.\n\n"
        f"{google_status}\n\n"
        "Cosa posso fare:\n"
        "📧 Gestire Gmail (recap, ricerca, bozze, invio)\n"
        "📅 Google Calendar & Tasks (leggi, aggiungi, ricorrenti)\n"
        "🔍 Ricerca web e navigazione\n"
        "📁 Gestione file\n\n"
        "Comandi:\n"
        "/myid — mostra il tuo Telegram ID\n"
        "/clear — resetta la conversazione\n"
        "/memory — mostra la memoria\n"
        "/test\\_recap — test recap email immediato\n"
        "/test\\_briefing — test briefing calendario immediato",
        parse_mode="Markdown",
    )


async def cmd_myid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    await update.message.reply_text(
        f"Il tuo Telegram ID: `{u.id}`\n"
        f"Username: @{u.username or 'N/A'}\n\n"
        f"Imposta `OWNER_TELEGRAM_ID={u.id}` nelle variabili d'ambiente su Railway.",
        parse_mode="Markdown",
    )


async def cmd_clear(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id):
        return
    reset_chat()
    await update.message.reply_text("Conversazione resettata. La memoria persistente è conservata.")


async def cmd_memory(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id):
        return
    mem = read_memory()
    if mem.strip():
        text = mem if len(mem) <= 4000 else mem[:4000] + "\n… [troncato]"
        await update.message.reply_text(f"**Memoria corrente:**\n\n{text}", parse_mode="Markdown")
    else:
        await update.message.reply_text("Nessuna memoria salvata.")


# ── Google Auth ────────────────────────────────────────────────────────────────

async def cmd_auth_google(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id):
        return
    try:
        from agent.google_auth import get_auth_url, is_authenticated
        if is_authenticated():
            await update.message.reply_text("✅ Già autenticato con Google!")
            return
        auth_url = get_auth_url()
        await update.message.reply_text(
            "Apri questo link nel browser e autorizza l'accesso:\n\n"
            f"`{auth_url}`\n\n"
            "Dopo l'autorizzazione, Google ti mostrerà un codice.\n"
            "Inviamelo con:\n`/google_code IL_CODICE`",
            parse_mode="Markdown",
        )
    except FileNotFoundError as e:
        await update.message.reply_text(
            f"❌ {e}\n\n"
            "Segui questi passi:\n"
            "1. Vai su console.cloud.google.com\n"
            "2. Crea un progetto → Abilita Gmail API, Calendar API, Tasks API\n"
            "3. Credenziali → OAuth 2.0 → Tipo: App Desktop\n"
            "4. Scarica il JSON e rinominalo `google_credentials.json`\n"
            "5. Caricalo nella cartella del progetto"
        )
    except Exception as e:
        await update.message.reply_text(f"Errore: {e}")


async def cmd_google_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id):
        return
    code = " ".join(context.args).strip()
    if not code:
        await update.message.reply_text("Usa: `/google_code IL_CODICE`", parse_mode="Markdown")
        return
    try:
        from agent.google_auth import exchange_code
        result = await asyncio.to_thread(exchange_code, code)
        await update.message.reply_text(result)
    except Exception as e:
        await update.message.reply_text(f"❌ Errore autenticazione: {e}")


# ── Test commands ──────────────────────────────────────────────────────────────

async def cmd_tracker(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id):
        return
    from agent.scheduler import send_evening_tracker
    await send_evening_tracker(context)


async def cmd_test_recap(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id):
        return
    await update.message.reply_text("Avvio test recap email...")
    from agent.scheduler import send_email_recap
    await send_email_recap(context)


async def cmd_test_briefing(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id):
        return
    await update.message.reply_text("Avvio test briefing calendario...")
    from agent.scheduler import send_calendar_briefing
    await send_calendar_briefing(context)


async def cmd_test_revolut(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id):
        return
    from agent.scheduler import send_revolut_reminder
    await send_revolut_reminder(context)


# ── Message handler ───────────────────────────────────────────────────────────

async def _reply(update: Update, text: str):
    """Send text reply, extracting and sending any embedded screenshots."""
    import re
    screenshots = re.findall(r'\[SCREENSHOT:([^\]]+)\]', text)
    clean_text = re.sub(r'\[SCREENSHOT:[^\]]+\]\n?', '', text).strip()

    # Send screenshots first
    for path in screenshots:
        p = os.path.join(path)  # normalize
        if os.path.exists(p):
            try:
                with open(p, 'rb') as f:
                    await update.message.reply_photo(photo=f)
            except Exception as e:
                logger.error(f"Screenshot send error: {e}")

    # Send text
    if clean_text:
        for chunk in [clean_text[i: i + 4096] for i in range(0, len(clean_text), 4096)]:
            await update.message.reply_text(chunk)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id):
        await update.message.reply_text("Non sei autorizzato ad usare questo bot.")
        return

    text = update.message.text
    if not text:
        return

    await update.effective_chat.send_action("typing")

    try:
        response = await asyncio.to_thread(process_message, text)
        await _reply(update, response)
    except Exception as e:
        logger.error(f"handle_message error: {e}")
        await update.message.reply_text(f"Errore inatteso: {e}")


async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id):
        return

    doc = update.message.document
    if not doc:
        return

    filename = doc.file_name or ""
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    if ext not in ("csv", "xlsx", "xls"):
        await update.message.reply_text("Manda il file come CSV (es. estratto_revolut.csv).")
        return

    await update.effective_chat.send_action("typing")
    await update.message.reply_text(f"📂 File ricevuto: `{filename}` — analizzo...", parse_mode="Markdown")

    try:
        tg_file = await context.bot.get_file(doc.file_id)
        local_path = f"/tmp/{filename}"
        await tg_file.download_to_drive(local_path)

        if ext != "csv":
            await update.message.reply_text(
                "Per ora supporto solo CSV. Da Revolut: Profilo → Estratto conto → Esporta → scegli CSV."
            )
            return

        with open(local_path, encoding="utf-8", errors="replace") as f:
            content = f.read()
        if len(content) > 30000:
            content = content[:30000] + "\n… [file troncato]"

        caption = update.message.caption or ""
        user_note = f"\n\nNota aggiuntiva: {caption}" if caption else ""
        prompt = (
            f"Ho ricevuto l'estratto conto Revolut ({filename}).\n"
            f"Analizza le spese mensili seguendo le istruzioni della workstation finance.{user_note}\n\n"
            f"Contenuto CSV:\n```\n{content}\n```"
        )

        response = await asyncio.to_thread(process_message, prompt)
        await _reply(update, response)

        # Salva su Supabase
        try:
            from datetime import datetime
            from agent.database import expense_report_save
            period = datetime.now().strftime("%Y-%m")
            expense_report_save(period=period, csv_raw=content, analysis_text=response)
        except Exception:
            pass

    except Exception as e:
        logger.error(f"handle_document error: {e}")
        await update.message.reply_text(f"Errore nell'analisi del file: {e}")


async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id):
        return

    await update.effective_chat.send_action("typing")

    try:
        # Download audio file
        voice = update.message.voice or update.message.audio
        tg_file = await context.bot.get_file(voice.file_id)
        ogg_path = f"/tmp/voice_{voice.file_id}.ogg"
        await tg_file.download_to_drive(ogg_path)

        # Transcribe
        from agent.transcriber import transcribe
        text = await asyncio.to_thread(transcribe, ogg_path)
        os.remove(ogg_path)

        if not text:
            await update.message.reply_text("Non sono riuscito a capire l'audio. Riprova.")
            return

        # Show transcription then process
        await update.message.reply_text(f"🎤 _{text}_", parse_mode="Markdown")
        await update.effective_chat.send_action("typing")

        response = await asyncio.to_thread(process_message, text)
        await _reply(update, response)

    except Exception as e:
        logger.error(f"handle_voice error: {e}")
        await update.message.reply_text(f"Errore nella trascrizione: {e}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    app = (
        ApplicationBuilder()
        .token(TELEGRAM_TOKEN)
        .build()
    )

    # Commands
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("myid", cmd_myid))
    app.add_handler(CommandHandler("clear", cmd_clear))
    app.add_handler(CommandHandler("memory", cmd_memory))
    app.add_handler(CommandHandler("tracker", cmd_tracker))
    app.add_handler(CommandHandler("test_recap", cmd_test_recap))
    app.add_handler(CommandHandler("test_briefing", cmd_test_briefing))
    app.add_handler(CommandHandler("test_revolut", cmd_test_revolut))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, handle_voice))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))

    # Scheduled jobs
    setup_scheduler(app)

    # Inizializza schema dieta di default se non già presente
    try:
        from agent.database import diet_initialize_if_empty
        diet_initialize_if_empty()
    except Exception as e:
        logger.warning(f"diet_initialize_if_empty: {e}")

    logger.info("Agente avviato — in ascolto su Telegram...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
