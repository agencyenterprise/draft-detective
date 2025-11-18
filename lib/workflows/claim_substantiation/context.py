from dataclasses import dataclass
from typing import Optional

from lib.services.vector_store import VectorStoreService


@dataclass
class ContextSchema:
    openai_api_key: Optional[str]
    vector_store: VectorStoreService
