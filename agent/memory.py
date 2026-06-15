from pathlib import Path
from datetime import datetime

MEMORY_FILE = Path(__file__).parent.parent / "memory.md"


def read_memory() -> str:
    # Prova prima Supabase, fallback su file locale
    try:
        from agent.database import memory_read
        db_content = memory_read()
        if db_content:
            return db_content
    except Exception:
        pass
    if MEMORY_FILE.exists():
        return MEMORY_FILE.read_text(encoding="utf-8")
    return ""


def write_to_memory(content: str) -> str:
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    entry = f"\n## [{timestamp}]\n{content}\n"

    # Leggi memoria corrente, aggiungi, riscrivi
    current = read_memory()
    new_content = current + entry

    # Salva su Supabase
    try:
        from agent.database import memory_write
        result = memory_write(new_content)
    except Exception:
        result = None

    # Salva sempre anche su file locale (backup)
    with open(MEMORY_FILE, "a", encoding="utf-8") as f:
        f.write(entry)

    return result or f"Memoria aggiornata ({len(content)} caratteri)"
