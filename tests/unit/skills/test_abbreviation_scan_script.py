"""The abbreviation-scan skill's script, as runners outside Draft Detective use it.

The rules are covered through the workflow in
`tests/unit/workflows/abbreviation_scan_v2/test_issues.py`. These tests cover
what only the script has: its stdlib port of rapidfuzz, and its command line.
"""

import json
import random
import subprocess
import sys

import pytest
from rapidfuzz import fuzz, utils

from lib.skills import _SKILLS_DIR, load_skill_script, skill_backend_files

_SCRIPT_PATH = _SKILLS_DIR / "abbreviation-scan" / "scripts" / "build_issues.py"
_script = load_skill_script("abbreviation-scan", "build_issues.py")

_WORDS = (
    "office of the under secretary defense national institute health research "
    "development organization treaty atlantic north department"
).split()


def _random_pairs(count: int) -> list[tuple[str, str]]:
    rng = random.Random(0)
    alphabet = "abcde fgh-.,'_XYZİ"
    pairs: list[tuple[str, str]] = []
    for _ in range(count):
        if rng.random() < 0.5:
            a = "".join(rng.choice(alphabet) for _ in range(rng.randint(0, 25)))
            b = "".join(rng.choice(alphabet) for _ in range(rng.randint(0, 40)))
        else:
            a = " ".join(rng.choice(_WORDS) for _ in range(rng.randint(1, 6)))
            b = " ".join(rng.choice(_WORDS) for _ in range(rng.randint(1, 8)))
        pairs.append((a, b))
    return pairs


@pytest.mark.parametrize(
    ("a", "b"),
    [
        ("North Atlantic Treaty Organization", "north atlantic treaty organisation"),
        ("Office of the Under Secretary", "the Office of the Under Secretary of War"),
        ("Large Language Model", "Large Language Models"),
        ("research and development", "R&D"),
        ("Department of Defense", "Department of Energy"),
        # Greek sigma: lowercased per character, never as a final sigma.
        ("ΟΣ", "οσ"),
        ("ΟΣ", "ος"),
    ],
)
def test_text_matches_agrees_with_rapidfuzz_on_definitions(a: str, b: str):
    expected = (
        fuzz.partial_ratio(a, b, processor=utils.default_process)
        >= _script.MATCH_THRESHOLD
    )
    assert _script.text_matches(a, b) is expected


def test_partial_ratio_scores_equal_rapidfuzz():
    for a, b in _random_pairs(3000):
        expected = fuzz.partial_ratio(a, b, processor=utils.default_process)
        actual = _script.partial_ratio(
            _script._default_process(a), _script._default_process(b)
        )
        assert actual == pytest.approx(expected, abs=1e-9), (a, b)


def _run_cli(catalogue: dict) -> list[dict]:
    completed = subprocess.run(
        [sys.executable, "-I", str(_SCRIPT_PATH)],
        input=json.dumps(catalogue),
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(completed.stdout)


def test_cli_reports_issues_with_line_one_for_a_missing_section():
    issues = _run_cli(
        {
            "abbreviations_section_found": False,
            "occurrences": [
                {
                    "abbr": "NATO",
                    "inline_definition": "",
                    "occurrence_number": 1,
                    "line_start": 7,
                    "line_end": 7,
                    "abbreviations_section_definition": None,
                }
            ],
        }
    )

    assert [(i["title"], i["start_line"], i["end_line"]) for i in issues] == [
        ("No Abbreviations section found", 1, 1),
        ("Abbreviation not defined at first use", 7, 7),
    ]
    assert {i["severity"] for i in issues} == {"medium"}
    assert all("occurrence_index" not in i for i in issues)


def test_cli_reports_nothing_for_an_empty_catalogue():
    assert _run_cli({"abbreviations_section_found": False, "occurrences": []}) == []


def test_mounted_skill_files_leave_out_the_scripts_bytecode():
    paths = skill_backend_files()

    assert "/skills/abbreviation-scan/scripts/build_issues.py" in paths
    assert not any("__pycache__" in path for path in paths)
