# test_explainer.py

from explainer import generate_explanation

# Synthetic listing
test_listing = {
    "id": "listing_001",
    "address": "123 Main St, Charlottesville, VA",
    "rent": 900,
    "pets_allowed": False,
    "parking_included": False,
    "amenities": ["washer", "dryer", "dishwasher"],
    "cost_score": 0.82,
    "location_score": 0.74,
    "size_score": 0.65,
    "amenities_score": 0.70,
    "composite_score": 0.73
}

# Synthetic student constraints
test_constraints = {
    "budget_min": 700,
    "budget_max": 1000,
    "roommates": 1,
    "pets": False,
    "lease_start": "2025-08-01",
    "lease_end": "2026-07-31",
    "amenities": ["washer"]
}

# Synthetic median stats from the filtered listing set
test_median_stats = {
    "rent": 1050,
    "cost_score": 0.65,
    "location_score": 0.70,
    "size_score": 0.60,
    "amenities_score": 0.65
}

if __name__ == "__main__":
    print("Running explanation generation test...\n")
    result = generate_explanation(test_listing, test_constraints, test_median_stats)
    print("Result:")
    print(f"  Explanation: {result['explanation_text']}")
    print(f"  Highlighted Features: {result['highlighted_features']}")