import re
from .database import connect

STOP = {
    "the","and","for","with","that","this","have","has","you","your","are","was","were",
    "can","could","would","should","what","when","where","why","how","from","into",
    "about","issue","problem","help","work","working","system","device","computer",
    "server","customer","user","users"
}

def terms(text):
    return set(w for w in re.findall(r"[a-z0-9]{3,}", (text or "").lower()) if w not in STOP)

def explain_match(query):
    q = terms(query)
    if not q:
        return {"state": "unknown", "message": "I need more detail before I can search FieldSeed knowledge."}

    con = connect()
    rows = []

    for r in con.execute("""
        SELECT id, pattern, category, confirmed_system, symptoms, root_cause, fix, confidence, success_count
        FROM knowledge
        ORDER BY id DESC
    """):
        data = {
            "id": r[0], "pattern": r[1], "category": r[2], "confirmed_system": r[3],
            "symptoms": r[4], "root_cause": r[5], "fix": r[6],
            "confidence": r[7], "success_count": r[8]
        }
        hay = " ".join(str(v or "") for v in data.values())
        score = len(q & terms(hay))
        if score:
            rows.append((score + 10, "knowledge", data))

    for r in con.execute("""
        SELECT id, title, category, confirmed_system, confirmed_facts, root_cause, resolution
        FROM tickets
        WHERE status='Closed'
        ORDER BY updated_at DESC
    """):
        data = {
            "id": r[0], "title": r[1], "category": r[2], "confirmed_system": r[3],
            "confirmed_facts": r[4], "root_cause": r[5], "resolution": r[6]
        }
        hay = " ".join(str(v or "") for v in data.values())
        score = len(q & terms(hay))
        if score:
            rows.append((score + 6, "closed_ticket", data))

    con.close()
    rows.sort(reverse=True, key=lambda x: x[0])

    if not rows or rows[0][0] < 12:
        return {
            "state": "unknown",
            "message": (
                "I do not have a confirmed knowledge match for that yet.\n\n"
                "I will not guess. Start or update a ticket, add what you find, then close it with the confirmed root cause and fix so I can know it next time."
            )
        }

    best_score, source, data = rows[0]
    state = "confirmed" if best_score >= 18 else "similar"

    lines = []
    if state == "confirmed":
        lines.append("I found confirmed FieldSeed knowledge that matches this.")
    else:
        lines.append("I found something similar in FieldSeed, but I would treat it as related knowledge, not a guaranteed fix.")
    lines.append("")

    if source == "knowledge":
        lines.append(f"Knowledge #{data['id']}")
        lines.append(f"System: {data.get('confirmed_system') or 'Unknown'}")
        lines.append(f"Pattern: {data.get('pattern') or 'Not recorded'}")
        if data.get("symptoms"):
            lines.append(f"Known symptoms: {data.get('symptoms')}")
        if data.get("root_cause"):
            lines.append(f"Confirmed root cause: {data.get('root_cause')}")
        if data.get("fix"):
            lines.append(f"Confirmed fix: {data.get('fix')}")
        lines.append(f"Success count: {data.get('success_count')}")
    else:
        lines.append(f"Closed Ticket #{data['id']}")
        lines.append(f"System: {data.get('confirmed_system') or 'Unknown'}")
        lines.append(f"Ticket: {data.get('title')}")
        if data.get("root_cause"):
            lines.append(f"Confirmed root cause: {data.get('root_cause')}")
        if data.get("resolution"):
            lines.append(f"Confirmed resolution: {data.get('resolution')}")

    lines.append("")
    lines.append("I am only using saved FieldSeed knowledge here. If the current issue differs, add new findings to the ticket before treating this as the fix.")

    return {"state": state, "message": "\n".join(lines), "source": source, "data": data, "score": best_score}
