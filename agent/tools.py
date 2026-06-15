from pathlib import Path
from agent.memory import read_memory as _read_memory, write_to_memory


# ── Tool implementations ───────────────────────────────────────────────────────

def search_web(query: str) -> str:
    try:
        from ddgs import DDGS
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=6))
        if not results:
            return "Nessun risultato trovato."
        parts = []
        for r in results:
            parts.append(f"**{r.get('title', '')}**\n{r.get('body', '')}\nURL: {r.get('href', '')}")
        return "\n\n".join(parts)
    except Exception as e:
        return f"Errore nella ricerca: {e}"


def browse_url(url: str) -> str:
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            ctx = browser.new_context(
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
            )
            page = ctx.new_page()
            page.goto(url, timeout=30000, wait_until="domcontentloaded")
            content = page.inner_text("body")
            browser.close()
        if len(content) > 8000:
            content = content[:8000] + "\n… [contenuto troncato]"
        return content
    except Exception as e:
        return f"Errore nel browser: {e}"


def write_memory(content: str) -> str:
    return write_to_memory(content)


def read_memory_tool() -> str:
    mem = _read_memory()
    return mem if mem.strip() else "Nessuna memoria salvata."


def read_file(path: str) -> str:
    try:
        fp = Path(path).expanduser()
        if not fp.exists():
            return f"File non trovato: {path}"
        if not fp.is_file():
            return f"Non è un file: {path}"
        content = fp.read_text(encoding="utf-8", errors="replace")
        if len(content) > 10000:
            content = content[:10000] + "\n… [file troncato]"
        return content
    except Exception as e:
        return f"Errore nella lettura: {e}"


def write_file(path: str, content: str) -> str:
    try:
        fp = Path(path).expanduser()
        fp.parent.mkdir(parents=True, exist_ok=True)
        fp.write_text(content, encoding="utf-8")
        return f"File scritto: {path} ({len(content)} caratteri)"
    except Exception as e:
        return f"Errore nella scrittura: {e}"


def list_directory(path: str = ".") -> str:
    try:
        dp = Path(path).expanduser()
        if not dp.exists():
            return f"Directory non trovata: {path}"
        if not dp.is_dir():
            return f"Non è una directory: {path}"
        items = []
        for item in sorted(dp.iterdir()):
            if item.name.startswith("."):
                continue
            if item.is_dir():
                items.append(f"[DIR]  {item.name}/")
            else:
                items.append(f"[FILE] {item.name} ({item.stat().st_size} B)")
        return f"Contenuto di {path}:\n" + "\n".join(items) if items else f"{path} è vuota"
    except Exception as e:
        return f"Errore: {e}"


# ── Gmail tools ───────────────────────────────────────────────────────────────

def gmail_get_today_emails() -> str:
    from agent.gmail import gmail_get_today_emails as _fn
    return _fn()

def gmail_search(query: str) -> str:
    """Cerca email o contatti in Gmail.

    Args:
        query: Query Gmail (es. 'from:mario@example.com', 'subject:fattura', 'mario rossi')
    """
    from agent.gmail import gmail_search as _fn
    return _fn(query)

def gmail_read_email(message_id: str) -> str:
    """Legge il testo completo di un'email dato il suo ID.

    Args:
        message_id: ID del messaggio Gmail
    """
    from agent.gmail import gmail_read_email as _fn
    return _fn(message_id)

def gmail_create_draft(to: str, subject: str, body: str) -> str:
    """Crea una bozza email in Gmail.

    Args:
        to: Indirizzo email del destinatario
        subject: Oggetto dell'email
        body: Corpo dell'email
    """
    from agent.gmail import gmail_create_draft as _fn
    return _fn(to, subject, body)

def gmail_send_draft(draft_id: str) -> str:
    """Invia una bozza Gmail esistente.

    Args:
        draft_id: ID della bozza (ottenuto da gmail_create_draft)
    """
    from agent.gmail import gmail_send_draft as _fn
    return _fn(draft_id)


# ── Calendar / Tasks tools ─────────────────────────────────────────────────────

