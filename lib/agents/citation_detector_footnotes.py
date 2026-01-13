from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableConfig

from lib.agents.citation_detector import CitationResponse
from lib.config.llm_models import gpt_5_mini_model
from lib.models.agent import LangChainAgent
from lib.workflows.context import ContextSchema
import json
from lib.models.footnote_item import FootnoteItem

_citation_detector_footnotes_prompt = ChatPromptTemplate.from_template(
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


class CitationDetectorFootnotesAgent(LangChainAgent):
    name = "Citation Detector (Footnotes)"
    description = "Detect citations in chunks with footnotes list"
    model = gpt_5_mini_model
    temperature = 0.0
    output_schema = CitationResponse

    async def ainvoke(
        self, prompt_kwargs: dict, config: RunnableConfig = None
    ) -> CitationResponse:
        messages = _citation_detector_footnotes_prompt.format_messages(**prompt_kwargs)
        return await self.llm.ainvoke(messages, config=config)


if __name__ == "__main__":
    import asyncio
    import os
    from pathlib import Path

    import nest_asyncio

    from lib.agents.formatting_utils import format_bibliography_prompt_section
    from lib.config.env import config
    from lib.config.logger import setup_logger
    from lib.models.bibliography_item import BibliographyItem
    from lib.services.file import create_file_document_from_path
    from lib.workflows.document_processing.graph import build_document_processing_graph
    from lib.workflows.document_processing.state import (
        DocumentProcessingWorkflowConfig,
        DocumentProcessingState,
    )
    from lib.workflows.footnote_extraction.graph import build_footnote_extraction_graph
    from lib.workflows.footnote_extraction.state import (
        FootnoteExtractionConfig,
        FootnoteExtractionState,
    )
    from lib.workflows.reference_extraction.graph import (
        build_reference_extraction_graph,
    )
    from lib.workflows.reference_extraction.state import (
        ReferenceExtractionConfig,
        ReferenceExtractionState,
    )

    nest_asyncio.apply()

    async def main(custom_chunk: str = None, ground_truth: dict = None):
        """
        Test the citation detector with footnotes agent using real document processing.
        """
        setup_logger()

        # Document setup
        doc_path = os.path.join(
            os.path.dirname(__file__),
            "../../rand-personal/2026-jan-energy-considerations-package/EnergyConsiderations.docx",
        )
        doc_path = os.path.abspath(doc_path)
        doc_dir = os.path.dirname(doc_path)
        doc_name = os.path.splitext(os.path.basename(doc_path))[0]

        # File paths for saved artifacts
        markdown_path = os.path.join(doc_dir, f"{doc_name}_processed.md")
        chunks_path = os.path.join(doc_dir, f"{doc_name}_chunks.json")
        references_path = os.path.join(doc_dir, f"{doc_name}_references.json")
        footnotes_path = os.path.join(doc_dir, f"{doc_name}_footnotes.json")

        context = ContextSchema(openai_api_key=config.OPENAI_API_KEY, vector_store=None)

        print(f"\n{'='*80}")
        print("DOCUMENT PROCESSING AND FOOTNOTE EXTRACTION")
        print(f"{'='*80}\n")

        # Track which steps need to run
        file_document = None
        chunks = None
        references = None
        footnotes = None

        # Step 1: Document Processing (chunks + markdown)
        if os.path.exists(chunks_path) and os.path.exists(markdown_path):
            print("Loading existing chunks...\n")
            with open(chunks_path, "r", encoding="utf-8") as f:
                chunks_data = json.load(f)
            print(f"   ✓ Loaded {len(chunks_data)} chunks\n")
        else:
            print("1. Document Processing...")
            file_document = await create_file_document_from_path(
                doc_path, file_id="test-file", markdown_convert=True
            )

            doc_config = DocumentProcessingWorkflowConfig(project_id="test")
            doc_state = DocumentProcessingState(config=doc_config, file=file_document)

            doc_graph = build_document_processing_graph()
            doc_result = await doc_graph.compile().ainvoke(doc_state, context=context)

            markdown_content = doc_result["file"].markdown
            chunks = doc_result["chunks"]
            file_document = doc_result["file"]

            # Save markdown
            with open(markdown_path, "w", encoding="utf-8") as f:
                f.write(markdown_content)

            # Save chunks
            chunks_data = [
                {
                    "chunk_index": chunk.chunk_index,
                    "content": chunk.content,
                    "start_page": chunk.start_page,
                    "end_page": chunk.end_page,
                }
                for chunk in chunks
            ]
            with open(chunks_path, "w", encoding="utf-8") as f:
                json.dump(chunks_data, f, indent=2, ensure_ascii=False)

            print(f"   ✓ Processed {len(chunks)} chunks")
            print(f"   ✓ Saved to {markdown_path}")
            print(f"   ✓ Saved to {chunks_path}\n")

        # Step 2: Reference Extraction
        if os.path.exists(references_path):
            print("Loading existing references...\n")
            with open(references_path, "r", encoding="utf-8") as f:
                references_data = json.load(f)
            references = [
                BibliographyItem(
                    text=ref["text"],
                    has_associated_supporting_document=ref.get(
                        "has_associated_supporting_document", False
                    ),
                    index_of_associated_supporting_document=ref.get(
                        "index_of_associated_supporting_document", -1
                    ),
                    name_of_associated_supporting_document=ref.get(
                        "name_of_associated_supporting_document", ""
                    ),
                )
                for ref in references_data
            ]
            print(f"   ✓ Loaded {len(references)} references\n")
        else:
            print("2. Reference Extraction...")

            # Load file if not already loaded
            if file_document is None:
                file_document = await create_file_document_from_path(
                    doc_path, file_id="test-file", markdown_convert=True
                )

            ref_config = ReferenceExtractionConfig(project_id="test")
            ref_state = ReferenceExtractionState(config=ref_config, file=file_document)

            ref_graph = build_reference_extraction_graph()
            ref_result = await ref_graph.compile().ainvoke(ref_state, context=context)

            references = ref_result["references"]

            # Save references
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

            print(f"   ✓ Extracted {len(references)} references")
            print(f"   ✓ Saved to {references_path}\n")

        # Step 3: Footnote Extraction
        if os.path.exists(footnotes_path):
            print("Loading existing footnotes...\n")
            with open(footnotes_path, "r", encoding="utf-8") as f:
                footnotes_data = json.load(f)
            footnotes = [
                FootnoteItem(
                    marker=fn["marker"],
                    text=fn["text"],
                    reference_code=fn.get("reference_code", ""),
                )
                for fn in footnotes_data
            ]
            print(f"   ✓ Loaded {len(footnotes)} footnotes\n")
        else:
            print("3. Footnote Extraction...")

            # Load file if not already loaded
            if file_document is None:
                file_document = await create_file_document_from_path(
                    doc_path, file_id="test-file", markdown_convert=True
                )

            footnote_config = FootnoteExtractionConfig(project_id="test")
            footnote_state = FootnoteExtractionState(
                config=footnote_config, file=file_document
            )

            footnote_graph = build_footnote_extraction_graph()
            footnote_result = await footnote_graph.compile().ainvoke(
                footnote_state, context=context
            )

            footnotes = footnote_result["footnotes"]

            # Save footnotes
            footnotes_data = [
                {
                    "index": i + 1,
                    "marker": fn.marker,
                    "text": fn.text,
                    "reference_code": fn.reference_code,
                }
                for i, fn in enumerate(footnotes)
            ]
            with open(footnotes_path, "w", encoding="utf-8") as f:
                json.dump(footnotes_data, f, indent=2, ensure_ascii=False)

            print(f"   ✓ Extracted {len(footnotes)} footnotes")
            print(f"   ✓ Saved to {footnotes_path}\n")

        # Use custom chunk if provided, otherwise use default test chunk
        if custom_chunk:
            test_chunk = custom_chunk
        else:
            test_chunk = """
The solar availability assessment for a potential data center site begins with a **Land Suitability and Availability Screen**, which involves visually inspecting satellite imagery[[107]](#footnote-108) to identify any structures, topographical features, or vegetation that could cause significant shading, as well as verifying the presence of large, clear areas suitable for ground-mounted solar installations. Next, the cleared area suitable for solar deployment is measured, typically in square feet, to estimate the scale of possible on-site solar generation. For sites that pass the initial land screen, the location is then matched to its corresponding **Global Horizontal Solar Irradiance (GHSI)** value—measured in kilowatt-hours per square meter per day (kWh/m²/day)—using geospatial solar resource maps.[[108]](#footnote-109)
            """.strip()

        print(f"\n{'='*80}")
        print("TESTING CITATION DETECTOR (FOOTNOTES) AGENT")
        print(f"{'='*80}\n")

        print(f"Test chunk:\n{test_chunk[:200]}...\n")
        print(f"Available footnotes: {len(footnotes)}")
        print(f"Available bibliography entries: {len(references)}\n")

        # Format bibliography
        formatted_bibliography = format_bibliography_prompt_section(
            references, supporting_files=[]
        )

        # Format footnotes list
        def _format_footnotes_list(footnotes_data):
            if not footnotes_data:
                return "No footnotes available."
            lines = []
            for fn in footnotes_data:
                lines.append(f"[{fn.marker}]. {fn.text}")
            return "\n".join(lines)

        footnotes_list = _format_footnotes_list(footnotes)

        # Create agent
        agent = CitationDetectorFootnotesAgent(context)

        # Run detection
        print("Running citation detection...\n")
        response = await agent.ainvoke(
            {
                "footnotes_list": footnotes_list,
                "bibliography": formatted_bibliography,
                "chunk": test_chunk,
            }
        )

        print(f"{'='*80}")
        print("RESULTS")
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
            print("No citations found")

        print(f"Overall rationale: {response.rationale}\n")

        # Calculate accuracy if ground truth provided
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

            accuracy = (correct / total_expected * 100) if total_expected > 0 else 0

            print(f"\nAccuracy: {correct}/{total_expected} = {accuracy:.1f}%")

        print(f"\n{'='*80}")
        print("SUMMARY")
        print(f"{'='*80}\n")
        print(f"Document: {doc_name}")
        print(
            f"Total chunks: {len(chunks_data) if 'chunks_data' in locals() else len(chunks)}"
        )
        print(f"Total references: {len(references)}")
        print(f"Total footnotes: {len(footnotes)}")
        print(f"\nProcessed files saved to: {doc_dir}/")
        print(f"  - {doc_name}_processed.md")
        print(f"  - {doc_name}_chunks.json")
        print(f"  - {doc_name}_references.json")
        print(f"  - {doc_name}_footnotes.json")
        print()

    # Example custom chunks for testing (replicated from citation_detector.py)
    EXAMPLE_CUSTOM_CHUNK_1 = """
    The solar availability assessment for a potential data center site begins with a **Land Suitability and Availability Screen**, which involves visually inspecting satellite imagery[[107]](#footnote-108) to identify any structures, topographical features, or vegetation that could cause significant shading, as well as verifying the presence of large, clear areas suitable for ground-mounted solar installations. Next, the cleared area suitable for solar deployment is measured, typically in square feet, to estimate the scale of possible on-site solar generation. For sites that pass the initial land screen, the location is then matched to its corresponding **Global Horizontal Solar Irradiance (GHSI)** value—measured in kilowatt-hours per square meter per day (kWh/m²/day)—using geospatial solar resource maps.[[108]](#footnote-109) In the framework, sites are scored from A to E based on GHSI values, with lower irradiance indicating limited potential and higher values representing stronger solar availability: less than 3.0 kWh/m²/day = E (inadequate), 3.0–4.0 = D (low potential), 4.0–5.0 = C (moderate potential), 5.0–6.5 = B (high potential), and greater than 6.5 kWh/m²/day = A (does not constrain potential). These thresholds correspond to the ranges presented in Appendix A.

    **Natural gas availability (BTM)**

    Our previous report, *Barriers and Solutions for Expanding US Net Available Capacity by 2030*,[[109]](#footnote-110) identified access to natural gas pipelines as an important factor for BTM power generation to support data center's energy needs. Natural gas-fired backup or baseload BTM generation can provide firm, dispatchable power to mitigate the variability of renewables and maintain high site reliability.[[110]](#footnote-111) This is especially important for data centers, which require continuous, uninterruptible power to avoid disruptions to computational tasks and maintain operational uptime. Stakeholders from the data center and energy sectors consider new natural gas capacity additions as one of the primary options currently available to maintain reliability while meeting increasing power capacity needs. The methodology for assessing natural gas availability for BTM generation builds on the **Global Gas Infrastructure Tracker** map to identify the presence and proximity of existing pipelines. If a sufficient pipeline network is identified in the vicinity, the next step is to consult  **Global Gas Infrastructure Tracker** to determine whether there are planned or ongoing pipeline expansion projects in the region that could enhance long-term supply reliability and capacity.[[111]](#footnote-112)
    """.strip()

    GROUND_TRUTH_1 = {
        "citations": [
            {
                "text": "[[107]](#footnote-108)",
                "bibliography_index": None,
            },
            {"text": "[[108]](#footnote-109)", "bibliography_index": 64},
            {"text": "[[109]](#footnote-110)", "bibliography_index": 2},
            {"text": "[[110]](#footnote-111)", "bibliography_index": 75},
            {"text": "[[111]](#footnote-112)", "bibliography_index": 49},
        ]
    }

    EXAMPLE_CUSTOM_CHUNK_2 = """
    * Based on literature reviews conducted as part of our previous reports, we identified key criteria for data center site selection, including grid, energy infrastructure, and environmental criteria.[[7]](#footnote-8)
    * Through analysis of the data drawn from Task 1, we identified barriers to increasing energy capacity for AI in specific locations[[8]](#footnote-9). Our approach accounts for a diverse range of factors that affect energy availability at a given location, including but not limited to energy prices, energy availability from the grid, potential energy from new generation, existing transmission and distribution infrastructure , and other potential constraints. These factors correspond to the categories used in the framework, such as Energy Supply, Energy System, Supporting Inputs, Environmental Considerations, and Governance and Community Considerations, which provide the basis for assigning the A‑to‑E grades to indicate best-to-worst conditions shown in later for each assessment site.
    * We categorized these barriers into a framework for multicriteria decision making and developed individual Key Performance Indicators (KPIs) and scoring criteria for each barrier. The final framework was developed after several rounds of feedback from stakeholders from the energy datacenter industry.[[9]](#footnote-10)
    * Using this framework, we assessed 22 sites: 17 identified by DOE, two private‑sector developments by the Stargate consortium, and three recently retired or retiring power plants.[[10]](#footnote-11)[[11]](#footnote-12)
    """.strip()

    GROUND_TRUTH_2 = {
        "citations": [
            {"text": "[[7]](#footnote-8)", "bibliography_index": None},
            {"text": "[[8]](#footnote-9)", "bibliography_index": 1},
            {"text": "[[9]](#footnote-10)", "bibliography_index": None},
            {"text": "[[10]](#footnote-11)", "bibliography_index": 77},
            {"text": "[[11]](#footnote-12)", "bibliography_index": 74},
        ]
    }

    EXAMPLE_CUSTOM_CHUNK_3 = """
    * The availability of reliable and scalable energy supply has emerged as a principal bottleneck to further AI development. Given the projected exponential growth in data center electricity consumption, energy access and location are becoming central determinants of AI competitiveness and innovation.[[20]](#footnote-21)
    * High-profile initiatives, such as the Stargate project in Texas, illustrate how targeted infrastructure investments and coordinated stakeholder efforts can enable regional clusters of AI activity. Recent developments have highlighted the limits of concentrated demand growth in terms of available land, workforce capacity, cooling needs and providing both sufficient power and backup power generation.[[21]](#footnote-22) Externalities from large single data centers may be exacerbated in terms of environmental impacts, pollution from electricity generation, and spiking labor and material costs in the local region.[[22]](#footnote-23)
    """.strip()

    GROUND_TRUTH_3 = {
        "citations": [
            {"text": "[[20]](#footnote-21)", "bibliography_index": 33},
            {"text": "[[21]](#footnote-22)", "bibliography_index": None},
            {"text": "[[22]](#footnote-23)", "bibliography_index": None},
        ]
    }

    # Run all test cases and display results in a table
    async def run_all_tests():
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
            # Let's create a simplified version
            setup_logger()
            context = ContextSchema(
                openai_api_key=config.OPENAI_API_KEY, vector_store=None
            )

            # Load saved files
            file_path = os.path.join(
                os.path.dirname(__file__),
                "../../rand-personal/2026-jan-energy-considerations-package/EnergyConsiderations.docx",
            )
            file_path = os.path.abspath(file_path)
            doc_dir = os.path.dirname(file_path)
            doc_name = os.path.splitext(os.path.basename(file_path))[0]
            references_path = os.path.join(doc_dir, f"{doc_name}_references.json")
            footnotes_path = os.path.join(doc_dir, f"{doc_name}_footnotes.json")

            # Load references
            with open(references_path, "r", encoding="utf-8") as f:
                references_data = json.load(f)
            references = [
                BibliographyItem(
                    text=ref["text"],
                    has_associated_supporting_document=ref.get(
                        "has_associated_supporting_document", False
                    ),
                    index_of_associated_supporting_document=ref.get(
                        "index_of_associated_supporting_document", -1
                    ),
                    name_of_associated_supporting_document=ref.get(
                        "name_of_associated_supporting_document", ""
                    ),
                )
                for ref in references_data
            ]

            # Load footnotes
            with open(footnotes_path, "r", encoding="utf-8") as f:
                footnotes_data = json.load(f)
            footnotes = [
                FootnoteItem(
                    marker=fn["marker"],
                    text=fn["text"],
                    reference_code=fn.get("reference_code", ""),
                )
                for fn in footnotes_data
            ]

            # Format bibliography
            formatted_bibliography = format_bibliography_prompt_section(
                references, supporting_files=[]
            )

            # Format footnotes list
            def _format_footnotes_list(footnotes_data):
                if not footnotes_data:
                    return "No footnotes available."
                lines = []
                for fn in footnotes_data:
                    lines.append(f"[{fn.marker}]. {fn.text}")
                return "\n".join(lines)

            footnotes_list = _format_footnotes_list(footnotes)

            # Run citation detection
            agent = CitationDetectorFootnotesAgent(context)
            response = await agent.ainvoke(
                {
                    "footnotes_list": footnotes_list,
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

    # Default: run main with default test chunk
    # asyncio.run(main())
