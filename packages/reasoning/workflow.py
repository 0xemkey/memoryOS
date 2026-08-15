from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from packages.reasoning.answerer import SanitizedReasoner
from packages.reasoning.models import ReasoningAnswer
from packages.retrieval.hybrid import SanitizedRetriever

MAX_RETRIEVAL_ROUNDS = 2
MAX_TOOL_CALLS = 4
MAX_EVIDENCE_CHUNKS = 10
MAX_GRAPH_EXPANSION_DEPTH = 2


class ReasoningState(BaseModel):
    sanitized_question: str
    retrieval_plan: list[str] = Field(default_factory=list)
    retrieval_queries: list[str] = Field(default_factory=list)
    filters: dict[str, Any] = Field(default_factory=dict)
    retrieved_source_ids: list[str] = Field(default_factory=list)
    tool_call_count: int = 0
    retrieval_round: int = 0
    evidence_sufficient: bool = False
    final_answer: str | None = None
    warnings: list[str] = Field(default_factory=list)
    audit_events: list[dict[str, Any]] = Field(default_factory=list)


class BoundedReasoningWorkflow:
    def __init__(self, retriever: SanitizedRetriever, reasoner: SanitizedReasoner):
        self.retriever = retriever
        self.reasoner = reasoner

    def run(
        self,
        sanitized_question: str,
        filters: dict[str, Any] | None = None,
    ) -> tuple[ReasoningAnswer, ReasoningState]:
        state = ReasoningState(sanitized_question=sanitized_question, filters=filters or {})
        state.retrieval_plan = self._plan_queries(sanitized_question)
        evidence: list[dict[str, Any]] = []

        for query in state.retrieval_plan:
            if state.retrieval_round >= MAX_RETRIEVAL_ROUNDS or state.tool_call_count >= MAX_TOOL_CALLS:
                state.warnings.append("reasoning_limits_reached")
                break
            if query in state.retrieval_queries:
                state.warnings.append("duplicate_query_skipped")
                continue
            state.retrieval_round += 1
            response = self._search_memory(state, query)
            state.warnings.extend(response.warnings)
            seen = {item["chunk_id"] for item in evidence}
            for item in response.results:
                if item["chunk_id"] not in seen:
                    evidence.append(item)
                    seen.add(item["chunk_id"])
            evidence = evidence[:MAX_EVIDENCE_CHUNKS]
            state.retrieved_source_ids = [item["chunk_id"] for item in evidence]
            if evidence:
                state.evidence_sufficient = True
                break

        answer = self.reasoner.answer(sanitized_question, evidence)
        state.final_answer = answer.sanitized_answer
        state.evidence_sufficient = answer.evidence_sufficient
        return answer, state

    def _search_memory(self, state: ReasoningState, query: str):
        state.tool_call_count += 1
        state.retrieval_queries.append(query)
        state.audit_events.append(
            {
                "event_type": "tool_called",
                "tool": "search_memory",
                "query_length": len(query),
                "tool_call_count": state.tool_call_count,
            }
        )
        return self.retriever.search(query, filters=state.filters, limit=MAX_EVIDENCE_CHUNKS)

    def _plan_queries(self, question: str) -> list[str]:
        cleaned = " ".join(question.split())
        if not cleaned:
            return [""]
        if len(cleaned.split()) <= 3:
            return [cleaned]
        reformulated = " ".join(word for word in cleaned.split() if len(word) > 3)
        return [cleaned, reformulated] if reformulated != cleaned else [cleaned]