def calendar_get_events(date_str: str = "oggi") -> str:
    """Recupera gli eventi del Google Calendar per una data.

    Args:
        date_str: Data in formato YYYY-MM-DD oppure 'oggi', 'domani', 'questa settimana'
    """
    from agent.gcalendar import calendar_get_events as _fn
    return _fn(date_str)

def calendar_add_event(
    title: str, date_str: str, start_time: str = "", end_time: str = "",
    description: str = "", location: str = "", recurrence: str = ""
) -> str:
    """Aggiunge un evento o task al Google Calendar.

    Args:
        title: Titolo dell'evento/task
        date_str: Data YYYY-MM-DD
        start_time: Orario inizio HH:MM (ometti per tutto il giorno)
        end_time: Orario fine HH:MM (ometti per durata 1h default)
        description: Descrizione opzionale
        location: Luogo opzionale
        recurrence: 'daily', 'weekly', 'monthly', o RRULE (opzionale)
    """
    from agent.gcalendar import calendar_add_event as _fn
    return _fn(title, date_str, start_time, end_time, description, location, recurrence)


def calendar_delete_event(event_id: str) -> str:
    """Cancella un evento dal Google Calendar.

    Args:
        event_id: ID dell'evento (da calendar_get_events, campo 'id')
    """
    from agent.gcalendar import calendar_delete_event as _fn
    return _fn(event_id)


def calendar_mark_done(event_id: str) -> str:
    """Segna un evento/task come FATTO: diventa verde sul Calendar e viene salvato nel DB.

    Args:
        event_id: ID dell'evento (da calendar_get_events, campo 'id')
    """
    from agent.gcalendar import calendar_mark_done as _fn
    return _fn(event_id)


def calendar_mark_not_done(event_id: str) -> str:
    """Segna un evento/task come NON FATTO: diventa rosso sul Calendar e viene salvato nel DB.

    Args:
        event_id: ID dell'evento (da calendar_get_events, campo 'id')
    """
    from agent.gcalendar import calendar_mark_not_done as _fn
    return _fn(event_id)


def calendar_reschedule_event(event_id: str, new_date: str, new_time: str = "") -> str:
    """Rimanda un evento a una nuova data/ora: diventa viola e si sposta sul Calendar, salvato nel DB.

    Args:
        event_id: ID dell'evento (da calendar_get_events)
        new_date: Nuova data YYYY-MM-DD
        new_time: Nuovo orario HH:MM (opzionale)
    """
    from agent.gcalendar import calendar_reschedule_event as _fn
    return _fn(event_id, new_date, new_time)


# ── Browser / Application tools ───────────────────────────────────────────────

def browser_fill_application(
    url: str,
    cv_type: str = "sales",
    how_did_you_hear: str = "LinkedIn - post or content",
    extra_fields: str = "",
) -> str:
    """Compila automaticamente un form di job application e restituisce screenshot.

    Args:
        url: URL del form di application
        cv_type: 'sales' o 'product' (scegli in base al ruolo)
        how_did_you_hear: Come hai trovato il lavoro (per radio button)
        extra_fields: Campi extra in formato 'campo=valore,campo2=valore2'
    """
    from agent.browser import browser_fill_application as _fn
    return _fn(url, cv_type, how_did_you_hear, extra_fields)


def browser_screenshot(url: str) -> str:
    """Scatta uno screenshot di una pagina web.

    Args:
        url: URL da fotografare
    """
    from agent.browser import browser_screenshot as _fn
    return _fn(url)


# ── Phone call tools ─────────────────────────────────────────────────────────

def call_make(phone_number: str, task: str, max_duration: int = 5) -> str:
    """Avvia una chiamata AI (Bland.ai) verso un numero italiano.

    Args:
        phone_number: Numero da chiamare (con o senza prefisso +39)
        task: Istruzione precisa in italiano su cosa fare durante la chiamata
        max_duration: Durata massima in minuti (default 5)
    """
    from agent.phone import call_make as _fn
    return _fn(phone_number, task, max_duration)


