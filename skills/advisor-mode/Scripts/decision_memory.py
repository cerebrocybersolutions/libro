"""
decision_memory.py — Cerebro-fit deferred reflection memory log.

TradingAgents deferred reflection pattern port (TA HIGH port §2).
Source: tools/trading-agents/tradingagents/agents/utils/memory.py (301 lines, Apache 2.0)
Decision: decisions/2026-04-29-deferred-reflection-memory-log.md
Pre-wiring tag: pre-decision-memory-wiring

Implements MemoryWriter contract for the "decisions" namespace
(decisions/2026-04-29-memory-architecture-unification.md).

Key differences from TradingAgents source:
  - domain replaces ticker (govcon-bid, fleet-routing, product-scope, etc.)
  - recommendation is PROCEED | DEFER | DECLINE | WATCH (not BUY/HOLD/SELL)
  - No auto-resolution — the operator reports outcomes (Human-in-the-Mix #4)
  - Rotation: oldest resolved entries drop when max_entries exceeded;
    pending entries always preserved (never auto-resolved)
  - Atomic writes via temp + os.replace (inherited from source)
  - Reflection prompt produces 2-4 sentences of plain prose (no markdown)

Principles: Governance #1 · Reversibility #5 · Observability #6 · Reproducibility #8
"""

from __future__ import annotations

import os
import re
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# ── Constants ─────────────────────────────────────────────────────────────────

_SEPARATOR = "\n\n<!-- ENTRY_END -->\n\n"
_SEP_RE = re.compile(r"\n\n<!-- ENTRY_END -->\n\n")

_VALID_RECOMMENDATIONS = frozenset({"PROCEED", "DEFER", "DECLINE", "WATCH"})

_DEFAULT_LOG = Path.home() / ".cerebro" / "memory" / "decisions.md"
_DEFAULT_MAX_ENTRIES = 100

# ── Entry dataclass ───────────────────────────────────────────────────────────

@dataclass
class DecisionEntry:
    domain: str                          # decision_domain (e.g. "govcon-bid")
    date: str                            # ISO date string YYYY-MM-DD
    recommendation: str                  # PROCEED | DEFER | DECLINE | WATCH
    decision_text: str                   # Full decision body from advisor/council session
    outcome: Optional[str] = None        # Qualitative outcome (operator-reported)
    vs_baseline: Optional[str] = None    # Relative to "what would have happened"
    elapsed_days: Optional[int] = None   # Days from decision to outcome report
    reflection: Optional[str] = None     # 2-4 sentence terse lesson

    @property
    def is_pending(self) -> bool:
        return self.outcome is None

    def header(self) -> str:
        """Single-line header matching the TradingMemoryLog format."""
        if self.is_pending:
            return f"[{self.date} | {self.domain} | {self.recommendation} | pending]"
        parts = [self.date, self.domain, self.recommendation]
        if self.outcome:
            parts.append(self.outcome[:60])
        if self.vs_baseline:
            parts.append(f"vs-baseline: {self.vs_baseline[:30]}")
        if self.elapsed_days is not None:
            parts.append(f"{self.elapsed_days}d")
        return "[" + " | ".join(parts) + "]"

    def to_markdown(self) -> str:
        """Render entry as markdown block for log file."""
        lines = [self.header(), "", "DECISION:", self.decision_text.strip()]
        if self.reflection:
            lines += ["", "REFLECTION:", self.reflection.strip()]
        return "\n".join(lines)


# ── Parser ────────────────────────────────────────────────────────────────────

_HEADER_RE = re.compile(
    r"^\[(?P<date>\d{4}-\d{2}-\d{2})\s*\|\s*"
    r"(?P<domain>[^\|]+?)\s*\|\s*"
    r"(?P<rec>PROCEED|DEFER|DECLINE|WATCH)\s*\|\s*"
    r"(?P<rest>[^\]]*)\]$"
)


