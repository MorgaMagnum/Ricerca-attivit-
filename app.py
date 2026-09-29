from flask import Flask, render_template, request, jsonify
import requests
import concurrent.futures
import threading
import sqlite3
import json
import os
import re
import base64
from datetime import datetime
from urllib.parse import quote_plus, urlparse, urljoin

app = Flask(__name__)
DB_PATH     = os.path.join(os.path.dirname(__file__), "searches.db")
CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")

def load_config() -> dict:
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def save_config(data: dict):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
OVERPASS_MIRRORS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
]
# Tempo massimo lato server Overpass; la richiesta HTTP attende un po' di più
OVERPASS_TIMEOUT_S = 300
OVERPASS_HTTP_TIMEOUT_S = OVERPASS_TIMEOUT_S + 30
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
HEADERS = {"User-Agent": "MorgantiTrovaClienti/1.0"}

# ---------------------------------------------------------------------------
# Categorie OSM
# ---------------------------------------------------------------------------
OSM_CATEGORIES = {
    "all":          {"label": "-- Tutte le categorie --",       "tags": []},  # gestito a parte
    "restaurant":   {"label": "Ristoranti",                     "tags": [("amenity", "restaurant")]},
    "bar":          {"label": "Bar / Caffè",                    "tags": [("amenity", "bar"), ("amenity", "cafe")]},
    "hotel":        {"label": "Hotel / B&B",                    "tags": [("tourism", "hotel"), ("tourism", "guest_house"), ("tourism", "bed_and_breakfast")]},
    "hairdresser":  {"label": "Parrucchieri",                   "tags": [("shop", "hairdresser")]},
    "beauty":       {"label": "Centri Estetici",                "tags": [("shop", "beauty")]},
    "bakery":       {"label": "Panetterie / Pasticcerie",       "tags": [("shop", "bakery"), ("shop", "pastry")]},
    "pharmacy":     {"label": "Farmacie",                       "tags": [("amenity", "pharmacy")]},
    "doctor":       {"label": "Medici / Studi Medici",          "tags": [("amenity", "doctors")]},
    "dentist":      {"label": "Dentisti",                       "tags": [("amenity", "dentist")]},
    "gym":          {"label": "Palestre / Fitness",             "tags": [("leisure", "fitness_centre")]},
    "craft":        {"label": "Artigiani",                      "tags": [("craft", "")]},
    "office":       {"label": "Uffici / Studi Professionali",   "tags": [("office", "")]},
    "real_estate":  {"label": "Agenzie Immobiliari",            "tags": [("office", "estate_agent")]},
    "lawyer":       {"label": "Avvocati / Notai",               "tags": [("office", "lawyer"), ("office", "notary")]},
    "accountant":   {"label": "Commercialisti / Consulenti",    "tags": [("office", "accountant"), ("office", "tax_advisor")]},
    "web_agency":   {"label": "Agenzie Web / Digitali",         "tags": [("office", "it"), ("office", "advertising_agency")]},
    "automotive":   {"label": "Officine / Autofficine",         "tags": [("shop", "car_repair")]},
    "clothing":     {"label": "Abbigliamento / Moda",           "tags": [("shop", "clothes"), ("shop", "shoes")]},
    "electronics":  {"label": "Elettronica / Telefonia",        "tags": [("shop", "electronics"), ("shop", "mobile_phone")]},
    "furniture":    {"label": "Arredamento / Interior",         "tags": [("shop", "furniture"), ("shop", "interior_decoration")]},
    "supermarket":  {"label": "Supermercati / Alimentari",      "tags": [("shop", "supermarket"), ("shop", "convenience")]},
    "shop_all":     {"label": "Negozi (tutti i tipi)",          "tags": [("shop", "")]},
}

