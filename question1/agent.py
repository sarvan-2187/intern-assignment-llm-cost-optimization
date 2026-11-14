from __future__ import annotations

import json
import re
from dataclasses import dataclass

from shared.billing import CostSession
from shared.llm import ChatMessage, LlmClient
from shared.tools import get_order, get_ticket


@dataclass
class TicketResolution:
    action: str
    kb_article: str
    customer_reply: str
    raw_completion: str


def parse_resolution(text: str) -> TicketResolution:
    m = re.search(r"\{[\s\S]*\}", text)
    if not m:
        raise ValueError(f"No JSON in model output:\n{text[:400]}")
    data = json.loads(m.group())
    return TicketResolution(
        action=str(data["action"]).upper(),
        kb_article=str(data["kb_article"]),
        customer_reply=str(data.get("customer_reply", "")),
        raw_completion=text,
    )


# Help center (data/kb/) distilled to one rule per article, most specific first.
# Rule ids must equal shared.kb.article_ids() (enforced by tests/test_question1.py).
# No reasoning/verbosity asks anywhere: output tokens cost 5x input.

# v2: plain-language conditions.
RULES_V2 = """\
subscription-cooling-off: subscription, cancelled <=30 days -> REFUND, else SEND_ARTICLE
digital-license-no-refund: license_revealed -> SEND_ARTICLE
custom-items-no-replace: customized and damage_reported -> ESCALATE_TIER2
damage-replacement-7-days: damage_reported, delivered <=7 days ago -> REPLACE
returns-within-30-days: physical, not opened, delivered <=30 days ago -> REFUND"""

SYSTEM_V2 = (
    "Tier-1 support. First matching rule wins, else ESCALATE_TIER2. "
    'Reply JSON only: {"action","kb_article","customer_reply"(1 sentence)}.\n'
    f"RULES (kb_article: condition -> action):\n{RULES_V2}"
)

# v3: conditions written directly in ORDER_SNAPSHOT field names.
RULES_V3 = """\
subscription-cooling-off: subscription_age_days<=30 REFUND else SEND_ARTICLE
digital-license-no-refund: license_revealed SEND_ARTICLE
custom-items-no-replace: customized+damage_reported ESCALATE_TIER2
damage-replacement-7-days: damage_reported, delivered_days_ago<=7 REPLACE
returns-within-30-days: physical, !opened, delivered_days_ago<=30 REFUND"""

SYSTEM_V3 = (
    "First match wins, else ESCALATE_TIER2. "
    "JSON only: action,kb_article,customer_reply (1 sentence).\n" + RULES_V3
)

# Identifiers only; no rule reads them.
_NOT_FOR_DECISION = ("order_id", "sku", "title")


def ticket_brief(ticket_id: str) -> str:
    """Customer's words + order decision fields (no identifiers), in snapshot markers.

    Shared by Q1 (user message) and Q2 (triage node).
    """
    ticket = get_ticket(ticket_id)
    order = get_order(ticket["order_id"])
    facts = {k: v for k, v in order.items() if k not in _NOT_FOR_DECISION}
    snapshot = json.dumps(facts, separators=(",", ":"))
    # ponytail: agent messages dropped (boilerplate today); keep them if they start carrying facts
    customer = "\n".join(m["text"] for m in ticket["messages"] if m["from"] == "customer")
    return f"CUSTOMER:\n{customer}\nORDER_SNAPSHOT:\n{snapshot}\nEND_SNAPSHOT"


class SupportCopilot:
    """
    ShopAssist Tier-1 copilot (v3, the graded default).

    Given a support ticket + order snapshot, choose an action, cite the help-center
    article, and draft the customer reply — in one short LLM call.
    """

    SYSTEM = SYSTEM_V3

    def __init__(self, session: CostSession | None = None):
        self.session = session or CostSession()
        self.llm = LlmClient(self.session)

    def build_messages(self, ticket_id: str) -> list[ChatMessage]:
        return [ChatMessage("system", self.SYSTEM), ChatMessage("user", ticket_brief(ticket_id))]

    def handle_ticket(self, ticket_id: str) -> TicketResolution:
        completion = self.llm.chat("handle_ticket", self.build_messages(ticket_id))
        return parse_resolution(completion)


class SupportCopilotV2(SupportCopilot):
    """v2: same user message as v3, plain-language rule table."""

    SYSTEM = SYSTEM_V2


VERSIONS = {"v2": SupportCopilotV2, "v3": SupportCopilot}