def _parse_entry(raw: str) -> Optional[DecisionEntry]:
    """Parse a single entry block. Returns None if header doesn't match."""
    raw = raw.strip()
    if not raw:
        return None

    lines = raw.split("\n")
    header_line = lines[0].strip()
    m = _HEADER_RE.match(header_line)
    if not m:
        return None

    date = m.group("date")
    domain = m.group("domain").strip()
    rec = m.group("rec").strip()
    rest = m.group("rest").strip()

    # Determine pending vs resolved from rest field
    is_pending = rest == "pending"

    # Extract decision_text
    decision_text = ""
    reflection = ""
    section = None
    buf: list[str] = []

    for line in lines[1:]:
        if line.strip() == "DECISION:":
            if section and buf:
                if section == "decision":
                    decision_text = "\n".join(buf).strip()
                elif section == "reflection":
                    reflection = "\n".join(buf).strip()
            section = "decision"
            buf = []
        elif line.strip() == "REFLECTION:":
            if section and buf:
                if section == "decision":
                    decision_text = "\n".join(buf).strip()
                elif section == "reflection":
                    reflection = "\n".join(buf).strip()
            section = "reflection"
            buf = []
        else:
            buf.append(line)

    if section == "decision" and buf:
        decision_text = "\n".join(buf).strip()
    elif section == "reflection" and buf:
        reflection = "\n".join(buf).strip()

    # Parse rest fields for resolved entries (outcome | vs_baseline | Nd)
    outcome = None
    vs_baseline = None
    elapsed_days = None
    if not is_pending:
        rest_parts = [p.strip() for p in rest.split("|")]
        if rest_parts:
            outcome = rest_parts[0] if rest_parts[0] else None
        for part in rest_parts[1:]:
            if part.startswith("vs-baseline:"):
                vs_baseline = part[len("vs-baseline:"):].strip()
            elif re.match(r"^\d+d$", part):
                try:
                    elapsed_days = int(part[:-1])
                except ValueError:
                    pass

    return DecisionEntry(
        domain=domain,
        date=date,
        recommendation=rec,
        decision_text=decision_text,
        outcome=outcome,
        vs_baseline=vs_baseline,
        elapsed_days=elapsed_days,
        reflection=reflection if reflection else None,
    )


# ── Main class ────────────────────────────────────────────────────────────────