# ---------------------------------------------------------------------------
# Temi proposta per tipo di attività
# ---------------------------------------------------------------------------
THEMES = {
    "food": {
        "primary": "#0f0500", "secondary": "#c0392b", "accent": "#e67e22",
        "gradient": "linear-gradient(160deg,#0f0500 0%,#7b1a00 60%,#c0392b 100%)",
        "font_head": "'Playfair Display', serif", "light_bg": False,
        "icon": "🍽️",
        "services": ["Menu del Giorno", "Prenotazioni Online", "Asporto & Delivery", "Eventi Privati"],
        "tagline": "Un'esperienza gastronomica indimenticabile",
        "about": "Da noi ogni piatto racconta una storia. Utilizziamo solo ingredienti freschi e di stagione, selezionati con cura dai migliori produttori locali. La nostra cucina unisce tradizione e creatività.",
        "menu": [
            {"cat": "Antipasti", "piatti": [("Bruschetta al pomodoro","€6"),("Tagliere misto","€12"),("Carpaccio di manzo","€14")]},
            {"cat": "Primi", "piatti": [("Tagliatelle al ragù","€14"),("Risotto ai funghi","€16"),("Spaghetti alle vongole","€17")]},
            {"cat": "Dolci", "piatti": [("Tiramisù della casa","€7"),("Panna cotta ai frutti","€6"),("Semifreddo al pistacchio","€8")]},
        ],
    },
    "cafe": {
        "primary": "#1c0d00", "secondary": "#6f4e37", "accent": "#d4a017",
        "gradient": "linear-gradient(160deg,#1c0d00 0%,#4a2c0a 60%,#6f4e37 100%)",
        "font_head": "'Raleway', sans-serif", "light_bg": False,
        "icon": "☕",
        "services": ["Espresso & Caffè Speciali", "Colazione Artigianale", "Aperitivo", "Cocktail & Spirits"],
        "tagline": "Dove ogni giorno inizia con il gusto giusto",
        "about": "Siamo il tuo angolo preferito della città. Caffè selezionati da ogni parte del mondo, cornetti sfornati ogni mattina e un'atmosfera che ti fa sentire subito a casa.",
        "drinks": [
            ("Espresso","€1.20"), ("Cappuccino","€1.50"), ("Caffè Americano","€2.00"),
            ("Marocchino","€2.00"), ("Latte Macchiato","€2.50"), ("Cold Brew","€3.50"),
        ],
    },
    "hotel": {
        "primary": "#08111a", "secondary": "#1a3a5c", "accent": "#c9a84c",
        "gradient": "linear-gradient(160deg,#08111a 0%,#0d2137 60%,#1a3a5c 100%)",
        "font_head": "'Cormorant Garamond', serif", "light_bg": True,
        "icon": "🏨",
        "services": ["Camere & Suite", "Colazione Inclusa", "Spa & Wellness", "Concierge 24h"],
        "tagline": "Il lusso dell'autenticita italiana",
        "about": "Un luogo dove il calore dell'ospitalità italiana si fonde con il comfort più raffinato. Ogni dettaglio è curato con amore per rendere il vostro soggiorno indimenticabile.",
        "rooms": [
            {"name": "Camera Classic", "desc": "Vista giardino, 22m²", "price": "da €89/notte", "icon": "🛏️"},
            {"name": "Camera Superior", "desc": "Vista panoramica, 32m²", "price": "da €129/notte", "icon": "✨"},
            {"name": "Suite Deluxe", "desc": "Terrazza privata, 55m²", "price": "da €249/notte", "icon": "👑"},
        ],
    },
    "wellness": {
        "primary": "#120820", "secondary": "#6a1e6e", "accent": "#e91e8c",
        "gradient": "linear-gradient(160deg,#120820 0%,#4a0e5e 60%,#6a1e6e 100%)",
        "font_head": "'Raleway', sans-serif", "light_bg": False,
        "icon": "✂️",
        "services": ["Taglio & Styling", "Colorazione & Balayage", "Trattamenti Premium", "Prenotazione Online"],
        "tagline": "Il tuo look, la nostra firma",
        "about": "Il nostro salone è uno spazio dove bellezza e benessere si incontrano. Ogni cliente è unico e merita un'attenzione personalizzata. Usiamo solo prodotti premium, rispettosi dei capelli e dell'ambiente.",
        "price_list": [
            ("Taglio donna", "da €35"), ("Taglio uomo", "da €20"), ("Piega", "da €25"),
            ("Colore", "da €60"), ("Balayage", "da €90"), ("Trattamento cheratina", "da €80"),
        ],
    },
    "sport": {
        "primary": "#050505", "secondary": "#1a1a1a", "accent": "#e53935",
        "gradient": "linear-gradient(160deg,#050505 0%,#1a0000 60%,#7b0000 100%)",
        "font_head": "'Oswald', sans-serif", "light_bg": False,
        "icon": "💪",
        "services": ["Sala Pesi & Cardio", "Corsi di Gruppo", "Personal Trainer", "Abbonamenti Flessibili"],
        "tagline": "NON ESISTONO LIMITI. SOLO OBIETTIVI.",
        "about": "La nostra struttura è progettata per chi vuole risultati veri. Attrezzature professionali, istruttori certificati e un ambiente che ti spinge sempre un passo oltre.",
        "stats": [("500+","Membri attivi"),("40+","Corsi settimanali"),("15+","Istruttori cert."),("5","Anni di eccellenza")],
        "plans": [
            {"name": "STARTER", "price": "€39", "period": "/mese", "features": ["Accesso sala pesi","Spogliatoi","1 corso/sett."], "highlight": False},
            {"name": "PRO", "price": "€59", "period": "/mese", "features": ["Tutto Starter","Corsi illimitati","1 PT session/mese","App tracking"], "highlight": True},
            {"name": "ELITE", "price": "€89", "period": "/mese", "features": ["Tutto Pro","PT illimitato","Nutrizione","Accesso H24"], "highlight": False},
        ],
    },
    "health": {
        "primary": "#0277bd", "secondary": "#0277bd", "accent": "#00897b",
        "gradient": "linear-gradient(160deg,#e3f2fd 0%,#b3e5fc 100%)",
        "font_head": "'Montserrat', sans-serif", "light_bg": True,
        "icon": "🩺",
        "services": ["Visite Specialistiche", "Prenotazione Online", "Referti Digitali", "Urgenze"],
        "tagline": "La tua salute, la nostra missione",
        "about": "Professionisti esperti e strumentazione all'avanguardia al servizio della tua salute. Un approccio umano e attento che mette sempre il paziente al centro.",
        "specialties": [
            ("Medicina Generale","🩺"),("Cardiologia","❤️"),("Dermatologia","🔬"),
            ("Pediatria","👶"),("Ortopedia","🦴"),("Psicologia","🧠"),
        ],
        "steps": [
            ("Prenota online","Scegli lo specialista e l'orario che preferisci in pochi click."),
            ("Vieni da noi","Ti accogliamo in un ambiente confortevole e privo di attese."),
            ("Ricevi i referti","I tuoi risultati disponibili digitalmente in 24 ore."),
        ],
    },
    "professional": {
        "primary": "#05060d", "secondary": "#0d1b4b", "accent": "#c9a84c",
        "gradient": "linear-gradient(160deg,#05060d 0%,#0d1b4b 100%)",
        "font_head": "'Cormorant Garamond', serif", "light_bg": False,
        "icon": "⚖️",
        "services": ["Consulenza Legale", "Contrattualistica", "Diritto Civile & Penale", "Assistenza Stragiudiziale"],
        "tagline": "Esperienza e rigore al tuo fianco",
        "about": "Offriamo consulenza professionale di alto livello con un approccio personalizzato. Ogni caso è unico e merita attenzione, dedizione e la massima competenza.",
        "areas": [
            ("Diritto Civile","⚖️"),("Diritto Penale","🔒"),("Diritto del Lavoro","👔"),
            ("Diritto di Famiglia","👨‍👩‍👧"),("Diritto Societario","🏢"),("Fiscale & Tributario","📊"),
        ],
        "stats": [("20+","Anni di esperienza"),("500+","Clienti assistiti"),("98%","Soddisfazione clienti"),("50+","Cause vinte")],
    },
    "realestate": {
        "primary": "#2c3e50", "secondary": "#2c3e50", "accent": "#e74c3c",
        "gradient": "linear-gradient(160deg,#2c3e50 0%,#34495e 100%)",
        "font_head": "'Raleway', sans-serif", "light_bg": True,
        "icon": "🏠",
        "services": ["Vendita Immobili", "Affitti Residenziali", "Valutazioni Gratuite", "Consulenza Mutui"],
        "tagline": "Ogni casa ha la sua storia. La tua inizia qui.",
        "about": "Conosciamo il territorio palmo a palmo. Trasparenza, professionalità e un network esclusivo ci permettono di trovare la soluzione giusta per ogni cliente.",
        "listings": [
            {"tipo": "Appartamento", "zona": "Centro Storico", "mq": "85m²", "prezzo": "€280.000", "tag": "IN VENDITA"},
            {"tipo": "Villa", "zona": "Zona Residenziale", "mq": "200m²", "prezzo": "€650.000", "tag": "ESCLUSIVA"},
            {"tipo": "Ufficio", "zona": "Business District", "mq": "120m²", "prezzo": "€1.800/mese", "tag": "AFFITTO"},
        ],
    },
    "automotive": {
        "primary": "#080808", "secondary": "#1a1a1a", "accent": "#ff6f00",
        "gradient": "linear-gradient(160deg,#080808 0%,#1a1a1a 60%,#2d0000 100%)",
        "font_head": "'Montserrat', sans-serif", "light_bg": False,
        "icon": "🔧",
        "services": ["Tagliando & Revisione", "Diagnostica Elettronica", "Gommista", "Carrozzeria & Verniciatura"],
        "tagline": "OFFICINA AUTORIZZATA. QUALITA CERTIFICATA.",
        "about": "Meccanici certificati, diagnostica di ultima generazione e ricambi originali. Preventivi trasparenti, tempi certi. La tua auto torna a casa come nuova.",
        "brands": ["FIAT","FORD","VW","BMW","MERCEDES","TOYOTA","RENAULT","PEUGEOT"],
        "service_list": [
            ("Tagliando base","da €89"),("Tagliando completo","da €149"),("Freni & Frizione","da €120"),
            ("Pneumatici (4 pz)","da €199"),("Diagnosi elettronica","€49"),("Revisione ministeriale","€79"),
        ],
    },
    "retail": {
        "primary": "#111111", "secondary": "#111111", "accent": "#c9a84c",
        "gradient": "linear-gradient(160deg,#111111 0%,#333333 100%)",
        "font_head": "'Montserrat', sans-serif", "light_bg": True,
        "icon": "🛍️",
        "services": ["Nuove Collezioni", "Abbigliamento Uomo & Donna", "Accessori di Lusso", "Sartoria su Misura"],
        "tagline": "Vesti il tuo stile. Racconta la tua storia.",
        "about": "Una selezione curata dei migliori brand e delle tendenze più attuali. Il nostro team di personal shopper è pronto a guidarti verso il look che ti rappresenta davvero.",
        "collections": [
            {"name": "Uomo", "lista": ["Giacche & Blazer","Camicie Premium","Pantaloni Sartoriali"], "color": "#1a1a2e"},
            {"name": "Donna", "lista": ["Abiti da Sera","Loungewear Chic","Accessori Luxury"], "color": "#3d0c02"},
            {"name": "New In", "lista": ["Collezione S/S 2025","Edizioni Limitate","Capsule Collection"], "color": "#0a2e0a"},
        ],
    },
    "tech": {
        "primary": "#01050e", "secondary": "#050d1f", "accent": "#00d4ff",
        "gradient": "linear-gradient(160deg,#01050e 0%,#050d1f 60%,#0a1628 100%)",
        "font_head": "'Montserrat', sans-serif", "light_bg": False,
        "icon": "💻",
        "services": ["Vendita & Noleggio", "Assistenza & Riparazione", "Configurazione", "Garanzia Estesa"],
        "tagline": "Tecnologia al tuo servizio. Sempre.",
        "about": "Siamo il punto di riferimento tech della zona. Offriamo i migliori dispositivi elettronici, assistenza rapida e competente. Riparazioni in giornata, preventivi gratuiti.",
        "categories": [
            {"name": "Smartphone & Tablet", "brands": "Apple · Samsung · Xiaomi · OnePlus", "icon": "📱"},
            {"name": "Computer & Laptop", "brands": "Apple · Dell · HP · Lenovo · ASUS", "icon": "💻"},
            {"name": "Audio & Gaming", "brands": "Sony · Bose · Razer · Logitech", "icon": "🎧"},
        ],
        "repairs": [
            ("Sostituzione schermo","da €59"),("Batteria","da €39"),("Connettore ricarica","da €49"),
            ("Scheda madre","da €89"),("Dati recupero","da €69"),("Software & Virus","da €35"),
        ],
    },
    "craft": {
        "primary": "#1a1008", "secondary": "#3e2723", "accent": "#bf8040",
        "gradient": "linear-gradient(160deg,#1a1008 0%,#3e2723 60%,#5d4037 100%)",
        "font_head": "'Playfair Display', serif", "light_bg": False,
        "icon": "🔨",
        "services": ["Lavorazioni su Misura", "Restauro & Recupero", "Preventivo Gratuito", "Consegna & Posa"],
        "tagline": "L'arte delle mani. La precisione del mestiere.",
        "about": "Ogni lavoro porta la nostra firma. Anni di esperienza, materiali selezionati e una cura artigianale che i macchinari non potranno mai replicare. Il vostro progetto, realizzato con passione.",
        "portfolio": [
            {"title": "Cucina su misura","mat": "Rovere massello","year": "2024"},
            {"title": "Scala in ferro battuto","mat": "Ferro + legno","year": "2024"},
            {"title": "Tavolo da pranzo","mat": "Noce americano","year": "2023"},
            {"title": "Portone d'ingresso","mat": "Abete lamellare","year": "2023"},
            {"title": "Libreria a muro","mat": "MDF laccato","year": "2023"},
            {"title": "Boiserie salone","mat": "Ciliegio naturale","year": "2022"},
        ],
        "process": [
            ("Sopralluogo gratuito","Veniamo da voi per capire spazi, esigenze e stile."),
            ("Progetto & preventivo","Disegno tecnico e preventivo dettagliato senza impegno."),
            ("Lavorazione artigianale","Ogni pezzo realizzato a mano nel nostro laboratorio."),
            ("Consegna & posa","Installiamo tutto con cura, fino al dettaglio finale."),
        ],
    },
    "default": {
        "primary": "#0a0f1e", "secondary": "#1a2a5c", "accent": "#4361ee",
        "gradient": "linear-gradient(160deg,#0a0f1e 0%,#1a2a5c 100%)",
        "font_head": "'Montserrat', sans-serif", "light_bg": False,
        "icon": "⭐",
        "services": ["Servizio Professionale", "Qualità Garantita", "Assistenza Clienti", "Preventivo Gratuito"],
        "tagline": "Professionalità e qualità al tuo servizio",
        "about": "Con anni di esperienza nel settore, offriamo servizi di alta qualità che soddisfano le esigenze di ogni cliente. La nostra dedizione e professionalità ci distinguono.",
    },
}

