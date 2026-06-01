import json
import platform
import socket
import subprocess
from datetime import datetime
from fieldseed.paths import EVIDENCE

def run_cmd(cmd, timeout=30):
    try:
        return subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT, timeout=timeout).decode(errors="ignore")
    except Exception as e:
        return f"ERROR: {e}"

def safe_name(value):
    value = (value or "Unknown").strip()
    safe = "".join(ch if ch.isalnum() or ch in ("-", "_", " ") else "_" for ch in value)
    return safe.strip().replace(" ", "_") or "Unknown"

def windows_commands(level="Standard"):
    commands = [
        ("systeminfo", "systeminfo"),
        ("ipconfig", "ipconfig /all"),
        ("services", "powershell -NoProfile -Command Get-Service"),
        ("system_events", "powershell -NoProfile -Command Get-EventLog -LogName System -Newest 100"),
        ("app_events", "powershell -NoProfile -Command Get-EventLog -LogName Application -Newest 100"),
    ]
    if level in ("Standard", "Deep"):
        commands.extend([
            ("disk_wmic", "wmic diskdrive get model,status,size"),
            ("disk_cim", "powershell -NoProfile -Command \"Get-CimInstance Win32_DiskDrive | Select-Object Model,Status,Size,SerialNumber | Format-Table -AutoSize\""),
            ("disk_getdisk", "powershell -NoProfile -Command Get-Disk"),
            ("physical_disk", "powershell -NoProfile -Command Get-PhysicalDisk"),
        ])
    if level == "Deep":
        commands.extend([
            ("installed_apps", "powershell -NoProfile -Command \"Get-ItemProperty HKLM:\\Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\* | Select-Object DisplayName,DisplayVersion,Publisher | Format-Table -AutoSize\""),
            ("processes", "powershell -NoProfile -Command \"Get-Process | Sort-Object CPU -Descending | Select-Object -First 100 | Format-Table -AutoSize\""),
            ("startup_items", "powershell -NoProfile -Command \"Get-CimInstance Win32_StartupCommand | Select-Object Name,Command,Location | Format-Table -AutoSize\""),
        ])
    return commands

def linux_commands(level="Standard"):
    commands = [("uname", "uname -a"), ("ip", "ip addr || ifconfig"), ("disk", "df -h")]
    if level in ("Standard", "Deep"):
        commands.append(("processes", "ps aux | head -100"))
    return commands

def collect(mission=None, progress=None):
    mission = mission or {}
    site = mission.get("site") or "Unknown Site"
    customer = mission.get("customer") or ""
    issue_type = mission.get("issue_type") or "Unknown"
    ticket_id = mission.get("ticket_id") or ""
    contact_name = mission.get("contact_name") or ""
    access_method = mission.get("access_method") or "USB Collector"
    level = mission.get("level") or "Standard"

    host = socket.gethostname()
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    folder = EVIDENCE / f"{safe_name(site)}_{safe_name(host)}_{stamp}"
    folder.mkdir(parents=True, exist_ok=True)

    data = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "site": site,
        "customer": customer,
        "issue_type": issue_type,
        "ticket_id": ticket_id,
        "contact_name": contact_name,
        "access_method": access_method,
        "collection_level": level,
        "hostname": host,
        "platform": platform.platform(),
        "system": platform.system(),
        "commands": {},
        "command_results": [],
    }

    commands = windows_commands(level) if platform.system().lower() == "windows" else linux_commands(level)
    total = len(commands)

    if progress:
        progress(0, total, f"Starting collection for {site} on {host}")

    for index, item in enumerate(commands, start=1):
        name, cmd = item
        if progress:
            progress(index - 1, total, f"Running {name}...")
        result = run_cmd(cmd)
        ok = not result.startswith("ERROR:")
        data["commands"][name] = result[:30000]
        data["command_results"].append({"name": name, "command": cmd, "ok": ok, "summary": result[:500]})
        (folder / f"{name}.txt").write_text(result, encoding="utf-8", errors="ignore")
        if progress:
            progress(index, total, f"Finished {name} ({'OK' if ok else 'FAILED'})")

    findings = []
    sys_events = data["commands"].get("system_events", "")
    if "disk" in sys_events.lower() and "error" in sys_events.lower():
        findings.append("System event logs mention disk errors. Review disk/controller health.")
    failed = [r["name"] for r in data["command_results"] if not r["ok"]]
    if failed:
        findings.append("Some collectors failed and may need fallback improvement: " + ", ".join(failed))
    services = data["commands"].get("services", "")
    for name in ["NinjaRMMAgent", "TeamViewer", "Tailscale", "AXIS", "CrowdStrike"]:
        if name.lower() in services.lower():
            findings.append(f"{name} detected in services.")

    data["findings"] = findings

    (folder / "evidence_package.json").write_text(json.dumps(data, indent=2), encoding="utf-8")
    (folder / "mission.json").write_text(json.dumps(mission, indent=2), encoding="utf-8")
    (folder / "quick_report.md").write_text(
        "# FieldSeed Evidence Package\n\n"
        f"Site: {site}\nCustomer: {customer}\nIssue Type: {issue_type}\nTicket ID: {ticket_id}\n"
        f"Access Method: {access_method}\nCollection Level: {level}\nHostname: {host}\n"
        f"Created: {data['created_at']}\nOS: {data['platform']}\n\nFindings:\n"
        + ("\n".join([f"- {x}" for x in findings]) if findings else "- No automatic findings yet.")
        + "\n",
        encoding="utf-8"
    )

    if progress:
        progress(total, total, f"Complete. Evidence saved: {folder}")

    return folder

def main():
    mission = {
        "site": input("Site name: ").strip() or "Unknown Site",
        "customer": input("Customer/company: ").strip(),
        "issue_type": input("Issue type: ").strip() or "Unknown",
        "ticket_id": input("Ticket ID if known, otherwise leave blank: ").strip(),
        "contact_name": input("Contact person: ").strip(),
        "access_method": "USB Collector",
        "level": input("Collection level Quick/Standard/Deep: ").strip() or "Standard",
    }
    print("Running FieldSeed Collector Mode...")
    print(f"Evidence saved: {collect(mission)}")

if __name__ == "__main__":
    main()
