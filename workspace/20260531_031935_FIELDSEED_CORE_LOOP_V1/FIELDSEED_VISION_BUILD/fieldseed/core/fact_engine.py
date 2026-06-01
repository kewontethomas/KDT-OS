REMOTE_TOOLS = {
    "logmein": "LogMeIn",
    "ninjaone": "NinjaOne",
    "ninja": "NinjaOne",
    "rdp": "RDP",
    "remote desktop": "RDP",
    "teamviewer": "TeamViewer",
}

EXPLICIT_SYSTEMS = {
    "openeye": "OpenEye",
    "command station": "OpenEye",
    "ccure": "CCure",
    "c-cure": "CCure",
    "istar": "CCure",
    "milestone": "Milestone XProtect",
    "xprotect": "Milestone XProtect",
    "salient": "Salient",
    "exacq": "ExacqVision",
    "sql server": "SQL Server",
}

CATEGORIES = {
    "Video / Camera": ["camera", "cameras", "recording", "playback", "video", "vms", "nvr"],
    "Access Control": ["badge", "reader", "door", "turnstile", "access", "cardholder"],
    "Windows / Server": ["windows", "server", "update", "boot", "login", "reboot", "shutdown"],
    "Network": ["network", "internet", "switch", "router", "ping", "dns", "ip address"],
    "Storage": ["raid", "drive", "disk", "storage", "ssd", "hdd"],
    "Application": ["app", "application", "software", "client", "portal"],
}

def lines(text):
    return [x.strip(" -•\t") for x in (text or "").splitlines() if x.strip()]

def detect_access(text):
    low = (text or "").lower()
    for key, tool in REMOTE_TOOLS.items():
        if key in low:
            return "Remote", tool
    if "on site" in low or "onsite" in low:
        return "On Site", ""
    if "phone" in low or "called" in low:
        return "Phone Only", ""
    if "winre" in low or "recovery" in low or "won't boot" in low:
        return "Rescue/WinRE", ""
    return "Unknown", ""

def detect_confirmed_system(text):
    low = (text or "").lower()
    found = []
    for key, value in EXPLICIT_SYSTEMS.items():
        if key in low and value not in found:
            found.append(value)
    return ", ".join(found) if found else "Unknown"

def detect_category(text):
    low = (text or "").lower()
    scores = {cat: sum(1 for w in words if w in low) for cat, words in CATEGORIES.items()}
    best = max(scores, key=scores.get)
    return best if scores[best] else "Unknown"

def confirmed_facts(text):
    facts = []
    for line in lines(text):
        low = line.lower()
        if any(w in low for w in ["customer says", "user says", "reported", "not working", "cannot", "can't", "failed", "offline", "stuck", "error", "connecting through", "logmein", "ninja", "remote", "onsite", "on site"]):
            facts.append(line)
    return facts or lines(text)[:4]

def unknowns_for(text, category, confirmed_system, access_mode):
    low = (text or "").lower()
    unknowns = []

    if confirmed_system == "Unknown":
        if category == "Video / Camera":
            unknowns.append("Identify the camera/VMS platform before using system-specific fixes.")
        elif category == "Access Control":
            unknowns.append("Identify the access control platform before using system-specific fixes.")
        else:
            unknowns.append("Identify the affected system/application/device.")

    if access_mode == "Unknown":
        unknowns.append("Confirm how you are working the issue: Remote, On Site, Phone Only, USB Collector, or Rescue/WinRE.")

    if not any(x in low for x in ["one user", "everyone", "all users", "multiple", "one camera", "all cameras", "one door", "all doors"]):
        unknowns.append("Confirm scope: one user/device, multiple users/devices, or everyone.")

    if not any(x in low for x in ["after", "recent", "changed", "replaced", "update", "password"]):
        unknowns.append("Ask what changed recently.")

    if category == "Video / Camera":
        unknowns.append("Confirm whether live video works, playback works, or both are failing.")
    elif category == "Access Control":
        unknowns.append("Confirm whether this is one badge/user, one reader/door, or a whole access group/site.")

    deduped = []
    for item in unknowns:
        if item not in deduped:
            deduped.append(item)
    return deduped

def analyze_intake(text):
    access_mode, access_tool = detect_access(text)
    system = detect_confirmed_system(text)
    category = detect_category(text)
    facts = confirmed_facts(text)
    unknowns = unknowns_for(text, category, system, access_mode)

    completeness = 0
    if category != "Unknown":
        completeness += 20
    if system != "Unknown":
        completeness += 25
    if access_mode != "Unknown":
        completeness += 15
    completeness += min(20, len(facts) * 5)
    completeness -= min(30, len(unknowns) * 5)
    completeness = max(0, min(100, completeness))

    if system != "Unknown":
        title = f"{system} {category} issue"
    elif category != "Unknown":
        title = f"{category} issue - system unknown"
    else:
        title = "New issue - system unknown"

    return {
        "title": title,
        "category": category,
        "confirmed_system": system,
        "access_mode": access_mode,
        "access_tool": access_tool,
        "confirmed_facts": facts,
        "unknowns": unknowns,
        "completeness": completeness,
        "next_action": unknowns[0] if unknowns else "Gather evidence or begin documented troubleshooting."
    }
