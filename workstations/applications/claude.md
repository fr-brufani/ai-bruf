# Applications Workstation

## Scope
Compilazione autonoma di form online: job applications, registrazioni, iscrizioni.

## Risorse disponibili
- Profilo completo: `00_resources/profile.md` — LEGGILO SEMPRE prima di compilare
- CV Sales (EN): `00_resources/CV_Francesco_Brufani_sales_eng.pdf`
- Altri CV: verranno aggiunti (chiedi a Francesco quale usare se non è chiaro)

## Flusso job application

1. **Leggi il profilo** con `read_file("00_resources/profile.md")`
2. **Compila il form** con `browser_fill_application(url=URL, cv_type="sales"|"product")` — questo apre il browser, compila tutti i campi e restituisce uno screenshot
3. Lo screenshot viene inviato a Francesco per revisione visiva
4. **Aspetta conferma esplicita** prima di procedere all'invio (Submit richiede click umano per reCAPTCHA)
5. Se manca un'informazione non presente nel profilo: chiedi a Francesco

**NON usare `browse_url` per leggere il form prima di compilare** — `browser_fill_application` gestisce tutto internamente.

## Campi standard — mapping
| Campo form | Valore |
|---|---|
| First name | Francesco |
| Last name | Brufani |
| Email | fr.brufani@gmail.com |
| Phone | +39 3315681407 |
| Address / City | Perugia, Italy |
| Date of birth | 15/08/1998 |
| Nationality | Italian |
| Degree | Bachelor's in Economics and Finance |
| University | Università Bocconi |
| Current role | Account Manager at Bizaway |

## Upload CV
- Per upload file: usa il PDF nella cartella `00_resources/`
- Se serve versione italiana o per ruolo diverso: chiedi a Francesco

## Cosa NON fare
- Non inviare mai senza conferma esplicita
- Non inventare informazioni non presenti nel profilo
- Non rispondere a domande salariali senza chiedere a Francesco prima
