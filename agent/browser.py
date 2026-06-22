"""
Browser automation for form filling and job applications.
Returns paths to screenshots so the Telegram handler can send them as images.
"""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

RESOURCES_DIR = Path(__file__).parent.parent / "00_resources"
SCREENSHOT_DIR = Path("/tmp/agent_screenshots")
SCREENSHOT_DIR.mkdir(exist_ok=True)

# CV mapping by role type
CV_MAP = {
    "sales": "CV_Francesco_Brufani_sales_eng.pdf",
    "account": "CV_Francesco_Brufani_sales_eng.pdf",
    "bdr": "CV_Francesco_Brufani_sales_eng.pdf",
    "product": "CV_Francesco_Brufani_product_eng.pdf",
    "automation": "CV_Francesco_Brufani_product_eng.pdf",
    "tech": "CV_Francesco_Brufani_product_eng.pdf",
    "ai": "CV_Francesco_Brufani_product_eng.pdf",
    "default": "CV_Francesco_Brufani_sales_eng.pdf",
}


def _get_cv_path(role_hint: str = "") -> str:
    hint = role_hint.lower()
    for key, filename in CV_MAP.items():
        if key in hint:
            cv_path = RESOURCES_DIR / filename
            if cv_path.exists():
                return str(cv_path)
    return str(RESOURCES_DIR / CV_MAP["default"])


def browser_fill_application(
    url: str,
    cv_type: str = "sales",
    how_did_you_hear: str = "LinkedIn - post or content",
    extra_fields: str = "",
) -> str:
    """Compila automaticamente un form di job application tramite Browser Use su Browserbase
    (browser cloud, AI-driven: riconosce i campi da solo su qualsiasi ATS). Carica il CV,
    compila tutti i campi, e si FERMA prima dell'invio restituendo un link di revisione.

    Args:
        url: URL del form di application (Ashby, Greenhouse, Lever, Workday, ecc.)
        cv_type: Tipo di CV da allegare: 'sales' o 'product' (default: sales)
        how_did_you_hear: Come hai trovato il lavoro
        extra_fields: Istruzioni aggiuntive in linguaggio naturale per campi specifici
    """
    return (
        "Le candidature ora si compilano dal Mac con Claude Code (browser reale di Francesco, "
        "CV già pronti, conferma prima di inviare). Digli di aprire la chat sul Mac e mandare lì "
        f"il link dell'offerta. (URL ricevuto: {url})"
    )


def _browser_fill_application_via_bridge(
    url: str,
    cv_type: str = "sales",
    how_did_you_hear: str = "LinkedIn - post or content",
    extra_fields: str = "",
) -> str:
    """[DISATTIVATO] Versione che passava dalla VM/Browserbase. Tenuta come riferimento."""
    import os, requests
    bridge_url = os.environ.get("BRIDGE_URL", "")
    bridge_secret = os.environ.get("BRIDGE_SECRET", "")
    if not bridge_url:
        return "Errore: BRIDGE_URL non configurato."
    extra = []
    if how_did_you_hear:
        extra.append(f"Per 'How did you hear about us' usa: {how_did_you_hear}.")
    if extra_fields:
        extra.append(extra_fields)
    try:
        resp = requests.post(
            f"{bridge_url}/apply",
            json={"url": url, "cv_type": cv_type, "extra": " ".join(extra), "secret": bridge_secret},
            timeout=620,
        )
        resp.raise_for_status()
        data = resp.json()
        result = data.get("response", "(nessuna risposta)")
        session_id = data.get("session_id", "")
    except requests.exceptions.Timeout:
        return "Timeout: la compilazione del form ha superato il tempo massimo."
    except Exception as e:
        return f"Errore bridge /apply: {e}"

    # Salva nel DB
    try:
        from urllib.parse import urlparse
        domain = urlparse(url).netloc.replace("www.", "").split(".")[0]
        from agent.database import job_application_save
        job_application_save(company=domain.capitalize(), role_title="", url=url,
                             cv_type=cv_type, notes=result[:500])
    except Exception:
        pass

    return (
        f"📝 Form compilato per: {url} (CV: {cv_type})\n\n{result}\n\n"
        f"ISTRUZIONI PER L'AGENTE: mostra a Francesco il riepilogo dei campi compilati qui sopra "
        f"e CHIEDI se confermare l'invio o modificare qualcosa. "
        f"Se conferma → chiama submit_application(session_id='{session_id}'). "
        f"Se chiede una modifica → chiama modify_application(session_id='{session_id}', change='...'). "
        f"NON inviare senza conferma esplicita di Francesco."
    )


