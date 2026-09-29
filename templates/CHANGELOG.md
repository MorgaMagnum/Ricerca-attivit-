# Changelog — email.html

---

## 2026-07-24

### Progetti portfolio aggiornati (PORTFOLIO_ITEMS)
- Sostituiti i 3 progetti precedenti (Net7 screenshot, RESPOND, ESPAD) con i progetti reali del portfolio:
  - **Net7** — immagine Cloudinary, link `/portfolio/net-7-sito-web/`
  - **Premio Cambiamenti 2026** — immagine Cloudinary, link `/portfolio/premio-cambiamenti-2026/`
  - **Confindustria Nautica** — immagine Cloudinary, link `/portfolio/confindustria-nautica-italiana/`
- Immagini ora ospitate su Cloudinary (whitelistate da Gmail, visibili senza blocchi)
- Layout alternato: img sinistra / img destra / img sinistra

### Sezione portfolio — fix grafico (buildPortfolioTable)
- Estratta la logica di costruzione tabella in funzione separata `buildPortfolioTable()` (riutilizzabile)
- Corretto bug strutturale: il gutter (spazio vuoto) era sempre a sinistra del testo invece che tra immagine e testo; con `imgRight:true` immagine e testo risultavano attaccati
- Larghezza immagini portata a pixel fissi `width:240px` (prima usava `width:48%`, inaffidabile nei table)
- Rimossi `height:162px` e `object-fit:cover` dalle immagini (Outlook non li supporta, causava distorsioni)
- Aggiunto `max-width:240px` e `height:auto` per scaling proporzionale cross-client
- Colore descrizione esplicitato a `color:#555555` (prima ereditava colori da antenati)
- Separatori tra i progetti: linea `#e8e8e8` con padding verticale uniforme (22px sopra e sotto)
- Titolo sezione cambiato da "I miei ultimi progetti" a "Alcuni dei progetti che ho realizzato"

### Saluto personalizzato per categoria (SALUTE)
- Aggiunta mappa `SALUTE_PREFIX` con prefisso specifico per ogni `themeKey`:
  - food → "Gentili proprietari del ristorante"
  - cafe → "Gentili proprietari del bar"
  - wellness → "Gentili proprietari del salone"
  - sport → "Gentili titolari della palestra"
  - hotel → "Gentili titolari della struttura ricettiva"
  - health → "Gentili titolari dello studio medico"
  - professional → "Gentili titolari dello studio professionale"
  - realestate → "Gentili titolari dell'agenzia immobiliare"
  - automotive → "Gentili titolari dell'officina"
  - retail → "Gentili proprietari del negozio"
  - tech → "Gentili titolari del negozio"
  - craft → "Gentili titolari dell'attività"
  - default → "Gentili proprietari"
- Il nome attività ora appare in `<strong>` dopo il prefisso (es. "Gentili proprietari del ristorante **La Trattoria**,")

### Template 1 · La Ricerca — aggiunta sezione portfolio
- Rimossa la frase generica "Se volete, posso mostrarvi qualche esempio del mio lavoro"
- Aggiunta sezione portfolio completa (`buildPortfolioTable()`) dopo l'highlight
- CTA "Richiedi un preventivo gratuito" spostato **dopo** i progetti (era prima, troppo prematuro)
- Aggiunta frase conclusiva breve prima del CTA

### Fallback email client (buildRichEmailHTML)
- Aggiunta inizializzazione MSO `<!--[if mso]><xml><o:OfficeDocumentSettings>...<![endif]-->` per rendering corretto a 96dpi in Outlook
- Tutti i colori `rgba()` sostituiti con colori solidi equivalenti (Outlook non supporta rgba):
  - `rgba(255,255,255,.85)` → `#d4d4d4`
  - `rgba(255,255,255,.88)` → `#e0e0e0`
  - `rgba(255,255,255,.65)` → `#a6a6a6`
- Aggiunto `role="presentation"` su tutte le tabelle layout
- Aggiunto `mso-table-lspace:0pt;mso-table-rspace:0pt` su tutte le tabelle (elimina gap indesiderati in Outlook)
- Aggiunto `mso-line-height-rule:exactly` sulle celle decorative teal
- Aggiunto bottone VML `<v:roundrect>` come fallback per Outlook 2007-2021 (Outlook ignora border-radius sui link)
- Media query mobile aggiuntiva `.em-port-img` per immagini portfolio responsive su client mobili
- Gradiente `linear-gradient` sui separatori teal rimosso (non supportato in Outlook) → sostituito con `bgcolor:#1abc9c` solido
