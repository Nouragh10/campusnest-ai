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
1. **Constraint Scoring** — filters and ranks listings by a composite cost + commute score
2. **Commute Estimation** — Google Maps Directions API with caching and Haversine fallback
3. **RAG Explanation** — LLM generates grounded 1-2 sentence explanation per listing

## Project Structure
```
campusnest-ai/
├── backend/
├── frontend/
├── data/
│   └── uva_buildings.csv
└── README.md
```

## Stack
- Backend: Python, Flask
- Frontend: React
- APIs: Google Maps Directions, OpenAI
- Libraries: Pandas, OpenAI Python SDK

## Evaluation
- Ranking quality: Precision@5 and NDCG@5 on 30-50 synthetic student profiles
- Explanation quality: Manual scoring of 50 LLM-generated explanations
- Commute accuracy: Mean absolute error vs. Google Maps ground truth
