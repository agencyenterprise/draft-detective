import asyncio
import re
import logging
from typing import List, Optional, Tuple
import nltk
from pydantic import BaseModel, Field

from lib.agents.models import ValidatedDocument, DocumentMetadata
from lib.models.agent import BaseAgent
from lib.services.fragment_detection import (
    has_suspicious_fragments,
    DetectionMethod,
)
from lib.agents.sentence_tokenizer import SentenceTokenizerAgent
from lib.workflows.context import ContextSchema
from langchain_core.runnables.config import RunnableConfig

from langchain_text_splitters import MarkdownHeaderTextSplitter

from lib.run_utils import MAX_CONCURRENT_TASKS

semaphore = asyncio.Semaphore(MAX_CONCURRENT_TASKS)

logger = logging.getLogger(__name__)

FRAGMENT_DETECTION_METHOD: DetectionMethod = "reconstruction"

# Download required NLTK data
try:
    nltk.data.find("tokenizers/punkt_tab")
except LookupError:
    try:
        nltk.download("punkt_tab")
    except Exception as e:
        # Fallback to older punkt tokenizer
        try:
            nltk.download("punkt")
        except Exception as fallback_error:
            raise RuntimeError(
                f"Failed to download NLTK punkt tokenizer: {e}. Fallback also failed: {fallback_error}"
            )


headers_to_split_on = [
    ("#", "H1"),
    ("##", "H2"),
    ("###", "H3"),
    ("####", "H4"),
]

markdown_splitter = MarkdownHeaderTextSplitter(
    headers_to_split_on, strip_headers=False, return_each_line=True
)


class ChunkWithLines(BaseModel):
    """A chunk with its line range in the original markdown."""

    text: str = Field(description="The chunk text")
    start_line: int = Field(ge=1, description="1-indexed starting line in markdown")
    end_line: int = Field(ge=1, description="1-indexed ending line in markdown")


class Paragraph(BaseModel):
    chunks: List[ChunkWithLines] = Field(
        description="The chunks extracted from the paragraph with line information"
    )
    headings: List[str] = Field(
        description="The headings associated with the paragraph. Each heading is a string that is the text of the heading listed according to the hierarchy of the heading."
    )


class DocumentChunkerResponse(BaseModel):
    paragraphs: List[Paragraph] = Field(
        description="The paragraphs extracted from the document, each with sentence-level chunks. When these chunks are all concatenated, they should recreate the content of the original document"
    )


def get_chunker_result_as_langchain_documents(
    chunker_result: DocumentChunkerResponse,
) -> List[ValidatedDocument]:
    chunks = []
    chunk_index = 0
    for paragraph_index, paragraph in enumerate(chunker_result.paragraphs):
        for index_within_paragraph, chunk in enumerate(paragraph.chunks):
            chunks.append(
                ValidatedDocument(
                    page_content=chunk.text,
                    metadata=DocumentMetadata(
                        paragraph_index=paragraph_index,
                        chunk_index=chunk_index,
                        chunk_index_within_paragraph=index_within_paragraph,
                        headings=paragraph.headings if paragraph.headings else None,
                        start_line=chunk.start_line,
                        end_line=chunk.end_line,
                    ),
                )
            )
            chunk_index += 1
    return chunks


def char_offset_to_line(text: str, char_offset: int) -> int:
    """Convert a character offset to a 1-indexed line number."""
    return text[:char_offset].count("\n") + 1


def find_text_line_range(
    full_text: str, search_text: str, search_start: int = 0
) -> Tuple[int, int, int]:
    """
    Find the line range of search_text within full_text.

    Args:
        full_text: The full markdown text
        search_text: The text to find
        search_start: Character offset to start searching from

    Returns:
        Tuple of (start_line, end_line, char_end_position)
        If not found, returns (1, 1, search_start)
    """
    pos = full_text.find(search_text, search_start)
    if pos == -1:
        # Fallback: try to find with stripped text
        stripped = search_text.strip()
        pos = full_text.find(stripped, search_start)
        if pos == -1:
            logger.warning(
                f"Could not find text in document, defaulting to line 1. "
                f"search_text={search_text[:100]!r}..."
            )
            return (1, 1, search_start)
        search_text = stripped

    start_line = char_offset_to_line(full_text, pos)
    end_pos = pos + len(search_text)
    end_line = char_offset_to_line(
        full_text, end_pos - 1
    )  # -1 to get line of last char
    return (start_line, end_line, end_pos)


def split_into_paragraphs(text: str) -> List[str]:
    """
    Split text into paragraphs based on blank lines (double newlines).
    This keeps code blocks, multi-line lists, and other formatted content intact.
    """
    # Split on newlines
    paragraphs = text.split("\n")
    return [p.strip() for p in paragraphs if p.strip()]


