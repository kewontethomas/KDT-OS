import json
import urllib.request
from .truth_gate import search_knowledge, safe_answer
from .database import connect, now

def ollama_online():
    try:
        urllib.request.urlopen("http://127.0.0.1:11434/api/tags", timeout=1)
        return True
    except Exception:
        return False

def save_chat(role, content):
    con = connect()
    con.execute("INSERT INTO ai_memory(created_at, role, content) VALUES (?, ?, ?)", (now(), role, content))
    con.commit()
    con.close()

def ask_fieldseed(prompt, model="llama3.1:8b"):
    save_chat("user", prompt)
    result = search_knowledge(prompt)

    if not result["has_answer"]:
        ans = safe_answer(prompt)
        save_chat("assistant", ans)
        return ans

    grounded_answer = result["match"]["message"]

    if not ollama_online():
        save_chat("assistant", grounded_answer)
        return grounded_answer

    full_prompt = f"""You are FieldSeed Brain.

Rewrite the grounded answer below in a natural, helpful technician tone.
Do not add new facts.
Do not add troubleshooting steps that are not already in the grounded answer.
Do not guess.
If the grounded answer says it is only similar knowledge, keep the uncertainty clear.

Grounded FieldSeed answer:
{grounded_answer}

User asked:
{prompt}

Final response:"""

    try:
        payload = json.dumps({"model": model, "prompt": full_prompt, "stream": False, "options": {"temperature": 0.05}}).encode("utf-8")
        req = urllib.request.Request("http://127.0.0.1:11434/api/generate", data=payload, headers={"Content-Type":"application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="ignore"))
        ans = data.get("response", "").strip() or grounded_answer
    except Exception:
        ans = grounded_answer

    save_chat("assistant", ans)
    return ans
