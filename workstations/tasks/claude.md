# Calendar / Task Workstation

## Sistema
Task e attività = **eventi Google Calendar**.
Il colore dell'evento indica lo stato. Il DB registra lo storico.

| Colore | Significato | Tool |
|---|---|---|
| Default | In programma / da fare | — |
| 🟢 Verde | Fatto ✅ | `calendar_mark_done` |
| 🔴 Rosso | Non fatto ❌ | `calendar_mark_not_done` |
| 🟣 Viola | Rimandato 🔄 | `calendar_reschedule_event` |

## Aggiungere un evento/task → `calendar_add_event`

| Richiesta | Cosa fare |
|---|---|
| "aggiungi palestra domani alle 7" | `calendar_add_event("Palestra", domani, "07:00")` |
| "riunione venerdì dalle 10 alle 11" | `calendar_add_event("Riunione", data, "10:00", "11:00")` |
| "ricordami di chiamare il commercialista" | `calendar_add_event("Chiama commercialista", oggi)` — tutto il giorno |
| "ogni lunedì call alle 9" | `calendar_add_event(..., recurrence="weekly")` |

- Senza orario → evento **tutto il giorno**
- Solo start_time → durata **1 ora** default

## Vedere il programma → `calendar_get_events`
- "cosa ho oggi/domani/questa settimana" → `calendar_get_events(date_str)`
- L'output include il campo `id` → serve per mark_done/not_done/reschedule/delete

## Segnare come fatto → `calendar_mark_done`
- "ho fatto palestra" → `calendar_get_events` se non conosci l'id → `calendar_mark_done(event_id)`
- Diventa verde sul Calendar + salvato nel DB

## Segnare come non fatto → `calendar_mark_not_done`
- "non ho fatto yoga", "saltato" → `calendar_mark_not_done(event_id)`
- Diventa rosso + salvato nel DB

## Rimandare → `calendar_reschedule_event`
- "rimanda palestra a domani", "sposta call a venerdì alle 10" → `calendar_reschedule_event(event_id, new_date, new_time)`
- Diventa viola + l'evento si sposta + salvato nel DB

## Cancellare → `calendar_delete_event`
- "cancella palestra di domani" → `calendar_get_events("domani")` → trova id → `calendar_delete_event(id)`

## Modificare orario (senza cambiare stato)
Non c'è un tool di edit diretto per l'orario: cancella e ricrea.
1. `calendar_get_events` → trova evento
2. `calendar_delete_event(id)`
3. `calendar_add_event(...)` con nuovo orario

## Flusso quando l'utente non sa l'id
Chiama sempre prima `calendar_get_events` per la data giusta, poi esegui l'azione.
Esempio: "ho fatto palestra di stamattina" → `calendar_get_events("oggi")` → trova Palestra → `calendar_mark_done(id)`

## Scheduler automatico
- **08:00** — Briefing: programma del giorno
- **10 min prima** di ogni evento con orario — Reminder automatico
- **22:00** — Mostra eventi di domani, chiede cosa aggiungere
- **22:30** — Recap: fatto ✅ / non fatto ❌ / rimandato 🔄 / non aggiornato ⏳
