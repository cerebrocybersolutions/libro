#!/usr/bin/env python3
"""
persona_loader.py — Persona layer loader for council-mode. Reads persona_tier_map.json +
per-persona system prompts and voice banks, and exposes them in the
shapes council_run.py / heartbeat.py need.

WHY THIS MODULE EXISTS
----------------------
Separates persona *data loading* from council *dispatch logic*. council_run.py
shouldn't know how voice banks are parsed; it just asks "give me the system
prompt for slot X" and "give me a PersonaBank dict for this roster".

CONTRACT
--------
    from persona_loader import PersonaLoader
    loader = PersonaLoader()  # auto-resolves paths

    loader.system_prompt_for("A-claude")          # → str | None
    loader.persona_banks_for(["A-claude", ...])   # → dict[slot, PersonaBank]
    loader.persona_name_for("A-claude")           # → str | None (e.g. "Sun Tzu")
    loader.enabled                                # → bool (is the map loaded?)

GRACEFUL DEGRADATION
--------------------
If the config file or any persona file is missing / malformed, the loader
returns None / {} rather than raising. Neutral council runs keep working.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Dict, List, Optional

# Local import — heartbeat lives next door in this same Scripts directory.
from heartbeat import PersonaBank


# Auto-resolve skill root from this file's location.
# This script lives at: <BRAIN_ROOT>/skills/council-mode/Scripts/persona_loader.py
# Skill root:            <BRAIN_ROOT>/skills/council-mode/
_SKILL_ROOT = Path(__file__).resolve().parents[1]
_DEFAULT_CONFIG = _SKILL_ROOT / "config" / "persona_tier_map.json"


# --- Voice bank parser ------------------------------------------------------

# Voice banks are markdown files with four sections:
#   ## Entry        → list of numbered lines
#   ## Heartbeat    → list
#   ## Completion   → list
#   ## Critique     → list
# Any "1. some line" style numbered list under one of those headers counts.

_HOOK_HEADERS = {
    "entry":      re.compile(r"^##\s+Entry\b", re.IGNORECASE),
    "heartbeat":  re.compile(r"^##\s+Heartbeat\b", re.IGNORECASE),
    "completion": re.compile(r"^##\s+Completion\b", re.IGNORECASE),
    "critique":   re.compile(r"^##\s+Critique\b", re.IGNORECASE),
}

_NUMBERED_LINE = re.compile(r"^\s*\d+\.\s+(.*\S.*)\s*$")
_ANY_HEADER    = re.compile(r"^##\s+\S")


def _parse_voice_bank(text: str) -> Dict[str, List[str]]:
    """Return {hook: [lines]} for hooks found in text. Missing hooks = []."""
    sections: Dict[str, List[str]] = {"entry": [], "heartbeat": [],
                                      "completion": [], "critique": []}
    current: Optional[str] = None
    for raw in text.splitlines():
        line = raw.rstrip()
        # New section header?
        matched = False
        for hook, pat in _HOOK_HEADERS.items():
            if pat.match(line):
                current = hook
                matched = True
                break
        if matched:
            continue
        # Any other "## " header closes the current hook's collection.
        if _ANY_HEADER.match(line) and current is not None:
            current = None
            continue
        if current is None:
            continue
        m = _NUMBERED_LINE.match(line)
        if m:
            sections[current].append(m.group(1).strip())
    return sections


# --- Loader -----------------------------------------------------------------


class PersonaLoader:
    """
    Reads the persona tier map + per-persona assets, on demand.
    Caches parsed content after first access. Safe to instantiate many times.
    """

    def __init__(
        self,
        config_path: Optional[Path] = None,
        skill_root: Optional[Path] = None,
    ):
        self.config_path = Path(
            os.environ.get("CEREBRO_PERSONA_MAP", config_path or _DEFAULT_CONFIG)
        )
        self.skill_root = Path(skill_root or _SKILL_ROOT)
        self._map: dict = {}
        self._sys_prompt_cache: Dict[str, Optional[str]] = {}
        self._bank_cache: Dict[str, Optional[PersonaBank]] = {}
        self._load_config()

    # --- Config ----

    def _load_config(self) -> None:
        if not self.config_path.exists():
            return
        try:
            with self.config_path.open() as f:
                self._map = json.load(f)
        except (json.JSONDecodeError, OSError):
            self._map = {}

    @property
    def enabled(self) -> bool:
        """True if the map was loaded and has at least one persona."""
        return bool(self._map.get("personas"))

    @property
    def version(self) -> str:
        return self._map.get("_meta", {}).get("version", "unknown")

    def roster(self, name: str = "full") -> List[str]:
        """Return a named roster list (e.g. 'full' or 'lean')."""
        return list(self._map.get("rosters", {}).get(name, []))

    # --- Slot → persona lookup ----

    def _persona_for_slot(self, slot: str) -> Optional[dict]:
        """Return the first persona dict whose slot matches, else None."""
        if not self._map:
            return None
        for persona_id, pdict in self._map.get("personas", {}).items():
            if pdict.get("slot") == slot:
                return {"id": persona_id, **pdict}
        return None

    def persona_id_for(self, slot: str) -> Optional[str]:
        p = self._persona_for_slot(slot)
        return p["id"] if p else None

    def persona_name_for(self, slot: str) -> Optional[str]:
        """Display name (e.g. 'Sun Tzu') for a slot, or None if unmapped."""
        p = self._persona_for_slot(slot)
        if not p:
            return None
        # Prefer an explicit display_name; fall back to prettifying the id.
        return p.get("display_name") or _prettify(p["id"])

    # --- System prompt ----

    def system_prompt_for(self, slot: str) -> Optional[str]:
        """
        Return the full persona system prompt markdown for a slot, or None
        if the slot has no persona or the prompt file is missing.
        """
        if slot in self._sys_prompt_cache:
            return self._sys_prompt_cache[slot]
        p = self._persona_for_slot(slot)
        result: Optional[str] = None
        if p and p.get("prompt_path"):
            path = self.skill_root / p["prompt_path"]
            if path.exists():
                try:
                    result = path.read_text()
                except OSError:
                    result = None
        self._sys_prompt_cache[slot] = result
        return result

    # --- Voice bank ----

    def persona_bank_for(self, slot: str) -> Optional[PersonaBank]:
        """Return a PersonaBank instance for a slot, or None if unavailable."""
        if slot in self._bank_cache:
            return self._bank_cache[slot]
        p = self._persona_for_slot(slot)
        result: Optional[PersonaBank] = None
        if p and p.get("voice_bank_path"):
            path = self.skill_root / p["voice_bank_path"]
            if path.exists():
                try:
                    text = path.read_text()
                    parsed = _parse_voice_bank(text)
                    result = PersonaBank(
                        name=self.persona_name_for(slot) or p["id"],
                        entry=parsed["entry"],
                        heartbeat=parsed["heartbeat"],
                        completion=parsed["completion"],
                        critique=parsed["critique"],
                    )
                except OSError:
                    result = None
        self._bank_cache[slot] = result
        return result

    def persona_banks_for(self, slots: List[str]) -> Dict[str, PersonaBank]:
        """Return {slot: PersonaBank} for slots that have banks. Skips unmapped slots."""
        out: Dict[str, PersonaBank] = {}
        for slot in slots:
            bank = self.persona_bank_for(slot)
            if bank is not None:
                out[slot] = bank
        return out


# --- Helpers ----------------------------------------------------------------


def _prettify(persona_id: str) -> str:
    """sun-tzu → Sun Tzu ; marcus-aurelius → Marcus Aurelius"""
    return " ".join(part.capitalize() for part in persona_id.split("-"))


# --- CLI inspection ---------------------------------------------------------

def _cli() -> int:
    import argparse
    p = argparse.ArgumentParser(description="Persona loader — inspect current map")
    p.add_argument("--slot", help="Show resolution for a specific slot (e.g. A-claude)")
    args = p.parse_args()

    loader = PersonaLoader()
    if not loader.enabled:
        print(f"Persona map not loaded. Path: {loader.config_path}")
        return 1

    print(f"Persona map {loader.version} from {loader.config_path}")
    print(f"Rosters: {list(loader._map.get('rosters', {}).keys())}")

    if args.slot:
        name = loader.persona_name_for(args.slot)
        prompt = loader.system_prompt_for(args.slot)
        bank = loader.persona_bank_for(args.slot)
        print(f"\nSlot {args.slot}:")
        print(f"  Persona:    {name or '(unmapped)'}")
        print(f"  Prompt:     {'loaded ' + str(len(prompt or ''))+' chars' if prompt else 'missing'}")
        if bank:
            print(f"  Voice bank: entry={len(bank.entry)} "
                  f"heartbeat={len(bank.heartbeat)} "
                  f"completion={len(bank.completion)} "
                  f"critique={len(bank.critique)}")
        else:
            print(f"  Voice bank: missing")
        return 0

    print(f"\nAll slot mappings:")
    for persona_id, pdict in loader._map.get("personas", {}).items():
        slot = pdict.get("slot")
        prompt_ok = (loader.skill_root / pdict.get("prompt_path", "")).exists()
        bank_ok = (loader.skill_root / pdict.get("voice_bank_path", "")).exists()
        print(f"  {slot:<10} → {persona_id:<18} "
              f"prompt={'✓' if prompt_ok else '✗'} "
              f"voice_bank={'✓' if bank_ok else '✗'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