def call_check_status(call_id: str) -> str:
    """Controlla stato e trascrizione di una chiamata in corso o completata.

    Args:
        call_id: ID della chiamata (da call_make)
    """
    from agent.phone import call_check_status as _fn
    return _fn(call_id)


def call_list_recent() -> str:
    """Mostra le ultime 10 chiamate effettuate con stato e durata."""
    from agent.phone import call_list_recent as _fn
    return _fn()


# ── Database tools ────────────────────────────────────────────────────────────

# ── Wedding tools ─────────────────────────────────────────────────────────────

def wedding_scrape_contact(url: str) -> str:
    """Visita un sito di professionista wedding e cerca nome, email e info di contatto.

    Args:
        url: URL del sito da visitare
    """
    import re
    text = browse_url(url)
    emails = re.findall(r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}', text)
    # Deoffusca email tipo "info [at] sito [dot] it"
    offuscated = re.findall(r'[\w.+\-]+\s*[\[\(]at[\]\)]\s*[\w.\-]+\s*[\[\(]dot[\]\)]\s*\w+', text, re.IGNORECASE)
    for o in offuscated:
        cleaned = re.sub(r'\s*[\[\(]at[\]\)]\s*', '@', o, flags=re.IGNORECASE)
        cleaned = re.sub(r'\s*[\[\(]dot[\]\)]\s*', '.', cleaned, flags=re.IGNORECASE)
        emails.append(cleaned.strip())
    emails = list(set(e for e in emails if not any(x in e.lower() for x in ['example', 'sentry', 'schema', 'pixel'])))
    result = f"URL: {url}\n"
    result += f"Email trovate: {', '.join(emails) if emails else 'nessuna'}\n"
    result += f"\nContenuto (primi 2000 car):\n{text[:2000]}"
    return result


def wedding_add_contact(
    name: str, category: str, email: str = "", website: str = "",
    location: str = "Umbria", notes: str = ""
) -> str:
    """Aggiunge un professionista wedding al tracker.

    Args:
        name: Nome del professionista o azienda
        category: wedding_planner | fotografo | catering | videomaker | floral_designer | agenzia | altro
        email: Email di contatto (opzionale)
        website: URL del sito (opzionale)
        location: Città/zona (default: Umbria)
        notes: Note aggiuntive (opzionale)
    """
    from agent.database import wedding_contact_add
    return wedding_contact_add(name, category, email, website, location, notes)


def wedding_list_contacts(status: str = "", category: str = "") -> str:
    """Mostra i contatti wedding con filtri opzionali.

    Args:
        status: Filtra per stato: new | contacted | replied | negotiating | archived
        category: Filtra per categoria (opzionale)
    """
    from agent.database import wedding_contact_list
    return wedding_contact_list(status, category)


def wedding_update_contact(
    contact_id: int, status: str = "", notes: str = "", email: str = ""
) -> str:
    """Aggiorna stato, note o email di un contatto wedding.

    Args:
        contact_id: ID del contatto (da wedding_list_contacts)
        status: Nuovo stato: new | contacted | replied | negotiating | archived
        notes: Note aggiuntive (opzionale)
        email: Aggiorna l'email (opzionale)
    """
    from agent.database import wedding_contact_update
    return wedding_contact_update(contact_id, status, notes, email)


def wedding_get_contact(contact_id: int) -> str:
    """Legge il profilo completo di un contatto wedding (usato prima di scrivere email).

    Args:
        contact_id: ID del contatto
    """
    from agent.database import wedding_contact_get
    c = wedding_contact_get(contact_id)
    if not c:
        return f"Contatto #{contact_id} non trovato."
    return (
        f"**{c['name']}** (#{c['id']})\n"
        f"Categoria: {c['category']}\n"
        f"Email: {c.get('email') or 'non disponibile'}\n"
        f"Sito: {c.get('website') or 'non disponibile'}\n"
        f"Stato: {c.get('status')}\n"
        f"Zona: {c.get('location')}\n"
        f"Note: {c.get('notes') or 'nessuna'}\n"
        f"Ultimo contatto: {c.get('last_contact') or 'mai'}"
    )




# ── Diet tools ────────────────────────────────────────────────────────────────

