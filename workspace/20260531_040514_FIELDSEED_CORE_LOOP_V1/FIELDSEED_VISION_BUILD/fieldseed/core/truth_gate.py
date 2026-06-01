from .knowledge_understanding import explain_match

def search_knowledge(query):
    match = explain_match(query)
    return {
        "has_answer": match.get("state") in ("confirmed", "similar"),
        "confidence": 90 if match.get("state") == "confirmed" else 55 if match.get("state") == "similar" else 0,
        "match": match,
    }

def safe_answer(query):
    return explain_match(query)["message"]