class CerebroDecisionMemory:
    """
    Append-only markdown decision log for Cerebro advisor and council sessions.

    File format: entries separated by `<!-- ENTRY_END -->` comments (safe hard delimiter).

    Usage::

        mem = CerebroDecisionMemory()
        mem.store_decision(
            domain="govcon-bid",
            date="2026-05-08",
            recommendation="PROCEED",
            decision_text="Council unanimously recommends bidding on SAMPLE-2026-00001...",
        )
        context = mem.get_past_context(domain="govcon-bid")
        # inject context into advisor system prompt

        # later, when outcome is known:
        mem.update_with_outcome(
            domain="govcon-bid",
            date="2026-05-08",
            outcome="Won contract, $145K awarded",
            reflection="SDVOSB set-aside was the key differentiator...",
        )

    Implements MemoryWriter contract:
        store_decision() → MemoryWriter.write(domain="decisions", payload=entry)
        get_past_context() → MemoryWriter.read(domain="decisions", query=domain)
    """

    def __init__(self, config: Optional[dict] = None) -> None:
        cfg = config or {}
        log_path_raw = cfg.get("decision_log_path", str(_DEFAULT_LOG))
        self._log_path = Path(log_path_raw).expanduser()
        self._max_entries = int(cfg.get("decision_log_max_entries", _DEFAULT_MAX_ENTRIES))
        self._log_path.parent.mkdir(parents=True, exist_ok=True)

    # ── Public API ────────────────────────────────────────────────────────────

    def store_decision(
        self,
        domain: str,
        date: str,
        recommendation: str,
        decision_text: str,
    ) -> None:
        """
        Record a decision as pending. Called at end of advisor/council session.
        Idempotency guard: if an entry for (domain, date, recommendation) already
        exists, this is a no-op (prevents duplicate entries on re-run).
        """
        if recommendation not in _VALID_RECOMMENDATIONS:
            raise ValueError(
                f"Invalid recommendation {recommendation!r}. "
                f"Must be one of {sorted(_VALID_RECOMMENDATIONS)}."
            )

        entries = self._load_entries()

        # Idempotency check
        for e in entries:
            if (e.domain == domain and e.date == date
                    and e.recommendation == recommendation):
                sys.stderr.write(
                    f"[decision_memory] store_decision: entry already exists "
                    f"({domain}, {date}, {recommendation}) — skipping\n"
                )
                return

        new_entry = DecisionEntry(
            domain=domain,
            date=date,
            recommendation=recommendation,
            decision_text=decision_text,
        )
        entries.append(new_entry)
        self._apply_rotation(entries)
        self._write(entries)
        sys.stderr.write(
            f"[decision_memory] stored: {domain} | {date} | {recommendation}\n"
        )

    def update_with_outcome(
        self,
        domain: str,
        date: str,
        outcome: str,
        reflection: str,
        vs_baseline: Optional[str] = None,
    ) -> None:
        """
        Resolve a pending entry with the operator's reported outcome + reflection.
        Atomic write via temp + os.replace (Reversibility #5).
        Human-in-the-Mix #4: the operator provides outcome and reflection prompt input;
        this method only stores the result — it does not generate reflection text.
        """
        entries = self._load_entries()
        found = False

        today = datetime.now(timezone.utc).date()

        for e in entries:
            if e.domain == domain and e.date == date and e.is_pending:
                try:
                    decision_date = datetime.fromisoformat(date).date()
                    elapsed = (today - decision_date).days
                except ValueError:
                    elapsed = None

                e.outcome = outcome
                e.vs_baseline = vs_baseline
                e.elapsed_days = elapsed
                e.reflection = reflection
                found = True
                sys.stderr.write(
                    f"[decision_memory] resolved: {domain} | {date} | "
                    f"outcome={outcome[:40]!r}\n"
                )
                break

        if not found:
            sys.stderr.write(
                f"[decision_memory] update_with_outcome: no pending entry "
                f"found for ({domain}, {date}) — no-op\n"
            )
            return

        self._write(entries)

    def get_past_context(
        self,
        domain: str,
        n_same: int = 3,
        n_cross: int = 2,
    ) -> str:
        """
        Return formatted past decisions for prompt injection.

        Returns last n_same resolved entries for the same domain +
        last n_cross resolved entries for other domains.
        Pending entries are excluded (no outcome = no lesson yet).
        Returns empty string if nothing relevant exists.
        """
        entries = self._load_entries()
        resolved = [e for e in entries if not e.is_pending]

        same = [e for e in reversed(resolved) if e.domain == domain][:n_same]
        other = [e for e in reversed(resolved) if e.domain != domain][:n_cross]
        combined = same + other

        if not combined:
            return ""

        parts = ["### Past Decisions (for context — do not cite as facts)"]
        for e in combined:
            label = "(same domain)" if e.domain == domain else f"(domain: {e.domain})"
            parts.append(f"\n**{e.date} | {e.recommendation}** {label}")
            parts.append(f"Decision: {e.decision_text[:200].strip()}...")
            if e.outcome:
                parts.append(f"Outcome: {e.outcome}")
            if e.reflection:
                parts.append(f"Lesson: {e.reflection}")

        return "\n".join(parts)

    def get_pending_entries(self) -> list[DecisionEntry]:
        """Return all pending (unresolved) entries."""
        return [e for e in self._load_entries() if e.is_pending]

    def get_all_entries(self) -> list[DecisionEntry]:
        """Return all entries (pending + resolved)."""
        return self._load_entries()

    # ── Internal ──────────────────────────────────────────────────────────────

    def _load_entries(self) -> list[DecisionEntry]:
        """Load all entries from the log file. Returns [] if file missing."""
        if not self._log_path.exists():
            return []
        raw = self._log_path.read_text(encoding="utf-8")
        if not raw.strip():
            return []
        blocks = _SEP_RE.split(raw)
        entries: list[DecisionEntry] = []
        for block in blocks:
            parsed = _parse_entry(block)
            if parsed is not None:
                entries.append(parsed)
        return entries

    def _apply_rotation(self, entries: list[DecisionEntry]) -> None:
        """
        Drop oldest resolved entries when max_entries exceeded.
        Pending entries are NEVER dropped (they haven't been acted on yet).
        """
        resolved = [e for e in entries if not e.is_pending]
        pending = [e for e in entries if e.is_pending]

        overflow = len(entries) - self._max_entries
        if overflow <= 0:
            return

        # Drop oldest resolved entries first
        to_drop = min(overflow, len(resolved))
        kept_resolved = resolved[to_drop:]  # oldest are at front

        entries.clear()
        entries.extend(kept_resolved + pending)
        sys.stderr.write(
            f"[decision_memory] rotation: dropped {to_drop} resolved entries "
            f"(cap={self._max_entries})\n"
        )

    def _write(self, entries: list[DecisionEntry]) -> None:
        """Atomic write via temp file + os.replace (Reversibility #5)."""
        content = _SEPARATOR.join(e.to_markdown() for e in entries)
        if content:
            content += "\n\n<!-- ENTRY_END -->\n\n"

        tmp_path = self._log_path.with_suffix(".md.tmp")
        tmp_path.write_text(content, encoding="utf-8")
        os.replace(str(tmp_path), str(self._log_path))
        sys.stderr.write(
            f"[decision_memory] wrote {len(entries)} entries "
            f"to {self._log_path}\n"
        )


