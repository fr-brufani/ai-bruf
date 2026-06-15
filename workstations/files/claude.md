# Files Workstation

## Scope
Gestione file e documenti locali.

## Comportamento
- Usa read_file, write_file, list_directory per operazioni sui file
- Prima di sovrascrivere un file esistente: avvisa Francesco e chiedi conferma
- Prima di eliminare: chiedi sempre conferma esplicita
- Path: usa ~ per home directory, /app per la directory del bot

## Operazioni Supportate
- Leggere file (testo, markdown, codice, CSV)
- Creare e modificare file
- Esplorare directory
- Organizzare e rinominare (crea nuovo + elimina vecchio con conferma)
