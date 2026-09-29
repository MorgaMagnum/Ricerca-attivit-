# Ricerca attività

Web app locale per trovare attività commerciali in una zona e individuare quelle **senza sito web** (o con un sito rotto o solo social), cioè i potenziali clienti per chi realizza siti.

Usa i dati gratuiti di OpenStreetMap. La chiave Serper.dev per le ricerche Google è facoltativa.

## Funzionalità

- **Ricerca per zona:** città o indirizzo, raggio da 0,5 a 60 km, 22 categorie (ristoranti, parrucchieri, avvocati, officine, negozi...).
- **Verifica siti:** controlla se il sito risponde e, con Serper, cerca su Google il sito delle attività che su OpenStreetMap non ce l'hanno. Recupera anche email, rating Google e TripAdvisor. I risultati restano in cache per 30 giorni.
- **Analisi del sito:** piattaforma usata, anno del copyright, compatibilità mobile.
- **Filtri e ordinamento:** con/senza sito, sito rotto, solo social, con/senza email, rating minimo, punteggio di priorità del lead.
- **Mappa:** vista Tabella/Mappa con i puntini colorati per stato del sito e il raggio di ricerca.
- **CRM leggero:** stato del contatto (nuovo, contattato, trattativa, chiuso, perso), note, data del prossimo contatto, gruppi, esclusi, registro delle email inviate.
- **Proposta ed email:** genera un'anteprima di sito su misura per l'attività e un'email di presentazione.
- **Storico:** ogni ricerca viene salvata e si può riaprire. Esportazione CSV.

## Requisiti

- Python 3.8 o superiore
- Connessione internet (Overpass, Nominatim, eventualmente Serper)

## Installazione

```bash
git clone https://github.com/MorgaMagnum/Ricerca-attivit-.git
cd Ricerca-attivit-
pip install -r requirements.txt
```

## Avvio

```bash
python app.py
```

Poi apri http://localhost:5000. Su Windows puoi anche fare doppio clic su `avvia.bat`.

Per usare un'altra porta imposta la variabile d'ambiente `PORT`, ad esempio in PowerShell:

```powershell
$env:PORT = "5050"; python app.py
```

## Configurazione (facoltativa)

Senza configurazione l'app funziona con i soli dati OpenStreetMap. Per la ricerca dei siti su Google:

1. Crea una chiave gratuita su [serper.dev](https://serper.dev) (2.500 ricerche al mese).
2. Inseriscila dal pannello **Impostazioni** nella barra laterale, oppure copia `config.example.json` in `config.json` e compila i campi:

```json
{
  "serper_key": "la-tua-chiave",
  "serper_limit": 50
}
```

`serper_limit` è il numero massimo di chiamate Serper per singola ricerca.

`config.json` è escluso da git: la chiave non finisce nel repository.

## Dati e backup

- Ricerche, cache dei siti, note CRM e registro email stanno in `searches.db` (SQLite), creato al primo avvio.
- A ogni avvio viene fatto un backup giornaliero in `backups/`; vengono tenuti gli ultimi 14.
- `searches.db` e `backups/` sono esclusi da git.

## Note sui raggi grandi

Con raggi sopra i 30–40 km in zone dense, i server Overpass pubblici possono essere lenti o rifiutare la query. Il tempo limite è di 5 minuti per server (con 3 server di riserva). Per le ricerche ampie conviene usare categorie specifiche.

## Struttura

```
app.py                  backend Flask: ricerca, verifica siti, CRM, API
templates/index.html    interfaccia principale
templates/proposal.html anteprima del sito proposto
templates/email.html    generatore email di presentazione
config.example.json     modello di configurazione
avvia.bat               avvio rapido su Windows
```

## Crediti dati

Dati © [OpenStreetMap](https://www.openstreetmap.org/copyright) contributors, tramite Overpass API e Nominatim.
