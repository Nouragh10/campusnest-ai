import json
import os
agent = None


def _get_agent():
    global agent
    if agent is not None:
        return agent

    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        return None

    try:
        import openai
    except ModuleNotFoundError:
        return None

    agent = openai.OpenAI(api_key=api_key)
    return agent

SYSTEM_PROMPT = """
You are a housing recommendation assistant for UVA students.
Given a listing and a student's constraints, write a 1-2 sentence explanation
of why this listing is a good match. You must ONLY reference facts provided
to you. Respond in JSON with keys: explanation_text, highlighted_features.
"highlighted_features" should only include positive attributes of the listing. 
In "highlighted_features", do not include restrictions or things the listing lacks, do not include the scores. 
"""

def build_context_packet(listing: dict, constraints: dict, median_stats: dict, retrieved_context: list | None) -> str:
    return f"""
    Listing: {json.dumps(listing)}
    Constraints: {json.dumps(constraints)}
    Median Stats: {json.dumps(median_stats)}
    Retrieved Context Chunks: {json.dumps(retrieved_context or [])}
    Rent: {listing['rent']}
    Score Breakdown: cost_score={listing['cost_score']}, location_score={listing['location_score']}, size_score={listing['size_score']}, amenities_score={listing['amenities_score']}
    """

def _fallback_explanation(listing, constraints, retrieved_context):
    building = listing.get("buildingName") or listing.get("statusText") or "This listing"
    rent = listing.get("rent")
    commute = listing.get("estimated_commute_minutes")
    destination = constraints.get("destination") or "campus"
    context_sentence = retrieved_context[0] if retrieved_context else "Matches your requested constraints."
    rent_text = f"${rent:.0f}/month" if isinstance(rent, (int, float)) else "a competitive monthly rent"
    commute_text = (
        f"about {commute:.1f} minutes from {destination}"
        if isinstance(commute, (int, float))
        else f"within reach of {destination}"
    )

    explanation = (
        f"{building} is a solid fit for your budget and bedroom constraints. "
        f"It offers {rent_text} and is {commute_text}. "
        f"{context_sentence}"
    )
    return {
        "explanation_text": explanation,
        "highlighted_features": [context_sentence],
    }


def generate_explanation(listing: dict, constraints: dict, median_stats: dict, retrieved_context: list | None = None) -> dict:
    llm_agent = _get_agent()
    if not llm_agent:
        return _fallback_explanation(listing, constraints, retrieved_context or [])

    context = build_context_packet(listing, constraints, median_stats, retrieved_context)
    response = llm_agent.chat.completions.create(
        model="gpt-4o-mini",
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": context}
        ]
    )
    result = json.loads(response.choices[0].message.content)
    return validate_explanation(result, listing)

def explanation_correction(result: dict, listing: dict, violations: list) -> dict:
    violations_str = ", ".join(violations)
    correction_instruction = f"""
Your previous explanation incorrectly mentioned: {violations_str}.
These features are NOT present in this listing. 
Rewrite the explanation without referencing them.
Previous explanation: {result["explanation_text"]}
Listing facts: {json.dumps(listing)}
"""
    llm_agent = _get_agent()
    if not llm_agent:
        return result
    response = llm_agent.chat.completions.create(
        model="gpt-4o-mini",
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": correction_instruction}
        ]
    )
    corrected = json.loads(response.choices[0].message.content)

    # Avoid infinite loop — only try once
    return corrected

def validate_explanation(result: dict, listing: dict) -> dict:
    explanation = result["explanation_text"].lower()
    violations = []

    # Define checkable claims
    checks = {
        "pet": bool(listing.get("pets_allowed", False)),
        "parking": bool(listing.get("parking_included", False)),
        "gym": "gym" in str(listing).lower(),
        "washer": "washer" in str(listing).lower(),
        # add more as needed
    }

    for keyword, is_true in checks.items():
        if keyword in explanation and not is_true:
            violations.append(keyword)

    if violations:
        # Re-prompt with a correction instruction
        return explanation_correction(result, listing, violations)
    
    return result