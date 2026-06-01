import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext
import threading
import os
import json

from fieldseed.core.database import init_db, connect
from fieldseed.core.ticket_manager import create_ticket, update_ticket, close_ticket, list_tickets, get_ticket, search_tickets, get_recent_ticket_choices, attach_evidence_to_ticket, list_open_tickets, set_ticket_status, search_tickets, get_recent_ticket_choices, attach_evidence_to_ticket
from fieldseed.core.ai_bridge import ask_fieldseed, ollama_online
from fieldseed.core.agent_loop import run_health_check
from fieldseed.core.core_loop import core_loop_tick, recent_core_memory, recent_observer_events
from fieldseed.core.evidence_engine import import_evidence, find_packages
from fieldseed.core.self_healing import visual_self_inspection, create_repair_plan, apply_repair_plan, analyze_screenshot_file, list_repair_candidates
from fieldseed.modes.collector import collect
from fieldseed.paths import TOOLS, EVIDENCE

class FieldSeedApp(tk.Tk):
    def __init__(self):
        super().__init__()
        init_db()
        self.title("FieldSeed Vision Build - Truth-Locked IT Intelligence")
        self.geometry("1360x860")
        self.minsize(1050, 700)
        self.colors = {"bg":"#050a18","panel":"#0c1630","card":"#111f43","card2":"#1d3970","text":"#f6fbff","muted":"#b8c7e6","accent":"#22d3ee","good":"#34d399","warn":"#fbbf24","danger":"#fb7185","line":"#2a4b86"}
        self.current_ticket_id = None
        self.configure(bg=self.colors["bg"])
        self.build()

    def build(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        sidebar = tk.Frame(self, bg=self.colors["panel"], width=245)
        sidebar.grid(row=0, column=0, sticky="ns")
        sidebar.grid_propagate(False)
        tk.Label(sidebar, text="🌱 FieldSeed", bg=self.colors["panel"], fg=self.colors["accent"], font=("Segoe UI", 22, "bold")).pack(anchor="w", padx=18, pady=(18,2))
        tk.Label(sidebar, text="Truth • Evidence • Growth", bg=self.colors["panel"], fg=self.colors["muted"], font=("Segoe UI", 9)).pack(anchor="w", padx=18, pady=(0,16))
        for page in ["Dashboard","Open Tickets","Search Tickets","Tickets","Brain","Collector","Evidence","Knowledge","Rescue","Growth"]:
            tk.Button(sidebar, text=page, anchor="w", command=lambda p=page:self.show(p), bg=self.colors["panel"], fg=self.colors["text"], activebackground=self.colors["card2"], activeforeground=self.colors["text"], bd=0, padx=16, pady=10).pack(fill="x", padx=8, pady=2)
        self.main = tk.Frame(self, bg=self.colors["bg"])
        self.main.grid(row=0, column=1, sticky="nsew")
        self.main.grid_columnconfigure(0, weight=1)
        self.main.grid_rowconfigure(2, weight=1)
        header = tk.Frame(self.main, bg=self.colors["bg"])
        header.grid(row=0, column=0, sticky="ew", padx=20, pady=(16,6))
        header.grid_columnconfigure(0, weight=1)
        self.title_label = tk.Label(header, text="Dashboard", bg=self.colors["bg"], fg=self.colors["text"], font=("Segoe UI", 23, "bold"))
        self.title_label.grid(row=0, column=0, sticky="w")
        self.ai_badge = tk.Label(header, text="AI: checking", bg=self.colors["card"], fg=self.colors["accent"], padx=10, pady=5)
        self.ai_badge.grid(row=0, column=1, padx=6)
        self.summary = tk.Label(self.main, text="", bg=self.colors["bg"], fg=self.colors["muted"], anchor="w")
        self.summary.grid(row=1, column=0, sticky="ew", padx=20)
        self.content = tk.Frame(self.main, bg=self.colors["bg"])
        self.content.grid(row=2, column=0, sticky="nsew", padx=20, pady=10)
        self.content.grid_columnconfigure(0, weight=1)
        self.content.grid_rowconfigure(0, weight=1)
        self.status_var = tk.StringVar(value="Ready")
        tk.Label(self.main, textvariable=self.status_var, bg=self.colors["panel"], fg=self.colors["muted"], anchor="w", padx=12, pady=5).grid(row=3, column=0, sticky="ew")
        self.show("Dashboard")
        self.after(1000, self.update_ai_badge)
        self.after(4000, self.active_agent_tick)

    def update_ai_badge(self):
        online = ollama_online()
        self.ai_badge.config(text="AI: online" if online else "AI: offline", fg=self.colors["good"] if online else self.colors["warn"])
        self.after(8000, self.update_ai_badge)

    def active_agent_tick(self):
        try:
            summary = core_loop_tick(run_deep=False)
            health = summary.get("health") or {}
            tickets = summary.get("tickets") or {}
            repairs = summary.get("repair_queue") or []
            checked = health.get("checked", 0) if isinstance(health, dict) else 0
            failures = len(health.get("failures", [])) if isinstance(health, dict) else 0
            open_count = tickets.get("open", 0) if isinstance(tickets, dict) else 0
            self.status_var.set(f"Core Loop: {checked} files checked, {failures} failures, {open_count} open ticket(s), {len(repairs)} repair candidate(s)")
        except Exception as e:
            self.status_var.set(f"Core Loop issue: {e}")
        self.after(180000, self.active_agent_tick)

    def clear(self):
        for w in self.content.winfo_children():
            w.destroy()

    def show(self, page):
        self.clear()
        self.title_label.config(text=page)
        getattr(self, "page_" + page.lower().replace(" ", "_"), self.page_dashboard)()

    def button(self, parent, text, command, kind="default"):
        bg = {"default":self.colors["card2"],"primary":self.colors["accent"],"good":self.colors["good"],"warn":self.colors["warn"],"danger":self.colors["danger"]}.get(kind,self.colors["card2"])
        fg = "#001018" if kind in ["primary","good","warn"] else self.colors["text"]
        return tk.Button(parent, text=text, command=command, bg=bg, fg=fg, bd=0, padx=12, pady=8, font=("Segoe UI",9,"bold"))

    def scroll_page(self):
        outer = tk.Frame(self.content, bg=self.colors["bg"])
        outer.grid(row=0, column=0, sticky="nsew")
        outer.grid_columnconfigure(0, weight=1)
        outer.grid_rowconfigure(0, weight=1)
        canvas = tk.Canvas(outer, bg=self.colors["bg"], highlightthickness=0, bd=0)
        bar = tk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        inner = tk.Frame(canvas, bg=self.colors["bg"])
        win = canvas.create_window((0,0), window=inner, anchor="nw")
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfigure(win, width=e.width))
        canvas.configure(yscrollcommand=bar.set)
        canvas.grid(row=0, column=0, sticky="nsew")
        bar.grid(row=0, column=1, sticky="ns")
        inner.grid_columnconfigure(0, weight=1)
        return inner

    def card(self, parent, title, body):
        f = tk.Frame(parent, bg=self.colors["card"], highlightbackground=self.colors["line"], highlightthickness=1)
        tk.Label(f, text=title, bg=self.colors["card"], fg=self.colors["text"], font=("Segoe UI",14,"bold")).pack(anchor="w", padx=14, pady=(12,3))
        tk.Message(f, text=body, bg=self.colors["card"], fg=self.colors["muted"], width=560, font=("Segoe UI",10)).pack(anchor="w", fill="x", padx=14, pady=(0,12))
        return f

    def page_dashboard(self):
        self.summary.config(text="A portable technician brain that refuses to guess and grows only from confirmed truth.")
        p = self.scroll_page()
        p.grid_columnconfigure((0,1), weight=1)
        items = [
            ("🎫 Tickets","Talk naturally. FieldSeed separates confirmed facts from unknowns and will not guess the system.","Tickets","primary"),
            ("🧠 Brain","Truth-locked AI. It only speaks from confirmed knowledge or asks for evidence.","Brain","good"),
            ("🧰 Collector","Run on another device without AI. It gathers evidence and brings it back to Brain Mode.","Collector","warn"),
            ("🌱 Growth","Active agent watches health, open tickets, and real improvement opportunities.","Growth","primary"),
        ]
        for i,(title,body,page,kind) in enumerate(items):
            c = self.card(p,title,body)
            c.grid(row=i//2, column=i%2, sticky="nsew", padx=8, pady=8)
            self.button(c,"Open",lambda p=page:self.show(p),kind).pack(anchor="w", padx=14, pady=(0,14))
        feed = tk.Frame(p, bg=self.colors["card"], highlightbackground=self.colors["accent"], highlightthickness=1)
        feed.grid(row=2, column=0, columnspan=2, sticky="ew", padx=8, pady=8)
        tk.Label(feed, text="Live System Feed", bg=self.colors["card"], fg=self.colors["accent"], font=("Segoe UI",15,"bold")).pack(anchor="w", padx=14, pady=(12,3))
        txt = scrolledtext.ScrolledText(feed, height=10, bg="#07111f", fg=self.colors["text"], bd=0, wrap="word")
        txt.pack(fill="both", expand=True, padx=14, pady=(0,14))
        con = connect()
        tickets = con.execute("SELECT id,title,status,completeness,next_action FROM tickets ORDER BY updated_at DESC LIMIT 5").fetchall()
        checks = con.execute("SELECT check_name,status,details FROM self_checks ORDER BY id DESC LIMIT 5").fetchall()
        ideas = con.execute("SELECT issue,suggested_fix,status FROM improvement_queue ORDER BY id DESC LIMIT 5").fetchall()
        con.close()
        txt.insert("end","Open Work:\\n" + ("\\n".join([f"#{i} [{s}] {t} ({c}%) | Next: {n}" for i,t,s,c,n in tickets]) or "No tickets yet."))
        txt.insert("end","\\n\\nActive Agent:\\n" + ("\\n".join([f"{n}: {s} - {d}" for n,s,d in checks]) or "No checks yet."))
        txt.insert("end","\\n\\nImprovement Queue:\\n" + ("\\n".join([f"[{s}] {i} -> {f}" for i,f,s in ideas]) or "No improvement ideas yet."))


    def page_open_tickets(self):
        self.summary.config(text="Track active work, add findings, and close tickets with confirmed solutions.")
        p = self.scroll_page()
        p.grid_columnconfigure(0, weight=1)

        top = tk.Frame(p, bg=self.colors["card"], highlightbackground=self.colors["line"], highlightthickness=1)
        top.grid(row=0, column=0, sticky="ew", pady=8)
        top.grid_columnconfigure(0, weight=1)
        tk.Label(top, text="Open Ticket Board", bg=self.colors["card"], fg=self.colors["text"], font=("Segoe UI", 15, "bold")).grid(row=0, column=0, sticky="w", padx=14, pady=(12, 3))
        tk.Message(
            top,
            text="Select a ticket by number, then add findings or close it with a confirmed solution. Closing a ticket automatically updates FieldSeed knowledge.",
            bg=self.colors["card"],
            fg=self.colors["muted"],
            width=820
        ).grid(row=1, column=0, sticky="w", padx=14, pady=(0,10))

        selector = tk.Frame(top, bg=self.colors["card"])
        selector.grid(row=2, column=0, sticky="w", padx=14, pady=(0, 12))
        tk.Label(selector, text="Ticket #:", bg=self.colors["card"], fg=self.colors["muted"]).pack(side="left")
        self.open_ticket_select = tk.StringVar()
        tk.Entry(selector, textvariable=self.open_ticket_select, bg=self.colors["card2"], fg=self.colors["text"], insertbackground=self.colors["text"], bd=0, width=10).pack(side="left", padx=8)
        self.button(selector, "Select", self.select_open_ticket, "primary").pack(side="left", padx=4)
        self.button(selector, "Refresh", self.refresh_open_tickets, "default").pack(side="left", padx=4)

        self.open_ticket_out = scrolledtext.ScrolledText(p, height=28, bg="#07111f", fg=self.colors["text"], bd=0, wrap="word")
        self.open_ticket_out.grid(row=1, column=0, sticky="nsew", pady=8)

        actions = tk.Frame(p, bg=self.colors["bg"])
        actions.grid(row=2, column=0, sticky="w")
        self.button(actions, "Add Finding To Selected", self.add_finding_ui, "good").pack(side="left", padx=4)
        self.button(actions, "Close Selected + Learn", self.close_ticket_ui, "warn").pack(side="left", padx=4)
        self.button(actions, "Mark Waiting", lambda: self.change_selected_status("Waiting"), "default").pack(side="left", padx=4)
        self.button(actions, "Mark In Progress", lambda: self.change_selected_status("In Progress"), "default").pack(side="left", padx=4)

        self.refresh_open_tickets()

    def refresh_open_tickets(self):
        if not hasattr(self, "open_ticket_out"):
            return
        self.open_ticket_out.delete("1.0", "end")
        rows = list_open_tickets()
        if not rows:
            self.open_ticket_out.insert("end", "No open tickets. Create one in Tickets.\n")
            return
        for r in rows:
            tid,title,status,category,system,access,tool,complete,next_action,updated = r
            self.open_ticket_out.insert("end", f"#{tid} [{status}] {title}\n")
            self.open_ticket_out.insert("end", f"Category: {category} | Confirmed System: {system} | Access: {access} {tool}\n")
            self.open_ticket_out.insert("end", f"Completeness: {complete}%\nNext: {next_action}\nUpdated: {updated}\n")
            self.open_ticket_out.insert("end", "-"*72 + "\n")

    def select_open_ticket(self):
        try:
            tid = int(self.open_ticket_select.get().strip())
        except Exception:
            messagebox.showinfo("Select Ticket", "Enter a valid ticket number.")
            return
        self.current_ticket_id = tid
        ticket, timeline = get_ticket(tid)
        if not ticket:
            messagebox.showinfo("Not found", f"Ticket #{tid} was not found.")
            return
        self.open_ticket_out.delete("1.0", "end")
        self.open_ticket_out.insert("end", self.render_ticket_text(ticket, timeline))

    def change_selected_status(self, status):
        if not self.current_ticket_id:
            messagebox.showinfo("No ticket selected", "Select a ticket first.")
            return
        set_ticket_status(self.current_ticket_id, status)
        self.refresh_open_tickets()

    def render_ticket_text(self, t, timeline):
        parts = []
        parts.append(f"Ticket #{t['id']}: {t['title']}")
        parts.append("")
        parts.append(f"Status: {t['status']}")
        parts.append(f"Site: {t.get('site', '')}")
        parts.append(f"Contact: {t.get('contact_name', '')} {t.get('contact_phone', '')} {t.get('contact_email', '')}")
        parts.append(f"Category: {t['category']}")
        parts.append(f"Confirmed System: {t['confirmed_system']}")
        parts.append(f"Access: {t['access_mode']} {t['access_tool']}")
        parts.append(f"Completeness: {t['completeness']}%")
        parts.append("")
        parts.append("Confirmed Facts:")
        parts.append(t["confirmed_facts"] or "None yet.")
        parts.append("")
        parts.append("Unknowns:")
        parts.append(t["unknowns"] or "No unknowns recorded.")
        parts.append("")
        parts.append("Next Action:")
        parts.append(t["next_action"] or "None.")
        parts.append("")
        parts.append("Timeline:")
        if timeline:
            for x in timeline:
                parts.append(f"- {x[0]} | {x[1]}")
                if x[2]:
                    parts.append(f"  Result: {x[2]}")
        else:
            parts.append("No timeline entries yet.")
        return "\n".join(parts)


    def page_search_tickets(self):
        self.summary.config(text="Find tickets by site, contact, issue words, system, status, notes, or anything related.")
        p = self.scroll_page()
        p.grid_columnconfigure(0, weight=1)

        box = tk.Frame(p, bg=self.colors["card"], highlightbackground=self.colors["line"], highlightthickness=1)
        box.grid(row=0, column=0, sticky="ew", pady=8)
        box.grid_columnconfigure(1, weight=1)

        tk.Label(box, text="Ticket Search", bg=self.colors["card"], fg=self.colors["text"], font=("Segoe UI", 15, "bold")).grid(row=0, column=0, columnspan=4, sticky="w", padx=14, pady=(12, 4))
        tk.Label(box, text="Search:", bg=self.colors["card"], fg=self.colors["muted"]).grid(row=1, column=0, sticky="w", padx=14, pady=8)

        self.ticket_search_var = tk.StringVar()
        tk.Entry(box, textvariable=self.ticket_search_var, bg=self.colors["card2"], fg=self.colors["text"], insertbackground=self.colors["text"], bd=0).grid(row=1, column=1, sticky="ew", padx=8, pady=8, ipady=5)

        self.ticket_status_filter = tk.StringVar(value="All")
        tk.OptionMenu(box, self.ticket_status_filter, "All", "Open", "In Progress", "Waiting", "Closed").grid(row=1, column=2, sticky="w", padx=8)
        self.button(box, "Search", self.run_ticket_search, "primary").grid(row=1, column=3, sticky="w", padx=8)

        select = tk.Frame(box, bg=self.colors["card"])
        select.grid(row=2, column=0, columnspan=4, sticky="w", padx=14, pady=(0,12))
        tk.Label(select, text="Open Ticket #:", bg=self.colors["card"], fg=self.colors["muted"]).pack(side="left")
        self.search_select_var = tk.StringVar()
        tk.Entry(select, textvariable=self.search_select_var, bg=self.colors["card2"], fg=self.colors["text"], insertbackground=self.colors["text"], bd=0, width=10).pack(side="left", padx=8)
        self.button(select, "Open Selected", self.open_ticket_from_search, "good").pack(side="left", padx=4)

        self.search_out = scrolledtext.ScrolledText(p, height=30, bg="#07111f", fg=self.colors["text"], bd=0, wrap="word")
        self.search_out.grid(row=1, column=0, sticky="nsew", pady=8)

        self.run_ticket_search()

    def run_ticket_search(self):
        if not hasattr(self, "search_out"):
            return
        query = self.ticket_search_var.get() if hasattr(self, "ticket_search_var") else ""
        status = self.ticket_status_filter.get() if hasattr(self, "ticket_status_filter") else "All"
        rows = search_tickets(query, status)
        self.search_out.delete("1.0", "end")
        if not rows:
            self.search_out.insert("end", "No matching tickets found.\n")
            return
        for r in rows:
            tid,title,status,site,contact,category,system,access,tool,complete,next_action,updated = r
            self.search_out.insert("end", f"#{tid} [{status}] {title}\n")
            self.search_out.insert("end", f"Site: {site} | Contact: {contact}\n")
            self.search_out.insert("end", f"Category: {category} | System: {system} | Access: {access} {tool}\n")
            self.search_out.insert("end", f"Completeness: {complete}% | Next: {next_action}\nUpdated: {updated}\n")
            self.search_out.insert("end", "-"*72 + "\n")

    def open_ticket_from_search(self):
        try:
            tid = int(self.search_select_var.get().strip())
        except Exception:
            messagebox.showinfo("Open Ticket", "Enter a valid ticket number.")
            return
        self.current_ticket_id = tid
        ticket, timeline = get_ticket(tid)
        if not ticket:
            messagebox.showinfo("Not Found", f"Ticket #{tid} was not found.")
            return
        self.search_out.delete("1.0", "end")
        if hasattr(self, "render_ticket_text"):
            self.search_out.insert("end", self.render_ticket_text(ticket, timeline))
        else:
            self.search_out.insert("end", str(ticket))

    def page_tickets(self):
        self.summary.config(text="Create technician tickets from messy customer language without assumptions.")
        p = self.scroll_page()
        p.grid_columnconfigure(0, weight=1)
        form = tk.Frame(p, bg=self.colors["card"], highlightbackground=self.colors["line"], highlightthickness=1)
        form.grid(row=0, column=0, sticky="ew", pady=8)
        form.grid_columnconfigure(0, weight=1)
        tk.Label(form, text="Tell FieldSeed what you know", bg=self.colors["card"], fg=self.colors["text"], font=("Segoe UI",14,"bold")).grid(row=0, column=0, sticky="w", padx=14, pady=(12,3))
        self.ticket_text = scrolledtext.ScrolledText(form, height=7, bg="#07111f", fg=self.colors["text"], insertbackground=self.colors["text"], bd=0, wrap="word")
        self.ticket_text.grid(row=1, column=0, sticky="ew", padx=14, pady=8)
        row = tk.Frame(form, bg=self.colors["card"])
        row.grid(row=2, column=0, sticky="w", padx=14, pady=(0,8))
        self.site_var = tk.StringVar()
        self.contact_name_var = tk.StringVar()
        self.contact_phone_var = tk.StringVar()
        self.contact_email_var = tk.StringVar()
        tk.Label(row, text="Site:", bg=self.colors["card"], fg=self.colors["muted"]).pack(side="left")
        tk.Entry(row, textvariable=self.site_var, bg=self.colors["card2"], fg=self.colors["text"], insertbackground=self.colors["text"], bd=0, width=22).pack(side="left", padx=6)
        tk.Label(row, text="Contact:", bg=self.colors["card"], fg=self.colors["muted"]).pack(side="left")
        tk.Entry(row, textvariable=self.contact_name_var, bg=self.colors["card2"], fg=self.colors["text"], insertbackground=self.colors["text"], bd=0, width=20).pack(side="left", padx=6)
        self.button(row,"Create Ticket",self.create_ticket_ui,"primary").pack(side="left", padx=6)

        row2 = tk.Frame(form, bg=self.colors["card"])
        row2.grid(row=3, column=0, sticky="w", padx=14, pady=(0,8))
        tk.Label(row2, text="Phone:", bg=self.colors["card"], fg=self.colors["muted"]).pack(side="left")
        tk.Entry(row2, textvariable=self.contact_phone_var, bg=self.colors["card2"], fg=self.colors["text"], insertbackground=self.colors["text"], bd=0, width=22).pack(side="left", padx=6)
        tk.Label(row2, text="Email:", bg=self.colors["card"], fg=self.colors["muted"]).pack(side="left")
        tk.Entry(row2, textvariable=self.contact_email_var, bg=self.colors["card2"], fg=self.colors["text"], insertbackground=self.colors["text"], bd=0, width=28).pack(side="left", padx=6)
        detail = tk.Frame(p, bg=self.colors["card"], highlightbackground=self.colors["line"], highlightthickness=1)
        detail.grid(row=1, column=0, sticky="nsew", pady=8)
        detail.grid_columnconfigure(0, weight=1)
        tk.Label(detail, text="Ticket Workspace", bg=self.colors["card"], fg=self.colors["text"], font=("Segoe UI",14,"bold")).grid(row=0, column=0, sticky="w", padx=14, pady=(12,3))
        self.ticket_out = scrolledtext.ScrolledText(detail, height=20, bg="#07111f", fg=self.colors["text"], bd=0, wrap="word")
        self.ticket_out.grid(row=1, column=0, sticky="nsew", padx=14, pady=8)
        actions = tk.Frame(detail, bg=self.colors["card"])
        actions.grid(row=2, column=0, sticky="w", padx=14, pady=(0,12))
        self.button(actions,"Add Finding",self.add_finding_ui,"good").pack(side="left", padx=4)
        self.button(actions,"Close + Learn",self.close_ticket_ui,"warn").pack(side="left", padx=4)
        self.button(actions,"Refresh",self.refresh_tickets,"default").pack(side="left", padx=4)
        self.refresh_tickets()

    def create_ticket_ui(self):
        text = self.ticket_text.get("1.0","end").strip()
        if not text:
            messagebox.showinfo("Missing info","Type what you know first.")
            return
        tid = create_ticket(text, self.site_var.get(), self.contact_name_var.get(), self.contact_phone_var.get(), self.contact_email_var.get())
        self.current_ticket_id = tid
        self.display_ticket(tid)

    def refresh_tickets(self):
        if not hasattr(self,"ticket_out"): return
        self.ticket_out.delete("1.0","end")
        for r in list_tickets():
            tid,title,status,category,system,access,tool,complete,next_action,updated = r
            self.ticket_out.insert("end",f"#{tid} [{status}] {title}\\nCategory: {category} | Confirmed System: {system} | Access: {access} {tool}\\nCompleteness: {complete}%\\nNext: {next_action}\\nUpdated: {updated}\\n\\n")


    def display_ticket(self, tid):
        t, timeline = get_ticket(tid)
        if not t:
            return
        self.ticket_out.delete("1.0","end")
        if hasattr(self, "render_ticket_text"):
            self.ticket_out.insert("end", self.render_ticket_text(t, timeline))
        else:
            self.ticket_out.insert("end", f"Ticket #{tid}: {t['title']}\n\nCategory: {t['category']}\nConfirmed System: {t['confirmed_system']}\nAccess: {t['access_mode']} {t['access_tool']}\nCompleteness: {t['completeness']}%\n\nConfirmed Facts:\n{t['confirmed_facts']}\n\nUnknowns:\n{t['unknowns']}\n\nNext Action:\n{t['next_action']}\n")

    def add_finding_ui(self):
        if not self.current_ticket_id:
            messagebox.showinfo("No ticket selected","Create a ticket first.")
            return
        win = tk.Toplevel(self); win.title("Add Finding"); win.geometry("620x420"); win.configure(bg=self.colors["bg"])
        tk.Label(win,text="What did you find?",bg=self.colors["bg"],fg=self.colors["text"]).pack(anchor="w",padx=12,pady=(10,2))
        note = scrolledtext.ScrolledText(win,height=8,bg="#07111f",fg=self.colors["text"],insertbackground=self.colors["text"],bd=0); note.pack(fill="both",expand=True,padx=12)
        tk.Label(win,text="Result / status",bg=self.colors["bg"],fg=self.colors["text"]).pack(anchor="w",padx=12,pady=(10,2))
        result = scrolledtext.ScrolledText(win,height=4,bg="#07111f",fg=self.colors["text"],insertbackground=self.colors["text"],bd=0); result.pack(fill="x",padx=12)
        def save():
            update_ticket(self.current_ticket_id, note.get("1.0","end").strip(), result.get("1.0","end").strip())
            win.destroy(); self.display_ticket(self.current_ticket_id)
            self.refresh_open_tickets() if hasattr(self, "refresh_open_tickets") else None
        self.button(win,"Save Finding",save,"primary").pack(pady=10)

    def close_ticket_ui(self):
        if not self.current_ticket_id:
            messagebox.showinfo("No ticket selected","Create a ticket first.")
            return
        win = tk.Toplevel(self); win.title("Close + Learn"); win.geometry("660x480"); win.configure(bg=self.colors["bg"])
        tk.Label(win,text="Confirmed root cause",bg=self.colors["bg"],fg=self.colors["text"]).pack(anchor="w",padx=12,pady=(10,2))
        root_box = scrolledtext.ScrolledText(win,height=6,bg="#07111f",fg=self.colors["text"],insertbackground=self.colors["text"],bd=0); root_box.pack(fill="x",padx=12)
        tk.Label(win,text="Confirmed resolution / fix",bg=self.colors["bg"],fg=self.colors["text"]).pack(anchor="w",padx=12,pady=(10,2))
        res_box = scrolledtext.ScrolledText(win,height=8,bg="#07111f",fg=self.colors["text"],insertbackground=self.colors["text"],bd=0); res_box.pack(fill="x",padx=12)
        def save():
            close_ticket(self.current_ticket_id, root_box.get("1.0","end").strip(), res_box.get("1.0","end").strip())
            win.destroy(); self.display_ticket(self.current_ticket_id)
            self.refresh_open_tickets() if hasattr(self, "refresh_open_tickets") else None
        self.button(win,"Close Ticket + Save Confirmed Knowledge",save,"warn").pack(pady=10)

    def page_brain(self):
        self.summary.config(text="Truth-locked assistant. It does not answer unless FieldSeed has confirmed knowledge.")
        frame = tk.Frame(self.content,bg=self.colors["bg"])
        frame.grid(row=0,column=0,sticky="nsew")
        frame.grid_columnconfigure(0,weight=1); frame.grid_rowconfigure(0,weight=1)
        self.brain_out = scrolledtext.ScrolledText(frame,bg="#07111f",fg=self.colors["text"],bd=0,wrap="word")
        self.brain_out.grid(row=0,column=0,sticky="nsew")
        self.brain_out.insert("end","FieldSeed Brain ready. Truth-locked mode is always on.\\n\\n")
        bottom = tk.Frame(frame,bg=self.colors["card"]); bottom.grid(row=1,column=0,sticky="ew",pady=(8,0)); bottom.grid_columnconfigure(0,weight=1)
        self.brain_in = tk.Text(bottom,height=3,bg=self.colors["card2"],fg=self.colors["text"],insertbackground=self.colors["text"],bd=0)
        self.brain_in.grid(row=0,column=0,sticky="ew",padx=8,pady=8)
        self.brain_in.bind("<Return>",lambda e:(self.send_brain(),"break")[1])
        self.button(bottom,"Send",self.send_brain,"primary").grid(row=0,column=1,padx=8)

    def send_brain(self):
        prompt = self.brain_in.get("1.0","end").strip()
        if not prompt: return
        self.brain_in.delete("1.0","end")
        self.brain_out.insert("end",f"You:\\n{prompt}\\n\\nFieldSeed:\\nThinking...\\n")
        def worker():
            try: ans = ask_fieldseed(prompt)
            except Exception as e: ans = f"I cannot answer safely: {e}\\nI will not guess without confirmed FieldSeed knowledge."
            self.after(0, lambda:self.brain_out.insert("end", ans+"\\n\\n"))
        threading.Thread(target=worker,daemon=True).start()


    def page_collector(self):
        self.summary.config(text="Create a collector mission before gathering evidence so every package knows the site, customer, issue, and access method.")
        p = self.scroll_page()
        p.grid_columnconfigure(0, weight=1)

        form = tk.Frame(p, bg=self.colors["card"], highlightbackground=self.colors["line"], highlightthickness=1)
        form.grid(row=0, column=0, sticky="ew", pady=8)
        form.grid_columnconfigure(1, weight=1)

        tk.Label(form, text="Collector Mission Setup", bg=self.colors["card"], fg=self.colors["text"], font=("Segoe UI", 15, "bold")).grid(row=0, column=0, columnspan=2, sticky="w", padx=14, pady=(12, 6))

        self.collect_site = tk.StringVar()
        self.collect_customer = tk.StringVar()
        self.collect_issue = tk.StringVar(value="Unknown")
        self.collect_ticket = tk.StringVar()
        self.collect_contact = tk.StringVar()
        self.collect_access = tk.StringVar(value="USB Collector")
        self.collect_level = tk.StringVar(value="Standard")

        fields = [
            ("Site / Building:", self.collect_site),
            ("Customer / Company:", self.collect_customer),
            ("Issue Type:", self.collect_issue),
            ("Ticket ID if known:", self.collect_ticket),
            ("Contact Person:", self.collect_contact),
        ]

        row = 1
        for label, var in fields:
            tk.Label(form, text=label, bg=self.colors["card"], fg=self.colors["muted"]).grid(row=row, column=0, sticky="w", padx=14, pady=5)
            tk.Entry(form, textvariable=var, bg=self.colors["card2"], fg=self.colors["text"], insertbackground=self.colors["text"], bd=0).grid(row=row, column=1, sticky="ew", padx=14, pady=5, ipady=5)
            row += 1

        tk.Label(form, text="Access Method:", bg=self.colors["card"], fg=self.colors["muted"]).grid(row=row, column=0, sticky="w", padx=14, pady=5)
        tk.OptionMenu(form, self.collect_access, "USB Collector", "Remote", "On Site", "Phone Support", "Rescue/WinRE").grid(row=row, column=1, sticky="w", padx=14, pady=5)
        row += 1

        tk.Label(form, text="Collection Level:", bg=self.colors["card"], fg=self.colors["muted"]).grid(row=row, column=0, sticky="w", padx=14, pady=5)
        tk.OptionMenu(form, self.collect_level, "Quick", "Standard", "Deep").grid(row=row, column=1, sticky="w", padx=14, pady=5)
        row += 1

        self.button(form, "Start Collector Mission", self.run_collector, "primary").grid(row=row, column=0, sticky="w", padx=14, pady=(10, 14))
        self.button(form, "Open Evidence Folder", lambda: os.startfile(str(EVIDENCE)), "default").grid(row=row, column=1, sticky="w", padx=14, pady=(10, 14))

        status = tk.Frame(p, bg=self.colors["card"], highlightbackground=self.colors["line"], highlightthickness=1)
        status.grid(row=1, column=0, sticky="ew", pady=8)
        status.grid_columnconfigure(0, weight=1)
        tk.Label(status, text="Collector Status", bg=self.colors["card"], fg=self.colors["text"], font=("Segoe UI", 14, "bold")).grid(row=0, column=0, sticky="w", padx=14, pady=(12, 3))

        self.collect_status = tk.StringVar(value="Ready.")
        tk.Label(status, textvariable=self.collect_status, bg=self.colors["card"], fg=self.colors["muted"], anchor="w").grid(row=1, column=0, sticky="ew", padx=14, pady=4)

        self.collect_canvas = tk.Canvas(status, height=22, bg="#07111f", highlightthickness=0)
        self.collect_canvas.grid(row=2, column=0, sticky="ew", padx=14, pady=(4, 8))

        self.collect_log = scrolledtext.ScrolledText(status, height=10, bg="#07111f", fg=self.colors["text"], bd=0, wrap="word")
        self.collect_log.grid(row=3, column=0, sticky="ew", padx=14, pady=(0, 14))

    def draw_collect_progress(self, done, total):
        if not hasattr(self, "collect_canvas"):
            return
        self.collect_canvas.delete("all")
        width = max(10, self.collect_canvas.winfo_width())
        pct = 0 if total == 0 else done / total
        self.collect_canvas.create_rectangle(0, 0, width, 22, fill="#07111f", outline="")
        self.collect_canvas.create_rectangle(0, 0, int(width * pct), 22, fill=self.colors["accent"], outline="")
        self.collect_canvas.create_text(width // 2, 11, text=f"{int(pct*100)}%", fill=self.colors["text"])

    def run_collector(self):
        site = self.collect_site.get().strip() if hasattr(self, "collect_site") else ""
        if not site:
            if not messagebox.askyesno("No site entered", "No site/building was entered. Continue as Unknown Site?"):
                return

        mission = {
            "site": site or "Unknown Site",
            "customer": self.collect_customer.get().strip() if hasattr(self, "collect_customer") else "",
            "issue_type": self.collect_issue.get().strip() if hasattr(self, "collect_issue") else "Unknown",
            "ticket_id": self.collect_ticket.get().strip() if hasattr(self, "collect_ticket") else "",
            "contact_name": self.collect_contact.get().strip() if hasattr(self, "collect_contact") else "",
            "access_method": self.collect_access.get() if hasattr(self, "collect_access") else "USB Collector",
            "level": self.collect_level.get() if hasattr(self, "collect_level") else "Standard",
        }

        self.collect_log.delete("1.0", "end")
        self.collect_status.set("Starting collector mission...")
        self.draw_collect_progress(0, 1)

        def progress(done, total, msg):
            self.after(0, lambda: self.collect_status.set(msg))
            self.after(0, lambda: self.draw_collect_progress(done, total))
            self.after(0, lambda: self.collect_log.insert("end", msg + "\n"))

        def worker():
            try:
                folder = collect(mission, progress=progress)
                self.after(0, lambda: messagebox.showinfo("Collector Complete", f"Evidence saved:\n{folder}"))
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("Collector Failed", str(e)))

        threading.Thread(target=worker, daemon=True).start()

    def page_evidence(self):
        self.summary.config(text="Import collector packages from other devices.")
        p = self.scroll_page()
        self.button(p,"Import Evidence Folder",self.import_evidence_ui,"primary").grid(row=0,column=0,sticky="w",pady=8)
        txt=scrolledtext.ScrolledText(p,height=28,bg="#07111f",fg=self.colors["text"],bd=0); txt.grid(row=1,column=0,sticky="nsew")
        txt.insert("end","\\n".join([str(x) for x in find_packages()]) or "No evidence packages found yet.")

    def import_evidence_ui(self):
        path = filedialog.askdirectory(title="Select evidence package folder")
        if not path: return
        try: messagebox.showinfo("Imported", import_evidence(path))
        except Exception as e: messagebox.showerror("Import Failed",str(e))

    def page_knowledge(self):
        self.summary.config(text="Confirmed fixes only. This is what Brain is allowed to use.")
        p=self.scroll_page()
        txt=scrolledtext.ScrolledText(p,height=30,bg="#07111f",fg=self.colors["text"],bd=0,wrap="word"); txt.grid(row=0,column=0,sticky="nsew")
        con=connect(); rows=con.execute("SELECT id,pattern,category,confirmed_system,root_cause,fix,confidence,success_count FROM knowledge ORDER BY id DESC").fetchall(); con.close()
        if not rows: txt.insert("end","No confirmed knowledge yet. Close tickets with verified resolutions to grow FieldSeed.")
        for r in rows:
            txt.insert("end",f"Knowledge #{r[0]}\\nPattern: {r[1]}\\nCategory: {r[2]} | System: {r[3]}\\nRoot Cause: {r[4]}\\nFix: {r[5]}\\nConfidence: {r[6]} | Successes: {r[7]}\\n\\n")

    def page_rescue(self):
        self.summary.config(text="Emergency repair tools for update loops and offline Windows repair.")
        p=self.scroll_page(); c=self.card(p,"Rescue Mode","Launch lightweight batch tools for WinRE/offline repair. Use carefully and document everything.")
        c.grid(row=0,column=0,sticky="ew",pady=8)
        self.button(c,"Open Rescue Menu",lambda:os.startfile(str(TOOLS/"FIELDSEED_RESCUE_MENU.bat")),"warn").pack(anchor="w",padx=14,pady=(0,14))


    def page_growth(self):
        self.summary.config(text="FieldSeed Core Loop: Observe → Detect → Learn → Propose → Repair → Test → Remember → Improve.")
        p = self.scroll_page()
        p.grid_columnconfigure(0, weight=1)

        top = tk.Frame(p, bg=self.colors["card"], highlightbackground=self.colors["line"], highlightthickness=1)
        top.grid(row=0, column=0, sticky="ew", pady=8)
        top.grid_columnconfigure(0, weight=1)

        tk.Label(top, text="Growth / Self-Inspection", bg=self.colors["card"], fg=self.colors["text"], font=("Segoe UI", 15, "bold")).grid(row=0, column=0, sticky="w", padx=14, pady=(12, 3))
        tk.Message(
            top,
            text="FieldSeed scans its own files, compile health, known failure patterns, screenshots, and improvement queue. It creates repair candidates automatically, but waits for your approval before applying.",
            bg=self.colors["card"],
            fg=self.colors["muted"],
            width=900
        ).grid(row=1, column=0, sticky="w", padx=14, pady=(0, 8))

        actions = tk.Frame(top, bg=self.colors["card"])
        actions.grid(row=2, column=0, sticky="w", padx=14, pady=(0, 12))
        self.button(actions, "Run Core Loop Now", self.run_core_loop_now_ui, "primary").pack(side="left", padx=4)
        self.button(actions, "Run Deep Self-Inspection", self.run_visual_self_inspection_ui, "default").pack(side="left", padx=4)
        self.button(actions, "Review Repair Queue", self.review_repair_queue_ui, "good").pack(side="left", padx=4)
        self.button(actions, "Add Screenshot Evidence", self.add_growth_screenshot_ui, "default").pack(side="left", padx=4)
        self.button(actions, "Run Basic Health Check", self.run_health_now, "default").pack(side="left", padx=4)

        self.growth_health_canvas = tk.Canvas(p, height=90, bg="#07111f", highlightthickness=0)
        self.growth_health_canvas.grid(row=1, column=0, sticky="ew", pady=8)

        self.growth_out = scrolledtext.ScrolledText(p, height=26, bg="#07111f", fg=self.colors["text"], bd=0, wrap="word")
        self.growth_out.grid(row=2, column=0, sticky="nsew", pady=8)

        con = connect()
        checks = con.execute("SELECT created_at,check_name,status,details,recommendation FROM self_checks ORDER BY id DESC LIMIT 30").fetchall()
        ideas = con.execute("SELECT created_at,source,issue,evidence,suggested_fix,status FROM improvement_queue ORDER BY id DESC LIMIT 30").fetchall()
        con.close()

        self.growth_out.insert("end", "Recent Self Checks:\n")
        for c in checks:
            self.growth_out.insert("end", f"{c[0]} [{c[2]}] {c[1]} - {c[3]} {c[4]}\n")
        self.growth_out.insert("end", "\nImprovement Queue:\n")
        for i in ideas:
            self.growth_out.insert("end", f"{i[0]} [{i[5]}] {i[2]}\nEvidence: {i[3]}\nSuggested: {i[4]}\n\n")

    def draw_growth_health(self, report):
        if not hasattr(self, "growth_health_canvas"):
            return
        canvas = self.growth_health_canvas
        canvas.delete("all")
        width = max(300, canvas.winfo_width())
        health = report.get("health", "Unknown")
        failures = report.get("summary", {}).get("compile_failures", 0)
        findings = report.get("summary", {}).get("known_findings", 0)

        color = self.colors["good"] if health == "Healthy" else self.colors["warn"] if health == "Needs Attention" else self.colors["danger"]
        canvas.create_rectangle(0, 0, width, 90, fill="#07111f", outline="")
        canvas.create_text(20, 20, anchor="w", text=f"Health: {health}", fill=color, font=("Segoe UI", 16, "bold"))
        canvas.create_text(20, 50, anchor="w", text=f"Compile failures: {failures}", fill=self.colors["text"], font=("Segoe UI", 10))
        canvas.create_text(220, 50, anchor="w", text=f"Known findings: {findings}", fill=self.colors["text"], font=("Segoe UI", 10))
        canvas.create_rectangle(20, 68, width - 20, 80, fill=self.colors["card2"], outline="")
        severity = min(1.0, (failures * 0.5) + (findings * 0.08))
        canvas.create_rectangle(20, 68, int(20 + (width - 40) * severity), 80, fill=color, outline="")

    def run_visual_self_inspection_ui(self):
        self.growth_out.delete("1.0", "end")
        self.growth_out.insert("end", "Running visual self-inspection...\n")

        def worker():
            try:
                report = visual_self_inspection()
                def update():
                    self.draw_growth_health(report)
                    self.growth_out.insert("end", "\nSelf-Inspection Report\n")
                    self.growth_out.insert("end", f"Health: {report.get('health')}\n")
                    self.growth_out.insert("end", f"Files checked: {report.get('files_checked')}\n")
                    self.growth_out.insert("end", f"Compile failures: {len(report.get('compile_failures', []))}\n")
                    self.growth_out.insert("end", f"Known findings: {len(report.get('known_findings', []))}\n\n")
                    if report.get("compile_failures"):
                        self.growth_out.insert("end", "Compile Failures:\n")
                        for item in report["compile_failures"]:
                            self.growth_out.insert("end", f"- {item['file']}: {item['error']}\n")
                    if report.get("known_findings"):
                        self.growth_out.insert("end", "\nKnown Findings:\n")
                        for f in report["known_findings"][:20]:
                            self.growth_out.insert("end", f"- [{f['risk']}] {f['title']} in {f['file']}\n  {f['description']}\n  Suggested: {f['suggested_fix']}\n")
                    if not report.get("known_findings") and not report.get("compile_failures"):
                        self.growth_out.insert("end", "No obvious self-issues found.\n")
                self.after(0, update)
            except Exception as e:
                self.after(0, lambda: self.growth_out.insert("end", f"Self-inspection failed: {e}\n"))

        threading.Thread(target=worker, daemon=True).start()


    def repair_known_issue_ui(self, rule_id):
        try:
            path, plan = create_repair_plan(rule_id)
            self.growth_out.insert("end", f"\nRepair plan created:\n{path}\n")
            self.growth_out.insert("end", json.dumps(plan, indent=2) + "\n")
            msg = (
                "FieldSeed created a repair plan.\n\n"
                f"Rule: {rule_id}\n"
                f"Risk: {plan.get('risk')}\n\n"
                "Apply this repair now?\n\n"
                "FieldSeed will back up files, compile-test after applying, and roll back if the compile test fails."
            )
            if messagebox.askyesno("Apply Repair?", msg):
                result = apply_repair_plan(path)
                self.growth_out.insert("end", "\nRepair Result:\n" + json.dumps(result, indent=2) + "\n")
                messagebox.showinfo("Repair Result", result.get("status", "Done"))
        except Exception as e:
            messagebox.showerror("Repair Failed", str(e))

    def add_growth_screenshot_ui(self):
        try:
            path = filedialog.askopenfilename(
                title="Select screenshot/image evidence",
                filetypes=[("Image files", "*.png *.jpg *.jpeg *.webp *.bmp"), ("All files", "*.*")]
            )
            if not path:
                return
            result = analyze_screenshot_file(path)
            self.growth_out.insert("end", "\nScreenshot Evidence:\n" + json.dumps(result, indent=2) + "\n")
            messagebox.showinfo("Screenshot Saved", result.get("message", "Saved."))
        except Exception as e:
            messagebox.showerror("Screenshot Evidence Failed", str(e))


    def review_repair_queue_ui(self):
        try:
            candidates = list_repair_candidates()
            self.growth_out.insert("end", "\nRepair Queue:\n")
            if not candidates:
                self.growth_out.insert("end", "No repair candidates yet. Run Visual Self-Inspection first.\n")
                return
            for idx, item in enumerate(candidates, start=1):
                self.growth_out.insert("end", f"{idx}. {item.get('rule_id')} | Risk: {item.get('risk')} | {item.get('description')}\n   Path: {item.get('path')}\n")
            newest = candidates[0]
            if messagebox.askyesno("Apply Newest Repair Candidate?", f"Apply newest repair candidate?\n\n{newest.get('rule_id')}\nRisk: {newest.get('risk')}\n\nFieldSeed will back up files, test, and roll back if needed."):
                result = apply_repair_plan(newest["path"])
                self.growth_out.insert("end", "\nRepair Result:\n" + json.dumps(result, indent=2) + "\n")
                messagebox.showinfo("Repair Result", result.get("status", "Done"))
        except Exception as e:
            messagebox.showerror("Repair Queue Failed", str(e))


    def run_core_loop_now_ui(self):
        self.growth_out.delete("1.0", "end")
        self.growth_out.insert("end", "Running FieldSeed Core Loop...\n")
        def worker():
            try:
                summary = core_loop_tick(run_deep=True)
                def update():
                    self.growth_out.insert("end", "\nCore Loop Summary:\n")
                    self.growth_out.insert("end", json.dumps(summary, indent=2, default=str)[:12000] + "\n\n")
                    self.growth_out.insert("end", "Recent Memory:\n")
                    for row in recent_core_memory(20):
                        created, memory_type, title, details, confidence, success_count, failure_count, last_seen = row
                        self.growth_out.insert("end", f"- [{memory_type}] {title} | Confidence: {confidence} | Success: {success_count} | Failure: {failure_count}\n")
                    self.growth_out.insert("end", "\nRecent Events:\n")
                    for row in recent_observer_events(20):
                        created, event_type, severity, title, details = row
                        self.growth_out.insert("end", f"- {created} [{severity}] {event_type}: {title}\n")
                self.after(0, update)
            except Exception as e:
                self.after(0, lambda: self.growth_out.insert("end", f"Core Loop failed: {e}\n"))
        threading.Thread(target=worker, daemon=True).start()

    def run_health_now(self):
        r=run_health_check()
        messagebox.showinfo("Health Check",f"Checked: {r['checked']}\\nFailures: {len(r['failures'])}\\nOpen tickets: {len(r['open_tickets'])}")

def main():
    app = FieldSeedApp()
    app.mainloop()

if __name__ == "__main__":
    main()
