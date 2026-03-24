## REVIEW CLEAN
## Multi-Persona Review Round 2: MetaReproducer Full Pipeline
### Date: 2026-03-24
### Files: ctgov_extractor.py (759→~770 lines), orchestrator.py, comparator.py, effect_extractor.py, run_audit.py, link_mega_data.py
### Summary: 3 P0, 7 P1, 6 P2 found → ALL P0 FIXED, ALL P1 FIXED, 3 P2 FIXED, 3 P2 deferred
### Status: 98/98 tests pass. Full audit: 174 moderate + 280 weak matches, 63 classified.

---

#### P0 -- Critical (ALL FIXED)

- **[FIXED] P0-1** [Statistical]: `continue` in binary sanity checks skipped sibling continuous branch.
- **[FIXED] P0-2** [Domain]: `dispersion_value_num` assumed to be SD, but AACT has SE/IQR/range. Now checks `dispersion_type`.
- **[FIXED] P0-3** [Domain]: OG000=experimental/OG001=control was unreliable. Now uses any two groups, reciprocal matching resolves direction.

#### P1 -- Important (ALL FIXED)

- **[FIXED] P1-1** [Statistical]: Double-zero studies (a=0, c=0) now excluded from binary computation.
- **[FIXED] P1-2** [Statistical]: SE floor (1e-10) prevents degenerate CIs for small samples.
- **[FIXED] P1-3** [Domain]: DOI trailing `]`, `"`, `'`, `>`, `:` now stripped.
- **[FIXED] P1-4** [Statistical]: Weak-only (20%) PDF matches now eligible for AACT improvement.
- **[FIXED] P1-7** [Domain]: Case-insensitive PARAM_TYPE_MAP lookup via `.title()` fallback.
- **[FIXED] P1-5** [Engineer]: Dead code `already_mapped_ncts` removed.
- **[FIXED] P1-6** [Statistical]: MD CI documented as z-based approximation (t-dist for future).

#### P2 -- Minor

- **[FIXED] P2-2**: Dead code removed (already_mapped_ncts).
- **[FIXED] P2-5**: Both-SDs-zero skipped in continuous computation.
- **[FIXED] P2-6**: ReDoS confirmed NOT a risk (explicit check).
- **P2-1** [Deferred]: OR/RR cross-matching — handled by PARAM_TYPE_MAP filtering.
- **P2-3** [Deferred]: DOI regex greediness — mitigated by expanded rstrip.
- **P2-4** [Deferred]: Mock-ZIP tests for DOI/PMID loaders — low priority.

#### Previous Review (Round 1): ALL 6 P0 + 10 P1 FIXED
