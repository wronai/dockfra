"""
dockfra.pipeline — Adaptive execution pipeline with observational learning.

Tracks errors, scores results, detects patterns, and adjusts strategy
across iterations. Not hardcoded — learns from outcomes.

Architecture:
  PipelineState  — persistent state for a ticket pipeline run
  StepResult     — structured result of each pipeline step
  ErrorTracker   — detects recurring error patterns
  PipelineRunner — orchestrates steps with adaptive retry logic
"""
import json
import os
import time
import logging
from pathlib import Path
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Persistent storage for pipeline runs
_PIPELINE_DIR = Path(os.environ.get("TICKETS_DIR",
    str(Path(__file__).resolve().parent.parent / "shared" / "tickets"))) / ".pipeline"


def _ensure_dir():
    _PIPELINE_DIR.mkdir(parents=True, exist_ok=True)


# ── Step Result (structured observation) ──────────────────────────────────────

class StepResult:
    """Structured result of a single pipeline step — the unit of observation."""
    __slots__ = ("step", "rc", "output", "duration", "error", "score", "meta")

    def __init__(self, step: str, rc: int = 0, output: str = "", duration: float = 0,
                 error: str = "", score: float = 1.0, meta: dict = None):
        self.step = step
        self.rc = rc
        self.output = output[:5000]
        self.duration = duration
        self.error = error[:2000]
        self.score = score  # 0.0 = total failure, 1.0 = perfect
        self.meta = meta or {}

    def ok(self) -> bool:
        return self.rc == 0 and self.score >= 0.5

    def to_dict(self) -> dict:
        return {
            "step": self.step, "rc": self.rc, "output": self.output[:500],
            "duration": round(self.duration, 2), "error": self.error[:500],
            "score": self.score, "meta": self.meta,
            "ok": self.ok(), "ts": datetime.now(timezone.utc).isoformat(),
        }


# ── Error Tracker (pattern detection) ────────────────────────────────────────

class ErrorTracker:
    """Tracks errors across pipeline runs. Detects recurring patterns."""

    def __init__(self):
        self._errors: list[dict] = []  # [{step, error, ts, ticket_id}]
        self._load()

    def _path(self) -> Path:
        _ensure_dir()
        return _PIPELINE_DIR / "error_log.json"

    def _load(self):
        p = self._path()
        if p.exists():
            try:
                self._errors = json.loads(p.read_text())[-200:]  # keep last 200
            except Exception:
                self._errors = []

    def _save(self):
        p = self._path()
        p.write_text(json.dumps(self._errors[-200:], indent=2))

    def record(self, step: str, error: str, ticket_id: str = ""):
        self._errors.append({
            "step": step, "error": error[:500], "ticket_id": ticket_id,
            "ts": datetime.now(timezone.utc).isoformat(),
        })
        self._save()

    def get_pattern(self, step: str, window: int = 10) -> dict:
        """Check if the same step has failed repeatedly in recent runs.
        Returns {recurring: bool, count: int, common_error: str, suggestion: str}."""
        recent = [e for e in self._errors[-window:] if e["step"] == step]
        if len(recent) < 2:
            return {"recurring": False, "count": len(recent), "common_error": "", "suggestion": ""}

        # Find most common error substring
        error_texts = [e["error"] for e in recent]
        # Simple frequency: first 100 chars as fingerprint
        fingerprints = {}
        for et in error_texts:
            fp = et[:100].strip()
            fingerprints[fp] = fingerprints.get(fp, 0) + 1
        common_fp = max(fingerprints, key=fingerprints.get) if fingerprints else ""
        count = fingerprints.get(common_fp, 0)

        suggestion = ""
        if count >= 3:
            if "OPENROUTER_API_KEY" in common_fp or "api_key" in common_fp.lower():
                suggestion = "change_model_or_key"
            elif "timeout" in common_fp.lower() or "timed out" in common_fp.lower():
                suggestion = "increase_timeout"
            elif "not found" in common_fp.lower() or "no such" in common_fp.lower():
                suggestion = "skip_step"
            elif "permission" in common_fp.lower():
                suggestion = "fix_permissions"
            else:
                suggestion = "ask_llm_for_fix"

        return {
            "recurring": count >= 2,
            "count": count,
            "common_error": common_fp,
            "suggestion": suggestion,
        }

    def clear(self):
        self._errors.clear()
        self._save()


