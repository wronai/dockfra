"""
ticket_system — Local + GitHub ticket management.
Used by: manager (create/assign), developer (read/update), autopilot (orchestrate).

Tickets stored as JSON files in /shared/tickets/
Optional sync with GitHub Issues via GITHUB_TOKEN + GITHUB_REPO.
"""
import os
import json
import glob
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

TICKETS_DIR = os.environ.get("TICKETS_DIR", "/shared/tickets")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
GITHUB_REPO = os.environ.get("GITHUB_REPO", "")  # "owner/repo"


def _ensure_dir():
    os.makedirs(TICKETS_DIR, exist_ok=True)


def _now():
    return datetime.now(timezone.utc).isoformat()


def _ticket_path(ticket_id):
    return os.path.join(TICKETS_DIR, f"{ticket_id}.json")


def _next_id():
    _ensure_dir()
    existing = glob.glob(os.path.join(TICKETS_DIR, "T-*.json"))
    nums = []
    for f in existing:
        name = os.path.basename(f).replace(".json", "")
        try:
            nums.append(int(name.split("-")[1]))
        except (IndexError, ValueError):
            pass
    return f"T-{max(nums, default=0) + 1:04d}"


# ── CRUD ──────────────────────────────────────────────

def create(title, description="", priority="normal", assigned_to="developer",
           labels=None, created_by="manager"):
    """Create a new ticket."""
    _ensure_dir()
    ticket_id = _next_id()
    ticket = {
        "id": ticket_id,
        "title": title,
        "description": description,
        "status": "open",
        "priority": priority,  # low, normal, high, critical
        "assigned_to": assigned_to,  # developer, monitor, autopilot
        "labels": labels or [],
        "created_by": created_by,
        "created_at": _now(),
        "updated_at": _now(),
        "comments": [],
        "github_issue_number": None,
    }
    with open(_ticket_path(ticket_id), "w") as f:
        json.dump(ticket, f, indent=2)
    logger.info(f"Created ticket {ticket_id}: {title}")
    return ticket


def get(ticket_id):
    """Get a ticket by ID."""
    path = _ticket_path(ticket_id)
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return json.load(f)


def update(ticket_id, **fields):
    """Update ticket fields."""
    ticket = get(ticket_id)
    if not ticket:
        return None
    for k, v in fields.items():
        if k in ticket and k not in ("id", "created_at", "created_by"):
            ticket[k] = v
    ticket["updated_at"] = _now()
    with open(_ticket_path(ticket_id), "w") as f:
        json.dump(ticket, f, indent=2)
    return ticket


def add_comment(ticket_id, author, text):
    """Add a comment to a ticket."""
    ticket = get(ticket_id)
    if not ticket:
        return None
    ticket["comments"].append({
        "author": author,
        "text": text,
        "timestamp": _now(),
    })
    ticket["updated_at"] = _now()
    with open(_ticket_path(ticket_id), "w") as f:
        json.dump(ticket, f, indent=2)
    return ticket


def list_tickets(status=None, assigned_to=None, priority=None):
    """List tickets with optional filters."""
    _ensure_dir()
    tickets = []
    for path in sorted(glob.glob(os.path.join(TICKETS_DIR, "T-*.json"))):
        with open(path) as f:
            t = json.load(f)
        if status and t["status"] != status:
            continue
        if assigned_to and t["assigned_to"] != assigned_to:
            continue
        if priority and t["priority"] != priority:
            continue
        tickets.append(t)
    return tickets


def close(ticket_id, closed_by="manager"):
    """Close a ticket."""
    return update(ticket_id, status="closed",
                  _closed_by=closed_by, _closed_at=_now())


# ── GitHub Integration ────────────────────────────────

def _github_api(method, endpoint, data=None):
    """Make a GitHub API request."""
    import urllib.request
    import urllib.error

    if not GITHUB_TOKEN or not GITHUB_REPO:
        return None

    url = f"https://api.github.com/repos/{GITHUB_REPO}{endpoint}"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
        "Content-Type": "application/json",
    }

    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        logger.error(f"GitHub API {e.code}: {e.read().decode()[:200]}")
        return None
    except Exception as e:
        logger.error(f"GitHub API error: {e}")
        return None