TYPE_THEME_MAP = {
    **{t: "food" for t in ["restaurant", "fast_food", "ice_cream", "pizza", "bakery", "pastry"]},
    **{t: "cafe" for t in ["bar", "cafe", "pub", "coffee", "biergarten"]},
    **{t: "wellness" for t in ["hairdresser", "beauty", "spa", "massage", "nail_salon", "cosmetics", "tanning"]},
    **{t: "sport" for t in ["fitness_centre", "gym", "sports_centre", "swimming_pool", "yoga", "martial_arts", "boxing"]},
    **{t: "hotel" for t in ["hotel", "guest_house", "hostel", "motel", "bed_and_breakfast", "chalet", "apartment"]},
    **{t: "health" for t in ["pharmacy", "doctors", "dentist", "clinic", "hospital", "optician", "hearing_aids", "physiotherapist"]},
    **{t: "professional" for t in ["lawyer", "notary", "accountant", "tax_advisor", "financial", "consulting", "insurance", "estate_agent_office"]},
    **{t: "realestate" for t in ["estate_agent", "property"]},
    **{t: "automotive" for t in ["car_repair", "car", "car_wash", "motorcycle", "tyres", "fuel", "car_parts"]},
    **{t: "retail" for t in ["clothes", "shoes", "jewellery", "boutique", "fashion", "tailor", "bag", "watches", "leather"]},
    **{t: "tech" for t in ["electronics", "mobile_phone", "computer", "video_games", "hifi", "appliance", "it", "advertising_agency"]},
    **{t: "craft" for t in ["carpenter", "electrician", "plumber", "painter", "blacksmith", "shoemaker", "tailor", "stonemason", "glaziery", "joiner", "key_cutter"]},
}


