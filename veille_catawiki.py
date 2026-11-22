# veille_catawiki.py — version alternative (données __NEXT_DATA__)
import json, os, re, smtplib, time, random
from email.message import EmailMessage
from pathlib import Path
from curl_cffi import requests

MOTS_EXCLUS = ["pièces", "parts", "bracelet seul", "boîte seule", "quartz", "quarz"]

RECHERCHES = []
for ligne in Path("recherches.txt").read_text(encoding="utf-8").splitlines():
    if ";" in ligne and not ligne.strip().startswith("#"):
        mots, budget = ligne.split(";", 1)
        RECHERCHES.append({"mots_cles": mots.strip(), "budget_max": int(budget.strip())})

EMAIL = os.environ["EMAIL"]
MDP = os.environ["EMAIL_MDP_APPLI"]
FICHIER_VUS = Path("lots_deja_vus.json")
vus = set(json.loads(FICHIER_VUS.read_text())) if FICHIER_VUS.exists() else set()

def trouver_lots(obj, acc):
    """Parcourt les données et garde tout objet qui ressemble à un lot."""
    if isinstance(obj, dict):
        titre = obj.get("title") or obj.get("name")
        lid = obj.get("id") or obj.get("lotId")
        if titre and lid and isinstance(titre, str):
            acc.append(obj)
        for v in obj.values():
            trouver_lots(v, acc)
    elif isinstance(obj, list):
        for v in obj:
            trouver_lots(v, acc)
    return acc

def prix_du_lot(lot):
    for cle in ("currentBidAmount", "current_bid", "bidAmount", "price", "amount"):
        v = lot.get(cle)
        if isinstance(v, dict):
            v = v.get("EUR") or v.get("amount") or v.get("value")
        if isinstance(v, (int, float)):
            return int(v)
    return None

nouveaux = []
for r in RECHERCHES:
    url = "https://www.catawiki.com/fr/s?q=" + r["mots_cles"].replace(" ", "+")
    rep = requests.get(url, impersonate="chrome", timeout=30)
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', rep.text, re.S)
    if not m:
        print(f"[{r['mots_cles']}] code {rep.status_code} — pas de données. Début: {rep.text[:200]!r}")
        continue
    lots = trouver_lots(json.loads(m.group(1)), [])
    print(f"[{r['mots_cles']}] code {rep.status_code} — {len(lots)} lots lus")
    for lot in lots:
        lid = str(lot.get("id") or lot.get("lotId"))
        titre = lot.get("title") or lot.get("name")
        if lid in vus or any(x.lower() in titre.lower() for x in MOTS_EXCLUS):
            continue
        p = prix_du_lot(lot)
        if p is None or p <= r["budget_max"]:
            nouveaux.append((lid, titre, p))
            vus.add(lid)
    time.sleep(random.uniform(5, 15))

print(f"TOTAL nouveaux lots: {len(nouveaux)}")
if nouveaux:
    msg = EmailMessage()
    msg["Subject"] = f"Catawiki : {len(nouveaux)} nouveau(x) lot(s)"
    msg["From"] = msg["To"] = EMAIL
    msg.set_content("\n\n".join(
        f"{t}\nOffre : {p or '?'} €\nhttps://www.catawiki.com/fr/l/{i}" for i, t, p in nouveaux))
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
        s.login(EMAIL, MDP)
        s.send_message(msg)
    FICHIER_VUS.write_text(json.dumps(sorted(vus)))