def diet_save_shopping(items_text: str, notes: str = "") -> str:
    """Salva la lista della spesa settimanale. Chiamare la domenica quando l'utente
    dice cosa ha comprato. Questa lista viene usata per le proposte pasto della settimana.

    Args:
        items_text: Lista degli ingredienti acquistati (testo libero, uno per riga)
        notes: Note aggiuntive opzionali (es. 'non ho pane', 'poco pesce')
    """
    from agent.database import diet_save_shopping as _fn
    return _fn(items_text, notes)


def diet_get_shopping() -> str:
    """Legge la lista della spesa della settimana corrente.

    Returns:
        Lista spesa con data settimana, o stringa vuota se non registrata
    """
    from agent.database import diet_get_shopping as _fn
    return _fn()


def diet_update_base(content: str) -> str:
    """Aggiorna lo schema base della dieta (usare quando l'utente vuole modificare il piano).

    Args:
        content: Nuovo schema dieta completo in testo libero
    """
    from agent.database import diet_save_base
    return diet_save_base(content)


# ── Database tools ────────────────────────────────────────────────────────────

def db_job_applications_list() -> str:
    """Mostra tutte le job application inviate con il bot, con stato aggiornato."""
    from agent.database import job_applications_list
    return job_applications_list()


def db_job_application_update(app_id: int, status: str, notes: str = "") -> str:
    """Aggiorna lo stato di una job application (es. dopo un colloquio o risposta).

    Args:
        app_id: ID dell'application (visibile in db_job_applications_list)
        status: Nuovo stato: 'applied', 'interviewing', 'offer', 'rejected', 'withdrawn'
        notes: Note aggiuntive opzionali (es. feedback ricevuto)
    """
    from agent.database import job_application_update_status
    return job_application_update_status(app_id, status, notes)


def db_select(table: str, filters: dict = None) -> str:
    """Legge righe da una tabella del database con filtri opzionali (SELECT).

    Args:
        table: Nome della tabella (es. 'user_tasks', 'agent_memory', 'wedding_contacts')
        filters: Dizionario colonna→valore per filtrare (es. {"status": "done", "id": 3})
    """
    from agent.database import db_select as _fn
    return _fn(table, filters or {})


def db_insert(table: str, data: dict) -> str:
    """Inserisce una nuova riga in una tabella del database (INSERT).

    Args:
        table: Nome della tabella
        data: Dizionario colonna→valore da inserire (es. {"title": "test", "status": "pending"})
    """
    from agent.database import db_insert as _fn
    return _fn(table, data)


def db_update(table: str, filters: dict, updates: dict) -> str:
    """Aggiorna righe esistenti in una tabella del database (UPDATE).

    Args:
        table: Nome della tabella
        filters: Condizioni WHERE — dizionario colonna→valore (es. {"id": 5})
        updates: Campi da aggiornare — dizionario colonna→nuovo_valore
    """
    from agent.database import db_update as _fn
    return _fn(table, filters, updates)


def db_delete(table: str, filters: dict) -> str:
    """Elimina righe da una tabella del database (DELETE). Richiede almeno un filtro.

    Args:
        table: Nome della tabella
        filters: Condizioni WHERE — dizionario colonna→valore (es. {"id": 3})
                 OBBLIGATORIO: almeno un filtro per sicurezza
    """
    from agent.database import db_delete as _fn
    return _fn(table, filters)


