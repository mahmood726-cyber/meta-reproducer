import pytest
import math
from pathlib import Path


def test_parse_rda_returns_review(sample_rda_data):
    """parse_rows returns a CochraneReview with correct structure."""
    from pipeline.rda_parser import parse_rows
    review = parse_rows("CD000123", sample_rda_data)
    assert review["review_id"] == "CD000123"
    assert len(review["outcomes"]) == 2
    assert review["total_k"] == 3


def test_parse_groups_by_outcome(sample_rda_data):
    """Studies are grouped by Analysis.name."""
    from pipeline.rda_parser import parse_rows
    review = parse_rows("CD000123", sample_rda_data)
    outcome_labels = [o["outcome_label"] for o in review["outcomes"]]
    assert "All-cause mortality" in outcome_labels
    assert "Hospital readmission" in outcome_labels


def test_study_data_types(sample_rda_data):
    """Binary studies have raw counts; continuous have means/SDs."""
    from pipeline.rda_parser import parse_rows
    review = parse_rows("CD000123", sample_rda_data)
    mortality = [o for o in review["outcomes"] if o["outcome_label"] == "All-cause mortality"][0]
    assert mortality["data_type"] == "binary"
    assert mortality["studies"][0]["events_int"] == 15
    readmission = [o for o in review["outcomes"] if o["outcome_label"] == "Hospital readmission"][0]
    assert readmission["data_type"] == "continuous"
    assert readmission["studies"][0]["mean_int"] == 12.3


def test_se_from_ci(sample_rda_data):
    """Raw Mean, CI.start, CI.end are stored."""
    from pipeline.rda_parser import parse_rows
    review = parse_rows("CD000123", sample_rda_data)
    mortality = [o for o in review["outcomes"] if o["outcome_label"] == "All-cause mortality"][0]
    s = mortality["studies"][0]
    assert s["mean"] == 0.75
    assert s["ci_start"] == 0.55
    assert s["ci_end"] == 1.02


def test_load_single_rda():
    """Load a real RDA file from Pairwise70."""
    from pipeline.rda_parser import load_rda
    rda_dir = Path(r"os.path.join(os.path.dirname(__file__), '..') - NHS\Documents\Pairwise70\data")
    rda_files = list(rda_dir.glob("*.rda"))
    if not rda_files:
        pytest.skip("Pairwise70 RDA files not available")
    review = load_rda(rda_files[0])
    assert review["review_id"] is not None
    assert len(review["outcomes"]) >= 1
    assert review["total_k"] >= 1


def test_post_2000_filter():
    """Studies before 2000 are excluded."""
    from pipeline.rda_parser import parse_rows
    old_data = [
        {"Study": "Old 1995", "Study.year": 1995, "Analysis.name": "Mortality",
         "Mean": 0.8, "CI.start": 0.5, "CI.end": 1.2,
         "Experimental.cases": 10, "Experimental.N": 50,
         "Control.cases": 15, "Control.N": 50,
         "Experimental.mean": None, "Experimental.SD": None,
         "Control.mean": None, "Control.SD": None},
        {"Study": "New 2005", "Study.year": 2005, "Analysis.name": "Mortality",
         "Mean": 0.7, "CI.start": 0.4, "CI.end": 1.1,
         "Experimental.cases": 8, "Experimental.N": 50,
         "Control.cases": 14, "Control.N": 50,
         "Experimental.mean": None, "Experimental.SD": None,
         "Control.mean": None, "Control.SD": None},
    ]
    review = parse_rows("CD000999", old_data)
    assert review["total_k"] == 1