def submit_application(session_id: str) -> str:
    """Invia (submit) una candidatura già compilata, DOPO conferma esplicita di Francesco.
    Usa il session_id restituito da browser_fill_application.

    Args:
        session_id: ID della sessione del form compilato
    """
    import os, requests
    bridge_url = os.environ.get("BRIDGE_URL", "")
    bridge_secret = os.environ.get("BRIDGE_SECRET", "")
    if not bridge_url:
        return "Errore: BRIDGE_URL non configurato."
    try:
        resp = requests.post(
            f"{bridge_url}/apply_submit",
            json={"session_id": session_id, "secret": bridge_secret},
            timeout=320,
        )
        resp.raise_for_status()
        return "📨 " + resp.json().get("response", "(nessuna risposta)")
    except Exception as e:
        return f"Errore invio candidatura: {e}"


def modify_application(session_id: str, change: str) -> str:
    """Modifica un campo di una candidatura già compilata (prima dell'invio), su richiesta di Francesco.

    Args:
        session_id: ID della sessione del form compilato
        change: Cosa modificare (es. "cambia il campo RAL in 50000")
    """
    import os, requests
    bridge_url = os.environ.get("BRIDGE_URL", "")
    bridge_secret = os.environ.get("BRIDGE_SECRET", "")
    if not bridge_url:
        return "Errore: BRIDGE_URL non configurato."
    try:
        resp = requests.post(
            f"{bridge_url}/apply_modify",
            json={"session_id": session_id, "change": change, "secret": bridge_secret},
            timeout=420,
        )
        resp.raise_for_status()
        return resp.json().get("response", "(nessuna risposta)") + (
            "\n\nISTRUZIONI: mostra il riepilogo aggiornato e chiedi di nuovo conferma per l'invio "
            "(submit_application) o altre modifiche."
        )
    except Exception as e:
        return f"Errore modifica candidatura: {e}"


