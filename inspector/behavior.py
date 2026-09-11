"""Rolling behaviour state for the anomaly layer.

M1 (confidence jump) needs the Trader's recent (setup_score, confidence) pairs.
S2 (sentiment spike) needs a history of aggregate sentiment scores.
Both were defined in anomaly.py but never fed in production. This keeps them
alive across cycles and persists them so a VPS restart does not reset M1/S2.

Only CLEAN observations should be recorded: in the harness we record the
unattacked run so an attacker cannot drag the baseline toward their target.
In live mode we record every proposal the gate did not flag as anomalous.
"""

from __future__ import annotations

import json
from collections import deque
from pathlib import Path
from typing import Optional


class BehaviorState:
    def __init__(self, max_conf: int = 200, max_sent: int = 500) -> None:
        self.confidences: deque[tuple[float, int]] = deque(maxlen=max_conf)
        self.sentiment_scores: deque[float] = deque(maxlen=max_sent)

    def record_proposal(self, setup_score: float, confidence: int) -> None:
        if confidence > 0:
            self.confidences.append((float(setup_score), int(confidence)))

    def record_sentiment(self, aggregate_score: Optional[float]) -> None:
        if aggregate_score is not None:
            self.sentiment_scores.append(float(aggregate_score))

    def trailing(self) -> list[tuple[float, int]]:
        return list(self.confidences)

    def sentiment_history(self) -> list[float]:
        return list(self.sentiment_scores)

    def save(self, path: Path | str) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "confidences": [list(x) for x in self.confidences],
                    "sentiment_scores": list(self.sentiment_scores),
                }
            ),
            encoding="utf-8",
        )

    @classmethod
    def load(cls, path: Path | str) -> "BehaviorState":
        st = cls()
        path = Path(path)
        if not path.exists():
            return st
        data = json.loads(path.read_text(encoding="utf-8"))
        for s, c in data.get("confidences", []):
            st.record_proposal(s, c)
        for v in data.get("sentiment_scores", []):
            st.record_sentiment(v)
        return st