def get_theme(btype: str) -> dict:
    key = TYPE_THEME_MAP.get((btype or "").lower(), "default")
    return {**THEMES[key], "theme_key": key}


def domain_suggestion(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return f"www.{slug[:30]}.it"


# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------
def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
        CREATE TABLE IF NOT EXISTS searches (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at   TEXT    NOT NULL,
            location     TEXT    NOT NULL,
            display_name TEXT,
            category     TEXT,
            category_label TEXT,
            radius_km    REAL,
            result_count INTEGER,
            has_check    INTEGER DEFAULT 0,
            results_json TEXT
        )""")
        conn.execute("""
        CREATE TABLE IF NOT EXISTS website_cache (
            name_key   TEXT PRIMARY KEY,
            website    TEXT,
            source     TEXT,
            checked_at TEXT NOT NULL
        )""")
        conn.execute("""
        CREATE TABLE IF NOT EXISTS business_notes (
            name_key   TEXT PRIMARY KEY,
            status     TEXT DEFAULT 'nuovo',
            note       TEXT DEFAULT '',
            updated_at TEXT NOT NULL
        )""")
        try:
            conn.execute("ALTER TABLE searches ADD COLUMN has_check INTEGER DEFAULT 0")
        except Exception:
            pass
        try:
            conn.execute("ALTER TABLE business_notes ADD COLUMN next_contact TEXT DEFAULT ''")
        except Exception:
            pass
        conn.execute("""
        CREATE TABLE IF NOT EXISTS email_log (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            name_key TEXT NOT NULL,
            name     TEXT,
            subject  TEXT,
            template TEXT,
            lang     TEXT,
            sent_at  TEXT NOT NULL
        )""")
        conn.commit()


BACKUP_DIR  = os.path.join(os.path.dirname(__file__), "backups")
BACKUP_KEEP = 14

def backup_db():
    """Copia giornaliera di searches.db in backups/ (una per giorno, ultime BACKUP_KEEP)."""
    if not os.path.exists(DB_PATH):
        return
    os.makedirs(BACKUP_DIR, exist_ok=True)
    target = os.path.join(BACKUP_DIR, f"searches-{datetime.now():%Y-%m-%d}.db")
    if os.path.exists(target):
        return
    try:
        # API di backup SQLite: copia consistente anche se il db e' in uso
        src, dst = sqlite3.connect(DB_PATH), sqlite3.connect(target)
        try:
            src.backup(dst)
        finally:
            src.close()
            dst.close()
    except Exception as e:
        print(f"[BACKUP] Errore durante il backup del database: {e}")
        return
    old = sorted(f for f in os.listdir(BACKUP_DIR) if f.startswith("searches-") and f.endswith(".db"))
    for name in old[:-BACKUP_KEEP]:
        os.remove(os.path.join(BACKUP_DIR, name))
    print(f"[BACKUP] Database salvato in {target}")


backup_db()
init_db()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def geocode(location: str):
    params = {"q": location, "format": "json", "limit": 1}
    try:
        r = requests.get(NOMINATIM_URL, params=params, headers=HEADERS, timeout=10)
        data = r.json()
        if data:
            return float(data[0]["lat"]), float(data[0]["lon"]), data[0].get("display_name", location)
    except Exception:
        pass
    return None, None, None


def build_overpass_query(lat: float, lon: float, radius_m: int, category_key: str) -> str:
    if category_key == "all":
        keys = ["shop", "amenity", "office", "craft", "tourism", "leisure"]
        lines = []
        for key in keys:
            for etype in ("node", "way"):
                lines.append(f'  {etype}["name"]["{key}"](around:{radius_m},{lat},{lon});')
        body = "\n".join(lines)
        return f'[out:json][timeout:{OVERPASS_TIMEOUT_S}];\n(\n{body}\n);\nout center tags;'

    tags = OSM_CATEGORIES.get(category_key, {}).get("tags", [])
    lines = []
    for key, value in tags:
        f = f'["{key}"="{value}"]' if value else f'["{key}"]'
        for etype in ("node", "way", "relation"):
            lines.append(f'  {etype}["name"]{f}(around:{radius_m},{lat},{lon});')
    body = "\n".join(lines)
    return f'[out:json][timeout:{OVERPASS_TIMEOUT_S}];\n(\n{body}\n);\nout center tags;'


_GENERIC_WORDS = {
    "ristorante","trattoria","pizzeria","osteria","enoteca","bar","caffe","cafe",
    "hotel","studio","agenzia","centro","negozio","parrucchiere","farmacia",
    "pasticceria","panetteria","gelateria","officina","carrozzeria","della",
    "dello","degli","dal","dei","delle","garage","store","shop","il","la","le",
    "un","una","di","da","in","con","per","tra","fra","sul","nel",
}

def check_website(url: str) -> dict:
    if not url:
        return {"status": "none", "code": None}
    url = url.strip()
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    ua = {"User-Agent": "Mozilla/5.0"}
    try:
        r = requests.head(url, timeout=6, allow_redirects=True, headers=ua)
        return {"status": "ok" if r.status_code < 400 else "error", "code": r.status_code}
    except Exception:
        pass
    try:
        r = requests.get(url, timeout=6, allow_redirects=True, headers=ua, stream=True)
        return {"status": "ok" if r.status_code < 400 else "error", "code": r.status_code}
    except Exception as e:
        return {"status": "unreachable", "code": None, "detail": str(e)[:80]}


_KNOWN_CHAINS = {
    "mcdonald","mcdonalds","starbucks","burger king","kfc","subway","ikea",
    "mediaworld","unieuro","euronics","esselunga","conad","coop","lidl","aldi",
    "decathlon","h&m","zara","primark","benetton","coin","ovs","pittarosso",
}

CACHE_TTL_DAYS = 30

def _name_key(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())[:60]

def cache_get(name: str) -> tuple:
    """Returns (website, source) from cache if fresh, else (None, None)."""
    key = _name_key(name)
    try:
        with sqlite3.connect(DB_PATH) as conn:
            row = conn.execute(
                "SELECT website, source, checked_at FROM website_cache WHERE name_key=?", (key,)
            ).fetchone()
        if row:
            checked_at = datetime.fromisoformat(row[2])
            if (datetime.now() - checked_at).days < CACHE_TTL_DAYS:
                return row[0], row[1]
    except Exception:
        pass
    return None, None

def cache_set(name: str, website: str, source: str):
    key = _name_key(name)
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO website_cache (name_key, website, source, checked_at) VALUES (?,?,?,?)",
                (key, website, source, datetime.now().isoformat())
            )
            conn.commit()
    except Exception:
        pass

_SERPER_BLACKLIST = {
    "paginegialle.it", "paginebianche.it", "tripadvisor.", "facebook.com", "instagram.com",
    "yelp.com", "tuttocitta.it", "foursquare.", "thefork.", "booking.com",
    "google.", "bing.com", "wikipedia.", "linkedin.com", "twitter.com", "x.com", "goo.gl",
    "tiktok.com", "youtube.com", "maps.google", "mappy.", "mapy.com", "virgilio.",
    "localb.", "trustpilot.", "infobel.", "kompass.", "europages.",
    "justeat.it", "glovoapp.com", "deliveroo.it", "ubereats.com",
    "amazon.it", "amazon.com", "subito.it", "misterimprese.com", "192.it",
    "cylex.it", "openstreetmap.org", "here.com", "unifi.it", "pinterest.com",
    "indeed.com", "matrimonio.com",
}

_TA_TYPES = {
    "restaurant","fast_food","pizza","ice_cream","bakery","pastry",
    "bar","cafe","pub","coffee","biergarten",
    "hotel","guest_house","hostel","bed_and_breakfast","motel",
}

def search_serper(name: str, address: str, api_key: str, search_city: str = "") -> dict:
    """Query Serper.dev Google Places. Returns {website, rating, review_count}."""
    city = search_city or (address.split(",")[-1].strip() if address else "")
    q = f"{name} {city}".strip()
    try:
        resp = requests.post(
            "https://google.serper.dev/places",
            headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
            json={"q": q, "gl": "it", "hl": "it"},
            timeout=8,
        )
        resp.raise_for_status()
        data = resp.json()
        places = data.get("places", [])
        if places:
            p = places[0]
            return {
                "website":      p.get("website", ""),
                "rating":       p.get("rating"),
                "review_count": p.get("ratingCount"),
            }
    except Exception:
        pass
    return {"website": "", "rating": None, "review_count": None}


def search_tripadvisor_rating(name: str, address: str, api_key: str, search_city: str = "") -> dict:
    """Try to get TripAdvisor rating via Serper web search. Returns {ta_rating, ta_review_count}."""
    city = search_city or (address.split(",")[-1].strip() if address else "")
    q = f'"{name}" {city} tripadvisor'
    try:
        resp = requests.post(
            "https://google.serper.dev/search",
            headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
            json={"q": q, "gl": "it", "hl": "it", "num": 5},
            timeout=8,
        )
        resp.raise_for_status()
        data = resp.json()
        for result in (data.get("organic") or []):
            if "tripadvisor" not in result.get("link", "").lower():
                continue
            # Serper sometimes returns rating directly
            if result.get("rating"):
                try:
                    return {
                        "ta_rating": float(str(result["rating"]).replace(",", ".")),
                        "ta_review_count": result.get("ratingCount"),
                    }
                except Exception:
                    pass
            # Fallback: parse snippet
            snippet = result.get("snippet", "")
            m = re.search(r"(\d[,\.]\d)\s*(?:/5|su\s*5|stelle|stars?)", snippet, re.I)
            if m:
                try:
                    return {"ta_rating": float(m.group(1).replace(",", ".")), "ta_review_count": None}
                except Exception:
                    pass
    except Exception:
        pass
    return {"ta_rating": None, "ta_review_count": None}


_INSTITUTIONAL_PREFIXES = ("comune.", "regione.", "provincia.")
_INSTITUTIONAL_SUFFIXES = (".gov.it", ".edu.it", ".edu")


def _is_directory_domain(url: str) -> bool:
    """Confronta per etichetta di dominio (non substring grezza), cosi'
    'facebook.com' non blocca anche 'mynotfacebook.com'."""
    host = urlparse(url).netloc.lower()
    host = host[4:] if host.startswith("www.") else host
    labels = host.split(".")
    for b in _SERPER_BLACKLIST:
        if b.endswith("."):
            if b[:-1] in labels:
                return True
        elif host == b or host.endswith("." + b):
            return True
    if host.startswith(_INSTITUTIONAL_PREFIXES) or host.endswith(_INSTITUTIONAL_SUFFIXES):
        return True
    return False


def _looks_like_homepage(url: str) -> bool:
    """Le pagine 'entita'/'informazioni'/schede di directory hanno path profondi;
    la home di un sito aziendale e' quasi sempre alla radice o a un solo livello."""
    segments = [s for s in urlparse(url).path.split("/") if s]
    return len(segments) <= 1


def search_organic_website(name: str, address: str, api_key: str, search_city: str = "") -> str:
    """Fallback quando Google Places non ha un sito associato: cerca tra i risultati
    organici di Google il primo link che sembri l'homepage del sito aziendale
    (non un social/directory noto e non una scheda/pagina interna di terzi)."""
    city = search_city or (address.split(",")[-1].strip() if address else "")
    q = f'"{name}" {city}'.strip()
    try:
        resp = requests.post(
            "https://google.serper.dev/search",
            headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
            json={"q": q, "gl": "it", "hl": "it", "num": 5},
            timeout=8,
        )
        resp.raise_for_status()
        data = resp.json()
        for result in (data.get("organic") or []):
            link = result.get("link", "")
            if link and not _is_directory_domain(link) and _looks_like_homepage(link):
                return link
    except Exception:
        pass
    return ""


def discover_website(name: str) -> str:
    """Try common domain patterns for a business. Returns URL if found, else ''."""
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    if not slug or len(slug) > 40:
        return ""
    slug_compact = slug.replace("-", "")
    # meaningful words = non-generic, length > 3
    words = [w for w in name.lower().split() if len(w) > 3 and w not in _GENERIC_WORDS]

    candidates = []
    if len(slug) <= 35:
        candidates.append(f"https://www.{slug}.it")
    if slug_compact != slug and len(slug_compact) <= 28:
        candidates.append(f"https://www.{slug_compact}.it")
    for w in words[:2]:
        candidates.append(f"https://www.{w}.it")

    ua = {"User-Agent": "Mozilla/5.0"}
    for url in candidates[:4]:
        try:
            r = requests.head(url, timeout=3, allow_redirects=True, headers=ua)
            if r.status_code < 400:
                # Quick content check: fetch page and verify name word appears
                try:
                    rg = requests.get(r.url, timeout=3, headers=ua)
                    content = rg.text.lower()[:3000]
                    if words and any(w in content for w in words):
                        return r.url
                except Exception:
                    pass
        except Exception:
            continue
    return ""




_PLATFORM_PATTERNS = [
    (r"wix\.com",        "Wix"),
    (r"jimdo\.com",      "Jimdo"),
    (r"weebly\.com",     "Weebly"),
    (r"squarespace",     "Squarespace"),
    (r"webnode\.",       "Webnode"),
    (r"wordpress",       "WordPress"),
    (r"joomla",          "Joomla"),
    (r"drupal",          "Drupal"),
    (r"altervista",      "Altervista"),
    (r"aruba\.it",       "Aruba Site"),
]

_EMAIL_RE        = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
_MAILTO_RE       = re.compile(r'mailto:([^"\'?&\s<>]+)', re.I)
_EMAIL_IMG_EXT   = re.compile(r"\.(png|jpe?g|gif|svg|webp|bmp)$", re.I)
_EMAIL_JUNK_DOMS = (
    "example.com", "wixpress.com", "sentry.io", "schema.org", "w3.org",
    "godaddy.com", "gstatic.com", "domain.com", "yourdomain.com",
    "email.com", "site.com", "company.com",
)


def _clean_email(raw: str) -> str:
    email = raw.strip().strip(".,;:)('\"").lower()
    if not _EMAIL_RE.fullmatch(email):
        return ""
    domain = email.split("@", 1)[1]
    if _EMAIL_IMG_EXT.search(email) or domain in _EMAIL_JUNK_DOMS:
        return ""
    return email


def extract_email_from_html(content: str) -> str:
    """Cerca prima i link mailto: (più affidabili), poi indirizzi email nel testo."""
    for raw in _MAILTO_RE.findall(content):
        email = _clean_email(raw)
        if email:
            return email
    for raw in _EMAIL_RE.findall(content):
        email = _clean_email(raw)
        if email:
            return email
    return ""


_CONTACT_LINK_RE = re.compile(r'<a\b[^>]*href=["\']([^"\']+)["\']', re.I)
_CONTACT_KEYWORDS = ("contatt", "contact", "kontakt", "contacto")


def _find_contact_link(html: str, base_url: str) -> str:
    """Cerca nel menu/footer un link a una pagina 'Contatti', restituendo l'URL
    assoluto solo se resta sullo stesso dominio del sito gia' verificato."""
    base_host = urlparse(base_url).netloc.lower()
    for href in _CONTACT_LINK_RE.findall(html):
        h = href.strip()
        if not h or h.startswith("#") or h.lower().startswith(("mailto:", "tel:", "javascript:")):
            continue
        if any(k in h.lower() for k in _CONTACT_KEYWORDS):
            full = urljoin(base_url, h)
            if urlparse(full).netloc.lower() == base_host:
                return full
    return ""


def check_and_analyze(url: str) -> tuple:
    """Single GET: returns (ws_result_dict, site_info_dict).
    Replaces separate check_website + analyze_site calls."""
    ws   = {"status": "unreachable", "code": None}
    info = {"site_platform": "", "site_copyright_year": None, "site_mobile_ok": None, "email": ""}
    if not url:
        return {"status": "none", "code": None}, info
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    ua = {"User-Agent": "Mozilla/5.0"}
    try:
        with requests.get(url, timeout=7, headers=ua, stream=True, allow_redirects=True) as r:
            ws["code"]   = r.status_code
            ws["status"] = "ok" if r.status_code < 400 else "error"
            if r.status_code < 400:
                raw = b""
                for chunk in r.iter_content(8192):
                    raw += chunk
                    if len(raw) >= 12000:
                        break
                content = raw.decode("utf-8", errors="ignore")
                cl      = content.lower()
                info["site_mobile_ok"] = 'name="viewport"' in cl
                info["email"]          = extract_email_from_html(content)
                if not info["email"]:
                    contact_url = _find_contact_link(content, r.url)
                    if contact_url:
                        try:
                            with requests.get(contact_url, timeout=6, headers=ua, stream=True, allow_redirects=True) as rc:
                                if rc.status_code < 400:
                                    craw = b""
                                    for chunk in rc.iter_content(8192):
                                        craw += chunk
                                        if len(craw) >= 12000:
                                            break
                                    info["email"] = extract_email_from_html(craw.decode("utf-8", errors="ignore"))
                        except Exception:
                            pass
                gen = (re.search(r'<meta[^>]+name=["\']generator["\'][^>]+content=["\']([^"\']+)["\']', content, re.I) or
                       re.search(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']generator["\']', content, re.I))
                gen_str = gen.group(1) if gen else ""
                for pattern, pname in _PLATFORM_PATTERNS:
                    if re.search(pattern, gen_str or cl, re.I):
                        info["site_platform"] = pname
                        break
                y = re.search(r"(?:©|&copy;)\s*(20\d{2})", content)
                if y:
                    info["site_copyright_year"] = int(y.group(1))
    except Exception as e:
        ws["detail"] = str(e)[:80]
    return ws, info


def parse_element(element: dict):
    tags = element.get("tags", {})
    name = tags.get("name")
    if not name:
        return None
    if element["type"] == "node":
        lat, lon = element.get("lat"), element.get("lon")
    else:
        c = element.get("center", {})
        lat, lon = c.get("lat"), c.get("lon")

    website = (tags.get("website") or tags.get("contact:website") or
               tags.get("url") or tags.get("contact:url") or "")
    phone = tags.get("phone") or tags.get("contact:phone") or ""
    email = tags.get("email") or tags.get("contact:email") or ""
    street = tags.get("addr:street", "")
    number = tags.get("addr:housenumber", "")
    city   = tags.get("addr:city", "")
    address = (" ".join(filter(None, [street, number])) + (f", {city}" if city else "")).strip(", ")
    specific = (tags.get("shop") or tags.get("amenity") or tags.get("office") or
                tags.get("craft") or tags.get("tourism") or tags.get("leisure") or "")
    return {
        "id": element.get("id"),
        "name": name,
        "type": specific,
        "address": address,
        "website": website,
        "phone": phone,
        "email": email,
        "lat": lat,
        "lon": lon,
        "website_status": None,
        "website_code": None,
        "website_source": "",
        "rating": None,
        "review_count": None,
        "ta_rating": None,
        "ta_review_count": None,
        "site_platform": "",
        "site_copyright_year": None,
        "site_mobile_ok": None,
    }


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.route("/")
def index():
    categories = {k: v["label"] for k, v in OSM_CATEGORIES.items()}
    return render_template("index.html", categories=categories)


@app.route("/api/search", methods=["POST"])
def search():
    data = request.get_json()
    location   = (data.get("location") or "").strip()
    radius_km  = float(data.get("radius", 2))
    category   = data.get("category", "restaurant")
    do_check   = bool(data.get("check_websites", False))

    if not location:
        return jsonify({"error": "Inserisci una località"}), 400

    lat, lon, display_name = geocode(location)
    if lat is None:
        return jsonify({"error": f"Località non trovata: {location}"}), 400

    radius_m = max(100, min(int(radius_km * 1000), 60000))
    query = build_overpass_query(lat, lon, radius_m, category)

    def run_overpass(qry):
        print(f"[QUERY]\n{qry}\n")
        last_error = ""
        for mirror in OVERPASS_MIRRORS:
            try:
                resp = requests.post(mirror, data={"data": qry}, headers=HEADERS, timeout=OVERPASS_HTTP_TIMEOUT_S)
                resp.raise_for_status()
                data = resp.json()
                remark = data.get("remark", "")
                print(f"[RESPONSE] status={resp.status_code}, elements={len(data.get('elements',[]))}, remark={remark}")
                if "timed out" in remark.lower():
                    raise Exception(f"Server-side timeout: {remark}")
                return data, None
            except requests.exceptions.Timeout:
                last_error = f"Timeout su {mirror}"
                print(f"[TIMEOUT] {mirror}")
            except Exception as e:
                last_error = str(e)
                print(f"[ERROR] {mirror}: {e}")
        return None, last_error

    osm_data, err = run_overpass(query)
    if osm_data is None:
        return jsonify({"error": f"Server Overpass non raggiungibile. Riprova tra qualche minuto. ({err})"}), 504

    def parse_elements(data):
        result, seen = [], set()
        for el in data.get("elements", []):
            eid = el.get("id")
            if eid in seen:
                continue
            seen.add(eid)
            b = parse_element(el)
            if b:
                result.append(b)
        return result

    businesses = parse_elements(osm_data)

    # Se 0 risultati, riprova con raggio doppio (max 15 km)
    if not businesses and radius_m < 15000:
        radius_m2 = min(radius_m * 2, 15000)
        query2 = build_overpass_query(lat, lon, radius_m2, category)
        osm_data2, _ = run_overpass(query2)
        if osm_data2:
            businesses = parse_elements(osm_data2)
            if businesses:
                radius_km = round(radius_m2 / 1000, 1)

    if do_check and businesses:
        cfg = load_config()
        serper_key   = cfg.get("serper_key", "")
        serper_limit = int(cfg.get("serper_limit", 50))
        serper_used  = 0
        serper_lock  = threading.Lock()

        def reserve_serper() -> bool:
            """Riserva in modo atomico una chiamata Serper (check_one gira su 20 thread).
            Ritorna False se non c'e' chiave o il limite e' raggiunto."""
            nonlocal serper_used
            if not serper_key:
                return False
            with serper_lock:
                if serper_used >= serper_limit:
                    return False
                serper_used += 1
                return True

        def fetch_ratings(b, name, extra):
            """Recupera rating Google/TripAdvisor via Serper, indipendentemente dal fatto
            che il sito web sia gia' noto (da OSM o cache)."""
            if not reserve_serper():
                return
            s_city = display_name.split(",")[0].strip() if display_name else ""
            sd = search_serper(name, b.get("address", ""), serper_key, search_city=s_city)
            if sd.get("rating") is not None:
                extra["rating"]       = sd["rating"]
                extra["review_count"] = sd.get("review_count")
            btype_lower = (b.get("type") or "").lower()
            if btype_lower in _TA_TYPES and reserve_serper():
                ta = search_tripadvisor_rating(name, b.get("address", ""), serper_key, search_city=s_city)
                if ta.get("ta_rating") is not None:
                    extra["ta_rating"]       = ta["ta_rating"]
                    extra["ta_review_count"] = ta.get("ta_review_count")

        def check_one(b):
            url  = b.get("website", "")
            name = b.get("name", "")
            extra = {}

            if url:
                ws, site = check_and_analyze(url)
                extra.update(site)
                fetch_ratings(b, name, extra)
                return url, ws, "", extra

            # 1. Cache locale
            cached_url, cached_src = cache_get(name)
            if cached_url is not None:
                if cached_url:
                    ws, site = check_and_analyze(cached_url)
                    extra.update(site)
                else:
                    ws = {"status": "none", "code": None}
                fetch_ratings(b, name, extra)
                return cached_url, ws, cached_src + "_cache", extra

            # 2. Skip catene note
            name_lower = name.lower()
            if any(chain in name_lower for chain in _KNOWN_CHAINS):
                return "", {"status": "none", "code": None}, "", extra

            # 3. Serper
            if reserve_serper():
                s_city = display_name.split(",")[0].strip() if display_name else ""
                sd = search_serper(name, b.get("address", ""), serper_key, search_city=s_city)
                found = sd.get("website", "")
                if sd.get("rating") is not None:
                    extra["rating"]       = sd["rating"]
                    extra["review_count"] = sd.get("review_count")
                # TripAdvisor rating for food/cafe/hotel types
                btype_lower = (b.get("type") or "").lower()
                if btype_lower in _TA_TYPES and reserve_serper():
                    ta = search_tripadvisor_rating(name, b.get("address", ""), serper_key, search_city=s_city)
                    if ta.get("ta_rating") is not None:
                        extra["ta_rating"]       = ta["ta_rating"]
                        extra["ta_review_count"] = ta.get("ta_review_count")
                source = "google"
                if not found and reserve_serper():
                    found = search_organic_website(name, b.get("address", ""), serper_key, search_city=s_city)
                    if found:
                        source = "google_organic"

                cache_set(name, found, source)
                if found:
                    ws, site = check_and_analyze(found)
                    extra.update(site)
                    return found, ws, source, extra
                return "", {"status": "none", "code": None}, "", extra

            return "", {"status": "none", "code": None}, "", extra

        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as ex:
            results = list(ex.map(check_one, businesses))
        for b, (found_url, res, source, extra) in zip(businesses, results):
            if found_url and not b.get("website"):
                b["website"] = found_url
                b["website_source"] = source
            b["website_status"] = res["status"]
            b["website_code"]   = res.get("code")
            if extra.get("email") and not b.get("email"):
                b["email"] = extra["email"]
            for field in ("rating", "review_count", "ta_rating", "ta_review_count", "site_platform", "site_copyright_year", "site_mobile_ok"):
                if extra.get(field) is not None:
                    b[field] = extra[field]

    with_website    = sum(1 for b in businesses if b["website"])
    without_website = len(businesses) - with_website

    # Auto-salva la ricerca
    cat_label = OSM_CATEGORIES.get(category, {}).get("label", category)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT INTO searches (created_at,location,display_name,category,category_label,radius_km,result_count,has_check,results_json) VALUES (?,?,?,?,?,?,?,?,?)",
            (datetime.now().isoformat(), location, display_name, category, cat_label,
             radius_km, len(businesses), int(do_check), json.dumps(businesses, ensure_ascii=False))
        )
        conn.commit()

    return jsonify({
        "businesses": businesses,
        "total": len(businesses),
        "with_website": with_website,
        "without_website": without_website,
        "location": {"lat": lat, "lon": lon, "display_name": display_name},
        "radius_km": radius_km,
        "checked": do_check,
    })


