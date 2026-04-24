from langgraph.graph import StateGraph

from lib.workflows.context import ContextSchema
from lib.workflows.literature_review.nodes.literature_review import literature_review
from lib.workflows.literature_review.state import LiteratureReviewState


def build_literature_review_graph() -> StateGraph:
    graph = StateGraph(LiteratureReviewState, context_schema=ContextSchema)

    graph.add_node("literature_review", literature_review)
    graph.set_entry_point("literature_review")
    graph.set_finish_point("literature_review")

    return graph  # type: ignore[return-value]
