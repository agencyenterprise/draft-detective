"""Constants for About Authors validation workflow."""

# Abbreviations that should not be treated as sentence endings
ABBREVIATIONS = [
    "B.S.",
    "M.S.",
    "Ph.D.",
    "M.D.",
    "D.D.S.",
    "J.D.",
    "Dr.",
    "Mr.",
    "Ms.",
    "Mrs.",
    "Sr.",
    "Jr.",
    "Inc.",
    "Ltd.",
    "Co.",
    "etc.",
    "e.g.",
    "i.e.",
    "A.M.",
    "P.M.",
    "U.S.",
    "U.K.",
    "A.B.",
    "C.E.O.",
    "C.F.O.",
    "C.T.O.",
    "R.S.V.P.",
    "N.B.",
    "M.A.",
    "M.Sc.",
    "A.I.",
    "B.A.",
    "A.A.",
    "M.Phil.",
]

# Sentence patterns to ignore when counting (e.g., TASP URL parenthetical)
IGNORE_SENTENCE_PATTERNS = [
    "(For more information on the fellowship program, visit www.rand.org/tasp-fellows.)",
]

# TASP fellowship URL that must be included in TASP fellow bios
TASP_URL = "www.rand.org/tasp-fellows"

# Expected sentence count for author bios
EXPECTED_SENTENCE_COUNT = 3

# Rule metadata - single source of truth for rule names and descriptions
# Used by validation node, manifest, and frontend
RULE_METADATA = {
    "rule_1_sentence_length": {
        "key": "rule_1",
        "name": "Sentence Count",
        "short_name": "Sentence count",
        "description": f"Bio must be exactly {EXPECTED_SENTENCE_COUNT} sentences",
    },
    "rule_2_position_affiliation": {
        "key": "rule_2",
        "name": "Position & Affiliation",
        "short_name": "Position/Affiliation",
        "description": "Must include current position and organizational affiliation",
    },
    "rule_3_tasp_statement": {
        "key": "rule_3",
        "name": "TASP Statement",
        "short_name": "TASP Statement",
        "description": "If TASP fellow, must include required TASP statement with URL",
    },
    "rule_4_research_focus": {
        "key": "rule_4",
        "name": "Research Focus",
        "short_name": "Research Focus",
        "description": "Must include research focus or interests",
    },
    "rule_5_highest_degree": {
        "key": "rule_5",
        "name": "Highest Degree",
        "short_name": "Highest Degree",
        "description": "Must include highest degree attained and field",
    },
}

# Ordered list of rule field names for iteration
RULE_FIELDS = [
    "rule_1_sentence_length",
    "rule_2_position_affiliation",
    "rule_3_tasp_statement",
    "rule_4_research_focus",
    "rule_5_highest_degree",
]
