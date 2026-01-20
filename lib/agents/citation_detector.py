from enum import Enum

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field

from lib.config.llm_models import gpt_5_mini_model
from lib.models.agent import LangChainAgent


class CitationType(str, Enum):
    BIBLIOGRAPHY = "bibliography"
    URL = "url"
    FOOTNOTE = "footnote"
    OTHER = "other"


class Citation(BaseModel):
    text: str = Field(
        description="The text of the citation or footnote mark, e.g., [1] or (Doe, et al., 2025), a url, etc. The bibliography/footnote itself is not a citation."
    )
    type: CitationType = Field(
        description="The type of the citation. This should be a value from the CitationType enum."
    )
    format: str = Field(
        description="The format of the citation or footnote mark, e.g., [number] or (Name, et al., Year), url, etc."
    )
    needs_bibliography: bool = Field(
        description="A boolean value indicating whether the citation refers to a bibliography entry or footnote in the document so it expected to have an associated bibliography entry or footnote"
    )
    associated_bibliography: str = Field(
        description="If the document includes a bibliography entry related to this citation, this will be an exact copy of that bibliography entry (do not include the entry number if there is one, just the full context of the bibliography entry), otherwise it will be an empty string."
    )
    index_of_associated_bibliography: int = Field(
        description="The index of the bibliography entry that this citation refers to, if any. Indices start at 1. If the citation does not refer to a bibliography entry, this should be -1."
    )
    rationale: str = Field(
        description="A very brief rationale for why you think this text is a citation"
    )


class CitationResponse(BaseModel):
    citations: list[Citation] = Field(
        description="A list of citations found in the chunk of text"
    )
    rationale: str = Field(
        description="Very brief rationale for why you think the chunk of text includes these citations, if any"
    )


class CitationResponseWithChunkIndex(CitationResponse):
    chunk_index: int = Field(
        description="The index of the chunk of text that contains the citations"
    )


_citation_detector_prompt = ChatPromptTemplate.from_template(
    """
## Task
You are a citation detector. You are given a chunk of text and you need to extract any citations made in that chunk of text.

- You will be given a list of extracted footnotes, a list of bibliography entries pre-extracted from the bibliography section of the full document and a chunk of text from that document.
- You need to return a list of citations made in that chunk of text.
- If there are no citations made in the chunk, return an empty list.
- The citation can be a footnote that can refer to multiple bibliography entries, so you need to return all the bibliography entries that the footnote refers to.
- If the chunk of text is a bibliographic entry itself, do not consider it a citation.

## Handling footnotes
Note that when you are given a footnote number, you need to look up the footnote in the list of footnotes, and then take the associated text for that footnote use that text to find the correct bibliography entry.  

## Return format
For each citation, you need to return the following information:
- The text of the citation/footnote mark
- The type of the citation/footnote mark. This should be a value from the CitationType enum.
- The format of the citation/footnote mark, e.g., [number] or (Name, et al., Year), url, etc.
- A boolean value indicating whether the citation refers to a bibliography entry or footnote in the document so it expected to have an associated bibliography entry or footnote. For example, URLs often do not refer to a bibliography entry so this should be False, but something like (Doe, et al., 2025) does refer to a bibliography entry so this should be True.
- If the document includes a bibliography entry related to this citation, this will be an exact copy of that bibliography entry from the list of bibliography entries I'm providing separately, otherwise it will be an empty string. Do not include the entry number if there is one, just the full context of the bibliography entry.
- Your very brief rationale for why you think this is a citation/footnote mark

## The list of footnotes extracted from the document
```
{footnotes_list}
```

## The list of bibliography entries (if any) extracted from the bibliography section of the full document
The indexes in this list should be used when returning index_of_associated_bibliography.
```
{bibliography}
```

## The chunk of text to extract citations from
```
{chunk}
```
"""
)


class CitationDetectorAgent(LangChainAgent):
    name = "Citation Detector"
    description = "Detect citations in chunks with footnotes list"
    model = gpt_5_mini_model
    temperature = 0.0
    output_schema = CitationResponse

    async def ainvoke(
        self, prompt_kwargs: dict, config: RunnableConfig = None
    ) -> CitationResponse:
        messages = _citation_detector_prompt.format_messages(**prompt_kwargs)
        return await self.llm.ainvoke(messages, config=config)