def push_to_github(ticket_id):
    """Create a GitHub Issue from a local ticket."""
    ticket = get(ticket_id)
    if not ticket:
        return None

    if ticket.get("github_issue_number"):
        logger.info(f"Ticket {ticket_id} already has GitHub issue #{ticket['github_issue_number']}")
        return ticket

    body = f"**Priority:** {ticket['priority']}\n"
    body += f"**Assigned to:** {ticket['assigned_to']}\n"
    body += f"**Created by:** {ticket['created_by']}\n\n"
    body += ticket.get("description", "")

    result = _github_api("POST", "/issues", {
        "title": f"[{ticket_id}] {ticket['title']}",
        "body": body,
        "labels": ticket.get("labels", []),
    })

    if result and "number" in result:
        update(ticket_id, github_issue_number=result["number"])
        logger.info(f"Pushed {ticket_id} → GitHub issue #{result['number']}")
        return get(ticket_id)
    return None


def pull_from_github():
    """Pull open GitHub Issues and create local tickets for new ones."""
    issues = _github_api("GET", "/issues?state=open&per_page=50")
    if not issues:
        return []

    created = []
    existing_nums = set()
    for t in list_tickets():
        if t.get("github_issue_number"):
            existing_nums.add(t["github_issue_number"])

    for issue in issues:
        if issue["number"] in existing_nums:
            continue
        if issue.get("pull_request"):
            continue

        ticket = create(
            title=issue["title"],
            description=issue.get("body", ""),
            labels=[l["name"] for l in issue.get("labels", [])],
            created_by="github",
        )
        update(ticket["id"], github_issue_number=issue["number"])
        created.append(ticket)

    return created


# ── CLI ───────────────────────────────────────────────

def format_ticket(t, verbose=False):
    """Format ticket for display."""
    status_icon = {"open": "○", "in_progress": "◐", "closed": "●"}.get(t["status"], "?")
    prio_icon = {"critical": "🔴", "high": "🟠", "normal": "🟡", "low": "🟢"}.get(t["priority"], "⚪")
    line = f"  {status_icon} {t['id']:8s} {prio_icon} {t['title'][:50]:50s} → {t['assigned_to']}"
    if t.get("github_issue_number"):
        line += f"  (GH#{t['github_issue_number']})"
    if verbose:
        line += f"\n    Status: {t['status']} | Created: {t['created_at'][:10]} | Comments: {len(t.get('comments', []))}"
        if t.get("description"):
            line += f"\n    {t['description'][:100]}"
    return line


if __name__ == "__main__":
    import sys
    args = sys.argv[1:]
    if not args:
        print("Usage: ticket_system.py <command> [args]")
        print("  list [--status=open] [--assigned=developer]")
        print("  create <title> [--desc=...] [--priority=normal] [--assign=developer]")
        print("  show <T-XXXX>")
        print("  update <T-XXXX> --status=in_progress")
        print("  comment <T-XXXX> <text>")
        print("  push <T-XXXX>        (push to GitHub)")
        print("  pull                  (pull from GitHub)")
        sys.exit(0)

    cmd = args[0]
    if cmd == "list":
        filters = {}
        for a in args[1:]:
            if a.startswith("--status="): filters["status"] = a.split("=", 1)[1]
            if a.startswith("--assigned="): filters["assigned_to"] = a.split("=", 1)[1]
        for t in list_tickets(**filters):
            print(format_ticket(t))
    elif cmd == "create" and len(args) > 1:
        kw = {"title": args[1]}
        for a in args[2:]:
            if a.startswith("--desc="): kw["description"] = a.split("=", 1)[1]
            if a.startswith("--priority="): kw["priority"] = a.split("=", 1)[1]
            if a.startswith("--assign="): kw["assigned_to"] = a.split("=", 1)[1]
        t = create(**kw)
        print(f"Created: {t['id']} — {t['title']}")
    elif cmd == "show" and len(args) > 1:
        t = get(args[1])
        if t:
            print(format_ticket(t, verbose=True))
        else:
            print(f"Ticket {args[1]} not found")
    elif cmd == "update" and len(args) > 1:
        fields = {}
        for a in args[2:]:
            if "=" in a:
                k, v = a.lstrip("-").split("=", 1)
                fields[k] = v
        t = update(args[1], **fields)
        print(f"Updated: {args[1]}" if t else f"Not found: {args[1]}")
    elif cmd == "comment" and len(args) > 2:
        t = add_comment(args[1], os.environ.get("SERVICE_ROLE", "unknown"), " ".join(args[2:]))
        print(f"Comment added to {args[1]}" if t else f"Not found: {args[1]}")
    elif cmd == "push" and len(args) > 1:
        r = push_to_github(args[1])
        print(f"Pushed {args[1]} to GitHub" if r else "Push failed")
    elif cmd == "pull":
        created = pull_from_github()
        print(f"Pulled {len(created)} new tickets from GitHub")
    else:
        print(f"Unknown command: {cmd}")
