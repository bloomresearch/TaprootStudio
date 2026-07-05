"""Belief extraction from free text.

Two implementations:
- RuleBasedExtractor: deterministic heuristics, no LLM/keys. Lets the whole loop
  be tested offline and serves as a graceful fallback.
- GeminiExtractor: strict-JSON LLM extraction (Gemini-first), used when a key is
  available. Both return the same ExtractedBelief shape.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Optional, Protocol

from .schema import BeliefType

_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+|\n+")

_CUES: list[tuple[BeliefType, tuple[str, ...]]] = [
    (BeliefType.DECISION, ("decided", "we'll use", "we will use", "go with", "let's use",
                            "chosen", "adopt", "settled on")),
    (BeliefType.REQUIREMENT, ("must", "need to", "needs to", "has to", "have to",
                              "required", "shall")),
    (BeliefType.CONSTRAINT, ("can't", "cannot", "must not", "avoid", "don't", "do not",
                             "without", "no docker", "not allowed")),
    (BeliefType.PREFERENCE, ("prefer", "i want", "we want", "i'd like", "would like",
                             "ideally", "i like", "rather")),
    (BeliefType.RISK, ("risk", "concern", "worried", "might break", "problem", "danger",
                       "fragile", "bottleneck")),
]

_HEDGES = ("maybe", "probably", "i think", "possibly", "might", "perhaps",
           "not sure", "tentative", "i guess", "could be", "unsure")
_STRONG = ("definitely", "must", "decided", "locked", "always", "certainly",
           "absolutely", "required")


@dataclass
class ExtractedBelief:
    statement: str
    type: BeliefType = BeliefType.FACT
    confidence: float = 0.6
    topic: Optional[str] = None
    tags: list[str] = field(default_factory=list)


class BeliefExtractor(Protocol):
    def extract(self, text: str) -> list[ExtractedBelief]:
        ...


def _classify(sentence: str) -> BeliefType:
    low = sentence.lower()
    if sentence.strip().endswith("?"):
        return BeliefType.OPEN_QUESTION
    for btype, cues in _CUES:
        if any(cue in low for cue in cues):
            return btype
    return BeliefType.FACT


def _confidence(sentence: str, btype: BeliefType) -> float:
    low = sentence.lower()
    conf = 0.6
    if any(h in low for h in _HEDGES):
        conf = 0.35
    if any(s in low for s in _STRONG):
        conf = max(conf, 0.85)
    if btype is BeliefType.OPEN_QUESTION:
        conf = 0.2
    return round(conf, 2)


class RuleBasedExtractor:
    """Heuristic extractor — no external calls."""

    def extract(self, text: str) -> list[ExtractedBelief]:
        out: list[ExtractedBelief] = []
        for raw in _SENT_SPLIT.split(text or ""):
            s = raw.strip()
            if len(s) < 8:
                continue
            btype = _classify(s)
            out.append(
                ExtractedBelief(
                    statement=s,
                    type=btype,
                    confidence=_confidence(s, btype),
                )
            )
        return out


_LLM_PROMPT = """You extract atomic BELIEFS from a message for a project belief graph.
Return STRICT JSON: {"beliefs": [{"statement": str, "type": one of \
["decision","assumption","requirement","constraint","preference","risk","open_question","fact"], \
"confidence": float 0..1}]}.
Rules: one claim per belief; keep statements self-contained; lower confidence for \
hedged language ("maybe", "I think"); use "open_question" for anything phrased as a \
question or an explicit unknown. Message:
---
{message}
---
JSON:"""


class GeminiExtractor:
    """LLM extractor using Google GenAI (Gemini). Requires GEMINI_API_KEY."""

    def __init__(self, api_key: Optional[str] = None, model: str = "gemini-2.0-flash") -> None:
        import os

        from google import genai  # lazy import; optional dependency

        self._client = genai.Client(api_key=api_key or os.environ["GEMINI_API_KEY"])
        self._model = model
        self._fallback = RuleBasedExtractor()

    def extract(self, text: str) -> list[ExtractedBelief]:
        try:
            resp = self._client.models.generate_content(
                model=self._model,
                contents=_LLM_PROMPT.replace("{message}", text or ""),
                config={"response_mime_type": "application/json"},
            )
            data = json.loads(resp.text)
            out: list[ExtractedBelief] = []
            for item in data.get("beliefs", []):
                try:
                    out.append(
                        ExtractedBelief(
                            statement=str(item["statement"]).strip(),
                            type=BeliefType(item.get("type", "fact")),
                            confidence=float(item.get("confidence", 0.6)),
                        )
                    )
                except (KeyError, ValueError):
                    continue
            return out or self._fallback.extract(text)
        except Exception:
            # Never let extraction crash the ingest loop.
            return self._fallback.extract(text)
