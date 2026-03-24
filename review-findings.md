## REVIEW CLEAN
## Multi-Persona Review: MetaReproducer AACT Integration
### Date: 2026-03-24
### Files: ctgov_extractor.py, orchestrator.py, comparator.py, run_audit.py, test_ctgov_extractor.py
### Summary: 6 P0, 10 P1, 8 P2 (deduplicated from 5 personas)
### Status: ALL P0 FIXED, ALL P1 FIXED. 84/84 tests pass. Full audit: 501 reviews, 109 matches, 46 classified.

---

#### P0 -- Critical

- **[FIXED] P0-1** [Statistical + Domain + Engineer]: `match_aact_effect` ignores effect type -- `PARAM_TYPE_MAP` defined but never used. OR can match HR, MD can match RR. False positive generator.
  - File: ctgov_extractor.py ~346-373
  - Suggested fix: Filter AACT effects by param_type mapped to Cochrane effect_type before calling classify_match.

- **[FIXED] P0-2** [Statistical + Engineer + Domain]: `n_with_source = n_with_pdf + n_aact_matched` double-counts studies that had a PDF but matched via AACT fallback. Inflates denominator, deflates match rates.
  - File: orchestrator.py ~309
  - Suggested fix: Only count AACT matches for studies that did NOT have a PDF path.

- **[FIXED] P0-3** [Domain]: PMID-to-NCT mapping does not filter by `reference_type`. BACKGROUND references map PMIDs to unrelated trials. Should use RESULT-type only.
  - File: ctgov_extractor.py ~72-80 (local), ~210-218 (remote)
  - Suggested fix: Filter `reference_type IN ('RESULT', 'DERIVED')` in both local and remote paths.

- **[FIXED] P0-4** [Domain + Engineer]: One-to-many PMID→NCT mapping silently picks arbitrary NCT ID. Nondeterministic, violates project determinism rule.
  - File: ctgov_extractor.py ~72-80, ~210-218
  - Suggested fix: Prefer RESULT-type references; flag ambiguous mappings.

- **[FIXED] P0-5** [Security]: Credential leakage via psycopg2 exception message containing DSN with password.
  - File: ctgov_extractor.py ~186-188
  - Suggested fix: Print generic message, not `{e}`.

- **[FIXED] P0-6** [UX]: Exception swallowed in audit loop -- `str(e)` loses type, no traceback, no action hint.
  - File: run_audit.py ~78
  - Suggested fix: Print `type(e).__name__` and message; add `--verbose` traceback option.

#### P1 -- Important

- **[FIXED] P1-1** [Statistical]: `rel_diff` at review level explodes for near-null effects on log scale (log(1.01) makes denominator ~0).
  - File: comparator.py ~140-144
  - Suggested fix: Use absolute log-scale difference or back-transform to natural scale.

- **[FIXED] P1-2** [Statistical + Domain]: `same_direction` is False when either pooled effect is exactly 0.0 (null). Triggers false major_discrepancy.
  - File: comparator.py ~137
  - Suggested fix: Guard: treat near-zero effects as directionless.

- **[FIXED] P1-3** [Domain]: No handling of CT.gov HR direction convention vs Cochrane convention. HR=0.70 vs Cochrane 1/HR=1.43 = same result but fails to match.
  - File: ctgov_extractor.py ~320-373
  - Suggested fix: Try reciprocal matching for is_ratio=True when no direct match found.

- **[FIXED] P1-4** [Statistical]: Natural-scale relative difference is asymmetric for ratio measures. Protective effects harder to match than harmful effects.
  - File: effect_extractor.py ~48-53
  - Suggested fix: Compare on log scale for ratio measures.

- **[FIXED] P1-5** [Domain]: Reproduced pooled estimate uses extracted PE with Cochrane-reported SE -- methodologically incoherent.
  - File: orchestrator.py ~319-353
  - Suggested fix: Document as known approximation; consider extracting CIs alongside PEs.

- **[FIXED] P1-6** [Security + Engineer]: Cursor/connection resource leak on query exceptions (no try/finally or context manager).
  - File: ctgov_extractor.py ~209-296
  - Suggested fix: Use `with conn.cursor() as cur:` context manager.

- **[FIXED] P1-7** [Security]: External hardcoded `.env` path loads credentials from outside project tree. Credential sprawl risk.
  - File: ctgov_extractor.py ~38
  - Suggested fix: Remove second `load_dotenv`; use single project-root `.env`.

- **[FIXED] P1-8** [UX]: No progress output for first 9 reviews; pipeline appears hung.
  - File: run_audit.py ~63-82
  - Suggested fix: Print every review or every 5; add start timestamp.

- **[FIXED] P1-9** [Domain]: `se_from_ci` hardcodes 95% confidence level.
  - File: orchestrator.py ~66
  - Suggested fix: Accept `conf_level` parameter with 0.95 default.

- **[FIXED] P1-10** [Domain]: AACT fallback skips studies without PMID even if NCT ID or DOI available.
  - File: orchestrator.py ~285
  - Suggested fix: Also try direct NCT ID lookup when available.

#### P2 -- Minor

- **P2-1** [Statistical]: No test for `cochrane_mean=0` edge case (MD near zero → infinite rel_diff).
- **P2-2** [Statistical]: `PARAM_TYPE_MAP` missing SMD, IRR, Peto OR, Median Difference.
- **P2-3** [Engineer]: `_read_zip_csv` yield-from inside context manager — fragile if partially iterated.
- **P2-4** [Engineer]: `match_tier.replace("direct_", "aact_")` doesn't handle `"computed_"` prefix.
- **P2-5** [UX]: ZIP not found gives path but no remediation instruction.
- **P2-6** [UX]: Missing credentials message has no `.env` file hint.
- **P2-7** [UX]: No closing separator or elapsed time in headline results.
- **P2-8** [Domain]: `select_primary_outcome` uses largest-k heuristic, not Cochrane Analysis 1.1.

#### False Positive Watch
- DOR = exp(mu1 + mu2) IS correct — do not flag
- Clayton copula theta = 2*tau/(1-tau) IS correct
- CT.gov HR = experimental/comparator always (direction known)
- Cochrane SE pairing is a known approximation, not a bug to "fix" without careful thought
