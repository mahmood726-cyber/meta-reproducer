import pytest
import math

@pytest.fixture
def binary_studies():
    """5 binary studies with known OR values for testing DL pooling."""
    return [
        {"yi": math.log(0.75), "sei": 0.20, "label": "Study A"},
        {"yi": math.log(0.80), "sei": 0.25, "label": "Study B"},
        {"yi": math.log(0.90), "sei": 0.30, "label": "Study C"},
        {"yi": math.log(0.70), "sei": 0.15, "label": "Study D"},
        {"yi": math.log(0.85), "sei": 0.22, "label": "Study E"},
    ]

@pytest.fixture
def homogeneous_studies():
    """3 identical studies (tau2 should be 0)."""
    return [
        {"yi": math.log(0.80), "sei": 0.20, "label": "Study 1"},
        {"yi": math.log(0.80), "sei": 0.20, "label": "Study 2"},
        {"yi": math.log(0.80), "sei": 0.20, "label": "Study 3"},
    ]

@pytest.fixture
def sample_rda_data():
    """Simulated RDA dataframe rows (as list of dicts)."""
    return [
        {
            "Study": "Smith 2005", "Study.year": 2005,
            "Analysis.name": "All-cause mortality",
            "Mean": 0.75, "CI.start": 0.55, "CI.end": 1.02,
            "Experimental.cases": 15, "Experimental.N": 100,
            "Control.cases": 20, "Control.N": 100,
            "Experimental.mean": None, "Experimental.SD": None,
            "Control.mean": None, "Control.SD": None,
        },
        {
            "Study": "Jones 2008", "Study.year": 2008,
            "Analysis.name": "All-cause mortality",
            "Mean": 0.60, "CI.start": 0.38, "CI.end": 0.95,
            "Experimental.cases": 10, "Experimental.N": 80,
            "Control.cases": 18, "Control.N": 85,
            "Experimental.mean": None, "Experimental.SD": None,
            "Control.mean": None, "Control.SD": None,
        },
        {
            "Study": "Lee 2010", "Study.year": 2010,
            "Analysis.name": "Hospital readmission",
            "Mean": -2.5, "CI.start": -5.1, "CI.end": 0.1,
            "Experimental.cases": None, "Experimental.N": 50,
            "Control.cases": None, "Control.N": 50,
            "Experimental.mean": 12.3, "Experimental.SD": 4.1,
            "Control.mean": 14.8, "Control.SD": 3.9,
        },
    ]

@pytest.fixture
def sample_extractions():
    """Simulated extraction results for comparator testing."""
    return [
        {"study_id": "Smith 2005", "extracted_effect": 0.73, "matched": True,
         "match_tier": "direct_5pct", "cochrane_giv_mean": 0.75},
        {"study_id": "Jones 2008", "extracted_effect": 0.62, "matched": True,
         "match_tier": "direct_5pct", "cochrane_giv_mean": 0.60},
        {"study_id": "Brown 2012", "extracted_effect": None, "matched": False,
         "match_tier": None, "cochrane_giv_mean": 0.88},
    ]
