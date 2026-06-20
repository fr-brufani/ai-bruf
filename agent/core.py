import os
import logging
import anthropic
from pathlib import Path
from agent.tools import TOOL_SCHEMAS, TOOL_MAP
from agent.memory import read_memory

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).parent.parent
MODEL = "claude-haiku-4-5-20251001"
MAX_TOKENS = 4096

_client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
_messages: list = []

# ── Routing keywords per workstation selettiva ────────────────────────────────
# Ordine: più specifici prima per evitare false positive
_WS_KEYWORDS = {
    "dev":          ["modifica il bot", "aggiungi un comando", "aggiungi una funzione",
                     "aggiungi un tool", "aggiungi la possibilità", "migliora il bot",
                     "cambia il bot", "il bot deve", "fai in modo che tu", "voglio che tu possa",
                     "crea un comando", "sviluppa", "modifica te stesso", "modifica il tuo codice"],
    "calls":        ["chiama", "telefona", "chiamata", "telefonata", "prenota per telefono",
                     "contatta telefonicamente", "fai una chiamata"],
    "diet":         ["cosa mangio", "mangio", "dieta", "colazione", "pranzo", "cena",
                     "merenda", "ingredienti", "pasto", "calorie", "macro", "spesa"],
    "email":        ["email", "gmail", "posta", "inbox", "mittente", "newsletter"],
    "finance":      ["revolut", "estratto conto", "budget", "finanze", "spese mensili", "transazion"],
    "wedding":      ["wedding", "matrimonio", "fotografo", "catering", "nozze"],
    "calendar":     ["calendario", "evento", "appuntamento", "palestra", "allenamento",
                     "riunione", "meeting", "aggiungi evento", "segna"],
    "applications": ["candidatura", "job application", "compila il form"],
    "research":     ["cerca online", "ricerca web", "notizie di"],
    "tasks":        ["task", "attività da fare"],
    "files":        ["leggi il file", "scrivi il file", "apri documento"],
}

_ALL_WORKSTATIONS = ("email", "research", "calendar", "files", "applications",
                     "finance", "wedding", "tasks", "diet", "calls", "dev")


def _detect_workstation(message: str):
    """Routing leggero: restituisce il nome della workstation rilevante, o None."""
    msg = message.lower()
    for ws, keywords in _WS_KEYWORDS.items():
        if any(kw in msg for kw in keywords):
            return ws
    return None


def _build_system_prompt(user_message: str = "") -> str:
    from datetime import datetime
    from zoneinfo import ZoneInfo
    now = datetime.now(ZoneInfo("Europe/Rome"))
    date_ctx = (
        f"# DATA E ORA ATTUALE\n"
        f"Oggi è {now.strftime('%A %d %B %Y')}, ore {now.strftime('%H:%M')} (Europe/Rome).\n"
        f"Formato date: YYYY-MM-DD (es. {now.strftime('%Y-%m-%d')}).\n"
    )

    constitution = (BASE_DIR / "CLAUDE.md").read_text(encoding="utf-8")

    memory = read_memory()
    memory_section = f"\n\n# MEMORIA PERSISTENTE\n{memory}" if memory.strip() else ""

    # Carica solo la workstation rilevante; fallback a tutte se ambiguo
    detected = _detect_workstation(user_message) if user_message else None
    if detected:
        ws_list = (detected,)
        logger.debug(f"Workstation rilevata: {detected}")
    else:
        ws_list = _ALL_WORKSTATIONS

    ws_sections = []
    for ws in ws_list:
        ws_file = BASE_DIR / "workstations" / ws / "claude.md"
        if ws_file.exists():
            ws_sections.append(f"## Workstation: {ws.upper()}\n{ws_file.read_text(encoding='utf-8')}")
    ws_block = "\n\n# CONTESTI WORKSTATION\n" + "\n\n".join(ws_sections) if ws_sections else ""

    return date_ctx + "\n" + constitution + memory_section + ws_block


def _load_history_from_db():
    """Carica la cronologia da Supabase all'avvio se _messages è vuoto."""
    global _messages
    try:
        from agent.database import messages_load
        loaded = messages_load(limit=10)
        if loaded:
            _messages = loaded
            logger.info(f"Cronologia caricata dal DB: {len(loaded)} messaggi")
    except Exception as e:
        logger.warning(f"Impossibile caricare cronologia dal DB: {e}")


def reset_chat():
    global _messages
    _messages = []
    try:
        from agent.database import messages_clear
        messages_clear()
    except Exception:
        pass
    logger.info("Conversazione resettata")


def _trim_history_to_clean_state():
    """Rimuove dalla history i messaggi dalla fine fino all'ultimo user-text pulito.
    Evita che tool_use orfani (senza tool_result) corrompano la conversazione successiva.
    """
    global _messages
    while _messages:
        last = _messages[-1]
        # Messaggio utente testuale = stato pulito, lo rimuoviamo e ci fermiamo
        if last["role"] == "user" and isinstance(last.get("content"), str):
            _messages.pop()
            return
        # Tutto il resto (tool_use, tool_result, assistant parziali) va rimosso
        _messages.pop()


def process_message(user_message: str) -> str:
    global _messages

    # Carica cronologia dal DB se la sessione è appena partita
    if not _messages:
        _load_history_from_db()

    detected_ws = _detect_workstation(user_message)
    system_prompt = _build_system_prompt(user_message)
    _messages.append({"role": "user", "content": user_message})

    # Per le chiamate telefoniche forza l'uso di call_make:
    # il modello tende a rifiutarsi per training ("gli AI non possono telefonare")
    # ma con tool_choice={"type":"tool","name":"call_make"} non può sottrarsi.
    first_call_kwargs = {}
    if detected_ws == "calls":
        first_call_kwargs["tool_choice"] = {"type": "tool", "name": "call_make"}

    try:
        response = _client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=system_prompt,
            tools=TOOL_SCHEMAS,
            messages=_messages,
            **first_call_kwargs,
        )

        # Agentic loop — handle tool calls
        for _ in range(10):
            if response.stop_reason != "tool_use":
                break

            _messages.append({"role": "assistant", "content": response.content})

            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    func = TOOL_MAP.get(block.name)
                    try:
                        result = func(**block.input) if func else f"Tool '{block.name}' non trovato"
                    except Exception as e:
                        result = f"Errore nell'esecuzione di {block.name}: {e}"
                    logger.info(f"Tool {block.name} → {str(result)[:100]}")
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": str(result),
                    })

            _messages.append({"role": "user", "content": tool_results})

            response = _client.messages.create(
                model=MODEL,
                max_tokens=MAX_TOKENS,
                system=system_prompt,
                tools=TOOL_SCHEMAS,
                messages=_messages,
            )

        # Save final response to history
        _messages.append({"role": "assistant", "content": response.content})

        text = "".join(block.text for block in response.content if hasattr(block, "text"))

        # Persisti lo scambio pulito su Supabase (solo testo, no tool_use)
        if text:
            try:
                from agent.database import messages_append
                messages_append("user", user_message)
                messages_append("assistant", text)
            except Exception:
                pass

        return text or "(risposta vuota)"

    except Exception as e:
        logger.error(f"Errore agent: {e}")
        _trim_history_to_clean_state()
        return f"Errore: {e}"
