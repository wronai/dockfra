"""
ticket_system — Thin wrapper for container scripts.

Canonical implementation lives in dockfra.tickets.
This file delegates to it when dockfra is importable (wizard/host),
otherwise provides a standalone fallback for SSH containers where
TICKETS_DIR defaults to /shared/tickets.
"""
import os
import sys

# In containers, TICKETS_DIR is /shared/tickets (via Docker volume).
# Override before importing dockfra.tickets so it picks up container path.
if "TICKETS_DIR" not in os.environ and os.path.isdir("/shared/tickets"):
    os.environ["TICKETS_DIR"] = "/shared/tickets"

try:
    # Try importing from dockfra package (works on host / when installed)
    from dockfra.tickets import *          # noqa: F401,F403
    from dockfra.tickets import (          # explicit re-exports for CLI
        create, get, update, add_comment, list_tickets, close,
        push_to_github, pull_from_github,
        push_to_jira, pull_from_jira,
        push_to_trello, pull_from_trello,
        push_to_linear, pull_from_linear,
        stats, sync_all, format_ticket,
        TICKETS_DIR,
    )
except ImportError:
    # Fallback: standalone mode inside Docker containers without dockfra pkg
    import json
    import glob
    import logging
    from datetime import datetime, timezone

    logger = logging.getLogger(__name__)
    TICKETS_DIR = os.environ.get("TICKETS_DIR", "/shared/tickets")
    GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
    GITHUB_REPO = os.environ.get("GITHUB_REPO", "")

    def _ensure_dir():
        os.makedirs(TICKETS_DIR, exist_ok=True)
        try:
            os.chmod(TICKETS_DIR, 0o1777)
        except OSError:
            pass

    def _chmod_world_rw(path):
        try:
            os.chmod(path, 0o666)
        except OSError:
            pass

    def _now():
        return datetime.now(timezone.utc).isoformat()

    def _ticket_path(tid):
        return os.path.join(TICKETS_DIR, f"{tid}.json")

    def _next_id():
        _ensure_dir()
        nums = []
        for f in glob.glob(os.path.join(TICKETS_DIR, "T-*.json")):
            try:
                nums.append(int(os.path.basename(f).replace(".json","").split("-")[1]))
            except (IndexError, ValueError):
                pass
        return f"T-{max(nums, default=0)+1:04d}"

    def create(title, description="", priority="normal", assigned_to="developer",
               labels=None, created_by="manager"):
        _ensure_dir()
        tid = _next_id()
        ticket = {"id":tid,"title":title,"description":description,"status":"open",
                  "priority":priority,"assigned_to":assigned_to,"labels":labels or [],
                  "created_by":created_by,"created_at":_now(),"updated_at":_now(),
                  "comments":[],"github_issue_number":None}
        p = _ticket_path(tid)
        with open(p,"w") as f: json.dump(ticket,f,indent=2)
        _chmod_world_rw(p)
        return ticket

    def get(tid):
        p = _ticket_path(tid)
        if not os.path.exists(p): return None
        with open(p) as f: return json.load(f)

    def update(tid, **fields):
        t = get(tid)
        if not t: return None
        for k,v in fields.items():
            if k not in ("id","created_at","created_by"): t[k]=v
        t["updated_at"]=_now()
        p = _ticket_path(tid)
        with open(p,"w") as f: json.dump(t,f,indent=2)
        _chmod_world_rw(p)
        return t

    def add_comment(tid, author, text):
        t = get(tid)
        if not t: return None
        t.setdefault("comments",[]).append({"author":author,"text":text,"timestamp":_now()})
        t["updated_at"]=_now()
        p = _ticket_path(tid)
        with open(p,"w") as f: json.dump(t,f,indent=2)
        _chmod_world_rw(p)
        return t

    def list_tickets(status=None, assigned_to=None, priority=None):
        _ensure_dir()
        tickets=[]
        for p in sorted(glob.glob(os.path.join(TICKETS_DIR,"T-*.json"))):
            try:
                with open(p) as f: t=json.load(f)
            except Exception: continue
            if status and t.get("status")!=status: continue
            if assigned_to and t.get("assigned_to")!=assigned_to: continue
            if priority and t.get("priority")!=priority: continue
            tickets.append(t)
        return tickets

    def close(tid, closed_by="manager"):
        return update(tid, status="closed")

    def push_to_github(tid): return None
    def pull_from_github(): return []
    def push_to_jira(tid): return None
    def pull_from_jira(): return []
    def push_to_trello(tid): return None
    def pull_from_trello(): return []
    def push_to_linear(tid): return None
    def pull_from_linear(): return []
    def stats(): return {"total":len(list_tickets()),"by_status":{},"by_priority":{},"by_assignee":{},"integrations":{}}
    def sync_all(): return {}

    def format_ticket(t, verbose=False):
        si={"open":"○","in_progress":"◐","closed":"●"}.get(t["status"],"?")
        pi={"critical":"🔴","high":"🟠","normal":"🟡","low":"🟢"}.get(t["priority"],"⚪")
        line=f"  {si} {t['id']:8s} {pi} {t['title'][:50]:50s} → {t['assigned_to']}"
        if t.get("github_issue_number"): line+=f"  (GH#{t['github_issue_number']})"
        if verbose:
            line+=f"\n    Status: {t['status']} | Created: {t['created_at'][:10]} | Comments: {len(t.get('comments',[]))}"
            if t.get("description"): line+=f"\n    {t['description'][:100]}"
        return line


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        print("Usage: ticket_system.py <command> [args]")
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
        if t: print(format_ticket(t, verbose=True))
        else: print(f"Ticket {args[1]} not found")
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