@app.route("/api/searches", methods=["GET"])
def list_searches():
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT id,created_at,location,display_name,category,category_label,radius_km,result_count,has_check FROM searches ORDER BY created_at DESC LIMIT 60"
        ).fetchall()
    return jsonify([dict(r) for r in rows])


@app.route("/api/searches/<int:sid>", methods=["GET"])
def get_search(sid):
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM searches WHERE id=?", (sid,)).fetchone()
    if not row:
        return jsonify({"error": "Not found"}), 404
    d = dict(row)
    d["businesses"] = json.loads(d.pop("results_json", "[]"))
    d["total"] = d["result_count"]
    d["with_website"]    = sum(1 for b in d["businesses"] if b.get("website"))
    d["without_website"] = d["total"] - d["with_website"]
    d["checked"]   = any(b.get("website_status") not in (None, "none") for b in d["businesses"])
    d["has_check"] = d["checked"]
    d["location_input"] = d.get("location", "")
    return jsonify(d)


@app.route("/api/cache", methods=["DELETE"])
def clear_cache():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("DELETE FROM website_cache")
        conn.commit()
    return jsonify({"ok": True})


@app.route("/api/config", methods=["GET"])
def get_config():
    cfg = load_config()
    return jsonify({"serper_key": cfg.get("serper_key", ""), "serper_limit": cfg.get("serper_limit", 50)})

