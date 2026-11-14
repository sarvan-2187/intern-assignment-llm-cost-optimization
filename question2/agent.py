from __future__ import annotations

from dataclasses import dataclass

from shared.billing import CostSession
from shared.kb import article_ids, load_article
from shared.llm import ChatMessage, LlmClient

from question1.agent import parse_resolution, ticket_brief

ACTIONS = ("REFUND", "REPLACE", "SEND_ARTICLE", "ESCALATE_TIER2")

# No reasoning/verbosity asks anywhere: output tokens cost 5x input.
COMPOSE_V1 = (
    "Pick an action (REFUND, REPLACE, SEND_ARTICLE, ESCALATE_TIER2) and the kb_article "
    "that backs it, using only these articles; none fits -> ESCALATE_TIER2. "
    "JSON only: action,kb_article,customer_reply (1 sentence).\nARTICLES:\n"
)
COMPOSE_V2 = (
    "Actions: REFUND, REPLACE, SEND_ARTICLE, ESCALATE_TIER2 (if no article fits). "
    "Cite the backing article. JSON only: action,kb_article,customer_reply (1 sentence).\n"
)


@dataclass
class TicketResolution:
    action: str
    kb_article: str


class SupportPipeline:
    """Same product as Question 1 — triage, retrieve, compose, audit (v2, graded).

    Only compose calls the LLM: each call costs >= ~600 points of output, more than
    the whole policy text it could save. Triage, retrieve and audit are code.
    """

    INSTRUCTIONS = COMPOSE_V2
    STRIP_MARKDOWN = True

    def __init__(self, session: CostSession | None = None):
        self.session = session or CostSession()
        self.llm = LlmClient(self.session)

    def handle_ticket(self, ticket_id: str) -> TicketResolution:
        brief = self._triage(ticket_id)
        articles = self._retrieve()
        draft = self._compose(brief, articles)
        return self._audit(draft, articles)

    def _triage(self, ticket_id: str) -> str:
        """Code: the facts compose needs — customer's words + decision fields."""
        return ticket_brief(ticket_id)

    def _retrieve(self) -> dict[str, str]:
        """Code: policy articles only; the ~210k tokens of routing notes carry no policy."""
        # ponytail: returns every policy article (~145 tokens); add top-k ranking once
        # policy text passes ~330 tokens/ticket, the point where an LLM triage pays for itself
        articles = {aid: load_article(aid).split("\n", 1)[1].strip() for aid in article_ids()}
        if self.STRIP_MARKDOWN:  # formatting only; the words are unchanged
            articles = {a: b.replace("**", "") for a, b in articles.items()}
        return articles

    def _compose(self, brief: str, articles: dict[str, str]) -> str:
        system = self.INSTRUCTIONS + "\n".join(f"{a}: {b}" for a, b in articles.items())
        return self.llm.chat(
            "compose", [ChatMessage("system", system), ChatMessage("user", brief)]
        )

    def _audit(self, draft: str, articles: dict[str, str]) -> TicketResolution:
        """Code guardrail: a known action backed by a retrieved article, else a human."""
        try:
            r = parse_resolution(draft)
        except (ValueError, KeyError):  # no JSON / bad JSON / missing field
            return TicketResolution("ESCALATE_TIER2", "")
        kb = r.kb_article if r.kb_article in articles else ""
        if r.action not in ACTIONS or not kb:
            return TicketResolution("ESCALATE_TIER2", kb)
        return TicketResolution(r.action, kb)


class SupportPipelineV1(SupportPipeline):
    """v1: the original compose instruction, Markdown kept in articles."""

    INSTRUCTIONS = COMPOSE_V1
    STRIP_MARKDOWN = False


VERSIONS = {"v1": SupportPipelineV1, "v2": SupportPipeline}