# Global error tracker instance
_error_tracker = ErrorTracker()


# ── Pipeline State (per-ticket persistent state) ─────────────────────────────

class PipelineState:
    """Persistent state for a ticket pipeline — tracks iterations, results, decisions."""

    def __init__(self, ticket_id: str):
        self.ticket_id = ticket_id
        self.iteration = 0
        self.steps: list[dict] = []
        self.decisions: list[dict] = []
        self.overall_score = 0.0
        self.started_at = ""
        self.finished_at = ""
        self._load()

    def _path(self) -> Path:
        _ensure_dir()
        return _PIPELINE_DIR / f"{self.ticket_id}.json"

    def _load(self):
        p = self._path()
        if p.exists():
            try:
                d = json.loads(p.read_text())
                self.iteration = d.get("iteration", 0)
                self.steps = d.get("steps", [])
                self.decisions = d.get("decisions", [])
                self.overall_score = d.get("overall_score", 0.0)
                self.started_at = d.get("started_at", "")
                self.finished_at = d.get("finished_at", "")
            except Exception:
                pass

    def save(self):
        p = self._path()
        p.write_text(json.dumps({
            "ticket_id": self.ticket_id,
            "iteration": self.iteration,
            "steps": self.steps[-50:],  # keep last 50 step results
            "decisions": self.decisions[-20:],
            "overall_score": self.overall_score,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
        }, indent=2))

    def start_iteration(self):
        self.iteration += 1
        if not self.started_at:
            self.started_at = datetime.now(timezone.utc).isoformat()

    def record_step(self, result: StepResult):
        self.steps.append(result.to_dict())
        if not result.ok():
            _error_tracker.record(result.step, result.error or result.output[:200], self.ticket_id)
        self.save()

    def record_decision(self, decision: str, reason: str):
        self.decisions.append({
            "decision": decision, "reason": reason,
            "iteration": self.iteration,
            "ts": datetime.now(timezone.utc).isoformat(),
        })
        self.save()

    def compute_overall_score(self) -> float:
        """Compute weighted score from all steps in current iteration."""
        iter_steps = [s for s in self.steps if s.get("ok") is not None]
        if not iter_steps:
            return 0.0
        weights = {"ticket-work": 0.1, "implement": 0.4, "test-local": 0.25,
                   "commit-push": 0.15, "status-review": 0.1}
        total_w = 0
        total_s = 0
        for s in iter_steps[-5:]:  # last 5 steps = current pipeline
            w = weights.get(s["step"], 0.1)
            total_w += w
            total_s += w * s["score"]
        self.overall_score = total_s / total_w if total_w else 0.0
        self.save()
        return self.overall_score

    def should_retry(self, step: str) -> tuple[bool, str]:
        """Decide if a failed step should be retried, based on error patterns.
        Returns (should_retry, reason)."""
        pattern = _error_tracker.get_pattern(step)
        if pattern["recurring"] and pattern["count"] >= 3:
            # Same error 3+ times — don't retry blindly, change strategy
            return False, f"powtarzający się błąd ({pattern['count']}x): {pattern['common_error'][:80]}"
        # Check this pipeline's iteration count
        if self.iteration >= 3:
            return False, f"osiągnięto limit iteracji ({self.iteration})"
        return True, "próba ponowna"

    def get_strategy_adjustment(self, step: str) -> str:
        """Based on error patterns, suggest a strategy adjustment.
        Returns one of: 'retry', 'skip', 'change_model', 'ask_user', 'abort'."""
        pattern = _error_tracker.get_pattern(step)
        if not pattern["recurring"]:
            return "retry"
        suggestion = pattern.get("suggestion", "")
        if suggestion == "change_model_or_key":
            return "change_model"
        elif suggestion == "skip_step":
            return "skip"
        elif suggestion == "increase_timeout":
            return "retry"  # but with longer timeout
        elif suggestion == "ask_llm_for_fix":
            return "ask_llm"
        else:
            return "ask_user"

    def summary(self) -> str:
        """Human-readable summary of pipeline state."""
        lines = [f"Pipeline `{self.ticket_id}` — iteracja #{self.iteration}"]
        lines.append(f"Wynik: **{self.overall_score:.0%}**")
        for s in self.steps[-5:]:
            icon = "✅" if s.get("ok") else "❌"
            lines.append(f"  {icon} {s['step']} — {s['score']:.0%} ({s['duration']:.1f}s)")
        current_decisions = [d for d in self.decisions if d.get("iteration") == self.iteration]
        if current_decisions:
            lines.append("Decyzje:")
            for d in current_decisions[-3:]:
                lines.append(f"  → {d['decision']}: {d['reason']}")
        return "\n".join(lines)


