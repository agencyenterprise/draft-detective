from lib.agents.citation_detector import CitationResponse
from lib.models.bibliography_item import BibliographyItem
from lib.services.file import FileDocument
from typing import Optional


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
        if associated_reference.has_associated_supporting_document:
            supporting_file = supporting_files[
                associated_reference.index_of_associated_supporting_document - 1
            ]
            cited_references_str += format_supporting_documents_prompt_section(
                supporting_file, truncate_at_character_count=truncate_at_character_count
            )
        else:
            cited_references_str += "No associated supporting document provided by the user, so this bibliography item cannot be used to substantiate the claim\n\n"

    cited_references_str += "\n\n"

    return cited_references_str
