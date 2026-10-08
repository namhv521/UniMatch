import csv
import hashlib
import json
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).parents[1]))

from src.data_pipeline.curate.quality import QualityGateError, validate_quality
from src.data_pipeline.extract.tech import TechTaxonomy, extract_tech_mentions
from src.data_pipeline.extract.thesis import extract_thesis
from src.data_pipeline.identity.resolve import normalize_person_name
from src.data_pipeline.provenance.assignments import propagate_thesis_technology
from src.data_pipeline.schemas import Advisor


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )


def main() -> None:
    root = Path(__file__).parents[1]
    version = "v2026-09-28"
    output = root / "data/curated/versions" / version
    report_root = root / "outputs/data_quality" / version
    output.mkdir(parents=True, exist_ok=True)
    report_root.mkdir(parents=True, exist_ok=True)
    taxonomy = TechTaxonomy.model_validate(
        yaml.safe_load((root / "configs/data/tech_taxonomy.yaml").read_text(encoding="utf-8"))
    )
    advisor_rows = list(csv.DictReader((root / "data/curated/advisors.csv").open(encoding="utf-8-sig")))
    advisors = [Advisor.from_curated_row(row) for row in advisor_rows]
    advisor_by_name = {normalize_person_name(row.name_normalized): row.advisor_id for row in advisors}
    split_artifact = json.loads((root / "data/curated/split_indices.json").read_text(encoding="utf-8"))
    student_split = {
        student_id: split_name
        for split_name, student_ids in split_artifact["student_ids"].items()
        for student_id in student_ids
    }
    theses: list[dict] = []
    assignments: list[dict] = []
    supervision: dict[str, str] = {}
    failures: list[dict] = []
    for path in sorted((root / "data/extracted/llm").glob("*.json")):
        artifact = json.loads(path.read_text(encoding="utf-8"))
        if "profile" not in artifact:
            continue
        try:
            extraction = extract_thesis(artifact, crawl_run_id="legacy-baseline")
            edge = extraction.supervision
            if edge:
                advisor_id = advisor_by_name.get(edge.advisor_name_normalized)
                edge = edge.model_copy(update={"advisor_id": advisor_id}) if advisor_id else None
            thesis = extraction.thesis.model_dump(mode="json")
            theses.append(thesis)
            if edge:
                supervision[extraction.thesis.thesis_id] = edge.advisor_id
                text = " ".join(filter(None, (extraction.thesis.title, extraction.thesis.abstract)))
                for mention in extract_tech_mentions(
                    text,
                    taxonomy,
                    source_ref=f"{extraction.thesis.thesis_id}#title-abstract",
                ):
                    for assignment in propagate_thesis_technology(extraction.thesis, edge, mention):
                        row = assignment.model_dump(mode="json")
                        row["thesis_id"] = extraction.thesis.thesis_id
                        assignments.append(row)
        except Exception as exc:
            failures.append({"source": path.name, "error": type(exc).__name__, "detail": str(exc)})

    split_by_thesis = {
        thesis["thesis_id"]: student_split.get(thesis["student_id"], "future") for thesis in theses
    }
    fitted = {thesis_id for thesis_id, split_name in split_by_thesis.items() if split_name == "train"}
    try:
        quality = validate_quality(
            theses=theses,
            advisors=[row.model_dump(mode="json") for row in advisors],
            assignments=assignments,
            verified_supervision=supervision,
            split_by_thesis=split_by_thesis,
            fitted_thesis_ids=fitted,
        )
    except QualityGateError as exc:
        quality = {"ready": False, "errors": exc.errors}
    quality.update(
        {
            "dataset_version": version,
            "scope": "validated subset; excluded records remain in failure_report.json",
            "complete_dataset": not failures and not json.loads((root / "data/curated/advisor_crawl_report.json").read_text())["profiles_needing_review"],
            "excluded_records": len(failures),
        }
    )
    thesis_rows = sorted(theses, key=lambda row: row["thesis_id"])
    advisor_output = sorted((row.model_dump(mode="json") for row in advisors), key=lambda row: row["advisor_id"])
    assignment_rows = sorted(assignments, key=lambda row: row["assignment_id"])
    _write_jsonl(output / "theses.jsonl", thesis_rows)
    _write_jsonl(output / "advisors.jsonl", advisor_output)
    _write_jsonl(output / "tech_assignments.jsonl", assignment_rows)
    (report_root / "quality_report.json").write_text(json.dumps(quality, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (report_root / "failure_report.json").write_text(json.dumps(failures, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    files = {}
    for path in sorted(output.iterdir()):
        files[path.name] = {"sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "bytes": path.stat().st_size}
    manifest = {"schema_version": "1.0", "dataset_version": version, "files": files, "quality_ready": quality["ready"]}
    (report_root / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"quality_ready": quality["ready"], "theses": len(theses), "assignments": len(assignments), "failures": len(failures)}))
    if not quality["ready"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
