#!/usr/bin/env python
"""Link Pairwise70 RDA studies to existing mega gold standard PDFs."""
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

MEGA_DIR = Path(r"C:\Users\user\rct-extractor-v2\gold_data\mega")
PDF_DIR = MEGA_DIR / "pdfs"


def build_study_pdf_map() -> dict:
    """Build mapping: (first_author, year) -> pdf_path from mega_matched.jsonl."""
    matched_path = MEGA_DIR / "mega_matched.jsonl"
    if not matched_path.exists():
        print(f"WARNING: {matched_path} not found")
        return {}
    mapping = {}
    with open(matched_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            entry = json.loads(line)
            pmcid = entry.get("pmcid")
            if not pmcid:
                continue
            pdf_path = PDF_DIR / f"{pmcid}.pdf"
            if not pdf_path.exists():
                continue
            author = entry.get("first_author", "")
            year = entry.get("year")
            key = (author.strip(), year)
            mapping[key] = str(pdf_path)
    return mapping


def link_reviews(reviews: list[dict], pdf_map: dict) -> None:
    """Mutate reviews in-place: set pdf_path on matching studies."""
    linked = 0
    total = 0
    for review in reviews:
        for outcome in review["outcomes"]:
            for study in outcome["studies"]:
                total += 1
                author = study["study_id"].strip()
                year = study.get("year")
                key = (author, year)
                if key in pdf_map:
                    study["pdf_path"] = pdf_map[key]
                    linked += 1
    print(f"Linked {linked}/{total} studies to PDFs ({100*linked/max(total,1):.1f}%)")


if __name__ == "__main__":
    from pipeline.rda_parser import load_all_rdas
    rda_dir = Path(r"C:\Users\user\OneDrive - NHS\Documents\Pairwise70\data")
    reviews = load_all_rdas(rda_dir)
    pdf_map = build_study_pdf_map()
    link_reviews(reviews, pdf_map)
