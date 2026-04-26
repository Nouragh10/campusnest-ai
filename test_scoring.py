import json
from scoring import score_listings, find_cheaper_alternatives


with open("data/zillow_dataset.json", "r", encoding="utf-8") as file:
    listings = json.load(file)


constraints = {
    "budget": 1400,
    "bedrooms": "1",
    "preferences": ["parking", "laundry"],
    "alpha": 0.5
}


destination = {
    "name": "Rice Hall",
    "lat": 38.0312,
    "lng": -78.5107,
    "transport_mode": "walk"
}


results = score_listings(
    listings=listings,
    constraints=constraints,
    destination=destination,
    limit=10
)


print("Top results:")

for listing in results:
    print(
        listing.get("statusText") or listing.get("buildingName") or "Unknown listing",
        "| rent:",
        listing.get("rent"),
        "| commute:",
        listing.get("estimated_commute_minutes"),
        "| score:",
        listing.get("composite_score")
    )


if results:
    alternatives = find_cheaper_alternatives(results[0], results)
    print("\nCheaper alternatives for top result:")

    for alt in alternatives:
        print(
            alt.get("statusText") or alt.get("buildingName") or "Unknown listing",
            "| rent:",
            alt.get("rent"),
            "| commute:",
            alt.get("estimated_commute_minutes")
        )