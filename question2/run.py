from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from question2.agent import VERSIONS  # noqa: E402

PUBLIC = ["T-1001", "T-1002", "T-1003", "T-1004"]
NODES = ["triage", "retrieve", "compose", "audit"]


def main() -> None:
    version = sys.argv[1] if len(sys.argv) > 1 else "v2"  # python run.py [v1|v2]
    pipe_cls = VERSIONS[version]
    rows = []
    for tid in PUBLIC:
        pipe = pipe_cls()  # fresh session = per-ticket billing
        res = pipe.handle_ticket(tid)
        calls = pipe.session.calls
        rows.append(
            {
                "ticket_id": tid,
                "action": res.action,
                "kb_article": res.kb_article,
                # nodes without an LLM call cost 0 points
                "nodes": {n: sum(c.points() for c in calls if c.label == n) for n in NODES},
                "calls": [
                    {
                        "label": c.label,
                        "input_tokens": c.input_tokens,
                        "cached_input_tokens": c.cached_prefix_tokens,
                        "output_tokens": c.output_tokens,
                        "points": c.points(),
                    }
                    for c in calls
                ],
                "points": pipe.session.total_points(),
            }
        )
    print(
        json.dumps(
            {
                "version": version,
                "resolutions": rows,
                "total_points": sum(r["points"] for r in rows),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