def _browser_fill_application_OLD_LOCAL(
    url: str,
    cv_type: str = "sales",
    how_did_you_hear: str = "LinkedIn - post or content",
    extra_fields: str = "",
) -> str:
    """[DEPRECATO] Vecchia versione con Playwright locale. Mantenuta come riferimento."""
    from playwright.sync_api import sync_playwright

    profile = {
        "name": "Francesco Brufani",
        "email": "fr.brufani@gmail.com",
        "phone": "+393315681407",
        "linkedin": "https://www.linkedin.com/in/francesco-brufani/",
    }

    cv_path = _get_cv_path(cv_type)
    screenshot_path = str(SCREENSHOT_DIR / "application_preview.png")
    filled = []
    errors = []

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            ctx = browser.new_context(
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                viewport={"width": 1280, "height": 900},
            )
            page = ctx.new_page()
            page.goto(url, timeout=30000, wait_until="networkidle")

            # ── Name ──────────────────────────────────────────────────────────
            name_sel = 'input[name="_systemfield_name"], input[placeholder*="name" i], input[id*="name" i]'
            if page.locator(name_sel).count() > 0:
                page.locator(name_sel).first.fill(profile["name"])
                filled.append(f"Nome: {profile['name']}")

            # ── Email ─────────────────────────────────────────────────────────
            email_sel = 'input[type="email"], input[name="_systemfield_email"]'
            if page.locator(email_sel).count() > 0:
                page.locator(email_sel).first.fill(profile["email"])
                filled.append(f"Email: {profile['email']}")

            # ── Phone ─────────────────────────────────────────────────────────
            phone_sel = 'input[type="tel"]'
            if page.locator(phone_sel).count() > 0:
                page.locator(phone_sel).first.fill(profile["phone"])
                filled.append(f"Telefono: {profile['phone']}")

            # ── LinkedIn ──────────────────────────────────────────────────────
            linkedin_sel = 'input[type="url"], input[placeholder*="linkedin" i], input[id*="linkedin" i]'
            if page.locator(linkedin_sel).count() > 0:
                page.locator(linkedin_sel).first.fill(profile["linkedin"])
                filled.append(f"LinkedIn: {profile['linkedin']}")

            # ── Resume upload ─────────────────────────────────────────────────
            file_sel = 'input[type="file"]'
            if page.locator(file_sel).count() > 0 and Path(cv_path).exists():
                page.locator(file_sel).first.set_input_files(cv_path)
                filled.append(f"CV allegato: {Path(cv_path).name}")

            # ── Radio / "How did you hear" ────────────────────────────────────
            try:
                radios = page.locator('input[type="radio"]').all()
                for radio in radios:
                    label_el = page.locator(f'label[for="{radio.get_attribute("id")}"]')
                    if label_el.count() > 0:
                        label_text = label_el.inner_text().strip()
                    else:
                        # Try sibling label
                        label_text = radio.evaluate(
                            'el => el.closest("label")?.innerText || el.parentElement?.innerText || ""'
                        ).strip()
                    if how_did_you_hear.lower() in label_text.lower():
                        radio.check()
                        filled.append(f"Come hai trovato: {label_text}")
                        break
            except Exception as e:
                errors.append(f"Radio: {e}")

            # ── Extra custom fields ───────────────────────────────────────────
            if extra_fields:
                for pair in extra_fields.split(","):
                    if "=" in pair:
                        key, val = pair.split("=", 1)
                        try:
                            sel = f'input[name*="{key.strip()}" i], textarea[name*="{key.strip()}" i]'
                            if page.locator(sel).count() > 0:
                                page.locator(sel).first.fill(val.strip())
                                filled.append(f"{key.strip()}: {val.strip()}")
                        except Exception as e:
                            errors.append(f"Campo {key}: {e}")

            # ── Screenshot ────────────────────────────────────────────────────
            page.wait_for_timeout(800)
            page.screenshot(path=screenshot_path, full_page=True)
            browser.close()

        summary = "\n".join(f"  ✅ {f}" for f in filled)
        err_summary = "\n".join(f"  ⚠️ {e}" for e in errors) if errors else ""

        # Salva nel DB
        try:
            from urllib.parse import urlparse
            domain = urlparse(url).netloc.replace("www.", "").split(".")[0]
            from agent.database import job_application_save
            job_application_save(
                company=domain.capitalize(),
                role_title="",
                url=url,
                cv_type=cv_type,
                notes="\n".join(filled),
            )
        except Exception:
            pass

        return (
            f"[SCREENSHOT:{screenshot_path}]\n"
            f"Form compilato per: {url}\n"
            f"CV usato: {Path(cv_path).name}\n\n"
            f"Campi compilati:\n{summary}"
            + (f"\n\nAttenzione:\n{err_summary}" if err_summary else "")
            + "\n\n⚠️ Apri il link sul browser per verificare e cliccare SUBMIT (reCAPTCHA richiede click umano)."
        )

    except Exception as e:
        return f"Errore durante la compilazione del form: {e}"


def browser_screenshot(url: str) -> str:
    """Apre un URL, scatta uno screenshot e lo restituisce.

    Args:
        url: URL da fotografare
    """
    from playwright.sync_api import sync_playwright

    screenshot_path = str(SCREENSHOT_DIR / "page_screenshot.png")
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_context().new_page()
            page.goto(url, timeout=30000, wait_until="domcontentloaded")
            page.wait_for_timeout(1500)
            page.screenshot(path=screenshot_path, full_page=False)
            browser.close()
        return f"[SCREENSHOT:{screenshot_path}]\nScreenshot di: {url}"
    except Exception as e:
        return f"Errore screenshot: {e}"
