# MetaReproducer — Design Specification (v2)

> Revised after spec review. Addresses P0-1 through P0-4, P1-1 through P1-8, and suggestions S1-S4.

## 1. Problem Statement

The reproducibility crisis in meta-analyses is well-documented but has never been computationally audited at scale. Manual reproducibility checks cover 20-50 reviews. No automated system exists to re-derive a published meta-analysis from its source trials and compare results.

## 2. Goal

Build a Python pipeline + HTML dashboard that:
1. Takes 465 Cochrane reviews (Pairwise70 RDA dataset, post-2000 studies)
2. Re-extracts effect sizes from source trial PDFs using RCT Extractor v10.3
3. Re-runs pooled meta-analysis (DL + REML) and compares against a reference pooled estimate computed from Cochrane's own per-study data
4. Reports reproducibility at two levels: study-level (individual effect agreement) and review-level (pooled estimate agreement)
5. Classifies review-level reproducibility (Reproduced / Minor / Major discrepancy)
6. Produces an error taxonomy
7. Visualizes results in an interactive dashboard
8. Supports a BMJ manuscript reporting the findings

## 3. Scope

**In scope:**
- Cochrane reviews only (structured RDA data)
- Pairwise70 dataset (465 reviews with post-2000 studies, cross-domain medicine)
- Re-extraction via existing RCT Extractor v10.3
- DL + REML pooled meta-analysis in Python
- Two-level reproducibility assessment (study-level + review-level)
- Three-tier review-level classification
- Error taxonomy
- Single-file HTML dashboard
- BMJ manuscript

**Out of scope (future work):**
- Non-Cochrane systematic reviews
- NLP parsing of review PDFs to identify included studies
- Real-time CT.gov monitoring / living observatory
- Non-English reviews
- Pre-2000 studies (Pairwise70 filter; see Section 14, P0-4)

## 4. Architecture

```
C:\Users\user\Downloads\MetaReproducer\
├── pipeline/
│   ├── orchestrator.py          # Main: RDA -> ReproducibilityReport
│   ├── rda_parser.py            # Extract per-study GIV data from RDA
│   ├── effect_inference.py      # Infer effect type from raw data vs GIV
│   ├── effect_extractor.py      # Wrapper around RCT Extractor v10.3
│   ├── meta_engine.py           # DL + REML pooled analysis (Python)
│   ├── comparator.py            # Two-level reproducibility classification
│   ├── taxonomy.py              # Error taxonomy classification
│   └── truthcert.py             # SHA-256 provenance chain per review
├── scripts/
│   ├── run_audit.py             # Batch: all 465 reviews -> results JSON
│   ├── run_single.py            # Debug: one review at a time
│   └── generate_tables.py       # BMJ manuscript tables from results
├── data/
│   ├── rda/                     # Symlink to Pairwise70 RDA files
│   ├── pdfs/                    # Symlink to existing downloaded PDFs
│   ├── doi_map/                 # mega_doi_lookup output (DOI/PMCID mapping)
│   └── results/                 # Output: per-review JSON + summary CSV
├── dashboard/
│   └── index.html               # Single-file interactive dashboard
├── paper/
│   └── metareproducer_bmj.md    # Manuscript
├── tests/
│   ├── test_rda_parser.py
│   ├── test_effect_inference.py
│   ├── test_meta_engine.py
│   ├── test_comparator.py
│   ├── test_taxonomy.py
│   ├── test_truthcert.py
│   ├── test_orchestrator.py
│   └── test_dashboard.py        # Selenium tests for dashboard
└── CLAUDE.md
```

## 5. Pipeline Modules

### 5.1 rda_parser.py

**Input:** Path to Cochrane RDA file.

**Key insight (P0-1 fix):** RDA files contain **per-study data only** — no pooled estimates, no model type, no effect type label. The data has 86,492 rows across 501 RDAs. 90.5% of rows have GIV (Generic Inverse Variance) fields: `GIV.Mean` (log-scale effect) and `GIV.SE`. Most also have raw count data (binary: events/totals; continuous: Mean/SD/N).

