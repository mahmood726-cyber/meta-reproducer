#!/usr/bin/env python
"""Run MetaReproducer audit on all Pairwise70 reviews."""
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline.rda_parser import load_all_rdas
from pipeline.effect_inference import infer_outcome_types
from pipeline.orchestrator import reproduce_outcome, select_primary_outcome

RDA_DIR = Path(r"C:\Users\user\OneDrive - NHS\Documents\Pairwise70\data")
RESULTS_DIR = Path(__file__).parent.parent / "data" / "results"


def main():
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    print("Loading all RDA files...")
    reviews = load_all_rdas(RDA_DIR)
    print(f"Loaded {len(reviews)} reviews")

    all_reports = []
    for i, review in enumerate(reviews):
        for outcome in review["outcomes"]:
            infer_outcome_types(outcome)

        if not review["outcomes"]:
            continue

        primary = select_primary_outcome(review["outcomes"])

        try:
            report = reproduce_outcome(review["review_id"], primary)
            all_reports.append(report)
        except Exception as e:
            print(f"  ERROR: {review['review_id']}: {e}")
            continue

        if (i + 1) % 10 == 0:
            print(f"  [{i+1}/{len(reviews)}] Last: {review['review_id']}", flush=True)

    summary_path = RESULTS_DIR / "summary.json"
    with open(summary_path, "w") as f:
        json.dump(all_reports, f, indent=2, default=str)
    print(f"\nSaved {len(all_reports)} reports to {summary_path}")

    # Headline stats
    study_total = sum(r["study_level"]["total_k"] for r in all_reports)
    study_matched = sum(r["study_level"]["matched_moderate"] for r in all_reports)
    review_classified = [r for r in all_reports if r["review_level"] is not None]
    reproduced = sum(1 for r in review_classified if r["review_level"]["classification"] == "reproduced")
    major = sum(1 for r in review_classified if r["review_level"]["classification"] == "major_discrepancy")

    print(f"\n=== HEADLINE RESULTS ===")
    print(f"Reviews processed: {len(all_reports)}")
    print(f"Study-level: {study_matched}/{study_total} matched within 10%")
    print(f"Review-level classified: {len(review_classified)}")
    print(f"  Reproduced: {reproduced}")
    print(f"  Major discrepancy: {major}")


if __name__ == "__main__":
    main()
