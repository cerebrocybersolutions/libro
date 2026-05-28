"""
json_checkpointer.py — Cerebro JSON-per-run checkpoint backend for council-mode v2
TradingAgents §4 port (LangGraph checkpoint pattern)

Implements a lightweight checkpointer that writes CouncilRunState to
state/council-runs/<run_id>.json on each checkpoint. Replaces LangGraph's
default SQLite checkpointer — JSON is git-trackable, inspectable without tooling,
and diff-friendly. Aligned with Lockstep #3 and Reproducibility #8.

At Cerebro volume (≤10 runs/session), JSON write performance is a non-issue.

LangGraph dependency is OPTIONAL — if LangGraph is not installed, this module
provides a standalone JsonRunStore that works without LangGraph's CheckpointSaver
interface. The store is still used by council_graph.py for persistence.

Wired: 2026-04-30 per decisions/2026-04-30-council-mode-v2-langgraph-typed-substates.md
Install: pip3 install "langgraph>=0.2,<0.3" --break-system-packages (when ready to wire Phase 4)
Snapshot tag: pre-council-mode-v2-langgraph-2026-04-30
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, Optional

from pydantic import BaseModel

# ── Repo-relative default path ─────────────────────────────────────────────────

_HERE = Path(__file__).resolve().parent
_BRAIN_ROOT = _HERE.parents[2]
_DEFAULT_RUNS_DIR = _BRAIN_ROOT / "state" / "council-runs"


# ── Standalone store (no LangGraph required) ──────────────────────────────────

class JsonRunStore:
    """
    Minimal key-value store for CouncilRunState JSON files.
    Works without LangGraph — council_graph.py uses this for checkpointing
    when LangGraph is available, and as a standalone store when it is not.
    """

    def __init__(self, runs_dir: Path = _DEFAULT_RUNS_DIR):
        self.runs_dir = runs_dir
        self.runs_dir.mkdir(parents=True, exist_ok=True)

    def put(self, run_id: str, state: BaseModel) -> Path:
        """Serialize state to JSON and write to runs_dir/<run_id>.json."""
        path = self.runs_dir / f"{run_id}.json"
        path.write_text(
            state.model_dump_json(indent=2),
            encoding="utf-8",
        )
        return path

    def get(self, run_id: str, model_class: type) -> Optional[BaseModel]:
        """Load and parse a run checkpoint."""
        path = self.runs_dir / f"{run_id}.json"
        if not path.exists():
            return None
        try:
            return model_class.model_validate_json(path.read_text(encoding="utf-8"))
        except Exception as e:
            import sys
            sys.stderr.write(f"[json_checkpointer] WARN: failed to parse {path}: {e}\n")
            return None

    def list_runs(self) -> list[dict]:
        """
        Return a list of dicts with run_id, final_outcome, started_at, task_preview.
        Used by sessionstart Tier-0 in-flight probe.
        """
        results = []
        for f in sorted(self.runs_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                results.append({
                    "run_id": data.get("run_id", f.stem),
                    "final_outcome": data.get("final_outcome"),
                    "started_at": data.get("started_at"),
                    "task_preview": (data.get("task") or "")[:80],
                    "path": str(f),
                })
            except Exception:
                pass
        return results

    def list_inflight(self) -> list[dict]:
        """Return only in-flight runs (final_outcome is None)."""
        return [r for r in self.list_runs() if r["final_outcome"] is None]

    def delete(self, run_id: str) -> bool:
        """Delete a checkpoint file. Returns True if deleted."""
        path = self.runs_dir / f"{run_id}.json"
        if path.exists():
            path.unlink()
            return True
        return False


# ── LangGraph checkpointer wrapper (optional) ─────────────────────────────────

def make_langgraph_checkpointer(runs_dir: Path = _DEFAULT_RUNS_DIR):
    """
    Returns a LangGraph-compatible checkpointer backed by JsonRunStore.
    Requires LangGraph to be installed (pip3 install "langgraph>=0.2,<0.3").
    Returns None if LangGraph is not available — callers should fall back to JsonRunStore.
    """
    try:
        from langgraph.checkpoint.base import BaseCheckpointSaver, CheckpointTuple, Checkpoint
        import uuid as _uuid

        store = JsonRunStore(runs_dir)

        class JsonCheckpointer(BaseCheckpointSaver):
            """LangGraph checkpointer that persists to JSON files."""

            def put(self, config, checkpoint, metadata, new_versions):
                thread_id = config["configurable"]["thread_id"]
                data = {
                    "thread_id": thread_id,
                    "checkpoint": checkpoint,
                    "metadata": metadata,
                    "ts": datetime.now(timezone.utc).isoformat(),
                }
                path = runs_dir / f"{thread_id}.checkpoint.json"
                runs_dir.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
                return config

            def get_tuple(self, config) -> Optional[CheckpointTuple]:
                thread_id = config["configurable"]["thread_id"]
                path = runs_dir / f"{thread_id}.checkpoint.json"
                if not path.exists():
                    return None
                try:
                    data = json.loads(path.read_text(encoding="utf-8"))
                    return CheckpointTuple(
                        config=config,
                        checkpoint=data["checkpoint"],
                        metadata=data.get("metadata", {}),
                        parent_config=None,
                    )
                except Exception:
                    return None

            def list(self, config, **kwargs) -> Iterator[CheckpointTuple]:
                # Single checkpoint per thread_id
                ct = self.get_tuple(config)
                if ct:
                    yield ct

        return JsonCheckpointer()

    except ImportError:
        return None


# ── CLI usage ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    store = JsonRunStore()
    runs = store.list_runs()
    if not runs:
        print("No council runs found in", store.runs_dir)
    else:
        print(f"Council runs ({len(runs)} total, {len(store.list_inflight())} in-flight):")
        for r in runs:
            status = r["final_outcome"] or "IN-FLIGHT"
            print(f"  {r['run_id']}  [{status}]  {r['task_preview']}")
