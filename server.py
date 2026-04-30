import json
import os
from pathlib import Path

from flask import Flask, abort, jsonify, request, send_from_directory

from explainer import generate_explanation
from location_service import geocode_destination, get_commute_lookup
from rag import retrieve_context
from scoring import passes_hard_constraints, score_listings


ROOT = Path(__file__).parent
DATASET_PATH = ROOT / "data" / "zillow_dataset.json"
FRONTEND_DIR = ROOT / "frontend"

_listings_cache = None


def load_listings():
    global _listings_cache
    if _listings_cache is not None:
        return _listings_cache
    print("CampusNest: loading listings from data/zillow_dataset.json ...", flush=True)
    with DATASET_PATH.open("r", encoding="utf-8") as file:
        _listings_cache = json.load(file)
    print(f"CampusNest: ready ({len(_listings_cache)} listings).", flush=True)
    return _listings_cache

PREFERENCE_MAP = {
    "petFriendly": "pet",
    "inUnitLaundry": "washer",
    "furnished": "furnished",
    "parkingIncluded": "parking",
}


def _normalize_transport(mode):
    mode = str(mode or "driving").lower()
    if mode in {"drive", "driving"}:
        return "driving"
    if mode in {"walk", "walking"}:
        return "walking"
    if mode in {"bike", "bicycling"}:
        return "bicycling"
    if mode in {"bus", "transit"}:
        return "transit"
    return "driving"


def _extract_constraints(payload):
    profile = payload.get("studentProfile", {})
    preferences = [PREFERENCE_MAP.get(pref, pref) for pref in profile.get("preferences", [])]
    return {
        "budget_max": profile.get("budget"),
        "bedrooms": profile.get("bedrooms"),
        "commute_max": profile.get("commuteConstraintMinutes"),
        "transport_mode": _normalize_transport(profile.get("transportMode")),
        "destination": profile.get("destination"),
        "preferences": preferences,
        "notes": profile.get("notes"),
    }


def _median_stats(scored):
    if not scored:
        return {}
    rents = sorted(item.get("rent", 0) for item in scored if item.get("rent") is not None)
    commute = sorted(
        item.get("estimated_commute_minutes")
        for item in scored
        if item.get("estimated_commute_minutes") is not None
    )
    return {
        "median_rent": rents[len(rents) // 2] if rents else None,
        "median_commute": commute[len(commute) // 2] if commute else None,
    }


app = Flask(__name__, static_folder="frontend", static_url_path="/frontend")


@app.get("/")
def index():
    return send_from_directory(FRONTEND_DIR, "index.html")


@app.get("/<path:filename>")
def frontend_assets(filename):
    # Serve frontend static assets from root so ./app.js and ./styles.css work.
    if filename.startswith("api/"):
        abort(404)
    asset_path = FRONTEND_DIR / filename
    if asset_path.exists() and asset_path.is_file():
        return send_from_directory(FRONTEND_DIR, filename)
    abort(404)


@app.get("/health")
def health():
    return jsonify({"ok": True})


@app.post("/api/recommendations")
def recommendations():
    payload = request.get_json(force=True, silent=True) or {}
    constraints = _extract_constraints(payload)
    destination = geocode_destination(constraints.get("destination", ""))
    listings = load_listings()

    prefiltered = [
        listing for listing in listings
        if passes_hard_constraints(listing, constraints)
    ]
    commute_lookup = get_commute_lookup(
        prefiltered,
        destination,
        constraints.get("transport_mode", "driving"),
    )

    destination_for_score = None
    if destination:
        destination_for_score = {
            "lat": destination["lat"],
            "lng": destination["lng"],
            "transport_mode": constraints.get("transport_mode", "driving"),
            "commute_lookup": commute_lookup,
        }

    scored = score_listings(
        prefiltered,
        constraints,
        destination=destination_for_score,
        limit=10,
    )
    medians = _median_stats(scored)

    enriched = []
    for listing in scored:
        context = retrieve_context(listing, constraints, destination)
        explanation = generate_explanation(listing, constraints, medians, context)
        item = listing.copy()
        item["explanation"] = explanation
        item["retrieved_context"] = context
        enriched.append(item)

    return jsonify(
        {
            "destination": destination,
            "count": len(enriched),
            "listings": enriched,
        }
    )


if __name__ == "__main__":
    # use_reloader=False: avoids a second process that can look like a "hang" with no output.
    # Default 5050: macOS often uses port 5000 for AirPlay Receiver (Control Center), which returns 403.
    port = int(os.environ.get("PORT", "5050"))
    print(f"\nCampusNest server — open http://127.0.0.1:{port} in your browser", flush=True)
    print("Press Ctrl+C in this terminal to stop the server.\n", flush=True)
    load_listings()
    app.run(debug=True, port=port, use_reloader=False)
