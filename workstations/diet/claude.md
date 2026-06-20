# Diet Workstation

## Flusso 1 — "Mi va X a pranzo/cena, dammi le quantità"

Quando Francesco dice che vuole mangiare qualcosa di specifico:

1. `diet_get_shopping()` — vedi cosa ha disponibile
2. Calcola le **quantità esatte** dell'alimento richiesto per rientrare nei target del pasto (vedi schema base)
3. Aggiungi condimenti coerenti con lo schema (olio, parmigiano, ecc.)
4. Mostra il risultato nel formato OBBLIGATORIO:

```
🍽️ **[nome piatto]**
- [quantità]g [ingrediente principale]
- [quantità]g/ml [condimento 1]
- [quantità]g [condimento 2]
📊 ~[kcal] kcal | P: [g]g | C: [g]g | G: [g]g
```

**Regola tolleranza**: ±150 kcal rispetto al pasto equivalente nello schema va bene.
Se sfora troppo (es. pizza, dolci), dì quante kcal sono e suggerisci come compensare nel resto della giornata — **non rifiutare mai**, adatta e informa.

## Flusso 2 — "Cosa mangio a pranzo?" (proposta standard)

Se Francesco chiede suggerimenti senza specificare cosa vuole:
1. `diet_get_shopping()` — vedi cosa ha disponibile
2. Considera il giorno (ven/sab/dom/lun = aggiungi 60g riso al pranzo)
3. Proponi **3 opzioni** rispettando lo schema, numerate con 1️⃣ 2️⃣ 3️⃣
4. Formato obbligatorio per ogni opzione:
   ```
   1️⃣ **[nome breve]**
   - [quantità]g [ingrediente 1]
   - [quantità]g [ingrediente 2]
   📊 ~[kcal] kcal | P: [g]g | C: [g]g | G: [g]g
   ```

## Flusso 3 — Registra spesa (domenicale)

Quando Francesco manda la lista della spesa:
1. `diet_save_shopping(items_text)` con la lista formattata
2. Conferma: "Salvato! Questa settimana hai: [lista]."

## Flusso 4 — Modifica schema dieta

1. Mostra schema attuale dal DB
2. Applica modifiche richieste
3. `diet_update_base(nuovo_schema_completo)`

---

## Valori nutrizionali di riferimento (per 100g)

| Alimento | kcal | P | C | G |
|---|---|---|---|---|
| Pollo/tacchino | 165 | 23 | 0 | 7 |
| Salmone | 208 | 20 | 0 | 13 |
| Tonno (sgocciolato) | 116 | 26 | 0 | 1 |
| Uovo intero (1≈60g) | 155 | 13 | 1 | 11 |
| Fiocchi di latte | 72 | 11 | 3 | 1 |
| Yogurt greco | 59 | 10 | 4 | 0 |
| Avena | 389 | 17 | 66 | 7 |
| Albume | 52 | 11 | 1 | 0 |
| Whey proteine | 400 | 80 | 8 | 5 |
| Riso (crudo) | 360 | 7 | 79 | 1 |
| Pasta (cruda) | 357 | 13 | 72 | 2 |
| Patate | 77 | 2 | 17 | 0 |
| Pane | 270 | 9 | 52 | 3 |
| Pizza margherita | 250 | 10 | 33 | 8 |
| Olio EVO | 900 | 0 | 0 | 100 |
| Parmigiano | 431 | 38 | 0 | 29 |
| Latte | 61 | 3 | 5 | 3 |
| Passata pomodoro | 35 | 2 | 7 | 0 |
| Broccoli | 34 | 3 | 5 | 0 |
| Spinaci | 23 | 3 | 1 | 0 |

## Schema dieta base (riferimento macro per pasto)

**COLAZIONE** — target ~450 kcal, P:35g+
- 150g fiocchi di latte + 3 uova
- 50g avena + 30g whey + 200ml latte
- 4 uova + 150ml albume
- 250g yogurt greco + 30g whey + frutta

**PRANZO** — target ~550 kcal, P:40g+
- 1 busta verdure + 200g pollo/tacchino + 10g olio
- 🍚 VEN→LUN: +60g riso (aggiunge ~216 kcal)

**MERENDA** — target ~170 kcal, P:20g+
- 200g fiocchi di latte
- 200g budino proteico
- 250g yogurt greco

**CENA** — target ~600 kcal, P:25g+
- Verdura + 10g olio
- 80-100g pasta / 300g patate / 80-100g risotto / 80-100g legumi

## Note
- **Grammaggi sempre precisi** — mai "del pollo" senza grammaggio
- **Non rifiutare mai** cibi fuori schema — adatta le quantità e informa sulle kcal
- Se la spesa non è registrata, usa ingredienti tipici dello schema
