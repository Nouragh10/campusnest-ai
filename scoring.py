import math
import json


def parse_price(value):
    if isinstance(value, (int, float)):
        return float(value)

    if not isinstance(value, str):
        return None

    digits = "".join(ch for ch in value if ch.isdigit() or ch == ".")
    if not digits:
        return None

    return float(digits)


def get_listing_price(listing):
    if isinstance(listing.get("minBaseRent"), (int, float)):
        return float(listing["minBaseRent"])

    if isinstance(listing.get("unformattedPrice"), (int, float)):
        return float(listing["unformattedPrice"])

    units = listing.get("units", [])
    prices = []

    for unit in units:
        price = parse_price(unit.get("price"))
        if price is not None:
            prices.append(price)

    if prices:
        return min(prices)

    return None


def normalize_bedrooms(value):
    if value is None:
        return None

    if isinstance(value, (int, float)):
        return int(value)

    value = str(value).lower()

    if "studio" in value:
        return 0

    digits = "".join(ch for ch in value if ch.isdigit())
    if not digits:
        return None

    return int(digits)


def get_available_bedrooms(listing):
    units = listing.get("units", [])
    bedrooms = []

    for unit in units:
        beds = normalize_bedrooms(unit.get("beds"))
        if beds is not None:
            bedrooms.append(beds)

    return bedrooms


def has_bedroom_match(listing, requested_bedrooms):
    if requested_bedrooms is None:
        return True

    available = get_available_bedrooms(listing)

    if not available:
        return True

    if requested_bedrooms == 3:
        return any(bed >= 3 for bed in available)

    return any(bed == requested_bedrooms for bed in available)


def get_lat_lng(listing):
    lat_long = listing.get("latLong", {})

    lat = lat_long.get("latitude") or listing.get("latitude")
    lng = lat_long.get("longitude") or listing.get("longitude")

    if lat is None or lng is None:
        return None, None

    return float(lat), float(lng)


def haversine_miles(lat1, lon1, lat2, lon2):
    radius = 3958.8

    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)

    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    )

    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return radius * c


def estimate_commute_minutes(listing, destination):
    listing_lat, listing_lng = get_lat_lng(listing)

    if listing_lat is None or listing_lng is None:
        return None

    dest_lat = destination.get("lat")
    dest_lng = destination.get("lng")

    if dest_lat is None or dest_lng is None:
        return None

    distance = haversine_miles(listing_lat, listing_lng, dest_lat, dest_lng)

    mode = destination.get("transport_mode", "walk")

    if mode == "drive":
        speed_mph = 20
    elif mode == "bus":
        speed_mph = 12
    else:
        speed_mph = 3

    return (distance / speed_mph) * 60


def normalize(value, min_value, max_value):
    if value is None:
        return 1.0

    if max_value == min_value:
        return 0.0

    return (value - min_value) / (max_value - min_value)


def passes_hard_constraints(listing, constraints):
    price = get_listing_price(listing)

    if price is None:
        return False

    budget_max = constraints.get("budget_max") or constraints.get("budget")

    if budget_max is not None and price > budget_max:
        return False

    requested_bedrooms = constraints.get("bedrooms")
    requested_bedrooms = normalize_bedrooms(requested_bedrooms)

    if not has_bedroom_match(listing, requested_bedrooms):
        return False

    return True


def calculate_amenities_score(listing, constraints):
    requested = constraints.get("amenities") or constraints.get("preferences") or []

    if not requested:
        return 0.0

    listing_text = json.dumps(listing).lower()

    matched = 0
    for amenity in requested:
        if str(amenity).lower() in listing_text:
            matched += 1

    missing_ratio = 1 - (matched / len(requested))
    return missing_ratio


def score_listings(listings, constraints, destination=None, limit=10):
    filtered = []

    for listing in listings:
        if not passes_hard_constraints(listing, constraints):
            continue

        price = get_listing_price(listing)
        commute = estimate_commute_minutes(listing, destination) if destination else None

        item = listing.copy()
        item["rent"] = price
        item["estimated_commute_minutes"] = commute

        filtered.append(item)

    if not filtered:
        return []

    rents = [item["rent"] for item in filtered if item["rent"] is not None]
    commutes = [
        item["estimated_commute_minutes"]
        for item in filtered
        if item["estimated_commute_minutes"] is not None
    ]

    min_rent = min(rents)
    max_rent = max(rents)

    min_commute = min(commutes) if commutes else 0
    max_commute = max(commutes) if commutes else 1

    alpha = constraints.get("alpha", 0.5)

    scored = []

    for item in filtered:
        cost_score = normalize(item["rent"], min_rent, max_rent)

        if item["estimated_commute_minutes"] is None:
            location_score = 1.0
        else:
            location_score = normalize(
                item["estimated_commute_minutes"],
                min_commute,
                max_commute
            )

        amenities_score = calculate_amenities_score(item, constraints)

        size_score = 0.0

        composite_score = (
            alpha * cost_score
            + (1 - alpha) * location_score
            + 0.15 * amenities_score
        )

        item["cost_score"] = round(cost_score, 3)
        item["location_score"] = round(location_score, 3)
        item["size_score"] = round(size_score, 3)
        item["amenities_score"] = round(amenities_score, 3)
        item["composite_score"] = round(composite_score, 3)

        scored.append(item)

    scored.sort(key=lambda x: x["composite_score"])

    return scored[:limit]


def find_cheaper_alternatives(target_listing, scored_listings, max_commute_difference=5, limit=2):
    target_rent = target_listing.get("rent")
    target_commute = target_listing.get("estimated_commute_minutes")

    if target_rent is None or target_commute is None:
        return []

    alternatives = []

    for listing in scored_listings:
        if listing.get("id") == target_listing.get("id"):
            continue

        rent = listing.get("rent")
        commute = listing.get("estimated_commute_minutes")

        if rent is None or commute is None:
            continue

        if rent < target_rent and abs(commute - target_commute) <= max_commute_difference:
            alternatives.append(listing)

    alternatives.sort(key=lambda x: x["rent"])

    return alternatives[:limit]