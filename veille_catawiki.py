# veille_catawiki.py
import json, os, re, smtplib, time, random
from email.message import EmailMessage
from pathlib import Path
from playwright.sync_api import sync_playwright

# ================= PARAMÈTRES À REMPLIR =================
RECHERCHES = [
    {"mots_cles": "Cartier Santos", "budget_max": 3000},
    {"mots_cles": "Rolex Datejust", "budget_max": 4500},
]
MOTS_EXCLUS = ["pièces", "parts", "bracelet seul", "boîte seule"]
# =========================================================

EMAIL = os.environ["EMAIL"]
MDP = os.environ["EMAIL_MDP_APPLI"]
FICHIER_VUS = Path("lots_deja_vus.json")
vus = set(json.loads(FICHIER_VUS.read_text())) if FICHIER_VUS.exists() else set()

def prix(texte):
    m = re.search(r"€\s?([\d\s\u202f.]+)", texte)
    return int(re.sub(r"\D", "", m.group(1))) if m else None

nouveaux = []
with sync_playwright() as pw:
    page = pw.chromium.launch().new_page()
    for r in RECHERCHES:
        page.goto("https://www.catawiki.com/fr/s?q=" + r["mots_cles"].replace(" ", "+"),
                  wait_until="networkidle")
        page.wait_for_timeout(3000)
        for a in page.query_selector_all("a[href*='/l/']"):
            h = a.get_attribute("href").split("?")[0]
            t = a.inner_text()
            if h in vus or any(x.lower() in t.lower() for x in MOTS_EXCLUS):
                continue
            p = prix(t)
            if p is None or p <= r["budget_max"]:
                nouveaux.append((h, t.strip().replace("\n", " | "), p))
                vus.add(h)
        time.sleep(random.uniform(5, 15))

if nouveaux:
    msg = EmailMessage()
    msg["Subject"] = f"Catawiki : {len(nouveaux)} nouveau(x) lot(s)"
    msg["From"] = msg["To"] = EMAIL
    msg.set_content("\n\n".join(
        f"{t}\nOffre : {p or '?'} €\nhttps://www.catawiki.com{h}" for h, t, p in nouveaux))
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
        s.login(EMAIL, MDP)
        s.send_message(msg)
    FICHIER_VUS.write_text(json.dumps(sorted(vus)))