TOOL_SCHEMAS = [
    {
        "name": "search_web",
        "description": "Cerca informazioni sul web tramite DuckDuckGo.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "La query di ricerca"}
            },
            "required": ["query"],
        },
    },
    {
        "name": "browse_url",
        "description": "Apre un URL nel browser headless e restituisce il testo della pagina.",
        "input_schema": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "URL completo da visitare (incluso https://)"}
            },
            "required": ["url"],
        },
    },
    {
        "name": "write_memory",
        "description": "Salva informazioni importanti nella memoria persistente dell'agente tra sessioni.",
        "input_schema": {
            "type": "object",
            "properties": {
                "content": {"type": "string", "description": "Il contenuto da ricordare"}
            },
            "required": ["content"],
        },
    },
    {
        "name": "read_memory_tool",
        "description": "Legge la memoria persistente dell'agente.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "read_file",
        "description": "Legge il contenuto di un file locale.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Percorso del file (assoluto o con ~)"}
            },
            "required": ["path"],
        },
    },
    {
        "name": "write_file",
        "description": "Crea o sovrascrive un file locale con il contenuto fornito.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Percorso del file"},
                "content": {"type": "string", "description": "Contenuto da scrivere"},
            },
            "required": ["path", "content"],
        },
    },
    {
        "name": "list_directory",
        "description": "Elenca file e cartelle in una directory locale.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Percorso della directory (default: .)"}
            },
            "required": [],
        },
    },
    # Browser / Applications
    {
        "name": "browser_fill_application",
        "description": "Compila automaticamente un form di job application (Ashby, Greenhouse, Lever, ecc.) con i dati del profilo di Francesco e allega il CV. Restituisce screenshot per revisione.",
        "input_schema": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "URL del form di application"},
                "cv_type": {"type": "string", "description": "'sales' per ruoli commerciali, 'product' per ruoli tech/product/AI"},
                "how_did_you_hear": {"type": "string", "description": "Risposta al radio 'Come hai trovato il lavoro?' (es. 'LinkedIn - post or content')"},
                "extra_fields": {"type": "string", "description": "Campi aggiuntivi: 'campo=valore,campo2=valore2' (opzionale)"},
            },
            "required": ["url"],
        },
    },
    {
        "name": "browser_screenshot",
        "description": "Scatta uno screenshot di una pagina web e lo mostra all'utente.",
        "input_schema": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "URL da fotografare"}
            },
            "required": ["url"],
        },
    },
    # Gmail
    {
        "name": "gmail_get_today_emails",
        "description": "Recupera tutte le email ricevute oggi nella inbox di Gmail.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "gmail_search",
        "description": "Cerca email o contatti in Gmail tramite query.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Query Gmail (es. 'from:mario@example.com', 'subject:fattura', 'mario rossi')"}
            },
            "required": ["query"],
        },
    },
    {
        "name": "gmail_read_email",
        "description": "Legge il testo completo di un'email dato il suo ID.",
        "input_schema": {
            "type": "object",
            "properties": {
                "message_id": {"type": "string", "description": "ID del messaggio Gmail"}
            },
            "required": ["message_id"],
        },
    },
    {
        "name": "gmail_create_draft",
        "description": "Crea una bozza email in Gmail e la mostra per revisione prima dell'invio.",
        "input_schema": {
            "type": "object",
            "properties": {
                "to": {"type": "string", "description": "Indirizzo email destinatario"},
                "subject": {"type": "string", "description": "Oggetto dell'email"},
                "body": {"type": "string", "description": "Corpo dell'email"},
            },
            "required": ["to", "subject", "body"],
        },
    },
    {
        "name": "gmail_send_draft",
        "description": "Invia una bozza Gmail esistente. Usare SOLO dopo conferma esplicita dell'utente.",
        "input_schema": {
            "type": "object",
            "properties": {
                "draft_id": {"type": "string", "description": "ID della bozza da inviare"}
            },
            "required": ["draft_id"],
        },
    },
    # Calendar / Tasks
    {
        "name": "calendar_get_events",
        "description": "Recupera gli eventi del Google Calendar per una data specifica.",
        "input_schema": {
            "type": "object",
            "properties": {
                "date_str": {"type": "string", "description": "Data: YYYY-MM-DD oppure 'oggi', 'domani', 'questa settimana'"}
            },
            "required": [],
        },
    },
    {
        "name": "calendar_add_event",
        "description": "Aggiunge un evento o task al Google Calendar. Funziona sia per appuntamenti con orario che per eventi tutto il giorno. Se non specifichi start_time, crea un evento tutto il giorno.",
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Titolo dell'evento/task"},
                "date_str": {"type": "string", "description": "Data YYYY-MM-DD"},
                "start_time": {"type": "string", "description": "Orario inizio HH:MM (ometti per tutto il giorno)"},
                "end_time": {"type": "string", "description": "Orario fine HH:MM (ometti per durata 1h default)"},
                "description": {"type": "string", "description": "Descrizione opzionale"},
                "location": {"type": "string", "description": "Luogo opzionale"},
                "recurrence": {"type": "string", "description": "'daily', 'weekly', 'monthly', o RRULE (lascia vuoto se non ricorrente)"},
            },
            "required": ["title", "date_str"],
        },
    },
    {
        "name": "calendar_delete_event",
        "description": "Cancella un evento dal Google Calendar. Prima usa calendar_get_events per trovare l'id dell'evento da cancellare.",
        "input_schema": {
            "type": "object",
            "properties": {
                "event_id": {"type": "string", "description": "ID dell'evento (campo 'id' da calendar_get_events)"},
            },
            "required": ["event_id"],
        },
    },
    {
        "name": "calendar_mark_done",
        "description": "Segna un evento come FATTO: diventa verde sul Calendar, salvato nel DB. Usa quando Francesco dice 'ho fatto X', 'fatto', 'completato'.",
        "input_schema": {
            "type": "object",
            "properties": {
                "event_id": {"type": "string", "description": "ID dell'evento (da calendar_get_events, campo 'id')"},
            },
            "required": ["event_id"],
        },
    },
    {
        "name": "calendar_mark_not_done",
        "description": "Segna un evento come NON FATTO: diventa rosso sul Calendar, salvato nel DB. Usa quando Francesco dice 'non ho fatto X', 'saltato', 'non ce l\\'ho fatta'.",
        "input_schema": {
            "type": "object",
            "properties": {
                "event_id": {"type": "string", "description": "ID dell'evento (da calendar_get_events, campo 'id')"},
            },
            "required": ["event_id"],
        },
    },
    {
        "name": "calendar_reschedule_event",
        "description": "Rimanda un evento a una nuova data/ora: diventa viola e si sposta sul Calendar, salvato nel DB. Usa quando Francesco dice 'rimanda X a domani', 'sposta X a venerdì alle 10'.",
        "input_schema": {
            "type": "object",
            "properties": {
                "event_id": {"type": "string", "description": "ID dell'evento (da calendar_get_events)"},
                "new_date": {"type": "string", "description": "Nuova data YYYY-MM-DD"},
                "new_time": {"type": "string", "description": "Nuovo orario HH:MM (opzionale)"},
            },
            "required": ["event_id", "new_date"],
        },
    },
    # Phone call tools
    {
        "name": "call_make",
        "description": "Esegui una telefonata reale verso qualsiasi numero (inclusi numeri italiani +39 mobile e fissi). Vapi.ai chiama fisicamente il numero, un AI parla in italiano seguendo le istruzioni e porta a termine il compito (prenotazione, informazioni, ecc.). Usare OBBLIGATORIAMENTE quando Francesco dice 'chiama', 'telefona', 'prenota per telefono'. NON dire mai che non puoi chiamare numeri italiani — funziona perfettamente.",
        "input_schema": {
            "type": "object",
            "properties": {
                "phone_number": {"type": "string", "description": "Numero da chiamare (es. 06-1234567 o +390612345678)"},
                "task": {"type": "string", "description": "Istruzione completa in italiano: cosa fare, nome Francesco, dettagli specifici (data/ora/persone), alternative se non disponibile"},
                "max_duration": {"type": "integer", "description": "Durata massima in minuti (default 5, max 10)"},
            },
            "required": ["phone_number", "task"],
        },
    },
    {
        "name": "call_check_status",
        "description": "Controlla lo stato e la trascrizione di una chiamata già avviata. Usare quando Francesco chiede 'com'è andata la chiamata?' o 'hai prenotato?'.",
        "input_schema": {
            "type": "object",
            "properties": {
                "call_id": {"type": "string", "description": "ID della chiamata (restituito da call_make)"},
            },
            "required": ["call_id"],
        },
    },
    {
        "name": "call_list_recent",
        "description": "Mostra le ultime 10 chiamate effettuate con stato e durata.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    # Wedding tools
    {
        "name": "wedding_scrape_contact",
        "description": "Visita un sito web di professionista wedding e cerca email e info di contatto.",
        "input_schema": {"type": "object", "properties": {"url": {"type": "string"}}, "required": ["url"]},
    },
    {
        "name": "wedding_add_contact",
        "description": "Aggiunge un professionista wedding al tracker (wedding planner, fotografo, catering, ecc.).",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Nome del professionista/azienda"},
                "category": {"type": "string", "description": "wedding_planner | fotografo | catering | videomaker | floral_designer | agenzia | altro"},
                "email": {"type": "string", "description": "Email (opzionale)"},
                "website": {"type": "string", "description": "URL sito (opzionale)"},
                "location": {"type": "string", "description": "Zona (default: Umbria)"},
                "notes": {"type": "string", "description": "Note (opzionale)"},
            },
            "required": ["name", "category"],
        },
    },
    {
        "name": "wedding_list_contacts",
        "description": "Mostra i contatti wedding con filtri per stato o categoria.",
        "input_schema": {
            "type": "object",
            "properties": {
                "status": {"type": "string", "description": "new | contacted | replied | negotiating | archived"},
                "category": {"type": "string", "description": "Filtra per categoria (opzionale)"},
            },
            "required": [],
        },
    },
    {
        "name": "wedding_update_contact",
        "description": "Aggiorna stato, note o email di un contatto wedding.",
        "input_schema": {
            "type": "object",
            "properties": {
                "contact_id": {"type": "integer", "description": "ID contatto (da wedding_list_contacts)"},
                "status": {"type": "string", "description": "new | contacted | replied | negotiating | archived"},
                "notes": {"type": "string", "description": "Note aggiuntive"},
                "email": {"type": "string", "description": "Aggiorna email"},
            },
            "required": ["contact_id"],
        },
    },
    {
        "name": "wedding_get_contact",
        "description": "Legge il profilo completo di un contatto wedding. Usare prima di scrivere un'email personalizzata.",
        "input_schema": {
            "type": "object",
            "properties": {"contact_id": {"type": "integer", "description": "ID del contatto"}},
            "required": ["contact_id"],
        },
    },
    # Diet tools
    {
        "name": "diet_save_shopping",
        "description": "Salva la lista della spesa settimanale. Usare la domenica quando Francesco dice cosa ha comprato. La lista viene usata per generare le proposte pasto personalizzate della settimana.",
        "input_schema": {
            "type": "object",
            "properties": {
                "items_text": {"type": "string", "description": "Lista ingredienti acquistati (testo libero, uno per riga o separati da virgola)"},
                "notes": {"type": "string", "description": "Note aggiuntive opzionali"},
            },
            "required": ["items_text"],
        },
    },
    {
        "name": "diet_get_shopping",
        "description": "Legge la lista della spesa registrata questa settimana. Usare quando si vuole sapere cosa c'è disponibile o prima di suggerire un pasto.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "diet_update_base",
        "description": "Aggiorna lo schema base della dieta (usare solo quando Francesco vuole modificare il piano alimentare, non per la spesa settimanale).",
        "input_schema": {
            "type": "object",
            "properties": {
                "content": {"type": "string", "description": "Nuovo schema dieta completo"}
            },
            "required": ["content"],
        },
    },
    # Database tools
    {
        "name": "db_job_applications_list",
        "description": "Mostra tutte le job application inviate tramite il bot con stato attuale.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "db_job_application_update",
        "description": "Aggiorna lo stato di una job application (dopo colloquio, risposta, ecc.).",
        "input_schema": {
            "type": "object",
            "properties": {
                "app_id": {"type": "integer", "description": "ID dell'application (da db_job_applications_list)"},
                "status": {"type": "string", "description": "'applied', 'interviewing', 'offer', 'rejected', 'withdrawn'"},
                "notes": {"type": "string", "description": "Note aggiuntive opzionali"},
            },
            "required": ["app_id", "status"],
        },
    },
    # CRUD generici
    {
        "name": "db_select",
        "description": "Legge righe da una qualsiasi tabella del database (SELECT). Usa per ispezionare dati, verificare record, trovare ID. Tabelle disponibili: agent_memory, user_tasks, wedding_contacts, job_applications, expense_reports, conversation_messages.",
        "input_schema": {
            "type": "object",
            "properties": {
                "table": {"type": "string", "description": "Nome della tabella"},
                "filters": {
                    "type": "object",
                    "description": "Filtri opzionali colonna→valore (es. {\"id\": 3, \"status\": \"done\"})",
                    "additionalProperties": True,
                },
            },
            "required": ["table"],
        },
    },
    {
        "name": "db_insert",
        "description": "Inserisce una nuova riga in una tabella del database (INSERT).",
        "input_schema": {
            "type": "object",
            "properties": {
                "table": {"type": "string", "description": "Nome della tabella"},
                "data": {
                    "type": "object",
                    "description": "Dati da inserire come dizionario colonna→valore",
                    "additionalProperties": True,
                },
            },
            "required": ["table", "data"],
        },
    },
    {
        "name": "db_update",
        "description": "Aggiorna righe esistenti in una tabella del database (UPDATE). Specifica i filtri per identificare le righe e i campi da modificare.",
        "input_schema": {
            "type": "object",
            "properties": {
                "table": {"type": "string", "description": "Nome della tabella"},
                "filters": {
                    "type": "object",
                    "description": "Condizioni WHERE: colonna→valore (es. {\"id\": 5})",
                    "additionalProperties": True,
                },
                "updates": {
                    "type": "object",
                    "description": "Campi da aggiornare: colonna→nuovo_valore",
                    "additionalProperties": True,
                },
            },
            "required": ["table", "filters", "updates"],
        },
    },
    {
        "name": "db_delete",
        "description": "Elimina righe da una tabella del database (DELETE). RICHIEDE almeno un filtro per sicurezza — non è possibile cancellare senza specificare quale riga. Usa per: cancellare spesa test, rimuovere record duplicati, pulire dati obsoleti.",
        "input_schema": {
            "type": "object",
            "properties": {
                "table": {"type": "string", "description": "Nome della tabella"},
                "filters": {
                    "type": "object",
                    "description": "Condizioni WHERE obbligatorie: colonna→valore (es. {\"id\": 3})",
                    "additionalProperties": True,
                },
            },
            "required": ["table", "filters"],
        },
    },
]

