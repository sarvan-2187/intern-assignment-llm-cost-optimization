from __future__ import annotations

import pytest

from eval.reference import TICKET_EXPECTATIONS
from question1.agent import RULES_V2, RULES_V3, VERSIONS
from shared.kb import article_ids
from shared.llm import _VERBOSE_HINTS

PUBLIC = ["T-1001", "T-1002", "T-1003", "T-1004"]
COPILOTS = pytest.mark.parametrize("copilot_cls", VERSIONS.values(), ids=VERSIONS.keys())


@COPILOTS
def test_baseline_resolves_public_tickets(copilot_cls):
    copilot = copilot_cls()
    for tid in PUBLIC:
        expected = TICKET_EXPECTATIONS[tid]
        got = copilot.handle_ticket(tid)
        assert got.action == expected.action
        assert got.kb_article == expected.kb_article


@COPILOTS
def test_holdout_subscription(copilot_cls):
    copilot = copilot_cls()
    got = copilot.handle_ticket("T-1091")
    exp = TICKET_EXPECTATIONS["T-1091"]
    assert got.action == exp.action
    assert got.kb_article == exp.kb_article


@COPILOTS
def test_cost_under_target(copilot_cls):
    for tid in PUBLIC:
        copilot = copilot_cls()
        copilot.handle_ticket(tid)
        assert copilot.session.total_points() <= 3000, tid


@COPILOTS
def test_prompt_has_no_verbose_hints(copilot_cls):
    prompt = copilot_cls.SYSTEM.lower()
    assert not [h for h in _VERBOSE_HINTS if h in prompt]


@pytest.mark.parametrize("rules", [RULES_V2, RULES_V3], ids=["v2", "v3"])
def test_rules_cover_kb(rules):
    rule_ids = {line.split(":", 1)[0] for line in rules.splitlines()}
    assert rule_ids == set(article_ids())


def test_v3_cheaper_than_v2():
    for tid in PUBLIC:
        v2, v3 = VERSIONS["v2"](), VERSIONS["v3"]()
        v2.handle_ticket(tid)
        v3.handle_ticket(tid)
        assert v3.session.total_points() < v2.session.total_points(), tid
