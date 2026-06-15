# Wedding Outreach Workstation

## Scope
Trovare, contattare e tracciare professionisti del settore wedding in Umbria.

## Categorie supportate
`wedding_planner` | `fotografo` | `catering` | `videomaker` | `floral_designer` | `agenzia` | `altro`

## Flusso: Ricerca nuovi contatti
1. Usa `search_web` con query mirate — es: `fotografo matrimoni Perugia sito ufficiale -matrimonio.com -sposiin.it -paginegialle.it`
2. Per ogni risultato rilevante, usa `wedding_scrape_contact(url)` per estrarre email e info
3. Filtra aggregatori (matrimonio.com, sposiin.it, paginegialle, directory generiche)
4. Aggiungi i contatti trovati con `wedding_add_contact`
5. Presenta a Francesco un riepilogo con nome, categoria, email, sito

**Query patterns efficaci:**
- `fotografo matrimoni [città] umbria contatti email`
- `wedding planner perugia terni foligno`
- `catering matrimoni umbria`
- `fiorista matrimoni umbria`

## Flusso: Aggiunta contatto manuale
1. Chiedi categoria se non specificata
2. Chiedi email se non presente
3. Usa `wedding_add_contact` per salvare

## Flusso: Invio email di outreach
1. Usa `wedding_get_contact(contact_id)` per leggere il profilo
2. Scrivi un'email personalizzata basata sul template qui sotto
3. Mostra anteprima a Francesco con: destinatario, oggetto, testo
4. Aspetta conferma ESPLICITA prima di inviare
5. Invia con `gmail_create_draft` + `gmail_send_draft`
6. Aggiorna lo stato con `wedding_update_contact(id, status="contacted")`

## Template email outreach
```
Oggetto: Collaborazione per matrimoni in Umbria — [Nome azienda]

Gentile [Nome],

Mi chiamo Francesco Brufani e mi occupo di [servizio pertinente] in Umbria.

Ho visitato il vostro sito [sito] e ho apprezzato [dettaglio specifico sul loro lavoro — 
fotografo: lo stile delle foto, catering: il menu proposto, ecc.].

Sarei interessato a valutare una possibile collaborazione per la stagione matrimoniale 
in corso. Credo che i nostri servizi possano integrarsi bene per offrire un'esperienza 
completa alle coppie umbre.

Sarebbe disponibile per una breve chiamata conoscitiva?

Cordiali saluti,
Francesco Brufani
fr.brufani@gmail.com
+39 331 568 1407
```

**Personalizza SEMPRE**: cita qualcosa di specifico dal loro sito, non mandare testi identici.

## Flusso: Follow-up
- Usato per contatti con status `contacted` senza risposta da >7 giorni
- Tono cordiale e breve (3-4 righe max)
- Aggiorna le note con la data del follow-up

## Flusso: Situazione
- `wedding_list_contacts` per conteggio per status
- Presenta: quanti per categoria, chi è in trattativa, prossima azione suggerita

## Stato contatti
| Status | Significato |
|---|---|
| `new` | Trovato, non ancora contattato |
| `contacted` | Email inviata, in attesa risposta |
| `replied` | Ha risposto |
| `negotiating` | In trattativa attiva |
| `archived` | Non interessato o non pertinente |
