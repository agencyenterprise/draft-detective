"""Constants for About This (Preface) validation workflow."""

# TASP Boilerplate - required exact text for source_tasp check
TASP_BOILERPLATE = (
    "RAND Global and Emerging Risks is a division of RAND that delivers rigorous and "
    "objective public policy research on the most consequential challenges to civilization "
    "and global security. This work was undertaken by the division's Technology and Security "
    "Policy Center, which explores how high-consequence, dual-use technologies change the "
    "global competition and threat environment, then develops policy and technology options "
    "to advance the security of the United States, its allies and partners, and the world. "
    "For more information, contact tasp@rand.org."
)

# Funding statement variants - any one of these is acceptable
FUNDING_STATEMENT_VARIANTS = [
    # Variant 1: Independent research with full donor list
    (
        "This [research/tool/effort] was independently initiated and conducted within the "
        "Technology and Security Policy Center using income from operations and gifts from "
        "philanthropic supporters, which have been made or recommended by DALHAP Investments Ltd., "
        "Effektiv Spenden, Ergo Impact, Founders Pledge, Charlottes och Fredriks Stiftelse, "
        "Good Ventures, Jaan Tallinn, Longview, Open Philanthropy, and Waking Up Foundation. "
        "A complete list of donors and funders is available at www.rand.org/TASP. "
        "RAND donors and grantors have no influence over research findings or recommendations."
    ),
    # Variant 2: External sponsorship
    "This [research/tool/effort] was sponsored by [identify the sponsoring or donor organization].",
    # Variant 3: General donor funding
    "Funding for this work was provided by gifts from RAND supporters.",
    # Variant 4: Mixed funding (independent start, external completion)
    (
        "This [research/tool/effort] was, at its inception, independently initiated and conducted "
        "within the Technology and Security Policy Center using income from operations and gifts "
        "from philanthropic supporters... This [research/tool/effort] was completed through funding "
        "provided by [identify the sponsoring or donor organization]..."
    ),
    # Variant 5: Publication funding
    (
        "...This [research/tool/effort] was published through funding provided by DALHAP "
        "Investments Ltd., as recommended by Ergo Impact and Fathom..."
    ),
    # Variant 6: Specific donors for completion
    (
        "...This effort was completed through funding provided by Chris Anderson and "
        "Jacqueline Novogratz, High Tide Foundation, Jaan Tallinn, Open Philanthropy, "
        "Sea Grape Foundation, and Valhalla Foundation..."
    ),
    # Variant 7: Direct sponsorship list
    (
        "This [research/tool/effort] was sponsored by Chris Anderson and Jacqueline Novogratz, "
        "High Tide Foundation, Jaan Tallinn, Open Philanthropy, Sea Grape Foundation, "
        "and Valhalla Foundation. RAND donors and grantors have no influence over research "
        "findings or recommendations."
    ),
]

# Requirement metadata - single source of truth
REQUIREMENT_METADATA = {
    "context": {
        "key": "context",
        "name": "Establishes Context",
        "short_name": "Context",
        "description": "Does the section establish the context that prompted the study?",
        "level": "sentence",
    },
    "objectives": {
        "key": "objectives",
        "name": "Explains Objectives",
        "short_name": "Objectives",
        "description": "Does the section explain the publication's objectives?",
        "level": "sentence",
    },
    "relationship": {
        "key": "relationship",
        "name": "Explains Relationship",
        "short_name": "Relationship",
        "description": "Does the section explain the relationship to other RAND work?",
        "level": "sentence",
    },
    "audience": {
        "key": "audience",
        "name": "Identifies Audience",
        "short_name": "Audience",
        "description": "Does the section identify the intended audience?",
        "level": "sentence",
    },
    "source_tasp": {
        "key": "source_tasp",
        "name": "TASP Boilerplate",
        "short_name": "TASP Source",
        "description": "Does a paragraph contain the TASP boilerplate text?",
        "level": "paragraph",
    },
    "source_funding": {
        "key": "source_funding",
        "name": "Funding Statement",
        "short_name": "Funding Source",
        "description": "Does a paragraph contain an approved funding statement?",
        "level": "paragraph",
    },
}

# Ordered list of requirement field names for iteration
REQUIREMENT_FIELDS = [
    "context",
    "objectives",
    "relationship",
    "audience",
    "source_tasp",
    "source_funding",
]

# Section headers to search for
PREFACE_SECTION_HEADERS = [
    "About This Report",
    "About This",
    "Preface",
    "Introduction",
    "Executive Summary",
    "About This Publication",
    "About This Document",
]