**Output:** `CochraneReview` dataclass:
```python
@dataclass
class CochraneStudy:
    study_id: str               # e.g., "Smith 2020"
    giv_mean: float             # GIV.Mean — log-scale effect (Cochrane-computed)
    giv_se: float               # GIV.SE — standard error on log scale
    weight: float | None        # Cochrane-assigned weight (if present)
    # Raw count data (binary outcomes)
    events_int: int | None
    total_int: int | None
    events_ctrl: int | None
    total_ctrl: int | None
    # Raw continuous data
    mean_int: float | None
    sd_int: float | None
    n_int: int | None
    mean_ctrl: float | None
    sd_ctrl: float | None
    n_ctrl: int | None
    # Linking metadata
    doi: str | None             # From mega_doi_lookup output
    pmcid: str | None
    pdf_path: str | None
    # Subgroup/outcome context
    subgroup: str | None
    outcome_label: str | None

@dataclass
class CochraneOutcome:
    outcome_label: str
    studies: list[CochraneStudy]
    inferred_effect_type: str   # OR, RR, HR, MD, SMD (inferred by effect_inference.py)
    data_type: str              # "binary", "continuous", "giv_only"
    k: int

@dataclass
class CochraneReview:
    review_id: str
    title: str
    therapeutic_area: str       # Inferred from Cochrane group or keywords
    outcomes: list[CochraneOutcome]
    total_k: int                # Total studies across all outcomes
```

**Key change from v1:** No `pooled_effect`, `model`, `tau2`, or `i2` fields — these are computed by `meta_engine.py`, not read from data. Multiple outcomes per review are explicitly modeled (P1-3 fix).

### 5.2 effect_inference.py (NEW — P0-1 fix)

**Purpose:** Infer the effect measure type for each outcome since RDA files don't label it.

**Algorithm:**
1. If outcome has binary raw data (events/totals for both arms):
   - Compute log(OR), log(RR) from raw counts
   - Compare each against `GIV.Mean` — the one matching within tolerance (1e-4) identifies the type
   - ~85% of binary entries match RR, ~9% match OR