# ── Pipeline Runner (adaptive orchestrator) ───────────────────────────────────

def run_step(exec_fn, step_name: str, *args, **kwargs) -> StepResult:
    """Execute a pipeline step, measure time, capture output, score result."""
    t0 = time.time()
    try:
        rc, output = exec_fn(*args, **kwargs)
        output = (output or "").strip()
        duration = time.time() - t0

        # Score the result
        score = 1.0 if rc == 0 else 0.0
        error = ""

        if rc == 0 and output:
            # Check for soft failures in output
            lower = output.lower()
            if "[llm] error" in lower or "openrouter_api_key not set" in lower:
                score = 0.1
                error = "LLM error in output"
            elif "nothing to commit" in lower:
                score = 0.2
                error = "No repository changes detected"
            elif "failed" in lower and "passed" not in lower:
                score = 0.3
                error = "Partial failure detected"
        elif rc != 0:
            error = output[:500]

        return StepResult(step_name, rc, output, duration, error, score)
    except Exception as e:
        return StepResult(step_name, -1, "", time.time() - t0, str(e), 0.0)


def evaluate_implementation(output: str) -> float:
    """Score an LLM implementation output based on heuristics.
    Returns 0.0-1.0 score."""
    if not output:
        return 0.0

    score = 0.5  # baseline
    lower = output.lower()

    # Positive signals
    if "```" in output:                    score += 0.15  # has code blocks
    if "file:" in lower or "path:" in lower: score += 0.1  # mentions file paths
    if "test" in lower:                     score += 0.05  # mentions testing
    if "import " in output:                 score += 0.05  # actual code
    if len(output) > 500:                   score += 0.05  # substantial output
    if len(output) > 2000:                  score += 0.05  # very detailed

    # Negative signals
    if "[llm] error" in lower:             score = 0.1
    if "api_key not set" in lower:         score = 0.05
    if "i cannot" in lower or "i'm unable" in lower: score -= 0.3
    if len(output) < 100:                   score -= 0.2   # too short

    return max(0.0, min(1.0, score))


def evaluate_test_output(output: str, rc: int) -> float:
    """Score test output."""
    if rc == 0:
        return 1.0
    if not output:
        return 0.3

    lower = output.lower()
    # Parse pass/fail counts
    import re
    passed = re.search(r'(\d+)\s*pass', lower)
    failed = re.search(r'(\d+)\s*fail', lower)
    if passed and failed:
        p, f = int(passed.group(1)), int(failed.group(1))
        if p + f > 0:
            return p / (p + f)
    if "passed" in lower and "failed" not in lower:
        return 0.9
    return 0.2


def build_retry_prompt(state: PipelineState, failed_step: StepResult, ticket: dict) -> str:
    """Build an LLM prompt that includes context from previous failures."""
    history = []
    for s in state.steps[-10:]:
        if not s.get("ok"):
            history.append(f"- Step '{s['step']}' failed: {s.get('error', '')[:200]}")

    prompt = (
        f"Implement this ticket (retry #{state.iteration}):\n"
        f"Title: {ticket.get('title', '')}\n"
        f"Description: {ticket.get('description', '')}\n\n"
    )

    if history:
        prompt += "Previous errors to avoid:\n" + "\n".join(history) + "\n\n"

    if failed_step.error:
        prompt += (
            f"The previous implementation attempt failed at step '{failed_step.step}' with:\n"
            f"```\n{failed_step.error[:500]}\n```\n\n"
            f"Fix the issue and provide an improved implementation.\n"
        )

    prompt += "Provide the code implementation. Write actual files, not just descriptions."
    return prompt
