import csv
import json
import os
import urllib.parse
import urllib.request
from pathlib import Path


DATA_DIR = Path(__file__).parent / "data"
BUILDINGS_CSV = DATA_DIR / "uva_buildings.csv"
LOCATION_CACHE_FILE = DATA_DIR / "location_cache.json"
COMMUTE_CACHE_FILE = DATA_DIR / "commute_cache.json"


def _load_json(path):
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def _save_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump(data, file, indent=2)


def load_building_coordinates():
    if not BUILDINGS_CSV.exists():
        return {}

    result = {}
    with BUILDINGS_CSV.open("r", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        for row in reader:
            name = str(row.get("name", "")).strip()
            lat = row.get("lat")
            lng = row.get("lng")
            aliases = str(row.get("aliases", "")).strip()
            if not name or not lat or not lng:
                continue
            key_names = [name]
            if aliases:
                key_names.extend(alias.strip() for alias in aliases.split("|") if alias.strip())
            for key in key_names:
                result[key.lower()] = {
                    "name": name,
                    "lat": float(lat),
                    "lng": float(lng),
                    "source": "local_csv",
                }
    return result


def _maps_get_json(url):
    with urllib.request.urlopen(url, timeout=12) as response:
        content = response.read().decode("utf-8")
    return json.loads(content)


def geocode_destination(destination_name):
    destination = destination_name.strip()
    if not destination:
        return None

    local = load_building_coordinates()
    key = destination.lower()
    if key in local:
        return local[key]

    cache = _load_json(LOCATION_CACHE_FILE)
    if key in cache:
        return cache[key]

    api_key = os.getenv("GOOGLE_MAPS_API_KEY", "").strip()
    if not api_key:
        return None

    query = urllib.parse.quote(f"{destination}, Charlottesville VA")
    url = (
        "https://maps.googleapis.com/maps/api/geocode/json"
        f"?address={query}&key={api_key}"
    )
    data = _maps_get_json(url)
    if data.get("status") != "OK" or not data.get("results"):
        return None

    first = data["results"][0]
    loc = first["geometry"]["location"]
    result = {
        "name": first.get("formatted_address", destination),
        "lat": float(loc["lat"]),
        "lng": float(loc["lng"]),
        "source": "google_geocode",
    }
    cache[key] = result
    _save_json(LOCATION_CACHE_FILE, cache)
    return result


def _commute_cache_key(listing_id, destination_key, transport_mode):
    return f"{listing_id}|{destination_key}|{transport_mode}"


def get_commute_lookup(listings, destination, transport_mode):
    if not destination:
        return {}

    destination_key = str(destination.get("name", "destination")).lower()
    cache = _load_json(COMMUTE_CACHE_FILE)
    api_key = os.getenv("GOOGLE_MAPS_API_KEY", "").strip()
    lookup = {}

    for listing in listings:
        listing_id = str(listing.get("id") or listing.get("zpid") or "")
        lat_long = listing.get("latLong") or {}
        origin_lat = lat_long.get("latitude") or listing.get("latitude")
        origin_lng = lat_long.get("longitude") or listing.get("longitude")
        if not listing_id or origin_lat is None or origin_lng is None:
            continue

        cache_key = _commute_cache_key(listing_id, destination_key, transport_mode)
        if cache_key in cache:
            lookup[listing_id] = cache[cache_key]
            continue

        if not api_key:
            continue

        origins = urllib.parse.quote(f"{origin_lat},{origin_lng}")
        destinations = urllib.parse.quote(f"{destination['lat']},{destination['lng']}")
        url = (
            "https://maps.googleapis.com/maps/api/distancematrix/json"
            f"?origins={origins}&destinations={destinations}&mode={transport_mode}&key={api_key}"
        )

        data = _maps_get_json(url)
        rows = data.get("rows", [])
        if not rows or not rows[0].get("elements"):
            continue
        element = rows[0]["elements"][0]
        if element.get("status") != "OK":
            continue
        duration = element.get("duration", {})
        seconds = duration.get("value")
        if seconds is None:
            continue
        minutes = round(float(seconds) / 60.0, 1)
        lookup[listing_id] = minutes
        cache[cache_key] = minutes

    _save_json(COMMUTE_CACHE_FILE, cache)
    return lookup