2. If outcome has continuous raw data (Mean/SD/N):
   - Compute MD = Mean_int - Mean_ctrl
   - Compute SMD (Hedges' g)
   - Compare against `GIV.Mean`
   - ~55% match MD, ~19% match SMD
3. If GIV-only (438 entries, ~0.5%):
   - Classify as `giv_only` — likely HR from time-to-event (P1-2 fix)
   - Use GIV.Mean and GIV.SE directly; effect type marked "unknown_ratio" (log-scale data suggests ratio)
4. Ambiguous cases (~6% binary, ~26% continuous):
   - Flag as `ambiguous`, default to most common type for the data category (RR for binary, MD for continuous)
   - Record ambiguity in error taxonomy

**Output:** `inferred_effect_type` field on `CochraneOutcome`.

### 5.3 effect_extractor.py

**Input:** `CochraneStudy` with `pdf_path`.

**Output:** `ExtractedEffect` dataclass:
```python
@dataclass
class ExtractedEffect:
    study_id: str
    extracted_effect: float | None
    extracted_ci_lower: float | None
    extracted_ci_upper: float | None
    extracted_se: float | None      # Back-calculated from CI
    extracted_effect_type: str | None
    match_tier: str | None          # STRICT tiers only (see below)
    extraction_method: str          # text, table, computation
    cochrane_giv_mean: float        # Reference value (log-scale)
    pct_difference: float | None
    matched: bool
    on_log_scale: bool              # Whether extracted value is on log scale
```

**Strict matching tiers (P0-3 fix):** For the reproducibility audit, only precise matches count:
- `direct_5pct` — extracted effect within 5% of Cochrane GIV.Mean (after log transform for ratio measures)
- `direct_10pct` — within 10%
- `computed_5pct` — effect computed from raw data (2x2 or Mean/SD/N) within 5% of GIV.Mean
- `computed_10pct` — computed within 10%

Excluded from reproducibility (used only in extractor validation, not here):
- reciprocal, signflip, scale transforms, >10% tolerances

**Implementation:** Thin wrapper calling existing RCT Extractor. Does NOT use LLM extraction (non-deterministic). Deterministic text + table + computation extraction only.

### 5.4 meta_engine.py

**Input:** List of study-level data (either Cochrane GIV values or extracted values) with SE.

**Output:** `PooledResult` dataclass:
```python
@dataclass
class PooledResult:
    method: str             # "DL" or "REML"
    pooled_effect: float    # On log scale for ratio measures
    pooled_ci_lower: float
    pooled_ci_upper: float
    pooled_se: float
    tau2: float
    tau2_ci: tuple[float, float] | None  # Q-profile CI
    i2: float
    q_stat: float
    q_pvalue: float
    k: int
    prediction_interval: tuple[float, float] | None
    converged: bool         # For REML (P1-7 fix)
```

**Implementation:** ~200 lines of Python.

**DerSimonian-Laird:**
- Standard inverse-variance weights: `w_i = 1 / (v_i + tau2_DL)`
- `tau2_DL = max(0, (Q - (k-1)) / C)` where `C = sum(w) - sum(w^2)/sum(w)`
- Guard: if C = 0 (all weights equal), tau2 = 0

**REML (P1-7 fix):**
- Fisher scoring iteration
- Convergence criteria: `|delta_tau2| < 1e-8` AND `iterations < 100`
- Starting value: DL tau2 estimate
- If non-convergence after 100 iterations: set `converged = False`, fall back to DL estimate
- If tau2 goes negative during iteration: clamp to 0

**SE derivation (P1-1 fix):**
- For extracted effects with CI: `se = (ln(ci_upper) - ln(ci_lower)) / (2 * z_alpha)` for ratio measures, where `z_alpha` is computed from confidence level (default 95%, `z = scipy.stats.norm.ppf(0.975)`)
- For small k (< 30): option to use t-distribution critical value instead of z
- For Cochrane GIV data: SE is directly available as `GIV.SE`
- NO hardcoded z=1.96

**Key design: Two pooled estimates per outcome (S3 suggestion):**
1. **Reference pooled** — pool Cochrane's GIV.Mean/GIV.SE values using our DL engine → this is what Cochrane would get (validates our engine)
2. **Reproduced pooled** — pool extracted effects using our DL engine → this is the reproducibility test

The comparison is Reference vs Reproduced, both from the same engine. This isolates extraction differences from engine differences.

### 5.5 comparator.py

**Input:** Reference pooled + Reproduced pooled + per-study extraction results.

**Output:** Two-level classification (P0-2 fix):

```python
@dataclass
class StudyLevelResult:
    total_studies: int          # Total studies across all outcomes with PDFs
    matched_strict: int         # Matched at direct_5pct or computed_5pct
    matched_moderate: int       # Matched at direct_10pct or computed_10pct
    match_rate_strict: float    # matched_strict / total_studies
    match_rate_moderate: float  # matched_moderate / total_studies
    no_pdf: int                 # Studies with no OA PDF available
    extraction_failed: int      # PDF available but extraction failed
    extracted_no_match: int     # Extracted but didn't match Cochrane

@dataclass
class ReviewLevelResult:
    tier: str                   # "reproduced", "minor", "major", "insufficient"
    reference_pooled: float     # From Cochrane GIV data
    reproduced_pooled: float    # From extracted effects
    pct_difference: float
    same_direction: bool
    same_significance: bool
    reference_k: int
    reproduced_k: int
    k_coverage: float
    details: str

@dataclass
class ReproducibilityReport:
    review_id: str
    outcome_label: str
    study_level: StudyLevelResult
    review_level: ReviewLevelResult | None  # None if insufficient k_coverage
    errors: ErrorTaxonomy
    cert: dict                  # TruthCert bundle
```

**Review-level classification rules (revised thresholds — P0-2 fix):**
- **Reproduced**: pooled effect within 10% AND same direction AND same significance AND k_coverage >= 0.50
- **Minor discrepancy**: same direction AND same significance, but effect >10% OR k_coverage 0.30-0.49
- **Major discrepancy**: different significance conclusion OR different direction (with k_coverage >= 0.30)
- **Insufficient**: k_coverage < 0.30 (too few studies extracted for meaningful pooled comparison)

Thresholds relaxed from v1 (was 5%/75%) based on actual data: only ~80 reviews achieve k_coverage >= 50%, and strict 5% study-level match is ~30-40%. The 10% pooled threshold accounts for cascading extraction uncertainty across multiple studies.

**Selection bias acknowledgment (P1-4, P1-5):** The reproduced pooled estimate uses a non-random subset of the original studies. This is explicitly documented as a limitation. Sensitivity analysis: compare k_coverage distribution against reproducibility classification to check for systematic bias (e.g., do reviews with higher k_coverage reproduce better simply because more studies were available?).

### 5.6 taxonomy.py

**Input:** Per-study extraction results + overall classification.

**Output:** `ErrorTaxonomy`:
```python
@dataclass
class ErrorTaxonomy:
    review_id: str
    outcome_label: str
    classification: str
    primary_error_source: str
    error_counts: dict[str, int]
    error_details: list[dict]
```

**Error categories:**
1. **missing_pdf** — No OA PDF available (PMCID missing or download failed)
2. **extraction_failure** — PDF available but text/table extraction produced nothing
3. **no_match** — Effect extracted but outside 10% of Cochrane GIV.Mean
4. **scale_mismatch** — Extracted effect type doesn't match inferred Cochrane type
5. **direction_flip** — Extracted effect has opposite sign on log scale
6. **computation_gap** — Cochrane computed from raw counts; PDF reports adjusted effect
7. **significance_shift** — Study-level effects match but pooled result crosses p=0.05
8. **ambiguous_type** — Effect type inference was ambiguous (from effect_inference.py)

### 5.7 truthcert.py

Unchanged from v1 — SHA-256 provenance chain per review. Hashes RDA input, PDF inputs, extraction outputs, pooling parameters, final classification.

### 5.8 orchestrator.py

```python
def reproduce_review(rda_path: str, pdf_dir: str, doi_map: dict) -> list[ReproducibilityReport]:
    # 1. Parse Cochrane RDA (per-study GIV data)
    review = rda_parser.parse(rda_path, doi_map)

    # 2. Infer effect types per outcome
    effect_inference.infer_types(review)

    reports = []
    for outcome in review.outcomes:
        # 3. Compute REFERENCE pooled from Cochrane GIV values
        ref_pooled = meta_engine.pool_from_giv(outcome.studies, method="DL")

        # 4. Extract effects from source PDFs
        extractions = []
        for study in outcome.studies:
            if study.pdf_path:
                ext = effect_extractor.extract(study, outcome.inferred_effect_type)
                extractions.append(ext)

        # 5. Study-level assessment
        study_result = comparator.assess_study_level(outcome.studies, extractions)

        # 6. Pool extracted effects (if enough matched)
        matched = [e for e in extractions if e.matched]
        review_result = None
        if len(matched) >= 2:
            repro_pooled = meta_engine.pool_from_extracted(matched, method="DL",
                                                           effect_type=outcome.inferred_effect_type)
            # 7. Review-level comparison
            review_result = comparator.assess_review_level(ref_pooled, repro_pooled, outcome.k)

        # 8. Error taxonomy
        errors = taxonomy.classify_errors(outcome, extractions, review_result)

        # 9. TruthCert
        cert = truthcert.certify(review, outcome, extractions, ref_pooled,
                                  repro_pooled if review_result else None)

        reports.append(ReproducibilityReport(
            review_id=review.review_id, outcome_label=outcome.outcome_label,
            study_level=study_result, review_level=review_result,
            errors=errors, cert=cert
        ))

    return reports
```

**Key change from v1:** Returns a list of reports (one per outcome per review), not a single report. The primary outcome selection (P1-3) is handled at the analysis/manuscript level, not in the pipeline — we compute all outcomes and let the analysis scripts select which to report.

**Subgroup handling (P1-8):** The RDA parser groups studies by outcome label and subgroup. Overall analyses (no subgroup label or subgroup="Total") are processed by default. Subgroup-specific analyses are stored but not included in the primary audit — available for sensitivity analysis.

## 6. Dashboard Design

Single-file HTML app (`dashboard/index.html`). Loads `data/results/summary.json` via file input. No server, no build step. Plotly.js for charts. CSS vars for dark/light theme.

### 6.1 Overview Panel
- **Two-level headline:**
  - Study-level: "X/Y individual effects reproduced within 10% (Z%)"
  - Review-level: "A/B meta-analyses classified: C Reproduced, D Minor, E Major"
- Donut chart: Reproduced / Minor / Major / Insufficient (color-coded)
- Therapeutic area breakdown (horizontal bar chart, sorted by study-level match rate)
- OA coverage summary: "F% of studies had OA PDFs available"

### 6.2 Review Explorer
- Searchable, sortable, filterable table
- Columns: Review title, Area, k, OA Coverage, Ref Pooled, Repro Pooled, % Diff, Classification (badge), Primary Error
- Filters: classification tier, therapeutic area, inferred effect type, review size (k), OA coverage range
- Click row -> drill-down

### 6.3 Drill-Down Panel (lazy-rendered — S1)
- Side-by-side forest plots (Reference vs Reproduced) — rendered on demand, not precomputed for all 465 reviews
- Per-study extraction table: Cochrane GIV.Mean vs Extracted effect, match tier, extraction method
- TruthCert provenance chain
- Error taxonomy breakdown for this review

### 6.4 Error Taxonomy View
- Stacked bar chart: error categories across all reviews
- Treemap: hierarchical error breakdown
- Filterable by therapeutic area, effect type, review size
- **Significance shift highlighted** as distinct finding (S2)

### 6.5 Fragility Landscape
- Scatter plot: X = k (study count), Y = % pooled effect difference
- Colored by classification tier, sized by k_coverage
- Hover shows review title + key stats
- Marginal density strips on X and Y axes

### 6.6 OA Coverage Analysis (NEW)
- Histogram: k_coverage distribution across reviews
- Scatter: k_coverage vs reproducibility classification
- Highlights the OA gap as both a finding and a limitation

### 6.7 Interactions
- Dark/light theme toggle (CSS vars + data-theme attribute)
- CSV export of results table
- PDF print stylesheet (A4, hides UI chrome)
- Keyboard accessible (tab navigation, Enter/Space activation)
- File input for loading results JSON (no hardcoded path)

## 7. Data Flow

```
Pairwise70 RDA files (465)
        |
        v
   rda_parser.py -----> CochraneReview (per-study GIV data, multiple outcomes)
        |
        v
   effect_inference.py -> Inferred effect types per outcome
        |
        +--> meta_engine.py (REFERENCE) --> PooledResult from Cochrane GIV
        |
        v
   effect_extractor.py --> ExtractedEffect per study (RCT Extractor, strict tiers)
        |
        v
   meta_engine.py (REPRODUCED) --> PooledResult from extracted effects
        |
        v
   comparator.py -------> Two-level classification (study + review)
        |
        v
   taxonomy.py ---------> ErrorTaxonomy (8 categories)
        |
        v
   truthcert.py --------> TruthCert bundle (SHA-256 provenance)
        |
        v
   results/summary.json --> dashboard/index.html
                        --> paper/tables + figures
```

## 8. Reproducibility Classification

### Study-level (primary outcome for BMJ headline)

| Tier | Definition |
|------|-----------|
| Strict match | Extracted effect within 5% of Cochrane GIV.Mean (on appropriate scale) |
| Moderate match | Within 10% |
| Weak match | Within 20% (reported for context, not primary) |
| No match | >20% or extraction failed |

### Review-level (pooled estimate comparison)

| Tier | Criteria |
|------|----------|
| Reproduced | Pooled effect within 10%, same direction, same significance, k_coverage >= 50% |
| Minor discrepancy | Same direction + significance, effect >10% OR k_coverage 30-49% |
| Major discrepancy | Different significance OR different direction (k_coverage >= 30%) |
| Insufficient | k_coverage < 30% |

**Expected distribution (honest estimates based on actual data):**
- ~80 reviews (17%) will have k_coverage >= 50% for full review-level assessment
- ~120 reviews (26%) will have k_coverage >= 30% for any review-level assessment
- ~345 reviews (74%) will be "insufficient" for pooled comparison
- Study-level: ~30-40% strict match, ~50-60% moderate match across ~1,290 study-PDF pairs

The large "insufficient" group is itself a finding: it quantifies the OA coverage barrier to computational reproducibility.

## 9. Testing Strategy

### Unit tests (pytest)
- `test_rda_parser.py`: Parse 3-5 known RDA files, verify study counts + GIV values + outcome grouping
- `test_effect_inference.py`: Verify OR/RR/MD/SMD inference against manually confirmed cases
- `test_meta_engine.py`: DL + REML on known datasets (compare against R metafor within 1e-6)
  - Include: REML convergence test, REML non-convergence fallback, tau2=0 case, k=2 edge case
- `test_comparator.py`: Classification logic with edge cases (borderline 10%, direction flip, k_coverage boundaries)
- `test_taxonomy.py`: Error categorization with synthetic data
- `test_truthcert.py`: Hash chain integrity, deterministic output

### Integration tests
- `test_orchestrator.py`: End-to-end on 3 known reviews with manually verified expected results
- **Cochrane-recomputed baseline (S3)**: Verify our DL engine reproduces Cochrane's pooled result when given Cochrane's own GIV data. If our engine disagrees with Cochrane, the comparison is invalid. Target: 10+ reviews, tolerance 1e-4.
- Golden output comparison: save expected JSON, compare on re-run

### Dashboard tests (Selenium)
- Load summary.json, verify overview numbers render
- Filter by classification, verify table updates
- Click drill-down, verify forest plot renders
- Dark mode toggle, CSV export, print layout

### R validation
- Compare DL/REML pooled results against `metafor::rma()` for 10+ reviews using GIV data
- Tolerance: 1e-6 for pooled effect, 1e-4 for tau2/I2
- REML convergence: verify both tools converge (or both fail) on same inputs

## 10. BMJ Manuscript Outline

**Title:** "Computational Reproducibility of Cochrane Meta-Analyses: An Automated Audit of 465 Systematic Reviews"

**Abstract** (~250 words): Objective, Design (computational reproducibility study), Setting (Cochrane Library), Data (465 reviews from Pairwise70, ~1,290 study-PDF pairs), Main outcome (study-level and review-level reproducibility rates), Results (headline numbers), Conclusion.

**Introduction** (~500 words): Reproducibility crisis in EBM, meta-analyses as foundation of clinical guidelines, no prior computational audit at this scale, the OA coverage barrier.

**Methods** (~1000 words):
- Data source: Pairwise70 (465 Cochrane reviews, post-2000, cross-domain)
- Effect type inference from GIV + raw data
- Extraction pipeline: RCT Extractor v10.3 (text + table + computation, deterministic only)
- Reference analysis: DL random-effects on Cochrane GIV data
- Reproduced analysis: DL random-effects on extracted effects
- Study-level classification: strict (5%) and moderate (10%) match
- Review-level classification: three-tier (reproduced/minor/major) with k_coverage thresholds
- Error taxonomy: 8 categories
- Software: MetaReproducer (open source, TruthCert provenance)

**Results** (~1500 words):
- Study-level reproducibility: X/1,290 matched within 5% (Y%), Z% within 10%
- OA coverage: A% of studies had PDFs, B% of reviews achieved k_coverage >= 50%
- Review-level: C Reproduced, D Minor, E Major (among assessable reviews)
- Error taxonomy distribution (Figure 2)
- Factors associated with non-reproducibility (logistic regression: k, effect type, year, area, k_coverage)
- Selection bias analysis: k_coverage vs classification
- Case studies: 3 reviews examined in detail (1 reproduced, 1 minor, 1 major)

**Discussion** (~1000 words):
- Comparison to prior manual reproducibility studies
- The OA barrier: most reviews cannot be computationally reproduced due to PDF access
- Why studies fail to match (adjusted vs unadjusted, outcome selection, data presentation)
- Implications for Cochrane: structured data deposition, FAIR principles
- Limitations: OA bias (newer/larger trials more likely OA), post-2000 filter, single pipeline, adjusted vs unadjusted effects, selection bias in pooled comparison
- Implications for practice: confidence calibration

**Figures:**
1. Study flow: PRISMA-style (465 reviews -> outcomes -> studies -> PDFs -> extractions -> classifications)
2. Error taxonomy: stacked bars by category
3. Fragility landscape: scatter (k vs % difference, colored by tier)
4. Case study: side-by-side forest plots

**Tables:**
1. Study-level reproducibility by effect measure type
2. Review-level reproducibility by therapeutic area (for assessable reviews)
3. Error taxonomy counts
4. Logistic regression: predictors of non-reproducibility
5. Sensitivity analysis: reproducibility at different k_coverage thresholds

**Supplementary (online):**
- Interactive dashboard URL
- Full per-review results (CSV)
- TruthCert bundles
- R validation scripts

## 11. Dependencies

- Python 3.11+ (not 3.13 due to WMI deadlock risk on Windows)
- RCT Extractor v10.3 (imported as library from `C:\Users\user\rct-extractor-v2\`)
- numpy, scipy (DL/REML computation, statistical tests)
- pytest (testing)
- Selenium + Chrome (dashboard tests)
- R + metafor (validation only, not in main pipeline)

## 12. Key Risks (updated)

| Risk | Mitigation |
|------|-----------|
| Only ~17% of reviews have k_coverage >= 50% for pooled comparison | Two-level design: study-level is primary (large N), review-level is secondary (smaller but still meaningful). The OA gap IS a finding. |
| Strict 5% match rate is ~30-40%, not 94.6% | Honest reporting. The 94.6% includes relaxed tiers used for extractor validation. The reproducibility audit uses only strict tiers. |
| Effect type must be inferred (~6% binary, ~26% continuous ambiguous) | effect_inference.py with back-computation + validation. Ambiguous cases flagged in taxonomy. |
| Adjusted vs unadjusted effects differ systematically | Documented as limitation + taxonomy category "computation_gap". Cochrane uses raw counts; papers report adjusted values. |
| OA PDF availability may be biased (newer/larger trials) | Report OA coverage distribution. Sensitivity analysis comparing assessable vs insufficient reviews. |
| Reproduced pooled uses subset of studies (selection bias) | Explicit limitation. Sensitivity analysis: k_coverage vs classification. |
| REML may not converge | Convergence flag. Fall back to DL. Report convergence rate. |
| BMJ word limits (~4000 words) | Tight prose; supplementary appendix for methods detail; dashboard as interactive supplement. |
| Multiple outcomes per review inflate review count | Primary analysis uses first/primary outcome per review. Sensitivity: all outcomes. |

## 13. Success Criteria (revised)

1. Pipeline processes all 465 reviews without manual intervention (graceful failure handling: log + skip on error — S4)
2. Engine validation: our DL engine matches R metafor within 1e-6 on Cochrane GIV data (10+ reviews)
3. Study-level: report match rates at 5%, 10%, 20% thresholds across ~1,290 PDFs
4. Review-level: classify all reviews with k_coverage >= 30% (~120 reviews)
5. All tests pass (unit + integration + R validation + dashboard)
6. TruthCert chain verifiable for every processed review
7. Dashboard renders correctly with full dataset
8. Manuscript draft complete with real numbers

## 14. Addressed Review Findings

### P0 fixes
- **P0-1**: No Cochrane pooled in RDA → compute Reference pooled from GIV.Mean/GIV.SE; compare Reference vs Reproduced using same engine
- **P0-2**: Only ~18% at k_coverage >= 50% → two-level design (study-level primary), relaxed thresholds, OA gap as explicit finding
- **P0-3**: 94.6% includes relaxed tiers → strict matching only (direct_5pct, direct_10pct, computed_5pct, computed_10pct); honest reporting
- **P0-4**: Post-2000 filter → documented; study is "465 reviews" not "501"; removing filter would reduce OA coverage further

### P1 fixes
- **P1-1**: Hardcoded z=1.96 → `scipy.stats.norm.ppf(0.975)`, t-distribution option for small k
- **P1-2**: GIV-only entries → handled as `giv_only` data type, effect type "unknown_ratio"
- **P1-3**: Multiple outcomes → `CochraneOutcome` model, pipeline processes all outcomes, analysis selects primary
- **P1-4**: Selection bias → documented limitation, sensitivity analysis
- **P1-5**: Subset vs full comparison → Reference pooled uses all GIV studies; Reproduced uses matched subset; difference documented
- **P1-6**: Weight circularity → both Reference and Reproduced use our engine's weights (same algorithm); comparison is fair
- **P1-7**: REML convergence → max iterations, convergence flag, DL fallback
- **P1-8**: Subgroups → parsed and stored, excluded from primary analysis, available for sensitivity

### Suggestions adopted
- **S1**: Lazy-rendered drill-down panels (not precomputed)
- **S2**: Significance shift highlighted as distinct finding
- **S3**: Cochrane-recomputed baseline as integration test (validates engine before comparing extractions)
- **S4**: Graceful failure tolerance in success criteria
