# CampusNest AI
AI-powered student housing recommendations for UVA students.

## Team
| Name | Computing ID |
|------|-------------|
| Norah Alghamdi | nwm3fj |
| Tina Fout | mpf5ss |
| Zachary Moore | sqr3xb |

## Problem
UVA students search for off-campus housing across many scattered platforms with no way to evaluate listings relative to their campus schedule or commute needs. CampusNest ranks listings by the best trade-off between affordability and commute convenience, with natural-language explanations for each recommendation.

## Architecture
1. **Flask API** — `POST /api/recommendations` loads listings, applies constraints, scores, and returns ranked results with explanations.
2. **Constraint scoring** — `scoring.py` filters by budget and bedrooms, applies max commute when commute data exists, and ranks by composite cost + location + amenities signals.
3. **Location + Google Maps** — `location_service.py` resolves destinations using `data/uva_buildings.csv` (name/aliases → lat/lng), optional Google Geocoding, and optional Google Distance Matrix for per-listing commute minutes. Results are cached under `data/` (see below).
4. **RAG-style explanations** — `rag.py` selects short context chunks per listing; `explainer.py` calls OpenAI when `OPENAI_API_KEY` is set, otherwise uses a deterministic template fallback.

## Project structure
```
campusnest-ai/
├── frontend/           # Static UI (served by Flask from /)
│   ├── index.html
│   ├── styles.css
│   └── app.js
├── data/
│   ├── zillow_dataset.json   # Listing corpus
│   ├── uva_buildings.csv     # Campus building names → coordinates
│   ├── location_cache.json   # Created at runtime (geocode cache)
│   └── commute_cache.json    # Created at runtime (Distance Matrix cache)
├── server.py           # Flask app + routes
├── scoring.py
├── location_service.py
├── rag.py
├── explainer.py
├── requirements.txt
├── test_scoring.py
├── test_explainer.py
├── index.html          # Redirects to frontend/ (optional entry)
└── README.md
```

## Stack
- **Backend:** Python 3, Flask  
- **Frontend:** HTML, CSS, vanilla JavaScript  
- **Optional APIs:** Google Maps (Geocoding, Distance Matrix), OpenAI Chat Completions  

## Prerequisites
- Python 3.11+ recommended (3.13 works).  
- On macOS, Homebrew Python is **PEP 668**–managed: do not `pip install` into the system interpreter; use a venv (below).

## Setup
From the repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt
```

### Environment variables (optional)

| Variable | Purpose |
|----------|---------|
| `OPENAI_API_KEY` | Enables LLM explanations in `explainer.py`. If unset, explanations use a simple template. |
| `GOOGLE_MAPS_API_KEY` | Enables Geocoding + Distance Matrix for destinations not in `uva_buildings.csv` and for accurate commute minutes. If unset, commute uses Haversine + mode speed heuristic when coordinates exist. |
| `PORT` | HTTP port for Flask (default **5050**). |

Example:

```bash
export OPENAI_API_KEY="sk-..."
export GOOGLE_MAPS_API_KEY="AIza..."
export PORT=5050
```

## Run
Start the combined backend and UI:

```bash
source .venv/bin/activate
python3 -u server.py
```

Open in a browser: **http://127.0.0.1:5050** (or `http://localhost:5050`).

### Why not port 5000?
On many Macs, **AirPlay Receiver** listens on port **5000** and returns **HTTP 403**. This project defaults to **5050** to avoid that conflict. Override with `PORT` if needed.

### Health check
```bash
curl -s http://127.0.0.1:5050/health
```

## API

### `POST /api/recommendations`
**Request body** (same shape the frontend sends):

```json
{
  "studentProfile": {
    "budget": 1800,
    "bedrooms": "1",
    "commuteConstraintMinutes": 30,
    "destination": "Rice Hall",
    "transportMode": "walking",
    "preferences": ["petFriendly", "inUnitLaundry"],
    "notes": ""
  },
  "metadata": {
    "createdAt": "2026-04-30T12:00:00.000Z",
    "source": "frontend-user-input"
  }
}
```

**Response** (abbreviated): `destination` (resolved coordinates if any), `count`, and `listings` array with scoring fields, `estimated_commute_minutes`, `explanation`, and `retrieved_context`.

## Frontend
1. Open the app URL (see **Run**).
2. Fill budget, bedrooms, max commute, primary destination (e.g. building name from `uva_buildings.csv`), transport mode, and optional preference checkboxes.
3. Click **Show Matching Listings** — the UI calls the API and renders cards (price, commute, AI or template explanation).
4. Form values persist in `localStorage` for quick iteration.

## Development notes
- **Static assets:** `index.html` references `./app.js` and `./styles.css`; Flask serves those from the `frontend/` directory at the site root so paths resolve correctly.
- **Tests:** `python3 test_scoring.py` and `python3 test_explainer.py` are smoke scripts, not a pytest suite.
- **Caches:** `data/location_cache.json` and `data/commute_cache.json` are written when Google APIs are used; safe to delete to force refresh.

## Evaluation (course goals)
- Ranking quality: Precision@5 / NDCG@5 on synthetic student profiles.  
- Explanation quality: manual rubric on LLM outputs.  
- Commute accuracy: MAE vs Google Maps when API key is enabled.
