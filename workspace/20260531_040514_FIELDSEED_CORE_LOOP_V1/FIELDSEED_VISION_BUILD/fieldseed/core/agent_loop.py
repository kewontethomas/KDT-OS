import py_compile
from fieldseed.paths import ROOT
from .database import connect, self_check_record, add_improvement

def run_health_check():
    failures = []
    checked = 0
    for py in ROOT.rglob("*.py"):
        try:
            py_compile.compile(str(py), doraise=True)
            checked += 1
        except Exception as e:
            failures.append((str(py.relative_to(ROOT)), str(e)))
    if failures:
        self_check_record("python_compile", "FAIL", f"{len(failures)} failure(s)", str(failures[:5]))
        add_improvement("active_agent", "Python compile failure detected", str(failures[:5]), "Repair failing files.")
    else:
        self_check_record("python_compile", "OK", f"{checked} Python files compiled", "")
    con = connect()
    open_tickets = con.execute("SELECT id,title,next_action FROM tickets WHERE status='Open' ORDER BY updated_at DESC LIMIT 5").fetchall()
    con.close()
    self_check_record("open_ticket_watch", "OK", f"{len(open_tickets)} open ticket(s)", "")
    return {"checked": checked, "failures": failures, "open_tickets": open_tickets}
