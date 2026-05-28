#!/usr/bin/env python3
"""
circuit_breaker.py — Failure-aware tier routing for orchestrator chains.

Keyed on (tier, task_class). Three states per key: closed (normal), open (skip to
escalate_to), half-open (one probe allowed to close). Trips when 3 failures occur in
a 24-hour window. Auto-transitions open → half-open after 24-hour cooldown. One
passing probe in half-open state closes the breaker.

State is persisted as JSON at state/circuit-breakers.json. Same
substrate the LLMs read — Markdown-4D-Chess-compatible (JSON is markdown-adjacent
enough for the thesis; it's text a human can read at a glance).

Usage (from orchestrator_run.py):

    from circuit_breaker import CircuitBreaker
    cb = CircuitBreaker()  # auto-resolves state file path

    # Before dispatch:
    if cb.is_open(tier, task_class):
        # Skip to escalate_to; record as pre-empted
        tier = escalate_to

    # After gate evaluation:
    cb.record(tier, task_class, passed=passed_gate)

Not hardcoded: threshold, cooldown, state file path — override via env vars or
constructor args.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


# Auto-resolve state file location from this script's path.
# This script lives at: master-brain/skills/orchestrator-mode/Scripts/circuit_breaker.py
# State file lives at:  master-brain/state/circuit-breakers.json
_DEFAULT_STATE_FILE = (
    Path(__file__).resolve().parent.parent.parent.parent / "state" / "circuit-breakers.json"
)

# Defaults per design doc — override via env or constructor.
_DEFAULT_FAIL_THRESHOLD = 3
_DEFAULT_WINDOW_SECONDS = 24 * 60 * 60  # 24 hours
_DEFAULT_COOLDOWN_SECONDS = 24 * 60 * 60  # 24 hours


@dataclass
class BreakerState:
    """Per-key breaker state. Lives inside the state file under its (tier::task_class) key."""
    state: str = "closed"  # closed | open | half-open
    failures: list = field(default_factory=list)  # list of ISO-8601 timestamps
    opened_at: Optional[str] = None  # ISO-8601 timestamp when last opened
    last_probe_passed: Optional[bool] = None

    def to_dict(self) -> dict:
        return {
            "state": self.state,
            "failures": self.failures,
            "opened_at": self.opened_at,
            "last_probe_passed": self.last_probe_passed,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "BreakerState":
        return cls(
            state=d.get("state", "closed"),
            failures=d.get("failures", []),
            opened_at=d.get("opened_at"),
            last_probe_passed=d.get("last_probe_passed"),
        )


class CircuitBreaker:
    def __init__(
        self,
        state_file: Optional[Path] = None,
        fail_threshold: int = _DEFAULT_FAIL_THRESHOLD,
        window_seconds: int = _DEFAULT_WINDOW_SECONDS,
        cooldown_seconds: int = _DEFAULT_COOLDOWN_SECONDS,
    ):
        self.state_file = Path(
            os.environ.get("CEREBRO_CB_STATE_FILE", state_file or _DEFAULT_STATE_FILE)
        )
        self.fail_threshold = int(os.environ.get("CEREBRO_CB_THRESHOLD", fail_threshold))
        self.window_seconds = int(os.environ.get("CEREBRO_CB_WINDOW_S", window_seconds))
        self.cooldown_seconds = int(os.environ.get("CEREBRO_CB_COOLDOWN_S", cooldown_seconds))
        self._state: dict = self._load()

    # --- Persistence ------------------------------------------------------

    def _load(self) -> dict:
        if not self.state_file.exists():
            return {}
        try:
            with self.state_file.open() as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            # Corrupted state file — start fresh, don't block the orchestrator.
            return {}

    def _save(self) -> None:
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.state_file.with_suffix(".tmp")
        with tmp.open("w") as f:
            json.dump(self._state, f, indent=2, sort_keys=True)
        tmp.replace(self.state_file)

    # --- Helpers ----------------------------------------------------------

    @staticmethod
    def _key(tier: str, task_class: str) -> str:
        return f"{tier}::{task_class}"

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _parse(ts: str) -> datetime:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))

    def _get(self, tier: str, task_class: str) -> BreakerState:
        key = self._key(tier, task_class)
        raw = self._state.get(key)
        if raw is None:
            return BreakerState()
        return BreakerState.from_dict(raw)

    def _put(self, tier: str, task_class: str, bs: BreakerState) -> None:
        key = self._key(tier, task_class)
        self._state[key] = bs.to_dict()

    def _prune_failures(self, bs: BreakerState) -> None:
        """Drop failure timestamps older than window_seconds."""
        cutoff = self._now().timestamp() - self.window_seconds
        bs.failures = [
            ts for ts in bs.failures
            if self._parse(ts).timestamp() > cutoff
        ]

    def _maybe_transition_open_to_half_open(self, bs: BreakerState) -> None:
        """If cooldown has elapsed, move open → half-open (allow one probe)."""
        if bs.state != "open" or not bs.opened_at:
            return
        age = self._now().timestamp() - self._parse(bs.opened_at).timestamp()
        if age >= self.cooldown_seconds:
            bs.state = "half-open"

    # --- Public API -------------------------------------------------------

    def is_open(self, tier: str, task_class: str) -> bool:
        """
        Return True if the breaker is currently OPEN (requests should be diverted).
        Returns False for closed or half-open (half-open allows the probe through).
        """
        bs = self._get(tier, task_class)
        self._maybe_transition_open_to_half_open(bs)
        # Persist the transition if it happened so observers see it.
        self._put(tier, task_class, bs)
        self._save()
        return bs.state == "open"

    def state_of(self, tier: str, task_class: str) -> str:
        """Return the current state string for a key (after any auto-transition)."""
        bs = self._get(tier, task_class)
        self._maybe_transition_open_to_half_open(bs)
        return bs.state

    def record(self, tier: str, task_class: str, passed: bool) -> str:
        """
        Record a gate outcome. Returns the *new* state after the update.

        Transitions:
          - closed + fail  → closed, accumulate; if threshold hit inside window, open.
          - closed + pass  → closed, clear failures (clean slate).
          - half-open + pass → closed.
          - half-open + fail → open (restart cooldown).
          - open + anything → no-op (shouldn't happen; is_open() should divert first).
        """
        bs = self._get(tier, task_class)
        self._maybe_transition_open_to_half_open(bs)
        now_iso = self._now().isoformat()

        if bs.state == "open":
            # Divert should have happened upstream; record but don't mutate state here.
            bs.last_probe_passed = passed
            self._put(tier, task_class, bs)
            self._save()
            return bs.state

        if bs.state == "half-open":
            if passed:
                bs.state = "closed"
                bs.failures = []
                bs.opened_at = None
                bs.last_probe_passed = True
            else:
                bs.state = "open"
                bs.opened_at = now_iso
                bs.failures.append(now_iso)
                bs.last_probe_passed = False
            self._put(tier, task_class, bs)
            self._save()
            return bs.state

        # closed
        if passed:
            bs.failures = []  # clean slate on success
        else:
            bs.failures.append(now_iso)
            self._prune_failures(bs)
            if len(bs.failures) >= self.fail_threshold:
                bs.state = "open"
                bs.opened_at = now_iso
        self._put(tier, task_class, bs)
        self._save()
        return bs.state

    def snapshot(self) -> dict:
        """Return a copy of the current state — for observability/reporting."""
        return json.loads(json.dumps(self._state))


# --- CLI for manual inspection / reset --------------------------------------

def _cli() -> int:
    import argparse
    p = argparse.ArgumentParser(description="Cerebro orchestrator circuit-breaker CLI")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("show", help="Print current state file")

    pr = sub.add_parser("reset", help="Reset breaker(s)")
    pr.add_argument("--tier", help="Tier name (e.g., B-claude); omit to reset all")
    pr.add_argument("--task-class", help="Task class; omit to match all for tier")
    pr.add_argument("--all", action="store_true", help="Reset every breaker")

    args = p.parse_args()
    cb = CircuitBreaker()

    if args.cmd == "show":
        snap = cb.snapshot()
        if not snap:
            print("(no breakers recorded)")
        else:
            print(json.dumps(snap, indent=2, sort_keys=True))
        return 0

    if args.cmd == "reset":
        if args.all:
            cb._state = {}
            cb._save()
            print("All breakers reset.")
            return 0
        if not args.tier:
            print("error: --tier required (or --all)")
            return 2
        if args.task_class:
            key = cb._key(args.tier, args.task_class)
            if key in cb._state:
                del cb._state[key]
                cb._save()
                print(f"Reset: {key}")
            else:
                print(f"(no breaker at {key})")
            return 0
        # tier without task_class: wipe all keys for that tier
        prefix = f"{args.tier}::"
        keys = [k for k in cb._state if k.startswith(prefix)]
        for k in keys:
            del cb._state[k]
        cb._save()
        print(f"Reset {len(keys)} breakers for tier={args.tier}")
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(_cli())