@app.route("/api/config", methods=["POST"])
def set_config():
    data = request.get_json()
    cfg = load_config()
    cfg["serper_key"]   = (data.get("serper_key") or "").strip()
    cfg["serper_limit"] = int(data.get("serper_limit") or 50)
    save_config(cfg)
    return jsonify({"ok": True})


@app.route("/api/searches/<int:sid>", methods=["DELETE"])
def delete_search(sid):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("DELETE FROM searches WHERE id=?", (sid,))
        conn.commit()
    return jsonify({"ok": True})


@app.route("/proposal")
def proposal():
    name    = request.args.get("name", "Azienda")
    btype   = request.args.get("type", "")
    address = request.args.get("address", "")
    phone   = request.args.get("phone", "")
    email   = request.args.get("email", "")
    lat     = request.args.get("lat", "")
    lon     = request.args.get("lon", "")
    theme   = get_theme(btype)
    domain  = domain_suggestion(name)

    q = quote_plus(f"{name} {address}".strip())
    google_search = f"https://www.google.com/search?q={q}"
    google_maps   = (f"https://www.google.com/maps/search/{q}"
                     if not (lat and lon) else
                     f"https://www.google.com/maps/search/?api=1&query={lat},{lon}")

    return render_template("proposal.html",
        name=name, btype=btype, address=address, phone=phone,
        email=email, lat=lat, lon=lon, theme=theme, domain=domain,
        google_search=google_search, google_maps=google_maps)


