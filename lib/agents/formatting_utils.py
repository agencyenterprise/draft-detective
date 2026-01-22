from lib.agents.citation_detector import CitationResponse
from lib.agents.document_summarizer import DocumentSummary
from lib.models.bibliography_item import (
    BibliographyItem,
    get_associated_supporting_file,
)
from lib.services.file import FileDocument
from typing import Dict, List, Optional
from lib.services.vector_store import RetrievedPassage
from lib.workflows.reference_extraction.state import ExtractedReference


def format_domain_context(domain: Optional[str]) -> str:
    """Format domain context for agent prompts."""
    if not domain:
        return ""

    return f"""
## Domain Context
Consider this user provided domain: ```{domain}```

When analyzing claims, consider domain-specific standards, terminology, and expectations. For example:
- What constitutes a significant claim may vary by domain
- Evidence requirements and citation standards may differ
- Technical terminology and concepts should be evaluated within domain context
"""


def format_audience_context(target_audience: Optional[str]) -> str:
    """Format target audience context for agent prompts."""
    if not target_audience:
        return ""

    return f"""
## Target Audience Context
Consider this user provided target audience: ```{target_audience}```

When evaluating claims and evidence, consider audience-appropriate standards:
- Adjust the rigor of substantiation requirements based on audience expertise level
- Consider what level of evidence and explanation is appropriate for this audience
- Factor in audience expectations for claims, citations, and supporting evidence
"""


def format_supporting_documents_prompt_section(
    supporting_document: FileDocument, truncate_at_character_count: int = None
):
    markdown = supporting_document.markdown
    output = f"""
File name: {supporting_document.file_name}
File content converted to markdown{" (truncated)" if truncate_at_character_count else ""}:
```markdown
{markdown[:truncate_at_character_count] if truncate_at_character_count else markdown}
```
"""

    return output


def format_supporting_documents_prompt_section_multiple(
    supporting_files: list[FileDocument],
    truncate_at_character_count: int = None,
) -> str:
    supporting_documents = "\n\n".join(
        [
            f"""### Supporting document #{index + 1} (index: {index+1})
{format_supporting_documents_prompt_section(doc, truncate_at_character_count=truncate_at_character_count)}
"""
            for index, doc in enumerate(supporting_files or [])
        ]
    )
    return supporting_documents


def format_cited_references(
    references: list[BibliographyItem],
    supporting_files: list[FileDocument],
    citations: CitationResponse,
    truncate_at_character_count: int | None = None,
) -> str:
    citations_with_associated_bibliography = [
        c for c in citations.citations if c.associated_bibliography
    ]

    if len(citations_with_associated_bibliography) == 0:
        return "No reference is cited as support for this claim.\n\n"

    cited_references_str = ""

    for citation in citations_with_associated_bibliography:
        bibliography_index = citation.index_of_associated_bibliography
        associated_reference = references[bibliography_index - 1]
        cited_references_str += f"""### Cited bibliography entry #{bibliography_index}
Citation text: `{citation.text}`
Bibliography entry text: `{associated_reference.text}`
"""
        supporting_file = get_associated_supporting_file(
            associated_reference, supporting_files
        )
        if supporting_file:
            cited_references_str += format_supporting_documents_prompt_section(
                supporting_file, truncate_at_character_count=truncate_at_character_count
            )
        else:
            cited_references_str += "No associated supporting document provided by the user, so this bibliography item cannot be used to substantiate the claim\n\n"

    cited_references_str += "\n\n"

    return cited_references_str


def format_bibliography_item_prompt_section(
    index: int,
    item: BibliographyItem,
    supporting_files: List[FileDocument],
    supporting_documents_summaries: Optional[Dict[int, DocumentSummary]] = None,
) -> str:
    result = f"""### Bibliography entry #{index + 1}
{item.text}"""

    # If this bibliography item has an associated supporting document, include its summary
    supporting_file = get_associated_supporting_file(item, supporting_files)
    if supporting_file and supporting_documents_summaries:
        # Find the index of this file in the supporting_files list
        doc_index = next(
            (
                i
                for i, f in enumerate(supporting_files)
                if f.file_id == supporting_file.file_id
            ),
            None,
        )
        if doc_index is not None:
            summary = supporting_documents_summaries.get(doc_index)
            if summary:
                result += f"""

#### Summary of the associated document
{summary.summary}

"""

    return result


def format_bibliography_prompt_section(
    references: List[BibliographyItem],
    supporting_files: List[FileDocument],
    supporting_documents_summaries: Optional[Dict[int, DocumentSummary]] = None,
) -> str:
    return "\n\n".join(
        [
            format_bibliography_item_prompt_section(
                index, item, supporting_files, supporting_documents_summaries
            )
            for index, item in enumerate(references)
        ]
    )


def format_retrieved_passages(passages: List["RetrievedPassage"]) -> str:
    """Format retrieved passages from RAG for use as cited references."""
    if not passages:
        return "No relevant passages found in supporting documents."

    formatted = []
    for i, passage in enumerate(passages, 1):
        formatted.append(
            f"#### Retrieved Passage {i} from {passage.source_file} (cosine distance: {passage.cosine_distance:.2f})\n"
            f"```\n{passage.content}\n```\n"
        )
    return "\n".join(formatted)


def format_bibliography(references: list[ExtractedReference]) -> str:
    """Format extracted references as a simple numbered list for the prompt."""

    if not references:
        return "No bibliography available."
    return "\n".join(f"{i + 1}. {ref.text}" for i, ref in enumerate(references))