# ── Reflection prompt template ─────────────────────────────────────────────────
#
# Used by advisor-mode sessionend Step 9.5 to generate the reflection text
# that gets passed to update_with_outcome(). The LLM output is stored verbatim
# and re-read by future advisor sessions via get_past_context().
#
REFLECTION_PROMPT_TEMPLATE = """\
You are reviewing a past Cerebro decision now that the outcome is known.
Write exactly 2-4 sentences of plain prose (no bullets, no headers, no markdown).

Decision made: {decision_text}
Recommendation: {recommendation}
Observed outcome: {outcome}

Cover in order:
1. Was the recommendation directionally correct? (cite the observed outcome)
2. Which part of the reasoning held or failed?
3. One concrete lesson to apply to the next similar decision.

Be terse. Your output will be stored verbatim and re-read by future advisor sessions.
"""


def generate_reflection_prompt(entry: DecisionEntry) -> str:
    """Build the reflection prompt for a just-resolved entry."""
    return REFLECTION_PROMPT_TEMPLATE.format(
        decision_text=entry.decision_text[:500].strip(),
        recommendation=entry.recommendation,
        outcome=entry.outcome or "(no outcome provided)",
    )


# ── CLI smoke ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        mem = CerebroDecisionMemory(config={
            "decision_log_path": str(Path(tmpdir) / "decisions.md"),
            "decision_log_max_entries": 10,
        })

        # store
        mem.store_decision(
            domain="govcon-bid",
            date="2026-05-08",
            recommendation="PROCEED",
            decision_text="Council recommends bidding on SAMPLE-2026-00001. "
                          "SDVOSB set-aside + CUI scope aligns with Cerebro capabilities.",
        )

        # idempotency guard
        mem.store_decision(
            domain="govcon-bid",
            date="2026-05-08",
            recommendation="PROCEED",
            decision_text="Duplicate — should be ignored.",
        )

        # pending check
        pending = mem.get_pending_entries()
        assert len(pending) == 1, f"Expected 1 pending, got {len(pending)}"
        assert pending[0].domain == "govcon-bid"
        print(f"  pending entry: {pending[0].header()}")

        # context pre-resolution (should be empty — no resolved entries yet)
        ctx = mem.get_past_context("govcon-bid")
        assert ctx == "", f"Expected empty context pre-resolution, got: {ctx!r}"
        print("  pre-resolution context: (empty — correct)")

        # resolve
        mem.update_with_outcome(
            domain="govcon-bid",
            date="2026-05-08",
            outcome="Won contract, $145K awarded 2026-07-01",
            reflection=(
                "PROCEED was correct — SDVOSB set-aside was the key differentiator. "
                "Pricing was 15% below winning average. "
                "Lesson: lead with SDVOSB status early in the technical volume."
            ),
        )

        # context post-resolution
        ctx = mem.get_past_context("govcon-bid")
        assert "PROCEED" in ctx
        assert "Lesson:" in ctx
        print(f"  post-resolution context snippet: {ctx[:80]}...")

        # reflection prompt
        resolved = [e for e in mem.get_all_entries() if not e.is_pending]
        prompt = generate_reflection_prompt(resolved[0])
        assert "Was the recommendation" in prompt
        print(f"  reflection prompt length: {len(prompt)} chars")

    print("[decision_memory] Smoke PASS — all assertions passed")