def format_footnotes_prompt_section(footnotes: list) -> str:
    """Format footnotes list for use in citation detection prompts.

    Args:
        footnotes: List of FootnoteItem objects or dicts with 'marker' and 'text' keys

    Returns:
        Formatted string with footnotes for the prompt
    """
    if not footnotes:
        return "No footnotes found in the document."

    formatted = []
    for footnote in footnotes:
        # Support both FootnoteItem objects and dicts
        if isinstance(footnote, dict):
            marker = footnote.get("marker", "")
            text = footnote.get("text", "")
        else:
            marker = footnote.marker
            text = footnote.text
        formatted.append(f"{marker}. {text}")

    return "\n".join(formatted)


if __name__ == "__main__":
    import asyncio
    import os
    import uuid
    import nest_asyncio
    from lib.config.logger import setup_logger
    from lib.config.env import config
    from lib.services.file import create_file_document_from_path
    from lib.workflows.context import ContextSchema
    from lib.workflows.document_processing.graph import build_document_processing_graph
    from lib.workflows.document_processing.state import (
        DocumentProcessingState,
        DocumentProcessingWorkflowConfig,
    )
    from lib.workflows.reference_extraction.graph import (
        build_reference_extraction_graph,
    )
    from lib.workflows.reference_extraction.state import (
        ReferenceExtractionState,
        ReferenceExtractionConfig,
    )
    from lib.agents.formatting_utils import format_bibliography_prompt_section

    nest_asyncio.apply()

    async def main(custom_chunk: str = None, ground_truth: dict = None):
        """
        Main function to test citation detector.

        Args:
            custom_chunk: Optional custom text to analyze instead of loading from file.
                         If provided, will skip document loading and use saved bibliography.
            ground_truth: Optional dict with expected citations for accuracy calculation.
                         Format: {
                             "citations": [
                                 {
                                     "text": "[[107]](#footnote-108)",
                                     "type": "footnote",
                                     "needs_bibliography": False,
                                     "bibliography_index": None
                                 },
                                 {
                                     "text": "[[108]](#footnote-109)",
                                     "type": "bibliography",
                                     "needs_bibliography": True,
                                     "bibliography_index": 64
                                 }
                             ]
                         }
        """
        import json
        from lib.services.file_artifacts_service.mock import MockFileArtifactsService
        from lib.services.vector_store import VectorStoreService

        # 1. Setup
        setup_logger()
        context = ContextSchema(
            openai_api_key=config.OPENAI_API_KEY,
            vector_store=VectorStoreService(config.DATABASE_URL, config.OPENAI_API_KEY),
            file_artifacts_service=MockFileArtifactsService(),
        )

        # 2. Load document
        # Default: Energy Conservation document
        # Fallback: Try a test document if Energy Conservation times out
        file_path = os.path.join(
            os.path.dirname(__file__),
            "../../rand-personal/2026-jan-energy-considerations-package/EnergyConsiderations.docx",
        )
        file_path = os.path.abspath(file_path)

        # Define paths for saved files
        doc_dir = os.path.dirname(file_path)
        doc_name = os.path.splitext(os.path.basename(file_path))[0]
        markdown_path = os.path.join(doc_dir, f"{doc_name}_processed.md")
        chunks_path = os.path.join(doc_dir, f"{doc_name}_chunks.json")
        references_path = os.path.join(doc_dir, f"{doc_name}_references.json")
        bibliography_path = os.path.join(doc_dir, f"{doc_name}_bibliography.txt")
        footnotes_path = os.path.join(doc_dir, f"{doc_name}_footnotes.json")

        # Check if all saved files exist
        all_saved_files_exist = all(
            os.path.exists(p)
            for p in [
                markdown_path,
                chunks_path,
                references_path,
                bibliography_path,
                footnotes_path,
            ]
        )

        if all_saved_files_exist:
            print(f"\n{'='*80}")
            print("LOADING FROM SAVED FILES (skipping processing)")
            print(f"{'='*80}\n")

            # Load markdown
            print(f"Loading markdown from: {markdown_path}")
            with open(markdown_path, "r", encoding="utf-8") as f:
                markdown_content = f.read()
            print(f"Loaded markdown: {len(markdown_content)} characters")

            # Create a minimal FileDocument for compatibility
            file_document = type(
                "FileDocument",
                (),
                {
                    "markdown": markdown_content,
                    "file_path": file_path,
                    "file_name": os.path.basename(file_path),
                },
            )()

            # Load chunks
            print(f"Loading chunks from: {chunks_path}")
            with open(chunks_path, "r", encoding="utf-8") as f:
                chunks_data = json.load(f)

            # Convert to chunk objects
            from lib.workflows.document_processing.state import DocumentChunk

            chunks = [
                DocumentChunk(
                    chunk_index=c["chunk_index"],
                    paragraph_index=c["paragraph_index"],
                    content=c["content"],
                )
                for c in chunks_data
            ]
            print(f"Loaded {len(chunks)} chunks")

            # Load references
            print(f"Loading references from: {references_path}")
            with open(references_path, "r", encoding="utf-8") as f:
                references_data = json.load(f)

            # Convert to BibliographyItem objects
            from lib.models.bibliography_item import BibliographyItem

            references = [
                BibliographyItem(
                    text=r["text"],
                    has_associated_supporting_document=r[
                        "has_associated_supporting_document"
                    ],
                    index_of_associated_supporting_document=r[
                        "index_of_associated_supporting_document"
                    ],
                    name_of_associated_supporting_document=r[
                        "name_of_associated_supporting_document"
                    ],
                )
                for r in references_data
            ]
            print(f"Loaded {len(references)} bibliography entries")

            # Load formatted bibliography
            print(f"Loading bibliography from: {bibliography_path}")
            with open(bibliography_path, "r", encoding="utf-8") as f:
                formatted_bibliography = f.read()

            # Load footnotes
            print(f"Loading footnotes from: {footnotes_path}")
            with open(footnotes_path, "r", encoding="utf-8") as f:
                footnotes = json.load(f)
            print(f"Loaded {len(footnotes)} footnotes")

            if references:
                print("\nFirst few bibliography entries:")
                for i, ref in enumerate(references[:3], 1):
                    print(f"  {i}. {ref.text[:100]}...")

        else:
            print(f"Loading document: {file_path}")
            print(f"File size: {os.path.getsize(file_path) / 1024:.1f} KB")

            try:
                file_document = await create_file_document_from_path(
                    file_path,
                    file_id=str(uuid.uuid4()),
                )
                print(f"Document loaded: {len(file_document.markdown)} characters")

                # Save markdown to file
                with open(markdown_path, "w", encoding="utf-8") as f:
                    f.write(file_document.markdown)
                print(f"Saved markdown to: {markdown_path}")

            except Exception as e:
                print(f"ERROR: Failed to load document: {e}")
                print(f"Error type: {type(e).__name__}")
                import traceback

                traceback.print_exc()
                return

            # 3. Process document (chunking)
            print("\nRunning document processing workflow...")
            doc_state = DocumentProcessingState(
                config=DocumentProcessingWorkflowConfig(project_id="test"),
                file=file_document,
                supporting_files=None,
            )
            doc_result = (
                await build_document_processing_graph()
                .compile()
                .ainvoke(doc_state, context=context)
            )
            chunks = doc_result["chunks"]
            print(f"Document chunked into {len(chunks)} chunks")

            # Save chunks to file for reference
            chunks_data = [
                {
                    "chunk_index": chunk.chunk_index,
                    "paragraph_index": chunk.paragraph_index,
                    "content": chunk.content,
                    "content_length": len(chunk.content),
                }
                for chunk in chunks
            ]
            with open(chunks_path, "w", encoding="utf-8") as f:
                json.dump(chunks_data, f, indent=2, ensure_ascii=False)
            print(f"Saved {len(chunks)} chunks to: {chunks_path}")

            # 4. Extract references
            print("\nRunning reference extraction workflow...")
            ref_state = ReferenceExtractionState(
                config=ReferenceExtractionConfig(project_id="test"),
                file=doc_result["file"],
                supporting_files=None,
                supporting_documents_summaries=None,
            )
            ref_result = (
                await build_reference_extraction_graph()
                .compile()
                .ainvoke(ref_state, context=context)
            )
            references = ref_result["references"]
            print(f"Extracted {len(references)} bibliography entries")

            if references:
                print("\nFirst few bibliography entries:")
                for i, ref in enumerate(references[:3], 1):
                    print(f"  {i}. {ref.text[:100]}...")

            # Save references to file
            references_data = [
                {
                    "index": i + 1,
                    "text": ref.text,
                    "has_associated_supporting_document": ref.has_associated_supporting_document,
                    "index_of_associated_supporting_document": ref.index_of_associated_supporting_document,
                    "name_of_associated_supporting_document": ref.name_of_associated_supporting_document,
                }
                for i, ref in enumerate(references)
            ]
            with open(references_path, "w", encoding="utf-8") as f:
                json.dump(references_data, f, indent=2, ensure_ascii=False)
            print(f"Saved {len(references)} references to: {references_path}")

            # Save formatted bibliography (as used by citation detector)
            formatted_bibliography = format_bibliography_prompt_section(
                references, supporting_files=[]
            )
            with open(bibliography_path, "w", encoding="utf-8") as f:
                f.write(formatted_bibliography)
            print(f"Saved formatted bibliography to: {bibliography_path}")

            # Note: For footnotes extraction in the non-cached path,
            # you would need to run footnote extraction workflow here
            # For now, we'll use an empty list
            footnotes = []
            print("Warning: Footnotes not extracted in non-cached path")

        # 5. Format bibliography (already loaded or created above)

        # 6. Format footnotes list
        formatted_footnotes = format_footnotes_prompt_section(footnotes)

        # 7. Select sample chunks or use custom chunk
        if custom_chunk:
            # Use custom chunk provided by user
            print(f"\n{'='*80}")
            print("ANALYZING CUSTOM CHUNK")
            print(f"{'='*80}\n")
            print(f"Custom chunk length: {len(custom_chunk)} characters")

            # Create a mock chunk object for custom text
            from lib.workflows.document_processing.state import DocumentChunk

            sample_chunks = [
                DocumentChunk(
                    chunk_index=0,
                    paragraph_index=0,
                    content=custom_chunk,
                )
            ]
            sample_size = 1
        else:
            # Use first N chunks from document
            sample_size = min(10, len(chunks))
            sample_chunks = chunks[:sample_size]
            print(f"\nAnalyzing first {sample_size} chunks for citations...")

        # 8. Detect citations
        citation_detector_agent = CitationDetectorAgent(context)
        total_citations = 0
        chunks_with_citations = 0

        for chunk in sample_chunks:
            print(f"\n{'='*80}")
            print(f"Chunk {chunk.chunk_index} (paragraph {chunk.paragraph_index}):")
            content_preview = (
                chunk.content[:200] + "..."
                if len(chunk.content) > 200
                else chunk.content
            )
            print(f"{content_preview}")

            response = await citation_detector_agent.ainvoke(
                {
                    "footnotes_list": formatted_footnotes,
                    "bibliography": formatted_bibliography,
                    "chunk": chunk.content,
                }
            )

            if response.citations:
                chunks_with_citations += 1
                total_citations += len(response.citations)
                print(f"\nFound {len(response.citations)} citation(s):")
                for i, citation in enumerate(response.citations, 1):
                    print(f"\n  Citation {i}:")
                    print(f"    Text: {citation.text}")
                    print(f"    Type: {citation.type.value}")
                    print(f"    Format: {citation.format}")
                    print(f"    Needs bibliography: {citation.needs_bibliography}")
                    if citation.associated_bibliography:
                        bib_preview = (
                            citation.associated_bibliography[:150] + "..."
                            if len(citation.associated_bibliography) > 150
                            else citation.associated_bibliography
                        )
                        print(
                            f"    Bibliography entry (index {citation.index_of_associated_bibliography}):"
                        )
                        print(f"      {bib_preview}")
                    else:
                        print(f"    Bibliography entry: None")
                    print(f"    Rationale: {citation.rationale}")
            else:
                print("  No citations found")

        # 7.5. Calculate accuracy if ground truth provided
        if ground_truth and custom_chunk:
            print(f"\n{'='*80}")
            print("ACCURACY ANALYSIS")
            print(f"{'='*80}\n")

            expected_citations = ground_truth.get("citations", [])
            detected_citations = response.citations if response.citations else []

            # Count correct bibliography index matches
            correct = 0
            total_expected = len(expected_citations)

            # Normalize citation text for comparison (extract footnote number)
            def normalize_citation_text(text: str) -> str:
                """Extract footnote number from various formats."""
                import re

                # Match patterns like [[107]](#footnote-108), [107], or just 107
                match = re.search(r"\[*(\d+)\]*(?:\(#footnote-\d+\))?", text)
                if match:
                    return match.group(1)
                return text.strip()

            # Display comparison for each citation
            print("Citation-by-Citation Comparison:\n")
            for i, exp_cit in enumerate(expected_citations, 1):
                citation_text = exp_cit["text"]
                exp_bib_idx = exp_cit.get("bibliography_index")
                normalized_expected = normalize_citation_text(citation_text)

                # Find matching detected citation by normalized text
                det_cit = None
                for c in detected_citations:
                    normalized_detected = normalize_citation_text(c.text)
                    if normalized_detected == normalized_expected:
                        det_cit = c
                        break

                if det_cit:
                    det_bib_idx = (
                        det_cit.index_of_associated_bibliography
                        if det_cit.associated_bibliography
                        else None
                    )
                    match = "✓" if exp_bib_idx == det_bib_idx else "✗"
                    if exp_bib_idx == det_bib_idx:
                        correct += 1

                    print(f"  {i}. {citation_text} (normalized: {normalized_expected})")
                    print(
                        f"     Detected as: {det_cit.text} (normalized: {normalize_citation_text(det_cit.text)})"
                    )
                    print(f"     Expected: {exp_bib_idx}")
                    print(f"     Detected: {det_bib_idx} {match}")
                else:
                    print(f"  {i}. {citation_text} (normalized: {normalized_expected})")
                    print(f"     Expected: {exp_bib_idx}")
                    print(f"     Detected: NOT FOUND ✗")
                    # Show what was actually detected for debugging
                    if detected_citations:
                        print(
                            f"     Available detected citations: {[c.text for c in detected_citations]}"
                        )

            accuracy = (correct / total_expected * 100) if total_expected > 0 else 0

            print(f"\nAccuracy: {correct}/{total_expected} = {accuracy:.1f}%")

        # 8. Summary statistics
        print(f"\n{'='*80}")
        print("SUMMARY:")
        print(f"  Total chunks analyzed: {sample_size}")
        print(f"  Chunks with citations: {chunks_with_citations}")
        print(f"  Total citations found: {total_citations}")
        print(f"  Bibliography entries available: {len(references)}")
        print(f"  Footnotes available: {len(footnotes)}")

        print(f"\n{'='*80}")
        print("SAVED FILES:")
        print(f"  Markdown: {markdown_path}")
        print(f"  Chunks: {chunks_path} ({len(chunks)} chunks)")
        print(f"  References: {references_path} ({len(references)} entries)")
        print(f"  Bibliography: {bibliography_path}")
        print(f"  Footnotes: {footnotes_path} ({len(footnotes)} footnotes)")
        print(
            f"\nThese files can be used for testing citation extraction without re-processing."
        )

    # first example custom chunk
    EXAMPLE_CUSTOM_CHUNK_1 = """
    The solar availability assessment for a potential data center site begins with a **Land Suitability and Availability Screen**, which involves visually inspecting satellite imagery[[107]](#footnote-108) to identify any structures, topographical features, or vegetation that could cause significant shading, as well as verifying the presence of large, clear areas suitable for ground-mounted solar installations. Next, the cleared area suitable for solar deployment is measured, typically in square feet, to estimate the scale of possible on-site solar generation. For sites that pass the initial land screen, the location is then matched to its corresponding **Global Horizontal Solar Irradiance (GHSI)** value—measured in kilowatt-hours per square meter per day (kWh/m²/day)—using geospatial solar resource maps.[[108]](#footnote-109) In the framework, sites are scored from A to E based on GHSI values, with lower irradiance indicating limited potential and higher values representing stronger solar availability: less than 3.0 kWh/m²/day = E (inadequate), 3.0–4.0 = D (low potential), 4.0–5.0 = C (moderate potential), 5.0–6.5 = B (high potential), and greater than 6.5 kWh/m²/day = A (does not constrain potential). These thresholds correspond to the ranges presented in Appendix A.

    **Natural gas availability (BTM)**

    Our previous report, *Barriers and Solutions for Expanding US Net Available Capacity by 2030*,[[109]](#footnote-110) identified access to natural gas pipelines as an important factor for BTM power generation to support data center’s energy needs. Natural gas-fired backup or baseload BTM generation can provide firm, dispatchable power to mitigate the variability of renewables and maintain high site reliability.[[110]](#footnote-111) This is especially important for data centers, which require continuous, uninterruptible power to avoid disruptions to computational tasks and maintain operational uptime. Stakeholders from the data center and energy sectors consider new natural gas capacity additions as one of the primary options currently available to maintain reliability while meeting increasing power capacity needs. The methodology for assessing natural gas availability for BTM generation builds on the **Global Gas Infrastructure Tracker** map to identify the presence and proximity of existing pipelines. If a sufficient pipeline network is identified in the vicinity, the next step is to consult  **Global Gas Infrastructure Tracker** to determine whether there are planned or ongoing pipeline expansion projects in the region that could enhance long-term supply reliability and capacity.[[111]](#footnote-112)
    """.strip()

    GROUND_TRUTH_1 = {
        "citations": [
            {
                "text": "[[107]](#footnote-108)",
                "bibliography_index": None,
            },  # reference but not in bibliography
            {"text": "[[108]](#footnote-109)", "bibliography_index": 64},
            {"text": "[[109]](#footnote-110)", "bibliography_index": 2},
            {"text": "[[110]](#footnote-111)", "bibliography_index": 75},
            {"text": "[[111]](#footnote-112)", "bibliography_index": 49},
        ]
    }

    # second example custom chunk
    EXAMPLE_CUSTOM_CHUNK_2 = """
    * Based on literature reviews conducted as part of our previous reports, we identified key criteria for data center site selection, including grid, energy infrastructure, and environmental criteria.[[7]](#footnote-8)
    * Through analysis of the data drawn from Task 1, we identified barriers to increasing energy capacity for AI in specific locations[[8]](#footnote-9). Our approach accounts for a diverse range of factors that affect energy availability at a given location, including but not limited to energy prices, energy availability from the grid, potential energy from new generation, existing transmission and distribution infrastructure , and other potential constraints. These factors correspond to the categories used in the framework, such as Energy Supply, Energy System, Supporting Inputs, Environmental Considerations, and Governance and Community Considerations, which provide the basis for assigning the A‑to‑E grades to indicate best-to-worst conditions shown in later for each assessment site.
    * We categorized these barriers into a framework for multicriteria decision making and developed individual Key Performance Indicators (KPIs) and scoring criteria for each barrier. The final framework was developed after several rounds of feedback from stakeholders from the energy datacenter industry.[[9]](#footnote-10)
    * Using this framework, we assessed 22 sites: 17 identified by DOE, two private‑sector developments by the Stargate consortium, and three recently retired or retiring power plants.[[10]](#footnote-11)[[11]](#footnote-12)
    """.strip()

    GROUND_TRUTH_2 = {
        "citations": [
            {
                "text": "[[7]](#footnote-8)",
                "bibliography_index": None,
            },  # non reference
            {
                "text": "[[8]](#footnote-9)",
                "bibliography_index": 1,
            },  # non reference
            {
                "text": "[[9]](#footnote-10)",
                "bibliography_index": None,
            },  # non reference
            {
                "text": "[[10]](#footnote-11)",
                "bibliography_index": 77,
            },  # non reference
            {"text": "[[11]](#footnote-12)", "bibliography_index": 74},
        ]
    }

    # third example custom chunk
    EXAMPLE_CUSTOM_CHUNK_3 = """
    * The availability of reliable and scalable energy supply has emerged as a principal bottleneck to further AI development. Given the projected exponential growth in data center electricity consumption, energy access and location are becoming central determinants of AI competitiveness and innovation.[[20]](#footnote-21)
    * High-profile initiatives, such as the Stargate project in Texas, illustrate how targeted infrastructure investments and coordinated stakeholder efforts can enable regional clusters of AI activity. Recent developments have highlighted the limits of concentrated demand growth in terms of available land, workforce capacity, cooling needs and providing both sufficient power and backup power generation.[[21]](#footnote-22) Externalities from large single data centers may be exacerbated in terms of environmental impacts, pollution from electricity generation, and spiking labor and material costs in the local region.[[22]](#footnote-23)
    """.strip()

    GROUND_TRUTH_3 = {
        "citations": [
            {"text": "[[20]](#footnote-21)", "bibliography_index": 33},
            {
                "text": "[[21]](#footnote-22)",
                "bibliography_index": None,
            },  # reference but not in bibliography
            {
                "text": "[[22]](#footnote-23)",
                "bibliography_index": None,
            },  # reference but not in bibliography
        ]
    }

    # Run all test cases and display results in a table
    async def run_all_tests():
        import json
        from tabulate import tabulate

        test_cases = [
            ("Example 1 - Solar & Natural Gas", EXAMPLE_CUSTOM_CHUNK_1, GROUND_TRUTH_1),
            ("Example 2 - Site Selection", EXAMPLE_CUSTOM_CHUNK_2, GROUND_TRUTH_2),
            ("Example 3 - AI Infrastructure", EXAMPLE_CUSTOM_CHUNK_3, GROUND_TRUTH_3),
        ]

        results = []

        for name, chunk, truth in test_cases:
            print(f"\n{'='*80}")
            print(f"Running: {name}")
            print(f"{'='*80}")

            # Run the test (we need to capture the accuracy)
            # For now, we'll need to modify main to return the accuracy
            # Let's create a simplified version
            from lib.services.file_artifacts_service.mock import (
                MockFileArtifactsService,
            )
            from lib.services.vector_store import VectorStoreService

            setup_logger()
            context = ContextSchema(
                openai_api_key=config.OPENAI_API_KEY,
                vector_store=VectorStoreService(
                    config.DATABASE_URL, config.OPENAI_API_KEY
                ),
                file_artifacts_service=MockFileArtifactsService(),
            )

            # Load saved files
            file_path = os.path.join(
                os.path.dirname(__file__),
                "../../rand-personal/2026-jan-energy-considerations-package/EnergyConsiderations.docx",
            )
            file_path = os.path.abspath(file_path)
            doc_dir = os.path.dirname(file_path)
            doc_name = os.path.splitext(os.path.basename(file_path))[0]
            markdown_path = os.path.join(doc_dir, f"{doc_name}_processed.md")
            bibliography_path = os.path.join(doc_dir, f"{doc_name}_bibliography.txt")
            footnotes_path = os.path.join(doc_dir, f"{doc_name}_footnotes.json")

            # Load markdown and bibliography
            with open(markdown_path, "r", encoding="utf-8") as f:
                markdown_content = f.read()
            with open(bibliography_path, "r", encoding="utf-8") as f:
                formatted_bibliography = f.read()
            with open(footnotes_path, "r", encoding="utf-8") as f:
                footnotes = json.load(f)

            # Format footnotes for the prompt
            formatted_footnotes = format_footnotes_prompt_section(footnotes)

            file_document = type(
                "FileDocument",
                (),
                {
                    "markdown": markdown_content,
                    "file_path": file_path,
                    "file_name": os.path.basename(file_path),
                },
            )()

            # Run citation detection
            citation_detector_agent = CitationDetectorAgent(context)
            response = await citation_detector_agent.ainvoke(
                {
                    "footnotes_list": formatted_footnotes,
                    "bibliography": formatted_bibliography,
                    "chunk": chunk,
                }
            )

            # Print detailed citation results
            print(f"\n{'='*80}")
            print("DETAILED RESULTS")
            print(f"{'='*80}\n")

            if response.citations:
                print(f"Found {len(response.citations)} citation(s):\n")
                for i, citation in enumerate(response.citations, 1):
                    print(f"Citation {i}:")
                    print(f"  Text: {citation.text}")
                    print(f"  Type: {citation.type.value}")
                    print(f"  Format: {citation.format}")
                    print(f"  Needs bibliography: {citation.needs_bibliography}")
                    if citation.associated_bibliography:
                        bib_preview = (
                            citation.associated_bibliography[:150] + "..."
                            if len(citation.associated_bibliography) > 150
                            else citation.associated_bibliography
                        )
                        print(
                            f"  Bibliography entry (index {citation.index_of_associated_bibliography}):"
                        )
                        print(f"    {bib_preview}")
                    else:
                        print(f"  Bibliography entry: None")
                    print(f"  Rationale: {citation.rationale}")
                    print()
            else:
                print("No citations found\n")

            print(f"Overall rationale: {response.rationale}\n")

            # Calculate accuracy
            expected_citations = truth.get("citations", [])
            detected_citations = response.citations if response.citations else []

            correct = 0
            total_expected = len(expected_citations)

            # Normalize citation text for comparison (extract footnote number)
            def normalize_citation_text(text: str) -> str:
                """Extract footnote number from various formats."""
                import re

                # Match patterns like [[107]](#footnote-108), [107], or just 107
                match = re.search(r"\[*(\d+)\]*(?:\(#footnote-\d+\))?", text)
                if match:
                    return match.group(1)
                return text.strip()

            # Display comparison for each citation
            if expected_citations:
                print(f"{'='*80}")
                print("CITATION-BY-CITATION COMPARISON")
                print(f"{'='*80}\n")
                for i, exp_cit in enumerate(expected_citations, 1):
                    citation_text = exp_cit["text"]
                    exp_bib_idx = exp_cit.get("bibliography_index")
                    normalized_expected = normalize_citation_text(citation_text)

                    # Find matching detected citation by normalized text
                    det_cit = None
                    for c in detected_citations:
                        normalized_detected = normalize_citation_text(c.text)
                        if normalized_detected == normalized_expected:
                            det_cit = c
                            break

                    if det_cit:
                        det_bib_idx = (
                            det_cit.index_of_associated_bibliography
                            if det_cit.associated_bibliography
                            else None
                        )
                        match = "✓" if exp_bib_idx == det_bib_idx else "✗"
                        if exp_bib_idx == det_bib_idx:
                            correct += 1

                        print(
                            f"  {i}. {citation_text} (normalized: {normalized_expected})"
                        )
                        print(
                            f"     Detected as: {det_cit.text} (normalized: {normalize_citation_text(det_cit.text)})"
                        )
                        print(f"     Expected: {exp_bib_idx}")
                        print(f"     Detected: {det_bib_idx} {match}")
                    else:
                        print(
                            f"  {i}. {citation_text} (normalized: {normalized_expected})"
                        )
                        print(f"     Expected: {exp_bib_idx}")
                        print(f"     Detected: NOT FOUND ✗")
                        # Show what was actually detected for debugging
                        if detected_citations:
                            print(
                                f"     Available detected citations: {[c.text for c in detected_citations]}"
                            )
                print()

            accuracy = (correct / total_expected * 100) if total_expected > 0 else 0

            results.append(
                {
                    "Test Case": name,
                    "Expected": total_expected,
                    "Detected": len(detected_citations),
                    "Correct": correct,
                    "Accuracy": f"{accuracy:.1f}%",
                }
            )

            print(
                f"Summary: Expected={total_expected}, Detected={len(detected_citations)}, Correct={correct}, Accuracy={accuracy:.1f}%"
            )

        # Display summary table
        print(f"\n{'='*80}")
        print("SUMMARY TABLE")
        print(f"{'='*80}\n")
        print(
            tabulate(
                results,
                headers="keys",
                tablefmt="grid",
            )
        )

    # Run all tests
    asyncio.run(run_all_tests())

    # To test individual cases:
    # asyncio.run(main(custom_chunk=EXAMPLE_CUSTOM_CHUNK_1, ground_truth=GROUND_TRUTH_1))
    # asyncio.run(main(custom_chunk=EXAMPLE_CUSTOM_CHUNK_2, ground_truth=GROUND_TRUTH_2))
    # asyncio.run(main(custom_chunk=EXAMPLE_CUSTOM_CHUNK_3, ground_truth=GROUND_TRUTH_3))

    # Default: analyze first 10 chunks from document
    # asyncio.run(main())
