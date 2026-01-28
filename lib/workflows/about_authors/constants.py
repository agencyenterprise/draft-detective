"""Constants for About Authors validation workflow."""

# Abbreviations that should not be treated as sentence endings
ABBREVIATIONS = [
    "B.S.", "M.S.", "Ph.D.", "M.D.", "D.D.S.", "J.D.", "Dr.",
    "Mr.", "Ms.", "Mrs.", "Sr.", "Jr.", "Inc.", "Ltd.", "Co.",
    "etc.", "e.g.", "i.e.", "A.M.", "P.M.", "U.S.", "U.K.",
    "A.B.", "C.E.O.", "C.F.O.", "C.T.O.", "R.S.V.P.",
    "N.B.", "M.A.", "M.Sc.", "A.I.", "B.A.", "A.A.", "M.Phil.",
]

# Sentence patterns to ignore when counting (e.g., TASP URL parenthetical)
IGNORE_SENTENCE_PATTERNS = [
    "(For more information on the fellowship program, visit www.rand.org/tasp-fellows.)",
]

# TASP fellowship URL that must be included in TASP fellow bios
TASP_URL = "www.rand.org/tasp-fellows"

# Expected sentence count for author bios
EXPECTED_SENTENCE_COUNT = 3

