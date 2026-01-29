"""
Constants for advocacy and tone detection.

Contains word lists, patterns, and thresholds used for procedural detection.
"""

# Trigger words - legal/regulatory terms that may need review
TRIGGER_WORDS = {
    # Legal terms
    "law", "statute", "regulation", "ordinance", "amendment", "act", "bill",
    "decree", "directive", "resolution", "legislation", "treaty", "accord", "charter",
    # Institutions
    "congress", "parliament", "senate", "judicial", "court", "tribunal",
    "agency", "regulator", "commission",
    # Compliance
    "compliance", "policy", "framework", "guideline", "code of conduct", "oversight",
    # Enforcement
    "sanction", "penalty", "fine", "liability", "prosecution", "indictment",
    "subpoena", "enforcement", "litigation",
    # Sensitive concepts
    "constitutional", "jurisdiction", "precedent", "due process",
    "fundamental rights", "civil rights", "human rights",
    "intellectual property", "copyright", "patent", "trademark",
}

# Advocacy patterns - normative/prescriptive language
ADVOCACY_PATTERNS = [
    # Obligations
    r"\bwe should\b", r"\bwe must\b", r"\bmust ensure\b", r"\bhave to\b", r"\bneed to\b",
    r"\bit is essential that\b", r"\bit is imperative that\b", r"\bit is necessary to\b",
    r"\bwe cannot allow\b", r"\bcannot ignore\b", r"\bthere is no choice but\b",
    r"\bit is our duty to\b",
    # Calls to action
    r"\bought to\b", r"\bpolicy should\b", r"\brecommend that\b", r"\bcall for\b",
    r"\burge .* to\b", r"\bencourage .* to\b", r"\bpropose that\b",
    r"\badvocate for\b", r"\bpress for\b", r"\blobby for\b",
    # Evaluative framing
    r"\bcritical to\b", r"\bvital to\b", r"\bof utmost importance\b",
    r"\bunacceptable that\b", r"\bwe demand\b",
    r"\bshould be adopted\b", r"\bshould be implemented\b", r"\bshould take action\b",
]

# Sections to skip (by heading content)
IGNORED_SECTION_KEYWORDS = [
    "author", "biograph", "abbrevi", "acronym", "glossary",
    "reference", "bibliograph", "works cited", "citation",
    "endnote", "acknowledg", "table of contents", "contents",
    "figures and tables", "list of figures", "list of tables", "appendix",
]

# TextBlob subjectivity threshold (0.0 = objective, 1.0 = subjective)
SUBJECTIVITY_THRESHOLD = 0.75

# Context window for LLM verification (chunks before/after)
CONTEXT_K = 2