@app.route("/logo")
def serve_logo():
    from flask import send_file
    path = os.path.join(os.path.dirname(__file__), "templates", "logo mio.png")
    return send_file(path, mimetype="image/png")


@app.route("/email")
def email_preview():
    name          = request.args.get("name", "Azienda")
    btype         = request.args.get("type", "")
    address       = request.args.get("address", "")
    city          = request.args.get("city", "")
    phone         = request.args.get("phone", "")
    email_addr    = request.args.get("email", "")
    lat           = request.args.get("lat", "")
    lon           = request.args.get("lon", "")
    rating        = request.args.get("rating", "")
    review_count  = request.args.get("review_count", "")
    ta_rating     = request.args.get("ta_rating", "")
    ta_review_count = request.args.get("ta_review_count", "")
    site_platform = request.args.get("site_platform", "")
    website       = request.args.get("website", "")
    website_status = request.args.get("website_status", "")
    theme         = get_theme(btype)
    # Embed logo as base64 so it always renders without depending on /logo route
    logo_b64 = ""
    try:
        logo_path = os.path.join(os.path.dirname(__file__), "templates", "logo mio.png")
        with open(logo_path, "rb") as f:
            logo_b64 = "data:image/png;base64," + base64.b64encode(f.read()).decode()
    except Exception:
        pass
    return render_template("email.html",
        name=name, btype=btype, address=address, city=city, phone=phone,
        email=email_addr, lat=lat, lon=lon,
        rating=rating, review_count=review_count,
        ta_rating=ta_rating, ta_review_count=ta_review_count,
        site_platform=site_platform, website=website, website_status=website_status,
        theme=theme, logo_b64=logo_b64)