TOOL_MAP = {
    "search_web": search_web,
    "browse_url": browse_url,
    "write_memory": write_memory,
    "read_memory_tool": read_memory_tool,
    "read_file": read_file,
    "write_file": write_file,
    "list_directory": list_directory,
    "gmail_get_today_emails": gmail_get_today_emails,
    "gmail_search": gmail_search,
    "gmail_read_email": gmail_read_email,
    "gmail_create_draft": gmail_create_draft,
    "gmail_send_draft": gmail_send_draft,
    "calendar_get_events": calendar_get_events,
    "calendar_add_event": calendar_add_event,
    "calendar_delete_event": calendar_delete_event,
    "calendar_mark_done": calendar_mark_done,
    "calendar_mark_not_done": calendar_mark_not_done,
    "calendar_reschedule_event": calendar_reschedule_event,
    "browser_fill_application": browser_fill_application,
    "browser_screenshot": browser_screenshot,
    "db_job_applications_list": db_job_applications_list,
    "db_job_application_update": db_job_application_update,
    # Phone calls
    "call_make": call_make,
    "call_check_status": call_check_status,
    "call_list_recent": call_list_recent,
    # Diet
    "diet_save_shopping": diet_save_shopping,
    "diet_get_shopping": diet_get_shopping,
    "diet_update_base": diet_update_base,
    # Wedding
    "wedding_scrape_contact": wedding_scrape_contact,
    "wedding_add_contact": wedding_add_contact,
    "wedding_list_contacts": wedding_list_contacts,
    "wedding_update_contact": wedding_update_contact,
    "wedding_get_contact": wedding_get_contact,
    # CRUD generici
    "db_select": db_select,
    "db_insert": db_insert,
    "db_update": db_update,
    "db_delete": db_delete,
}
