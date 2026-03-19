#!/usr/bin/env python
"""Generate BMJ manuscript tables from audit results."""
import sys
import json
import csv
from pathlib import Path
from collections import Counter

sys.path.insert(0, str(Path(__file__).parent.parent))

RESULTS_DIR = Path(__file__).parent.parent / "data" / "results"


def main():
    summary_path = RESULTS_DIR / "summary.json"
    if not summary_path.exists():
        print("Run run_audit.py first to generate results.")
        sys.exit(1)

    with open(summary_path) as f:
        reports = json.load(f)

    print(f"\n=== Table 1: Study-level by effect type ===")
    by_type = {}
    for r in reports:
        et = r.get("inferred_effect_type", "unknown")
        if et not in by_type:
            by_type[et] = {"total": 0, "strict": 0, "moderate": 0}
        by_type[et]["total"] += r["study_level"]["n_with_pdf"]
        by_type[et]["strict"] += r["study_level"]["matched_strict"]
        by_type[et]["moderate"] += r["study_level"]["matched_moderate"]

    for et, counts in sorted(by_type.items()):
        n = counts["total"]
        s = counts["strict"]
        m = counts["moderate"]
        print(f"  {et}: {s}/{n} strict ({100*s/max(n,1):.1f}%), "
              f"{m}/{n} moderate ({100*m/max(n,1):.1f}%)")

    print(f"\n=== Table 2: Review-level classification ===")
    classified = [r for r in reports if r["review_level"] is not None]
    tiers = Counter(r["review_level"]["classification"] for r in classified)
    insufficient = sum(1 for r in reports if r["review_level"] is None)
    print(f"  Reproduced: {tiers.get('reproduced', 0)}")
    print(f"  Minor discrepancy: {tiers.get('minor_discrepancy', 0)}")
    print(f"  Major discrepancy: {tiers.get('major_discrepancy', 0)}")
    print(f"  Insufficient coverage: {insufficient}")

    print(f"\n=== Table 3: Error taxonomy ===")
    error_totals = Counter()
    for r in reports:
        for k, v in r["errors"].items():
            if k not in ("primary_error_source",) and isinstance(v, int):
                error_totals[k] += v
    for cat, count in error_totals.most_common():
        print(f"  {cat}: {count}")

    csv_path = RESULTS_DIR / "summary_table.csv"
    with open(csv_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["review_id", "outcome", "effect_type", "total_k",
                          "n_with_pdf", "matched_strict", "matched_moderate",
                          "review_tier", "ref_pooled", "repro_pooled", "pct_diff"])
        for r in reports:
            rl = r.get("review_level") or {}
            ref_p = r.get("reference_pooled") or {}
            rep_p = r.get("reproduced_pooled") or {}
            writer.writerow([
                r["review_id"], r["outcome_label"], r.get("inferred_effect_type"),
                r["study_level"]["total_k"], r["study_level"]["n_with_pdf"],
                r["study_level"]["matched_strict"], r["study_level"]["matched_moderate"],
                rl.get("classification", "insufficient"),
                ref_p.get("pooled"), rep_p.get("pooled"),
                rl.get("rel_diff"),
            ])
    print(f"\nCSV saved: {csv_path}")


if __name__ == "__main__":
    main()
