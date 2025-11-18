from langchain.chat_models import init_chat_model
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field

from lib.agents.models import ValidatedDocument
from lib.config.llm_models import gpt_4_1_model
from lib.models.agent import DEFAULT_LLM_TIMEOUT, AgentProtocol

from lib.workflows.claim_substantiation.context import ContextSchema


class Paragraph(BaseModel):
    chunks: list[str] = Field(
        description="The chunks extracted from the paragraph, that when concatenated should recreate the content of the original paragraph"
    )


class DocumentChunkerResponse(BaseModel):
    paragraphs: list[Paragraph] = Field(
        description="The paragraphs extracted from the document, each with sentence-level chunks. When these chunks are all concatenated, they should recreate the content of the original document"
    )


def get_chunker_result_as_langchain_documents(
    chunker_result: DocumentChunkerResponse,
) -> list[ValidatedDocument]:
    chunks = []
    chunk_index = 0
    for paragraph_index, paragraph in enumerate(chunker_result.paragraphs):
        for index_within_paragraph, chunk in enumerate(paragraph.chunks):
            chunks.append(
                ValidatedDocument(
                    page_content=chunk,
                    metadata={
                        "paragraph_index": paragraph_index,
                        "chunk_index": chunk_index,
                        "chunk_index_within_paragraph": index_within_paragraph,
                    },
                )
            )
            chunk_index += 1
    return chunks


_document_chunker_agent_system_prompt = f"""You will be given a markdown document.

Your task:
- Break the document into paragraphs that preserve the original order and include every piece of content exactly once.
- Within each paragraph, emit an ordered list of sentence-level chunks.
- Headings must stay with the paragraph they introduce, and MUST be the first chunk in that paragraph (for example: `## Methods`). Copy the exact heading text from the source (including markdown markers like `#`, `##`, etc.) and never invent or modify them.
- Every chunk MUST be a verbatim substring copied from the original text. Do not fabricate, rewrite, paraphrase, expand, or add/remove characters (including heading markers, blank lines, or punctuation).
- Preserve markdown syntax (headings, list markers, emphasis, code fences, blank lines, etc.) exactly as it appears in the original text. If the source contains blank lines, include them within the surrounding chunk; do not emit empty or whitespace-only chunks under any circumstances.
- Prefer breaking prose into sentence-level chunks while keeping short related sentences together when it improves readability.
- Never drop content, merge unrelated sections, or reorder chunks. If unsure, keep more text together rather than omitting anything.
- The concatenation of every chunk in order must recreate the original document text character-for-character (aside from insignificant trailing whitespace and new line differences).
- Chunks should be stripped of new line or space characters at the beginning and end.
- Do NOT create any empty string chunks or chunks that only have white space or new line characters. If the source has extra blank lines between paragraphs, remove them.

Follow this procedure exactly:
1. Work with a copy of the original markdown text.
2. For each paragraph, emit sentence-level chunks by slicing contiguous substrings directly from the paragraph text. Prefer sentence-level boundaries (`.` `?` `!`).
3. Keep all markdown tokens (headings, list markers) attached to the content they modify, but do not add any markdown tokens (e.g., ##) yourself.
3. If blank lines separate portions of the paragraph, attach the newline characters to the preceding or following chunk so that no chunk is empty or only has white space or new line characters.
4. Make sure that if all chunks are concatenated in order, the reconstructed string matches the original markdown exactly (minus any insignificant white space or new line differences).

I will send the markdown document that you need to chunk as my next message.
"""


class DocumentChunkerAgent(AgentProtocol):
    name = "Document Chunker"
    description = "Chunk a document into paragraphs and each paragraph into reasonable sentence-level chunks"

    def __init__(self, context: ContextSchema):
        self.llm = init_chat_model(
            gpt_4_1_model.model_name,
            temperature=0.2,
            timeout=DEFAULT_LLM_TIMEOUT,
            api_key=context.openai_api_key,
        ).with_structured_output(DocumentChunkerResponse)

    async def ainvoke(
        self,
        prompt_kwargs: dict,
        config: RunnableConfig = None,
    ) -> DocumentChunkerResponse:
        template = ChatPromptTemplate(
            [
                ("system", _document_chunker_agent_system_prompt),
                ("user", "{full_document}"),
            ]
        )
        messages = template.invoke(prompt_kwargs)
        return await self.llm.ainvoke(messages, config=config)
