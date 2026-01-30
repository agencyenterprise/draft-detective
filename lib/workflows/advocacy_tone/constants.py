"""
Constants for advocacy and tone detection.

Values loaded from workflow_config.yaml.
"""

from lib.config.workflow_config import get_workflow_config

_config = get_workflow_config("advocacy_tone")

# Trigger words - legal/regulatory terms that may need review
TRIGGER_WORDS = set(_config.get("trigger_words", []))

# Advocacy patterns - normative/prescriptive language (regex)
ADVOCACY_PATTERNS = _config.get("advocacy_patterns", [])

# Sections to skip (by heading content)
IGNORED_SECTION_KEYWORDS = _config.get("ignored_section_keywords", [])

# TextBlob subjectivity threshold (0.0 = objective, 1.0 = subjective)
SUBJECTIVITY_THRESHOLD = _config.get("subjectivity_threshold", 0.75)

# Context window for LLM verification (chunks before/after)
CONTEXT_K = _config.get("context_k", 2)
