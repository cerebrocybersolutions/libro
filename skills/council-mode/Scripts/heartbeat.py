#!/usr/bin/env python3
"""
heartbeat.py — Progress heartbeat emitter for long-running orchestration skills.

Kills silent waits. Emits to stderr by default so it doesn't corrupt
stdout-captured results.

WHY THIS EXISTS
---------------
Feedback memory (2026-04-17): any Cerebro subprocess running >15 seconds
must surface progress. Silent waits feel broken. This module is the
load-bearing piece for that rule across council-mode, advisor-dispatch,
and orchestrator-mode.

WHY IT'S PERSONA-AWARE
----------------------
Second load-bearing use: the persona voice-chirp layer (see
master-brain/decisions/persona-layer-design-brief.md — Voice Chirps
addendum, 2026-04-17 PM-3). Four hook points — entry, heartbeat,
completion, critique — map to four vocabulary banks per persona.
If no bank is attached for a slot, neutral messages fire. The UX
fix works with or without persona banks installed.

BASIC USAGE (neutral messages)
------------------------------
    from heartbeat import Heartbeat

    hb = Heartbeat(slots=["C-claude", "B-claude"], cadence_sec=30)
    hb.start()
    try:
        # Dispatch work; slot_started called inside worker thread so it
        # reflects ACTUAL start (not submit time, which differs under
        # ThreadPoolExecutor + MAX_CONCURRENCY).
        hb.slot_started("C-claude")
        result = do_work("C-claude")
        hb.slot_completed("C-claude", elapsed=result["elapsed"],
                          status=result["status"])
    finally:
        hb.stop()

PERSONA USAGE (voice chirps)
----------------------------
    from heartbeat import Heartbeat, PersonaBank

    sun_tzu = PersonaBank(
        name="Sun Tzu",
        entry=["First, the terrain.", "Before acting, know the cost."],
        heartbeat=["Still counting.", "The adversary is slower than I am."],
        completion=["Delivered.", "I counted. The rest was noise."],
    )
    hb = Heartbeat(
        slots=["C-claude", "B-claude"],
        cadence_sec=30,
        personas={"C-claude": sun_tzu},
    )

THREAD SAFETY
-------------
Internal state is guarded by a Lock. The heartbeat thread is a daemon;
it exits automatically on process exit even if stop() isn't called.

OUTPUT CONTRACT
---------------
All emissions go to the `stream` argument (default: sys.stderr).
Callers can redirect for testing or capture. Emissions are one line
each, prefixed with `[mm:ss]` elapsed time. No ANSI/color codes —
callers can pipe through their own styling layer if desired.
"""

import random
import sys
import threading
import time
from typing import Dict, List, Optional


class PersonaBank:
    """
    Voice-chirp vocabulary for a single persona.

    Each bank is a list of short lines (≤ 140 chars recommended). One is
    picked at random when the corresponding hook fires. Empty lists are
    allowed — the emitter falls back to neutral messages for that hook.
    """

    def __init__(
        self,
        name: str,
        entry: Optional[List[str]] = None,
        heartbeat: Optional[List[str]] = None,
        completion: Optional[List[str]] = None,
        critique: Optional[List[str]] = None,
    ):
        self.name = name
        self.entry = list(entry or [])
        self.heartbeat = list(heartbeat or [])
        self.completion = list(completion or [])
        self.critique = list(critique or [])

    def pick(self, hook: str) -> str:
        """Return a random line from the requested bank, or '' if bank empty."""
        bank = getattr(self, hook, None)
        if not bank:
            return ""
        return random.choice(bank)


