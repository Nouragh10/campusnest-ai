import json
import re


def _tokenize(text):
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def _listing_chunks(listing, destination, constraints):
    amenities = []
    recommendation = listing.get("listCardRecommendation", {})
    zov = recommendation.get("zovInsight", {})
    if zov.get("displayString"):
        amenities.append(zov["displayString"])

    units = listing.get("units") or []
    unit_summary = ", ".join(f"{u.get('beds')} bed at {u.get('price')}" for u in units[:4] if u.get("beds"))
    chunks = [
        f"Building name: {listing.get('buildingName') or listing.get('statusText') or 'Unknown'}",
        f"Address: {listing.get('address') or 'Unavailable'}",
        f"Rent range: min {listing.get('minBaseRent')} max {listing.get('maxBaseRent')}",
        f"Unit options: {unit_summary or 'Unavailable'}",
        f"Destination: {destination.get('name') if destination else constraints.get('destination', 'Unknown')}",
        f"Preference hints: {json.dumps(constraints.get('preferences') or [])}",
        f"Listing insight amenities: {', '.join(amenities) if amenities else 'None detected'}",
    ]
    return chunks


def retrieve_context(listing, constraints, destination, top_k=3):
    query = " ".join(
        [
            str(constraints.get("destination", "")),
            str(constraints.get("notes", "")),
            " ".join(str(item) for item in constraints.get("preferences", [])),
            str(constraints.get("bedrooms", "")),
        ]
    )
    query_tokens = _tokenize(query)
    chunks = _listing_chunks(listing, destination, constraints)

    scored = []
    for chunk in chunks:
        chunk_tokens = _tokenize(chunk)
        overlap = len(query_tokens.intersection(chunk_tokens))
        scored.append((overlap, chunk))

    scored.sort(key=lambda pair: pair[0], reverse=True)
    best = [chunk for _, chunk in scored[:top_k]]
    return best
