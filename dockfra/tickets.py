"""
dockfra.tickets — Local + external ticket management.

Canonical module used by:
  - Wizard (app.py) — direct import
  - SSH containers (shared/lib/ticket_system.py) — thin wrapper

Tickets stored as JSON files in TICKETS_DIR.
Optional sync with GitHub Issues, Jira, Trello, Linear.
"""
import os
import json
import glob
import logging
from pathlib import Path
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Auto-detect tickets dir: use project-relative path on host, /shared/tickets in container
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_HOST_TICKETS = str(_PROJECT_ROOT / "shared" / "tickets")
TICKETS_DIR = os.environ.get("TICKETS_DIR", _HOST_TICKETS)

# Integration credentials (read from env, can be updated at runtime)
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
GITHUB_REPO = os.environ.get("GITHUB_REPO", "")

JIRA_URL = os.environ.get("JIRA_URL", "")
JIRA_EMAIL = os.environ.get("JIRA_EMAIL", "")
JIRA_TOKEN = os.environ.get("JIRA_TOKEN", "")
JIRA_PROJECT = os.environ.get("JIRA_PROJECT", "")

TRELLO_KEY = os.environ.get("TRELLO_KEY", "")
TRELLO_TOKEN_ENV = os.environ.get("TRELLO_TOKEN", "")
TRELLO_BOARD = os.environ.get("TRELLO_BOARD", "")
TRELLO_LIST = os.environ.get("TRELLO_LIST", "")

LINEAR_TOKEN = os.environ.get("LINEAR_TOKEN", "")
LINEAR_TEAM = os.environ.get("LINEAR_TEAM", "")


def reload_env():
    """Re-read integration credentials from environment (call after save_env)."""
    global GITHUB_TOKEN, GITHUB_REPO
    global JIRA_URL, JIRA_EMAIL, JIRA_TOKEN, JIRA_PROJECT
    global TRELLO_KEY, TRELLO_TOKEN_ENV, TRELLO_BOARD, TRELLO_LIST
    global LINEAR_TOKEN, LINEAR_TEAM
    GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
    GITHUB_REPO = os.environ.get("GITHUB_REPO", "")
    JIRA_URL = os.environ.get("JIRA_URL", "")
    JIRA_EMAIL = os.environ.get("JIRA_EMAIL", "")
    JIRA_TOKEN = os.environ.get("JIRA_TOKEN", "")
    JIRA_PROJECT = os.environ.get("JIRA_PROJECT", "")
    TRELLO_KEY = os.environ.get("TRELLO_KEY", "")
    TRELLO_TOKEN_ENV = os.environ.get("TRELLO_TOKEN", "")
    TRELLO_BOARD = os.environ.get("TRELLO_BOARD", "")
    TRELLO_LIST = os.environ.get("TRELLO_LIST", "")
    LINEAR_TOKEN = os.environ.get("LINEAR_TOKEN", "")
    LINEAR_TEAM = os.environ.get("LINEAR_TEAM", "")


def _ensure_dir():
    os.makedirs(TICKETS_DIR, exist_ok=True)
    try:
        os.chmod(TICKETS_DIR, 0o1777)
    except OSError:
        pass


def _chmod_world_rw(path):
    """Make a ticket file world-readable/writable so any container UID can edit it."""
    try:
        os.chmod(path, 0o666)
    except OSError:
        pass


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
        "priority": priority,
        "assigned_to": assigned_to,
        "labels": labels or [],
        "created_by": created_by,
        "created_at": _now(),
        "updated_at": _now(),
        "comments": [],
        "github_issue_number": None,
    }
    p = _ticket_path(ticket_id)
    with open(p, "w") as f:
        json.dump(ticket, f, indent=2)
    _chmod_world_rw(p)
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
        if k not in ("id", "created_at", "created_by"):
            ticket[k] = v
    ticket["updated_at"] = _now()
    p = _ticket_path(ticket_id)
    with open(p, "w") as f:
        json.dump(ticket, f, indent=2)
    _chmod_world_rw(p)
    return ticket


def add_comment(ticket_id, author, text):
    """Add a comment to a ticket."""
    ticket = get(ticket_id)
    if not ticket:
        return None
    ticket.setdefault("comments", []).append({
        "author": author,
        "text": text,
        "timestamp": _now(),
    })
    ticket["updated_at"] = _now()
    p = _ticket_path(ticket_id)
    with open(p, "w") as f:
        json.dump(ticket, f, indent=2)
    _chmod_world_rw(p)
    return ticket


def list_tickets(status=None, assigned_to=None, priority=None):
    """List tickets with optional filters."""
    _ensure_dir()
    tickets = []
    for path in sorted(glob.glob(os.path.join(TICKETS_DIR, "T-*.json"))):
        try:
            with open(path) as f:
                t = json.load(f)
        except Exception:
            continue
        if status and t.get("status") != status:
            continue
        if assigned_to and t.get("assigned_to") != assigned_to:
            continue
        if priority and t.get("priority") != priority:
            continue
        tickets.append(t)
    return tickets


