# ShopAssist — support copilot cost lab

**ShopAssist** is a Tier-1 support agent for an e-commerce company. For each ticket it:

1. Reads the customer thread (`data/tickets/`)
2. Loads order facts (`data/orders/` via `shared/tools.py`)
3. Picks an action (`REFUND`, `REPLACE`, `SEND_ARTICLE`, `ESCALATE_TIER2`)
4. Cites the help-center article that backs the decision (`data/kb/`)

| Track | Code | Spec |
|-------|------|------|
| Q1 — single call | [question1/agent.py](question1/agent.py) | [questions/question-1.md](questions/question-1.md) |
| Q2 — pipeline | [question2/agent.py](question2/agent.py) | [questions/question-2.md](questions/question-2.md) |

## Solution

Blog post walking through the whole solution: **[sarvan-intern-assignment-blog.vercel.app](https://sarvan-intern-assignment-blog.vercel.app/)**

| | Target | Baseline | **Solution** | Write-up |
|---|---:|---:|---:|---|
| Q1: one LLM call per ticket | ≤ 3,000 | 8,878 | **1,163** (−87%) | [SOLUTIONS/Q1.md](SOLUTIONS/Q1.md) |
| Q2: four-node pipeline | ≤ 2,500 | 73,415 | **1,376** (−98%) | [SOLUTIONS/Q2.md](SOLUTIONS/Q2.md) |

Average points per public ticket. All answers stay correct, including the holdout T-1091; all 23 tests pass.

## Run

```bash
pip install -r requirements.txt
pytest -q
python question1/run.py
python question2/run.py
```

`shared/llm.py` provides a local `LlmClient` with the same billing accounting you would use against a hosted chat API. Do not import `eval/reference.py` from your agent.

## Billing

| Input | Cached input | Output |
|------:|-------------:|-------:|
| 3 | 0.3 | 15 |

Cached input = identical prefix ≥ 1024 tokens across calls.

```
points = uncached_input × 3 + cached_input × 0.3 + output × 15
```

Per-call details are in `shared/billing.py` (`CostSession` on your agent).
