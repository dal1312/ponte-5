# Ponte Unified App

Sito statico/PWA unificato per **Al Ponte di Schiavonia**.

Il progetto combina:

- frontend statico derivato da `PONTE-quattro`;
- menu reale esportato da Dishcovery;
- pipeline di aggiornamento dati con `tools/refresh_menu.py`;
- app ordine via WhatsApp con carrello locale.

## Struttura

```text
.
├── index.html
├── menu.html
├── ordina.html
├── contatti.html
├── css/styles.css
├── js/main.js
├── js/menu-data.js
├── data/restaurant.json
├── data/menu.csv
├── assets/dishcovery-images/
├── tools/refresh_menu.py
└── manifest.json
```

## Uso locale

```bash
python -m http.server 8080
```

Apri:

```text
http://localhost:8080/
```

## Aggiornare il menu da Dishcovery

Setup:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Aggiornamento da API:

```bash
python tools/refresh_menu.py
```

Aggiornamento dal JSON locale:

```bash
python tools/refresh_menu.py --from-file
```

Output aggiornati:

- `data/restaurant.json`
- `data/menu.csv`
- `js/menu-data.js`
- `assets/dishcovery-images/`

## Deploy

La cartella e' statica: puo' essere pubblicata su GitHub Pages, Netlify, Vercel o qualsiasi hosting HTTP.
