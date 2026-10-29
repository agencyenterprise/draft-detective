"""The annotation sets users can work on: the Writing Style Review preset's checks
and the content checks whose passages call for judgment.

Each set lives in its own module under ``sets/``; adding one means writing the
module and listing it here, then running the sync.
"""

from lib.services.annotations.set_spec import AnnotationSetSpec
from lib.services.annotations.sets.active_voice import ACTIVE_VOICE
from lib.services.annotations.sets.advocacy_tone_v2 import ADVOCACY_TONE
from lib.services.annotations.sets.audience_fit import AUDIENCE_FIT
from lib.services.annotations.sets.concision_precision import CONCISION_PRECISION
from lib.services.annotations.sets.headers_skimmability import HEADERS_SKIMMABILITY
from lib.services.annotations.sets.inference_validation_v2 import INFERENCE_VALIDATION
from lib.services.annotations.sets.methodological_alignment import (
    METHODOLOGICAL_ALIGNMENT,
)
from lib.services.annotations.sets.narrative_synthesis import NARRATIVE_SYNTHESIS
from lib.services.annotations.sets.recommendation_check import RECOMMENDATION_CHECK
from lib.services.annotations.sets.sentence_structure import SENTENCE_STRUCTURE
from lib.services.annotations.sets.writing_consistency import WRITING_CONSISTENCY

ANNOTATION_SETS: list[AnnotationSetSpec] = [
    ACTIVE_VOICE,
    ADVOCACY_TONE,
    AUDIENCE_FIT,
    CONCISION_PRECISION,
    HEADERS_SKIMMABILITY,
    NARRATIVE_SYNTHESIS,
    SENTENCE_STRUCTURE,
    WRITING_CONSISTENCY,
    INFERENCE_VALIDATION,
    METHODOLOGICAL_ALIGNMENT,
    RECOMMENDATION_CHECK,
]
