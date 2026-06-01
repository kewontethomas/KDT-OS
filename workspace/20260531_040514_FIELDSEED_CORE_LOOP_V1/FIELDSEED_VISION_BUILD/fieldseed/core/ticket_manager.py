from .database import connect, now
from .fact_engine import analyze_intake

def create_ticket(text, site="", contact_name="", contact_phone="", contact_email=""):
    a = analyze_intake(text)
    con = connect()
    cur = con.cursor()
    ts = now()
    cur.execute("""
        INSERT INTO tickets(created_at, updated_at, title, site, contact_name, contact_phone, contact_email, category, confirmed_system, access_mode, access_tool, raw_intake, confirmed_facts, unknowns, next_action, completeness)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (ts, ts, a["title"], site, contact_name, contact_phone, contact_email, a["category"], a["confirmed_system"], a["access_mode"], a["access_tool"], text, "\n".join(a["confirmed_facts"]), "\n".join(a["unknowns"]), a["next_action"], a["completeness"]))
    tid = cur.lastrowid
    con.commit()
    con.close()
    return tid

def update_ticket(ticket_id, note, result=""):
    con = connect()
    ts = now()
    con.execute("INSERT INTO timeline(ticket_id, created_at, note, result) VALUES (?, ?, ?, ?)", (ticket_id, ts, note, result))
    row = con.execute("SELECT raw_intake, confirmed_facts FROM tickets WHERE id=?", (ticket_id,)).fetchone()
    if row:
        combined = f"{row[0] or ''}\n{row[1] or ''}\n{note}\n{result}"
        a = analyze_intake(combined)
        con.execute("""
            UPDATE tickets SET updated_at=?, category=?, confirmed_system=?, access_mode=?, access_tool=?, confirmed_facts=?, unknowns=?, next_action=?, completeness=?
            WHERE id=?
        """, (ts, a["category"], a["confirmed_system"], a["access_mode"], a["access_tool"], "\n".join(a["confirmed_facts"]), "\n".join(a["unknowns"]), a["next_action"], a["completeness"], ticket_id))
    con.commit()
    con.close()

def close_ticket(ticket_id, root_cause, resolution):
    con = connect()
    ts = now()
    con.execute("UPDATE tickets SET updated_at=?, status='Closed', root_cause=?, resolution=?, completeness=100, next_action='' WHERE id=?", (ts, root_cause, resolution, ticket_id))
    row = con.execute("SELECT title, category, confirmed_system, confirmed_facts FROM tickets WHERE id=?", (ticket_id,)).fetchone()
    if row:
        title, category, system, facts = row
        con.execute("""
            INSERT INTO knowledge(created_at, source_ticket_id, pattern, category, confirmed_system, symptoms, root_cause, fix, confidence, confirmed, success_count)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 100, 1, 1)
        """, (ts, ticket_id, title, category, system, facts, root_cause, resolution))
    con.commit()
    con.close()

def list_tickets(limit=100):
    con = connect()
    rows = con.execute("""
        SELECT id,title,status,category,confirmed_system,access_mode,access_tool,completeness,next_action,updated_at
        FROM tickets
        ORDER BY CASE status WHEN 'Open' THEN 0 WHEN 'In Progress' THEN 1 WHEN 'Waiting' THEN 2 ELSE 3 END, updated_at DESC
        LIMIT ?
    """, (limit,)).fetchall()
    con.close()
    return rows

def get_ticket(ticket_id):
    con = connect()
    row = con.execute("SELECT * FROM tickets WHERE id=?", (ticket_id,)).fetchone()
    if not row:
        con.close()
        return None, []
    cols = [d[0] for d in con.execute("SELECT * FROM tickets WHERE id=?", (ticket_id,)).description]
    timeline = con.execute("SELECT created_at,note,result,evidence_path FROM timeline WHERE ticket_id=? ORDER BY id", (ticket_id,)).fetchall()
    con.close()
    return dict(zip(cols, row)), timeline


def list_open_tickets(limit=100):
    con = connect()
    rows = con.execute("""
        SELECT id,title,status,category,confirmed_system,access_mode,access_tool,completeness,next_action,updated_at
        FROM tickets
        WHERE status!='Closed'
        ORDER BY updated_at DESC
        LIMIT ?
    """, (limit,)).fetchall()
    con.close()
    return rows

def set_ticket_status(ticket_id, status):
    con = connect()
    con.execute("UPDATE tickets SET updated_at=?, status=? WHERE id=?", (now(), status, ticket_id))
    con.commit()
    con.close()


def search_tickets(query="", status_filter="All", limit=100):
    q = f"%{query.strip()}%"
    con = connect()
    params = []
    where = []
    if query.strip():
        where.append("""(
            title LIKE ? OR site LIKE ? OR contact_name LIKE ? OR contact_phone LIKE ? OR contact_email LIKE ?
            OR category LIKE ? OR confirmed_system LIKE ? OR access_mode LIKE ? OR access_tool LIKE ?
            OR raw_intake LIKE ? OR confirmed_facts LIKE ? OR unknowns LIKE ? OR next_action LIKE ?
        )""")
        params.extend([q] * 13)
    if status_filter != "All":
        where.append("status=?")
        params.append(status_filter)

    sql = """
        SELECT id,title,status,site,contact_name,category,confirmed_system,access_mode,access_tool,completeness,next_action,updated_at
        FROM tickets
    """
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY updated_at DESC LIMIT ?"
    params.append(limit)
    rows = con.execute(sql, params).fetchall()
    con.close()
    return rows

def get_recent_ticket_choices(limit=25):
    con = connect()
    rows = con.execute("""
        SELECT id,title,status,site,contact_name,category,confirmed_system,updated_at
        FROM tickets
        ORDER BY updated_at DESC
        LIMIT ?
    """, (limit,)).fetchall()
    con.close()
    return rows

def attach_evidence_to_ticket(ticket_id, evidence_path, note="Evidence package attached"):
    con = connect()
    con.execute(
        "INSERT INTO timeline(ticket_id, created_at, note, result, evidence_path) VALUES (?, ?, ?, ?, ?)",
        (ticket_id, now(), note, "", evidence_path)
    )
    con.execute("UPDATE tickets SET updated_at=? WHERE id=?", (now(), ticket_id))
    con.commit()
    con.close()