class Heartbeat:
    """
    Progress emitter for long-running parallel dispatches.

    Fires on four hooks:
      - slot_started()   — called when a worker actually begins running
      - slot_completed() — called when a worker returns
      - (internal)       — background thread emits every cadence_sec
                           while any slot is still in-flight
      - slot_critique()  — optional, called post-run if a persona should
                           react to another slot's output

    If a persona bank is registered for a slot, a random line from the
    matching hook bank is emitted. If not, a neutral message fires.
    """

    def __init__(
        self,
        slots: List[str],
        cadence_sec: int = 30,
        personas: Optional[Dict[str, PersonaBank]] = None,
        stream=None,
    ):
        self.slots = list(slots)
        self.cadence_sec = max(5, cadence_sec)  # floor at 5s — no spam
        self.personas = dict(personas or {})
        self.stream = stream if stream is not None else sys.stderr

        self._start_time: Optional[float] = None
        self._running_slots: set = set()
        self._completed: List[str] = []
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

    # ── Internal helpers ─────────────────────────────────────────────────

    def _elapsed_tag(self) -> str:
        if self._start_time is None:
            return "[0:00]"
        sec = int(time.time() - self._start_time)
        return f"[{sec // 60}:{sec % 60:02d}]"

    def _emit(self, line: str) -> None:
        try:
            print(line, file=self.stream, flush=True)
        except Exception:
            # Never let the emitter break the caller. Silent-wait is
            # better than a crashed dispatch.
            pass

    def _slot_label(self, slot: str) -> str:
        """Display label: persona name if attached, else slot name."""
        persona = self.personas.get(slot)
        return f"{slot} ({persona.name})" if persona else slot

    def _persona_line(self, slot: str, hook: str, fallback: str) -> str:
        persona = self.personas.get(slot)
        if persona:
            line = persona.pick(hook)
            if line:
                return line
        return fallback

    # ── Public lifecycle ─────────────────────────────────────────────────

    def start(self) -> None:
        """Begin the background heartbeat thread. Safe to call once."""
        if self._thread is not None:
            return
        self._start_time = time.time()
        self._thread = threading.Thread(
            target=self._heartbeat_loop,
            daemon=True,
            name="cerebro-heartbeat",
        )
        self._thread.start()

    def stop(self) -> None:
        """Stop the heartbeat thread and wait for it to exit (2s timeout)."""
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None

    # ── Hook callbacks ───────────────────────────────────────────────────

    def slot_started(self, slot: str) -> None:
        with self._lock:
            self._running_slots.add(slot)
        label = self._slot_label(slot)
        line = self._persona_line(slot, "entry", f"{label} starts.")
        self._emit(f"{self._elapsed_tag()} {label}: {line}")

    def slot_completed(
        self,
        slot: str,
        elapsed: float,
        status: str = "ok",
    ) -> None:
        with self._lock:
            self._running_slots.discard(slot)
            self._completed.append(slot)
        label = self._slot_label(slot)
        base = self._persona_line(slot, "completion", f"{label} done.")
        status_tail = "" if status == "ok" else f" [{status}]"
        self._emit(
            f"{self._elapsed_tag()} {label}: {base} "
            f"({elapsed:.1f}s){status_tail}"
        )

    def slot_critique(self, slot: str, target: str, line: str) -> None:
        """
        Post-run critique chirp. Caller composes the line (or pulls it
        from persona.critique bank), emitter just formats + emits.
        """
        label = self._slot_label(slot)
        target_label = self._slot_label(target)
        self._emit(
            f"{self._elapsed_tag()} {label} → {target_label}: {line}"
        )

    # ── Background loop ──────────────────────────────────────────────────

    def _heartbeat_loop(self) -> None:
        while not self._stop_event.wait(self.cadence_sec):
            with self._lock:
                running = sorted(self._running_slots)
                done = sorted(self._completed)

            if not running:
                # Nothing in flight — heartbeat has nothing to say.
                # If stop() hasn't been called, we keep looping quietly
                # in case new slots start later.
                continue

            # Emit a neutral summary line. Per-slot persona heartbeats
            # would require tracking per-slot cadence; v1 keeps it simple
            # with one aggregate line.
            pieces = [f"running: {', '.join(running)}"]
            if done:
                pieces.append(f"done: {', '.join(done)}")
            self._emit(f"{self._elapsed_tag()} heartbeat — {' | '.join(pieces)}")


# ── Self-test ─────────────────────────────────────────────────────────────

def _selftest():
    """Simulate a 3-slot run with varied durations. Run: python3 heartbeat.py"""
    import concurrent.futures

    slots = ["C-claude", "B-claude", "C-local"]
    durations = {"C-claude": 2.0, "B-claude": 5.0, "C-local": 8.0}

    # Optional persona demo — uncomment to test voice chirps
    personas = {
        "C-claude": PersonaBank(
            name="Diogenes",
            entry=["Begin. I will be brief."],
            completion=["Done. It was not much."],
        ),
    }

    hb = Heartbeat(slots=slots, cadence_sec=3, personas=personas)
    hb.start()

    def work(slot):
        hb.slot_started(slot)
        time.sleep(durations[slot])
        hb.slot_completed(slot, elapsed=durations[slot], status="ok")
        return slot

    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
            futs = [pool.submit(work, s) for s in slots]
            for f in concurrent.futures.as_completed(futs):
                f.result()
    finally:
        hb.stop()

    print("\n[selftest] complete.", file=sys.stderr)


if __name__ == "__main__":
    _selftest()