def close(ticket_id, closed_by="manager"):
    """Close a ticket."""
    return update(ticket_id, status="closed")


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


# ── Jira Integration ─────────────────────────────────

def _jira_api(method, endpoint, data=None):
    """Make a Jira Cloud REST API request."""
    import urllib.request
    import urllib.error
    import base64

    if not all([JIRA_URL, JIRA_EMAIL, JIRA_TOKEN]):
        return None

    url = f"{JIRA_URL.rstrip('/')}/rest/api/3{endpoint}"
    cred = base64.b64encode(f"{JIRA_EMAIL}:{JIRA_TOKEN}".encode()).decode()
    headers = {
        "Authorization": f"Basic {cred}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        logger.error(f"Jira API error: {e}")
        return None


def push_to_jira(ticket_id):
    """Create a Jira issue from a local ticket."""
    ticket = get(ticket_id)
    if not ticket or not JIRA_PROJECT:
        return None
    if ticket.get("jira_key"):
        return ticket
    prio_map = {"critical": "Highest", "high": "High", "normal": "Medium", "low": "Low"}
    result = _jira_api("POST", "/issue", {
        "fields": {
            "project": {"key": JIRA_PROJECT},
            "summary": f"[{ticket_id}] {ticket['title']}",
            "description": {"type": "doc", "version": 1, "content": [
                {"type": "paragraph", "content": [
                    {"type": "text", "text": ticket.get("description", "") or ticket["title"]}
                ]}
            ]},
            "issuetype": {"name": "Task"},
            "priority": {"name": prio_map.get(ticket.get("priority", "normal"), "Medium")},
        }
    })
    if result and "key" in result:
        update(ticket_id, jira_key=result["key"])
        logger.info(f"Pushed {ticket_id} → Jira {result['key']}")
        return get(ticket_id)
    return None


def pull_from_jira():
    """Pull open Jira issues and create local tickets."""
    if not JIRA_PROJECT:
        return []
    result = _jira_api("GET", f"/search?jql=project={JIRA_PROJECT}+AND+status!=Done&maxResults=50")
    if not result or "issues" not in result:
        return []
    existing_keys = {t.get("jira_key") for t in list_tickets() if t.get("jira_key")}
    created = []
    for issue in result["issues"]:
        if issue["key"] in existing_keys:
            continue
        desc = ""
        try:
            if isinstance(issue["fields"].get("description"), dict):
                desc = issue["fields"]["description"].get("content", [{}])[0].get("content", [{}])[0].get("text", "")
        except (IndexError, KeyError, TypeError):
            pass
        ticket = create(title=issue["fields"]["summary"], description=desc, created_by="jira")
        update(ticket["id"], jira_key=issue["key"])
        created.append(ticket)
    return created


# ── Trello Integration ───────────────────────────────

def _trello_api(method, endpoint, params=None, data=None):
    """Make a Trello REST API request."""
    import urllib.request
    import urllib.error
    import urllib.parse

    if not all([TRELLO_KEY, TRELLO_TOKEN_ENV]):
        return None

    base_params = {"key": TRELLO_KEY, "token": TRELLO_TOKEN_ENV}
    if params:
        base_params.update(params)
    qs = urllib.parse.urlencode(base_params)
    url = f"https://api.trello.com/1{endpoint}?{qs}"
    body = json.dumps(data).encode() if data else None
    headers = {"Content-Type": "application/json"} if data else {}
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        logger.error(f"Trello API error: {e}")
        return None


def push_to_trello(ticket_id):
    """Create a Trello card from a local ticket."""
    ticket = get(ticket_id)
    if not ticket or not TRELLO_LIST:
        return None
    if ticket.get("trello_card_id"):
        return ticket
    result = _trello_api("POST", "/cards", params={
        "idList": TRELLO_LIST,
        "name": f"[{ticket_id}] {ticket['title']}",
        "desc": ticket.get("description", ""),
    })
    if result and "id" in result:
        update(ticket_id, trello_card_id=result["id"])
        logger.info(f"Pushed {ticket_id} → Trello card {result['id']}")
        return get(ticket_id)
    return None


def pull_from_trello():
    """Pull cards from Trello board and create local tickets."""
    if not TRELLO_BOARD:
        return []
    result = _trello_api("GET", f"/boards/{TRELLO_BOARD}/cards")
    if not result:
        return []
    existing_ids = {t.get("trello_card_id") for t in list_tickets() if t.get("trello_card_id")}
    created = []
    for card in result:
        if card["id"] in existing_ids or card.get("closed"):
            continue
        ticket = create(title=card["name"], description=card.get("desc", ""), created_by="trello")
        update(ticket["id"], trello_card_id=card["id"])
        created.append(ticket)
    return created


# ── Linear Integration ───────────────────────────────

def _linear_api(query, variables=None):
    """Make a Linear GraphQL API request."""
    import urllib.request
    import urllib.error

    if not LINEAR_TOKEN:
        return None
    url = "https://api.linear.app/graphql"
    headers = {
        "Authorization": LINEAR_TOKEN,
        "Content-Type": "application/json",
    }
    body = json.dumps({"query": query, "variables": variables or {}}).encode()
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        logger.error(f"Linear API error: {e}")
        return None


def push_to_linear(ticket_id):
    """Create a Linear issue from a local ticket."""
    ticket = get(ticket_id)
    if not ticket or not LINEAR_TEAM:
        return None
    if ticket.get("linear_id"):
        return ticket
    prio_map = {"critical": 1, "high": 2, "normal": 3, "low": 4}
    result = _linear_api("""
        mutation($title: String!, $teamId: String!, $description: String, $priority: Int) {
            issueCreate(input: {title: $title, teamId: $teamId, description: $description, priority: $priority}) {
                issue { id identifier url }
            }
        }""", {
        "title": f"[{ticket_id}] {ticket['title']}",
        "teamId": LINEAR_TEAM,
        "description": ticket.get("description", ""),
        "priority": prio_map.get(ticket.get("priority", "normal"), 3),
    })
    if result and "data" in result:
        issue = result["data"].get("issueCreate", {}).get("issue", {})
        if issue:
            update(ticket_id, linear_id=issue["identifier"], linear_url=issue.get("url", ""))
            logger.info(f"Pushed {ticket_id} → Linear {issue['identifier']}")
            return get(ticket_id)
    return None


def pull_from_linear():
    """Pull open Linear issues and create local tickets."""
    if not LINEAR_TEAM:
        return []
    result = _linear_api("""
        query($teamId: String!) {
            team(id: $teamId) {
                issues(filter: {state: {type: {nin: ["completed","canceled"]}}}, first: 50) {
                    nodes { id identifier title description priority }
                }
            }
        }""", {"teamId": LINEAR_TEAM})
    if not result or "data" not in result:
        return []
    issues = result["data"].get("team", {}).get("issues", {}).get("nodes", [])
    existing_ids = {t.get("linear_id") for t in list_tickets() if t.get("linear_id")}
    created = []
    for issue in issues:
        if issue["identifier"] in existing_ids:
            continue
        ticket = create(title=issue["title"], description=issue.get("description", ""), created_by="linear")
        update(ticket["id"], linear_id=issue["identifier"])
        created.append(ticket)
    return created


# ── Statistics ───────────────────────────────────────

def stats():
    """Return ticket statistics summary."""
    tickets = list_tickets()
    total = len(tickets)
    by_status = {}
    by_priority = {}
    by_assignee = {}
    for t in tickets:
        by_status[t["status"]] = by_status.get(t["status"], 0) + 1
        by_priority[t["priority"]] = by_priority.get(t["priority"], 0) + 1
        by_assignee[t["assigned_to"]] = by_assignee.get(t["assigned_to"], 0) + 1
    integrations = {
        "github": bool(GITHUB_TOKEN and GITHUB_REPO),
        "jira": bool(JIRA_URL and JIRA_EMAIL and JIRA_TOKEN),
        "trello": bool(TRELLO_KEY and TRELLO_TOKEN_ENV),
        "linear": bool(LINEAR_TOKEN),
    }
    return {
        "total": total,
        "by_status": by_status,
        "by_priority": by_priority,
        "by_assignee": by_assignee,
        "integrations": integrations,
    }


def sync_all():
    """Sync tickets with all configured external services. Returns summary."""
    reload_env()
    results = {}
    if GITHUB_TOKEN and GITHUB_REPO:
        try:
            pulled = pull_from_github()
            results["github"] = {"pulled": len(pulled), "ok": True}
        except Exception as e:
            results["github"] = {"error": str(e), "ok": False}
    if JIRA_URL and JIRA_EMAIL and JIRA_TOKEN and JIRA_PROJECT:
        try:
            pulled = pull_from_jira()
            results["jira"] = {"pulled": len(pulled), "ok": True}
        except Exception as e:
            results["jira"] = {"error": str(e), "ok": False}
    if TRELLO_KEY and TRELLO_TOKEN_ENV and TRELLO_BOARD:
        try:
            pulled = pull_from_trello()
            results["trello"] = {"pulled": len(pulled), "ok": True}
        except Exception as e:
            results["trello"] = {"error": str(e), "ok": False}
    if LINEAR_TOKEN and LINEAR_TEAM:
        try:
            pulled = pull_from_linear()
            results["linear"] = {"pulled": len(pulled), "ok": True}
        except Exception as e:
            results["linear"] = {"error": str(e), "ok": False}
    return results


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
        print("Usage: python -m dockfra.tickets <command> [args]")
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
