[DATE]

The Editor
The BMJ

Dear Editor,

We submit the manuscript **"Computational Reproducibility of Cochrane Meta-Analyses: An Automated Audit of 501 Systematic Reviews"** for consideration as a Research Article in *The BMJ*.

**Why this matters:** Meta-analyses from the Cochrane Collaboration are considered the gold standard of clinical evidence. Yet no large-scale study has tested whether these analyses can be computationally reproduced from their source trial data. We present the first automated reproducibility audit at this scale.

**What we did:** We developed MetaReproducer, a deterministic 8-module Python pipeline that re-extracts effect sizes from open-access trial PDFs and re-pools them using DerSimonian-Laird and REML, validated against the R metafor package. We applied it to 501 Cochrane systematic reviews encompassing 14,340 individual studies.

**Key findings:**
- Only 11.8% of studies had openly accessible full-text PDFs — the dominant barrier
- Among 287 reviews with at least one accessible study, the per-review strict match rate was 5.1%
- Only 6 reviews (1.2%) yielded sufficient data for classification: 1 reproduced, 3 showed minor discrepancies, 2 showed major discrepancies including a direction reversal
- The primary barrier is access, not methodology: 88.2% of studies were simply inaccessible

**Policy implication:** No methodological improvement can fix a reproducibility problem caused by locked-away evidence. Mandating structured data deposition for trials included in systematic reviews — analogous to ClinicalTrials.gov for trial registration — would transform reproducibility from an aspiration to a routine, automated audit.

The pipeline (98/98 tests pass), complete results, and an interactive dashboard are publicly available. The manuscript has not been submitted elsewhere.

Yours sincerely,

Mahmood Ahmad
Royal Free Hospital, London, UK
mahmood.ahmad2@nhs.net
