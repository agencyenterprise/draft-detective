"""LangGraph graph for DOCX generation workflow."""

from langgraph.graph import StateGraph

from lib.workflows.context import ContextSchema
from lib.workflows.docx_generation.nodes.generate_docx import generate_docx
from lib.workflows.docx_generation.nodes.prepare_docx_inputs import prepare_docx_inputs
from lib.workflows.docx_generation.state import DocxGenerationState


def build_docx_generation_graph() -> StateGraph:
    graph = StateGraph(DocxGenerationState, context_schema=ContextSchema)

    graph.add_node("prepare_docx_inputs", prepare_docx_inputs)
    graph.add_node("generate_docx", generate_docx)

    graph.set_entry_point("prepare_docx_inputs")
    graph.add_edge("prepare_docx_inputs", "generate_docx")
    graph.set_finish_point("generate_docx")
    return graph
