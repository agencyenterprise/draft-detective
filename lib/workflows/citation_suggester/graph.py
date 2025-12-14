from langgraph.graph import StateGraph

from lib.workflows.context import ContextSchema
from lib.workflows.citation_suggester.nodes.suggest_citations import suggest_citations
from lib.workflows.citation_suggester.state import CitationSuggesterState


def build_citation_suggester_graph() -> StateGraph:
    graph = StateGraph(CitationSuggesterState, context_schema=ContextSchema)

    graph.add_node("suggest_citations", suggest_citations)
    graph.set_entry_point("suggest_citations")
    graph.set_finish_point("suggest_citations")

    return graph
