import asyncio
import re
import logging
from typing import List, Optional
import nltk
from pydantic import BaseModel, Field

from lib.agents.models import ValidatedDocument, DocumentMetadata
from lib.models.agent import BaseAgent
from lib.services.fragment_detection import (
    has_suspicious_fragments,
    DetectionMethod,
)
from lib.services.llm_sentence_tokenizer import (
    llm_tokenize_paragraph,
    FRAGMENT_DETECTION_METHOD,
)
from lib.workflows.claim_substantiation.context import ContextSchema
from langchain_core.runnables.config import RunnableConfig

logger = logging.getLogger(__name__)

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


class Paragraph(BaseModel):
    chunks: List[str] = Field(
        description="The chunks extracted from the paragraph, that when concatenated should recreate the content of the original paragraph"
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
                    page_content=chunk,
                    metadata=DocumentMetadata(
                        paragraph_index=paragraph_index,
                        chunk_index=chunk_index,
                        chunk_index_within_paragraph=index_within_paragraph,
                    ),
                )
            )
            chunk_index += 1
    return chunks


def split_into_paragraphs(text: str) -> List[str]:
    """
    Split text into paragraphs based on blank lines (double newlines).
    This keeps code blocks, multi-line lists, and other formatted content intact.
    """
    # Split on blank lines (double newlines or more)
    paragraphs = re.split(r"\n\s*\n", text)
    return [p.strip() for p in paragraphs if p.strip()]


async def split_paragraph_into_sentences(
    paragraph: str,
    detection_method: Optional[DetectionMethod] = None,
    context: ContextSchema = None,
) -> List[str]:
    """
    Split a paragraph into sentences using NLTK's sentence tokenizer.

    Uses a hybrid approach:
    1. Fast NLTK tokenization first
    2. Fragment detection to identify problems
    3. LLM fallback for suspicious fragments

    Args:
        paragraph: The text to split into sentences
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

    # Reference-style numbered entries: split multiple references into separate chunks
    lines = [ln.strip() for ln in paragraph.split("\n") if ln.strip()]
    if any(re.match(r"^\d+\.\s+", ln) for ln in lines):
        # This paragraph contains numbered references
        chunks = []
        for line in lines:
            if re.match(r"^\d+\.\s+", line):
                # This is a numbered reference item - keep as one chunk
                chunks.append(line)
            else:
                # Continuation line - attach to previous chunk
                if chunks:
                    chunks[-1] = f"{chunks[-1]} {line}"
                else:
                    chunks.append(line)
        return chunks

    # Detect unnumbered citations/references
    # Must start VERY specifically like a citation
    has_year = re.search(r"\b(19|20)\d{2}\b", paragraph)
    starts_like_citation = (
        # Author format: "LastName, FirstInitial."
        re.match(r"^[A-Z][a-z]+,\s+[A-Z]\.", paragraph)
        or
        # Organization with year early: "Org Name (Acronym). (Year)"
        (
            re.match(r"^[A-Z].*\(.*\)\.\s*\(", paragraph)
            and len(paragraph.split()[0]) > 2
        )
    )

    if has_year and starts_like_citation:
        return [paragraph.strip()]

    # For list items (-, *) we want sentence-level chunks, while preserving marker on first sentence
    if (
        paragraph.startswith("- ")
        or paragraph.startswith("* ")
        or paragraph.startswith("1. ")
    ):
        # Extract the list marker
        if paragraph.startswith("- "):
            marker = "- "
        elif paragraph.startswith("* "):
            marker = "* "
        elif paragraph.startswith("1. "):
            marker = "1. "
        else:
            marker = ""

        # Remove the marker and split into sentences
        content = paragraph[len(marker) :].strip()
        sentences = nltk.sent_tokenize(content)

        # Clean up sentences and add marker back to first sentence
        cleaned_sentences = []
        for i, sentence in enumerate(sentences):
            sentence = sentence.strip()
            if sentence:
                if i == 0 and marker:
                    cleaned_sentences.append(f"{marker}{sentence}")
                else:
                    cleaned_sentences.append(sentence)

        # Check for suspicious fragments before returning
        method = detection_method or FRAGMENT_DETECTION_METHOD
        suspicion_detected, suspicion_score = await has_suspicious_fragments(
            cleaned_sentences, paragraph, method=method
        )

        if suspicion_detected:
            logger.info(
                f"Fragment detection triggered LLM fallback for list item: method={method}, "
                f"score={suspicion_score}, nltk_fragments={len(cleaned_sentences)}, "
                f"paragraph={paragraph}..."
            )
            result = await llm_tokenize_paragraph(paragraph, context=context)
            return result

        return cleaned_sentences

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
        result = await llm_tokenize_paragraph(paragraph, context=context)

    return result


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

    async def ainvoke(
        self,
        prompt_kwargs: dict,
        config: RunnableConfig = None,
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

        # Split document into paragraphs
        paragraphs = split_into_paragraphs(full_document)

        from lib.run_utils import MAX_CONCURRENT_TASKS

        semaphore = asyncio.Semaphore(MAX_CONCURRENT_TASKS)

        async def process_paragraph(paragraph_text: str) -> Optional[Paragraph]:
            if not paragraph_text.strip():
                return None

            async with semaphore:
                sentences = await split_paragraph_into_sentences(
                    paragraph_text, context=self.context
                )

            return Paragraph(chunks=sentences) if sentences else None

        tasks = [process_paragraph(p) for p in paragraphs]
        results = await asyncio.gather(*tasks)

        paragraph_objects = [p for p in results if p is not None]

        return DocumentChunkerResponse(paragraphs=paragraph_objects)
