"""Generate diffable Markdown variants by removing selected inline definitions.

One-time migration (keeps DOCX originals and legacy reference keys):
    python -m evals_inspectai.e2e.abbreviation_checker.generate_test_variants --migrate-docx

Generate variants directly from baseline Markdown, without DOCX conversion:
    python -m evals_inspectai.e2e.abbreviation_checker.generate_test_variants --source baseline.md --output-dir variants

Migration preserves exact converter text/line numbering and existing annotations.
Generation edits only referenced definitions. Neither operation stages/publishes files.
"""

import argparse
import asyncio
import json
import random
import re
from pathlib import Path

_DATA_DIR = Path(__file__).resolve().parent / "data"
_SEED = 42
_MULTI_COUNT = 20


def _load_targets(entries: list[dict]) -> list[dict]:
    targets: dict[str, dict] = {}
    for entry in entries:
        if not entry.get("ignored") and entry.get("inline_definition"):
            targets.setdefault(entry["abbr"], entry)
    return list(targets.values())


def _remove_definition(text: str, entry: dict) -> str:
    """Edit exactly one referenced definition, never all matching document text."""
    lines = text.splitlines(keepends=True)
    start, end = entry["line_start"] - 1, entry["line_end"]
    if not 0 <= start < end <= len(lines):
        raise ValueError(f"Invalid reference line range for {entry['abbr']}")
    if start + 1 != end:
        raise ValueError("Definition removal currently requires a single source line")
    pattern = re.compile(
        re.escape(entry["inline_definition"])
        + r"[ \t]+\(("
        + re.escape(entry["abbr"])
        + r"s?)\)",
        re.IGNORECASE,
    )
    matches = list(pattern.finditer(lines[start]))
    if len(matches) != 1:
        raise ValueError(
            f"Expected exactly one definition for {entry['abbr']} on line {start + 1}, "
            f"found {len(matches)}; source/reference need review"
        )
    lines[start] = pattern.sub(lambda match: match.group(1), lines[start], count=1)
    return "".join(lines)


def _build_references(original: dict, removed: list[dict]) -> dict:
    keys = {(e["abbr"], e["occurrence_number"], e["line_start"]) for e in removed}
    patched = []
    for source in original["abbreviations"]:
        entry = dict(source)
        if (entry["abbr"], entry["occurrence_number"], entry["line_start"]) in keys:
            entry["inline_definition"] = ""
        patched.append(entry)
    return {**original, "abbreviations": patched}


def generate(source: Path, references: Path, output_dir: Path) -> int:
    """Plan and validate every edit before writing any output files."""
    text = source.read_text(encoding="utf-8")
    original = json.loads(references.read_text(encoding="utf-8"))[source.name]
    targets = _load_targets(original["abbreviations"])
    if not targets:
        raise ValueError("No inline definitions available to remove")
    planned: dict[Path, str] = {}
    reference_sets: dict[Path, dict] = {}

    def add_variant(group: str, name: str, removed: list[dict]) -> None:
        if Path(name).name != name or "\\" in name:
            raise ValueError(f"Abbreviation produces unsafe variant filename: {name!r}")
        variant = text
        for target in removed:
            variant = _remove_definition(variant, target)
        directory = output_dir / group
        planned[directory / name] = variant
        reference_sets.setdefault(directory, {})[name] = _build_references(
            original, removed
        )

    for target in targets:
        add_variant("single", f"{target['abbr']}_no_def.md", [target])
    rng = random.Random(_SEED)
    for index in range(1, _MULTI_COUNT + 1):
        removed = rng.sample(targets, rng.randint(1, len(targets)))
        label = "_".join(sorted(e["abbr"] for e in removed))
        add_variant("multi", f"variant_{index:02d}_{label}.md", removed)

    # Parse all existing reference maps before any document is overwritten.
    for directory, entries in reference_sets.items():
        path = directory / "references.json"
        existing = json.loads(path.read_text()) if path.exists() else {}
        planned[path] = json.dumps({**existing, **entries}, indent=2) + "\n"
    for path, content in planned.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    return sum(path.suffix == ".md" for path in planned)


async def migrate_docx(data_dir: Path) -> int:
    """Snapshot existing DOCX variants; no LLM, annotation changes or deletion.

    Validate all conversions/collisions before writing. Existing Markdown must
    equal its conversion: rerunning cannot overwrite manual Markdown edits.
    """
    from lib.services.converters.base import convert_to_markdown

    planned: dict[Path, str] = {}
    reference_sets: dict[Path, dict] = {}
    for directory in (
        data_dir,
        data_dir / "variants" / "single",
        data_dir / "variants" / "multi",
    ):
        files = sorted(
            p for p in directory.glob("*.docx") if not p.name.startswith("~$")
        )
        if not files:
            continue
        reference_path = directory / "references.json"
        refs = json.loads(reference_path.read_text(encoding="utf-8"))
        for document in files:
            if document.name not in refs:
                raise ValueError(f"Missing reference for {document.name}")
            target = document.with_suffix(".md")
            text = await convert_to_markdown(str(document), converter="markitdown")
            if target.exists() and target.read_text(encoding="utf-8") != text:
                raise ValueError(f"Refusing to overwrite edited Markdown: {target}")
            if target.name in refs and refs[target.name] != refs[document.name]:
                raise ValueError(f"Conflicting reference for {target.name}")
            planned[target] = text
            refs[target.name] = refs[document.name]
        reference_sets[reference_path] = refs
    if not planned:
        raise ValueError(f"No DOCX sources found under {data_dir}")
    for path, text in planned.items():
        path.write_text(text, encoding="utf-8")
    for path, refs in reference_sets.items():
        path.write_text(json.dumps(refs, indent=2) + "\n", encoding="utf-8")
    return len(planned)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=_DATA_DIR)
    parser.add_argument(
        "--source", type=Path, help="Baseline Markdown; required unless migrating DOCX"
    )
    parser.add_argument(
        "--references", type=Path, help="Defaults to references.json beside source"
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="Required for generation; existing matching variants are replaced",
    )
    parser.add_argument("--migrate-docx", action="store_true")
    args = parser.parse_args()
    if args.migrate_docx:
        count = asyncio.run(migrate_docx(args.data_dir))
        print(
            f"Converted {count} documents to Markdown; originals and legacy reference keys retained."
        )
    else:
        if args.source is None or args.output_dir is None:
            parser.error("generation requires --source and --output-dir")
        count = generate(
            args.source,
            args.references or args.source.parent / "references.json",
            args.output_dir,
        )
        print(f"Generated {count} Markdown variants and updated their references.")


if __name__ == "__main__":
    main()
