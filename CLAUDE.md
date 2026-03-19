# MetaReproducer

## Purpose
Automated reproducibility audit of 465 Cochrane meta-analyses.
Pipeline re-extracts effects from trial PDFs, re-pools, compares against Cochrane reference.

## Key paths
- RDA files: C:/Users/user/OneDrive - NHS/Documents/Pairwise70/data/
- RCT Extractor: C:/Users/user/rct-extractor-v2/
- Mega gold data: C:/Users/user/rct-extractor-v2/gold_data/mega/
- Gold standard pooled: C:/Users/user/Downloads/Metaprojects/TruthCert-Validation-Papers/data/gold_standard/

## Rules
- Use `python` not `python3` (Windows)
- No hardcoded z=1.96 — use scipy.stats.norm.ppf
- No LLM extraction — deterministic only
- Test-first: run tests after every change
