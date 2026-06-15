# Finance Workstation

## Scope
Analisi estratti conto Revolut e spese personali mensili.

## Formato CSV Revolut
Colonne standard dell'export Revolut:
`Type, Product, Started Date, Completed Date, Description, Amount, Fee, Currency, State, Balance`

Regole di parsing:
- **Amount negativo** = spesa; **Amount positivo** = entrata/ricarica
- Considera solo righe con `State = COMPLETED`
- Escludi righe con Amount > 0 dalle spese (a meno che non sia richiesto esplicitamente)
- La data da usare è `Completed Date`

## Analisi standard (falla sempre, in questo ordine)

1. **Totale speso** nel periodo (somma amount negativi)
2. **Breakdown per categoria** — raggruppa le Description in macro-categorie:
   - 🛒 Spesa/Supermercato (Esselunga, Conad, Carrefour, Lidl, ecc.)
   - 🍕 Ristoranti/Bar/Food delivery (Glovo, Deliveroo, Just Eat, ecc.)
   - 🚗 Trasporti (Trenitalia, Italo, Uber, Bolt, benzina, parcheggio)
   - 🏠 Casa/Bollette (luce, gas, affitto, internet)
   - 🎬 Abbonamenti (Netflix, Spotify, Amazon Prime, ecc.)
   - 🛍️ Shopping (Amazon, Zara, ecc.)
   - 💊 Salute/Farmacia
   - 💪 Sport/Palestra
   - ✈️ Viaggi/Hotel
   - 💼 Lavoro/Professionale
   - ❓ Altro
3. **Top 10 merchant** per importo totale speso
4. **Media giornaliera di spesa**
5. **Transazioni anomale** — spese singole > €100

## Output format
- Usa tabelle Markdown per i breakdown (| Categoria | Totale | % |)
- Evidenzia le anomalie con ⚠️
- Chiudi con 2-3 insight pratici (es. "Hai speso il 40% in ristoranti, potresti ridurre...")
- Sii conciso, no preamboli
