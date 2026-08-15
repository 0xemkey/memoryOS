from __future__ import annotations

from packages.reasoning import BoundedReasoningWorkflow, SanitizedReasoner
from packages.reasoning.workflow import MAX_EVIDENCE_CHUNKS, MAX_RETRIEVAL_ROUNDS
from packages.retrieval.hybrid import RetrievalResponse


class FakeRetriever:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def search(self, query, filters=None, limit=10):
        self.calls.append((query, filters, limit))
        if self.responses:
            return self.responses.pop(0)
        return RetrievalResponse(results=[])


def chunk(index: int) -> dict:
    return {
        "chunk_id": f"schunk_{index}",
        "sanitized_content": f"sanitized evidence {index}",
        "provider": "generic_json",
        "sanitized_title": "Synthetic",
    }


def test_workflow_terminates_after_first_sufficient_round() -> None:
    retriever = FakeRetriever([RetrievalResponse(results=[chunk(1)])])
    answer, state = BoundedReasoningWorkflow(retriever, SanitizedReasoner()).run("what happened?")

    assert state.retrieval_round == 1
    assert state.tool_call_count == 1
    assert state.evidence_sufficient
    assert answer.citation_ids == ["schunk_1"]


def test_workflow_uses_second_round_when_first_empty() -> None:
    retriever = FakeRetriever([RetrievalResponse(results=[]), RetrievalResponse(results=[chunk(2)])])
    answer, state = BoundedReasoningWorkflow(retriever, SanitizedReasoner()).run("tell me about local retrieval")

    assert state.retrieval_round == 2
    assert state.tool_call_count == 2
    assert answer.citation_ids == ["schunk_2"]


def test_hard_retrieval_round_limit() -> None:
    retriever = FakeRetriever([RetrievalResponse(results=[]), RetrievalResponse(results=[]), RetrievalResponse(results=[chunk(3)])])
    answer, state = BoundedReasoningWorkflow(retriever, SanitizedReasoner()).run("tell me about local retrieval")

    assert state.retrieval_round == MAX_RETRIEVAL_ROUNDS
    assert len(retriever.calls) == MAX_RETRIEVAL_ROUNDS
    assert answer.evidence_sufficient is False


def test_evidence_limit_is_enforced() -> None:
    retriever = FakeRetriever([RetrievalResponse(results=[chunk(index) for index in range(20)])])
    _, state = BoundedReasoningWorkflow(retriever, SanitizedReasoner()).run("anything")

    assert len(state.retrieved_source_ids) == MAX_EVIDENCE_CHUNKS


def test_audit_events_do_not_store_query_text() -> None:
    retriever = FakeRetriever([RetrievalResponse(results=[chunk(1)])])
    _, state = BoundedReasoningWorkflow(retriever, SanitizedReasoner()).run("secret question text")

    assert state.audit_events
    assert "secret question text" not in str(state.audit_events)
    assert state.audit_events[0]["tool"] == "search_memory"


def test_duplicate_query_is_skipped() -> None:
    retriever = FakeRetriever([])
    workflow = BoundedReasoningWorkflow(retriever, SanitizedReasoner())
    workflow._plan_queries = lambda question: ["same", "same"]  # type: ignore[method-assign]
    _, state = workflow.run("same")

    assert state.retrieval_queries == ["same"]
    assert "duplicate_query_skipped" in state.warnings