async def split_paragraph_into_sentences(
    paragraph: str,
    sentence_tokenizer: SentenceTokenizerAgent,
    detection_method: Optional[DetectionMethod] = None,
) -> List[str]:
    """
    Split a paragraph into sentences using NLTK's sentence tokenizer.

    Uses a hybrid approach:
    1. Fast NLTK tokenization first
    2. Fragment detection to identify problems
    3. LLM fallback for suspicious fragments via SentenceTokenizerAgent

    Args:
        paragraph: The text to split into sentences
        sentence_tokenizer: Agent used as LLM fallback for complex tokenization
        detection_method: Optional override for fragment detection method

    Returns:
        List of sentence chunks
    """
    if re.match(r"^#{1,6}\s+", paragraph):
        return [paragraph.strip()]

    # Check if this is a code block (fenced with backticks)
    # Now that we split on blank lines, code blocks come as complete multi-line paragraphs
    if "```" in paragraph:
        return [paragraph.strip()]

    # Use NLTK sentence tokenizer for regular text
    sentences = nltk.sent_tokenize(paragraph)

    # Clean up sentences (remove extra whitespace)
    cleaned_sentences = [s.strip() for s in sentences if s.strip()]

    # Post-process: merge author with adjacent year in parentheses
    merged: List[str] = []
    for s in cleaned_sentences:
        if merged and re.match(r"^\(\d{4}\)$", s):
            merged[-1] = f"{merged[-1]} {s}"
        else:
            merged.append(s)

    method = detection_method or FRAGMENT_DETECTION_METHOD

    suspicion_detected, suspicion_score = await has_suspicious_fragments(
        merged, paragraph, method=method
    )

    result = merged

    if suspicion_detected:
        logger.info(
            f"Fragment detection triggered LLM fallback: method={method}, "
            f"score={suspicion_score}, nltk_fragments={len(merged)}, "
            f"paragraph={paragraph}..."
        )
        llm_result = await sentence_tokenizer.ainvoke({"paragraph": paragraph})
        result = llm_result.chunks

    return result


async def process_paragraph_sentences(
    para_text: str,
    headings: List[str],
    sentence_tokenizer: SentenceTokenizerAgent,
) -> Tuple[str, List[str], List[str]]:
    """Process paragraph to get sentences, return (para_text, headings, sentences)."""
    if not para_text.strip():
        return (para_text, headings, [])
    async with semaphore:
        sentences = await split_paragraph_into_sentences(
            para_text, sentence_tokenizer=sentence_tokenizer
        )
    return (para_text, headings, sentences)


class DocumentChunkerAgent(BaseAgent):
    name = "Document Chunker (NLTK)"
    description = "Chunk a document into paragraphs and each paragraph into sentence-level chunks using NLTK"

    # This agent doesn't use LLM - it uses NLTK for tokenization,
    # TODO: If we have more agents not using LLM, we should add a base class for them
    model = None  # type: ignore[assignment]
    temperature = 0.0
    output_schema = None

    def __init__(self, context: ContextSchema):
        self.context = context
        self.sentence_tokenizer = SentenceTokenizerAgent(context)

    async def ainvoke(
        self,
        prompt_kwargs: dict,
        config: Optional[RunnableConfig] = None,
    ) -> DocumentChunkerResponse:
        """
        Process a document using NLTK sentence tokenization.

        Args:
            prompt_kwargs: Dictionary containing 'full_document' key with the document text
            config: Optional configuration (not used in NLTK implementation)

        Returns:
            DocumentChunkerResponse with paragraphs and sentence chunks
        """
        full_document = prompt_kwargs.get("full_document", "")

        if not full_document.strip():
            return DocumentChunkerResponse(paragraphs=[])

        # Split document by headings
        md_header_splits = markdown_splitter.split_text(full_document)

        # List of paragraphs to process later, to break into sentence-level chunks
        # Tuple of (paragraph, section_headings_list)
        paragraphs_to_process: List[Tuple[str, List[str]]] = []

        for text_section in md_header_splits:
            section_headings_list = []
            if text_section.metadata:
                # Sort by heading level to ensure hierarchical order (H1, H2, H3, H4)
                sorted_metadata = sorted(
                    text_section.metadata.items(), key=lambda x: x[0]
                )
                for _, heading_value in sorted_metadata:
                    section_headings_list.append(heading_value)

            logger.debug("Text section: ", text_section.page_content)

            # Split document into paragraphs
            paragraphs = split_into_paragraphs(text_section.page_content)

            # Add paragraphs to list to process later
            paragraphs_to_process.extend(
                [(p, section_headings_list) for p in paragraphs]
            )

        # Process paragraphs with sentence tokenization (parallel)
        # First pass: get sentence chunks without line numbers
        tasks = [
            process_paragraph_sentences(para, headings, self.sentence_tokenizer)
            for (para, headings) in paragraphs_to_process
        ]
        sentence_results = await asyncio.gather(*tasks)

        # Second pass: assign line numbers sequentially
        paragraphs_objects: List[Paragraph] = []
        search_pos = 0

        for para_text, headings, sentences in sentence_results:
            if not sentences:
                continue

            chunks_with_lines: List[ChunkWithLines] = []
            for sentence in sentences:
                start_line, end_line, next_pos = find_text_line_range(
                    full_document, sentence, search_pos
                )
                chunks_with_lines.append(
                    ChunkWithLines(
                        text=sentence, start_line=start_line, end_line=end_line
                    )
                )
                search_pos = next_pos

            paragraphs_objects.append(
                Paragraph(chunks=chunks_with_lines, headings=headings)
            )

        return DocumentChunkerResponse(paragraphs=paragraphs_objects)
