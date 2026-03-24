#!/usr/bin/env python
"""Run MetaReproducer audit on all Pairwise70 reviews."""
import sys
import json
import time
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline.rda_parser import load_all_rdas
from pipeline.effect_inference import infer_outcome_types
from pipeline.orchestrator import reproduce_outcome, select_primary_outcome

# Also import the linking module
sys.path.insert(0, str(Path(__file__).parent))
from link_mega_data import build_study_pdf_map, build_study_pmid_map, link_reviews

RDA_DIR = Path(r"C:\Users\user\OneDrive - NHS\Documents\Pairwise70\data")
RESULTS_DIR = Path(__file__).parent.parent / "data" / "results"


def main():
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    print("Loading all RDA files...")
    reviews = load_all_rdas(RDA_DIR)
    print(f"Loaded {len(reviews)} reviews")

    # Link studies to existing PDFs and PMIDs from mega gold standard
    print("Linking studies to PDFs and PMIDs...")
    pdf_map = build_study_pdf_map()
    pmid_map = build_study_pmid_map()
    link_reviews(reviews, pdf_map, pmid_map)

    # Initialize AACT CT.gov lookup (second extraction pathway)
    # Prefer local ZIP (fast, no network) → fall back to remote PostgreSQL
    from pipeline.ctgov_extractor import (
        build_aact_lookup_local, get_connection, build_aact_lookup,
    )
    # Collect all PMIDs from linked studies
    all_pmids = []
    for review in reviews:
        for outcome in review["outcomes"]:
            for study in outcome["studies"]:
                pmid = study.get("pmid")
                if pmid:
                    all_pmids.append(str(pmid))
    all_pmids = list(set(all_pmids))
    print(f"Looking up {len(all_pmids)} PMIDs in AACT...")

    # Try local ZIP first
    aact_lookup = build_aact_lookup_local(pmids=all_pmids)
    if not aact_lookup:
        # Fall back to remote
        conn = get_connection()
        if conn:
            aact_lookup = build_aact_lookup(conn, all_pmids)
            conn.close()
    if aact_lookup:
        print(f"AACT lookup: {len(aact_lookup)} studies with CT.gov data")
    else:
        print("AACT unavailable — using PDF pathway only")

    all_reports = []
    t_start = time.time()
    n_errors = 0
    for i, review in enumerate(reviews):
        for outcome in review["outcomes"]:
            infer_outcome_types(outcome)

        if not review["outcomes"]:
            continue

        primary = select_primary_outcome(review["outcomes"])

        try:
            report = reproduce_outcome(review["review_id"], primary,
                                       aact_lookup=aact_lookup)
            all_reports.append(report)
        except Exception as e:
            # P0-6: Include exception type for actionable diagnosis
            print(f"  ERROR: {review['review_id']}: {type(e).__name__}: {e}")
            if "--verbose" in sys.argv:
                traceback.print_exc()
            n_errors += 1
            continue

        # P1-8: Progress every 5 reviews instead of 10
        if (i + 1) % 5 == 0:
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

    elapsed = time.time() - t_start
    n_unclassified = len(all_reports) - len(review_classified)

    print(f"\n=== HEADLINE RESULTS ({elapsed:.0f}s) ===")
    print(f"Reviews processed: {len(all_reports)} ({n_errors} errors)")
    print(f"Study-level: {study_matched}/{study_total} matched within 10% (moderate tier)")
    print(f"Review-level classified: {len(review_classified)} ({n_unclassified} unclassifiable)")
    print(f"  Reproduced: {reproduced}")
    print(f"  Major discrepancy: {major}")
    print(f"{'=' * 40}")


if __name__ == "__main__":
    main()