@app.route("/api/notes", methods=["GET"])
def get_notes():
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT * FROM business_notes").fetchall()
    return jsonify([dict(r) for r in rows])


@app.route("/api/notes/<path:name_key>", methods=["POST"])
def save_note(name_key):
    data = request.get_json()
    status       = (data.get("status") or "nuovo").strip()[:20]
    note         = (data.get("note") or "")[:500]
    next_contact = (data.get("next_contact") or "").strip()[:10]
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO business_notes (name_key, status, note, next_contact, updated_at) VALUES (?,?,?,?,?)",
            (name_key, status, note, next_contact, datetime.now().isoformat())
        )
        conn.commit()
    return jsonify({"ok": True})


@app.route("/api/email-log", methods=["GET"])
def list_email_log():
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("""
            SELECT e.* FROM email_log e
            INNER JOIN (
                SELECT name_key, MAX(sent_at) AS max_sent FROM email_log GROUP BY name_key
            ) m ON e.name_key = m.name_key AND e.sent_at = m.max_sent
        """).fetchall()
    return jsonify([dict(r) for r in rows])


@app.route("/api/email-log/<path:name_key>", methods=["POST"])
def log_email_sent(name_key):
    data     = request.get_json()
    name     = (data.get("name") or "")[:200]
    subject  = (data.get("subject") or "")[:300]
    template = (data.get("template") or "")[:100]
    lang     = (data.get("lang") or "")[:10]
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT INTO email_log (name_key, name, subject, template, lang, sent_at) VALUES (?,?,?,?,?,?)",
            (name_key, name, subject, template, lang, datetime.now().isoformat())
        )
        conn.commit()
    return jsonify({"ok": True})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=True, port=port, threaded=True)
