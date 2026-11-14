from __future__ import annotations

import pytest

from shared.kb import expanded_help_center_blob
from shared.llm import _VERBOSE_HINTS
from shared.tokens import count_tokens
from eval.reference import TICKET_EXPECTATIONS
from question2.agent import VERSIONS, TicketResolution

PUBLIC = ["T-1001", "T-1002", "T-1003", "T-1004"]
PIPELINES = pytest.mark.parametrize("pipe_cls", VERSIONS.values(), ids=VERSIONS.keys())


def test_help_center_exceeds_context():
    assert count_tokens(expanded_help_center_blob()) > 200_000


@PIPELINES
def test_pipeline_resolves_public_tickets(pipe_cls):
    pipe = pipe_cls()
    for tid in PUBLIC:
        expected = TICKET_EXPECTATIONS[tid]
        got = pipe.handle_ticket(tid)
        assert got.action == expected.action
        assert got.kb_article == expected.kb_article


@PIPELINES
def test_holdout_subscription(pipe_cls):
    got = pipe_cls().handle_ticket("T-1091")
    exp = TICKET_EXPECTATIONS["T-1091"]
    assert (got.action, got.kb_article) == (exp.action, exp.kb_article)


@PIPELINES
def test_cost_under_target(pipe_cls):
    for tid in PUBLIC:
        pipe = pipe_cls()
        pipe.handle_ticket(tid)
        assert pipe.session.total_points() <= 2500, tid


@PIPELINES
def test_audit_guardrail(pipe_cls):
    pipe = pipe_cls()
    articles = pipe._retrieve()
    esc = "ESCALATE_TIER2"
    assert pipe._audit("no json here", articles) == TicketResolution(esc, "")
    assert pipe._audit('{"action":"GIFT_CARD","kb_article":"returns-within-30-days"}', articles) == (
        TicketResolution(esc, "returns-within-30-days")
    )
    assert pipe._audit('{"action":"REFUND","kb_article":"made-up-article"}', articles) == (
        TicketResolution(esc, "")
    )
    assert pipe._audit('{"action":"REPLACE","kb_article":"damage-replacement-7-days"}', articles) == (
        TicketResolution("REPLACE", "damage-replacement-7-days")
    )


@PIPELINES
def test_compose_prompt_has_no_verbose_hints(pipe_cls):
    pipe = pipe_cls()
    prompt = (pipe.INSTRUCTIONS + "\n".join(pipe._retrieve().values())).lower()
    assert not [h for h in _VERBOSE_HINTS if h in prompt]


def test_v2_cheaper_than_v1():
    for tid in PUBLIC:
        v1, v2 = VERSIONS["v1"](), VERSIONS["v2"]()
        v1.handle_ticket(tid)
        v2.handle_ticket(tid)
        assert v2.session.total_points() < v1.session.total_points(), tid
