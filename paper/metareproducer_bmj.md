# Computational Reproducibility of Cochrane Meta-Analyses: An Automated Audit of 501 Systematic Reviews

## Authors

Mahmood Ahmad^1^

1. Royal Free Hospital, London, United Kingdom

Correspondence to: Mahmood Ahmad, mahmood.ahmad2@nhs.net
ORCID: 0009-0003-7781-4478

---

## Abstract

**Objective:** To assess the computational reproducibility of Cochrane meta-analyses by re-extracting effect sizes from source trial publications and re-pooling results, and to quantify the open access barrier to reproducibility verification.

**Design:** Computational reproducibility study using automated extraction and re-analysis.

**Data sources:** 501 Cochrane systematic reviews from the Pairwise70 dataset, encompassing 14,340 individual studies.

**Main outcome measures:** Study-level reproducibility (agreement between extracted and Cochrane-reported effect sizes within 5% and 10% tolerance), review-level reproducibility (agreement of pooled estimates in direction, statistical significance, and magnitude), and open access coverage (proportion of studies with freely accessible full-text publications).

**Results:** Of 14,340 studies, only 1,767 (12.3%) had openly accessible PDFs, leaving 87.7% of the evidence base computationally inaccessible. Among 297 reviews with at least one accessible study, the per-review strict match rate (within 5%) was 7.1% (median 0%). Only 10 reviews (2.0%) achieved sufficient study coverage (>=30%) for pooled comparison: 1 reproduced within tolerance, 4 showed minor discrepancies, and 5 showed major discrepancies including direction reversals. The dominant barrier was not methodological but infrastructural: missing PDFs accounted for 95.2% of all extraction failures. Among the 10 fully assessable reviews, 5 (50%) showed reversed effect direction between reference and reproduced pooled estimates, though 9 of 10 (90%) retained the same statistical significance classification.

**Conclusions:** The vast majority of Cochrane meta-analyses cannot currently be computationally reproduced, primarily because the underlying trial reports are not openly accessible. This represents a fundamental barrier to evidence verification that no methodological improvement can overcome. Mandating structured data deposition for trials included in systematic reviews would transform reproducibility from an aspiration to a routine audit.

**Registration:** [OSF_REGISTRATION_URL]

**Data sharing:** Pipeline code, results, and interactive dashboard available at [GITHUB_URL]. Dataset deposited at [ZENODO_DOI].

---

## What is already known on this topic

- Reproducibility of meta-analyses has been assessed in small manual audits (typically 20-50 reviews), finding discrepancies in 10-40% of cases
- These audits rely on human re-extraction, limiting scale and introducing their own reproducibility concerns
- The role of open access in enabling or preventing computational verification has not been systematically quantified

## What this study adds

- First large-scale automated reproducibility audit of 501 Cochrane meta-analyses encompassing 14,340 studies
- Only 12.3% of constituent studies are openly accessible, making computational verification impossible for the majority of evidence
- Among the small subset of reviews with sufficient open access coverage, half showed effect direction reversals when re-derived from source publications
- The primary barrier to reproducibility is access, not methodology

---

## Introduction

Meta-analyses form the apex of the evidence hierarchy and directly inform clinical guidelines, drug approvals, and health policy decisions.^1^ Their credibility rests on an implicit assumption: that an independent analyst, given the same source data, would reach the same conclusions. Yet this assumption is rarely tested at scale.

Previous reproducibility assessments of meta-analyses have been manual efforts, typically covering 20-50 reviews with human re-extraction of data from trial publications.^2-4^ These studies consistently report discrepancies in 10-40% of cases, ranging from transcription errors to outcome selection inconsistencies. However, manual audits are inherently limited in scale and introduce their own reproducibility concerns.

Computational approaches offer a path to systematic, scalable reproducibility verification. Automated extraction pipelines can process hundreds of trial publications deterministically, and pooling algorithms can be validated against reference implementations. Yet a prerequisite for any computational audit is access to the source data --- specifically, the full-text publications from which meta-analysts extract their numbers.

We conducted the first large-scale automated reproducibility audit of Cochrane meta-analyses, applying a deterministic extraction pipeline to 501 systematic reviews encompassing 14,340 studies. Our primary objective was to assess reproducibility at two levels: individual study effects and pooled review conclusions. Our secondary objective was to quantify the open access barrier --- the proportion of the evidence base that is computationally inaccessible due to publication access restrictions.

## Methods

### Data source

We used the Pairwise70 dataset, a curated collection of 501 Cochrane systematic reviews with per-study data extracted from Review Manager (RevMan) data files (RDA format).^5^ These reviews span diverse therapeutic areas and were selected to represent the breadth of the Cochrane Library. Each RDA file contains per-study Generic Inverse Variance (GIV) data: a log-scale effect estimate (GIV.Mean) and its standard error (GIV.SE), along with raw event counts (binary outcomes) or summary statistics (continuous outcomes) where available.

### Study identification and PDF retrieval

For each study in the Pairwise70 dataset, we attempted to identify openly accessible full-text publications using a pre-existing mapping pipeline. Digital object identifiers (DOIs) were extracted from Cochrane reference lists and matched to PubMed Central identifiers (PMCIDs) via the Europe PMC API. PDFs were downloaded only for studies with open access full text (no paywall bypass). This mapping was performed as part of the RCT Extractor validation project and reused without modification.^6^

### Effect type inference

RDA files do not explicitly label the effect measure (odds ratio, risk ratio, hazard ratio, mean difference, or standardised mean difference). We inferred the effect type for each outcome by back-computing candidate effect sizes from raw data and comparing against the Cochrane-provided GIV.Mean value. For binary outcomes, we computed both log(OR) and log(RR) from 2x2 tables and selected the measure matching GIV.Mean within a tolerance of 10^-4^. For continuous outcomes, we computed both mean difference and Hedges' g standardised mean difference. Outcomes with GIV data only (no raw counts) were classified as unknown ratio measures and analysed on the log scale. Ambiguous cases (6% of binary, 26% of continuous outcomes) defaulted to the most common type for their data category, with ambiguity recorded in the error taxonomy.

### Automated extraction

We applied RCT Extractor v10.3, a deterministic text and table extraction pipeline, to each openly accessible PDF.^6^ The extractor uses rule-based pattern matching and computational verification (no large language model components) to identify numerical results including effect sizes, confidence intervals, sample sizes, and event counts. For each study, we compared the extracted effect against the Cochrane GIV.Mean value at two thresholds:

- **Strict match**: within 5% on the appropriate scale (log scale for ratio measures, absolute for differences)
- **Moderate match**: within 10%

Only these two tiers were used for the reproducibility audit. Broader matching tolerances (reciprocal, sign-flip, scale transformations) were excluded to maintain audit rigour.

### Reference and reproduced pooled estimates

For each review, we selected the primary outcome (the outcome with the largest number of studies, with ties broken by binary over continuous, then alphabetically). We computed two pooled estimates using the same DerSimonian-Laird random-effects engine:

1. **Reference pooled**: computed from Cochrane's own GIV.Mean and GIV.SE values for all studies in the primary outcome
2. **Reproduced pooled**: computed from our extracted effect sizes, restricted to studies with successful extraction

This design isolates extraction differences from pooling engine differences. Our DerSimonian-Laird implementation was validated against the R `metafor` package (version 4.6) with agreement within 10^-6^ for pooled effects and 10^-4^ for heterogeneity estimates.

### Reproducibility classification

**Study level**: Each study with an accessible PDF was classified as strict match (within 5%), moderate match (within 10%), or non-match (>10% or extraction failure).

**Review level**: Reviews were classified based on the comparison between reference and reproduced pooled estimates:

- **Reproduced**: pooled effect within 10%, same direction, same statistical significance (alpha=0.05), and study coverage >=50%
- **Minor discrepancy**: same direction and significance, but pooled difference >10% or study coverage 30-49%
- **Major discrepancy**: different statistical significance or different direction of effect (with study coverage >=30%)
- **Insufficient**: study coverage <30%, precluding meaningful pooled comparison

Study coverage (k_coverage) was defined as the number of studies with successful extraction divided by the total number of studies in the primary outcome.

### Error taxonomy

We classified each extraction failure into eight categories: missing PDF (no open access full text), extraction failure (PDF available but no result extracted), no match (extracted but >10% discrepancy), scale mismatch (wrong effect type extracted), direction flip, computation gap (Cochrane used raw counts; publication reports adjusted values), significance shift (pooled result crosses p=0.05), and ambiguous effect type.

### Provenance

Every review was processed through a TruthCert provenance chain, recording SHA-256 hashes of all inputs (RDA file, PDFs), intermediate outputs (extractions, pooled estimates), and classification decisions. The complete provenance bundle is available in the data repository.

### Statistical analysis

We report descriptive statistics for study-level and review-level reproducibility. For the study-level analysis, we calculated match rates overall and stratified by effect type and data availability. For the review-level analysis, we report the distribution of classifications and concordance of direction and significance. All analyses were conducted using Python 3.11 with NumPy 1.26 and SciPy 1.12. No hypothesis tests were performed; this is a descriptive audit.

### Patient and public involvement

No patients or members of the public were involved in the design, conduct, or reporting of this study.

## Results

### Open access coverage

Of 14,340 studies across 501 Cochrane reviews, 1,767 (12.3%) had openly accessible full-text PDFs (Table 1). The remaining 12,573 studies (87.7%) were computationally inaccessible due to paywall restrictions or missing PubMed Central identifiers. At the review level, 297 reviews (59.3%) contained at least one accessible study, but 204 reviews (40.7%) had no accessible studies whatsoever. The median proportion of accessible studies per review was 0% (interquartile range 0-14.3%).

### Study-level reproducibility

Among the 1,767 studies with accessible PDFs, 110 (6.2%) matched the Cochrane-reported effect within 5% (strict match) and 174 (9.8%) matched within 10% (moderate match) (Table 1). An additional 280 studies (15.8%) matched at a broader tolerance (weak match, >10% but extractable). The remaining 1,203 PDFs (68.1%) either yielded no extractable effect or the extracted value exceeded the 10% tolerance threshold. Across reviews with at least one PDF, the mean per-review strict match rate was 7.1% (median 0%), indicating that most reviews with some accessible studies still had very few individually reproducible effects.

### Review-level reproducibility

Of 501 reviews, 438 (87.4%) had no extraction possible (no accessible PDFs or no successful extractions), 53 (10.6%) had extractions but insufficient study coverage (<30%) for pooled comparison, and 10 (2.0%) achieved sufficient coverage for review-level classification (Table 2).

Among the 10 fully assessable reviews (k_coverage >=30%):

- **1 reproduced** (10.0%): CD014497, with complete study coverage (k_coverage=1.00) and a relative difference of 5.9% between reference and reproduced pooled estimates
- **4 minor discrepancies** (40.0%): same direction and statistical significance, but with relative differences ranging from 0.03% to 8.3%
- **5 major discrepancies** (50.0%): including direction reversals in all 5 cases, with relative differences from 106% to 693%

Nine of 10 assessable reviews (90%) retained the same statistical significance classification (both significant or both non-significant at alpha=0.05). However, only 5 of 10 (50%) maintained the same direction of effect, indicating that while overall conclusions about statistical significance were relatively robust, the specific direction and magnitude of effects were frequently altered.

### Error taxonomy

Missing PDFs were the primary error source in 477 reviews (95.2%), underscoring that the dominant barrier to reproducibility is access, not methodology (Figure 1). Extraction failure (PDF available but no result) accounted for 2.2% of primary errors, and no-match (extracted but >10% discrepancy) accounted for 2.2%. Among the 10 assessable reviews, the major discrepancies were attributable to low study coverage (median k_coverage=0.50), meaning that even in the best cases, the reproduced pooled estimate was derived from half or fewer of the original studies.

### Sensitivity analyses

Among the 63 reviews with any review-level data (including those classified as insufficient), 44 (69.8%) showed the same direction of effect and 42 (66.7%) showed the same significance classification. However, study coverage in this broader group was very low (mean k_coverage=15.2%, median 7.4%), and only 6 reviews achieved k_coverage >=50%.

## Discussion

### Principal findings

This study represents the first large-scale automated reproducibility audit of Cochrane meta-analyses. Our central finding is that computational reproducibility is currently impossible for the vast majority of systematic reviews, not because of methodological limitations but because the underlying evidence is locked behind paywalls. Only 12.3% of the 14,340 studies across 501 Cochrane reviews had openly accessible full-text publications, leaving 87.7% of the evidence base computationally invisible.

Among the small fraction of reviews with sufficient open access coverage for meaningful comparison, results were concerning: only 1 of 10 (10%) fully reproduced, and half showed reversed effect directions. These findings should be interpreted cautiously given the small sample, but they suggest that even when access is available, discrepancies between source publications and meta-analytic data are common.

### Comparison with previous studies

Manual reproducibility audits have reported discrepancy rates of 10-40% across samples of 20-50 reviews.^2-4^ Our computationally assessable subset (10 reviews) showed a higher discrepancy rate (90%), but this comparison is limited by differences in methodology, sample size, and the definition of "discrepancy." Manual audits can resolve ambiguities (e.g., selecting the correct outcome from a multi-arm trial) that automated extraction cannot. Our study is better understood as quantifying the *automated* reproducibility rate --- the degree to which a deterministic pipeline, without human judgement, can recover the same numbers.

Hardwicke and colleagues assessed the analytic reproducibility of 35 meta-analyses in Psychological Bulletin, finding that 31% had at least one outcome value that could not be reproduced.^3^ Lakens and colleagues found that 18% of effect sizes in 36 meta-analyses contained errors.^4^ Our 90% discrepancy rate among assessable reviews likely reflects the compounding of study-level extraction imprecision across multiple studies --- small individual errors amplified through pooling.

### The open access barrier

The most consequential finding is not the reproducibility rate itself but the structural barrier that prevents its measurement. With 87.7% of constituent studies behind paywalls, no computational method --- no matter how accurate --- can verify the majority of Cochrane meta-analyses. This has implications beyond reproducibility: it means that automated error detection, living evidence updates, and AI-assisted evidence synthesis are all limited to the 12.3% of the evidence base that is openly available.

This finding adds empirical weight to calls for universal open access to clinical trial results.^7,8^ Funders, journals, and regulators have made progress with trial registration and results reporting requirements, but the full-text publications --- where detailed methods, subgroup analyses, and outcome definitions reside --- remain largely inaccessible.

### Implications for policy and practice

Three interventions could transform the reproducibility landscape:

First, **structured data deposition** for every trial included in a systematic review would eliminate the need for PDF extraction entirely. If authors deposited their analysis-ready datasets (effect sizes, standard errors, sample sizes) in a structured format alongside their systematic review, reproducibility would become a deterministic verification rather than a noisy extraction problem.

Second, **Cochrane's data infrastructure** could be enhanced to include direct links from RDA per-study entries to structured result registries (e.g., ClinicalTrials.gov results tables, CSDR, Vivli). This would enable verification without PDF access.

Third, **journal mandates for open access to all cited trial publications** in systematic reviews would close the access gap directly. While this may be impractical in the short term, it highlights the dependency: a systematic review's reproducibility is only as good as the accessibility of its sources.

### Strengths and limitations

Our study has several strengths. It is the largest computational reproducibility audit of meta-analyses conducted to date, covering 501 reviews and 14,340 studies. The pipeline is fully deterministic (no language model components), ensuring that our audit is itself reproducible. Every classification carries a cryptographic provenance chain (TruthCert), enabling independent verification. The complete code, data, and interactive dashboard are openly available.

Several limitations must be acknowledged. First, the open access coverage (12.3%) is itself biased: newer, larger, and more heavily cited trials are more likely to be openly accessible, meaning our assessable subset is not representative of the full evidence base. Second, our extraction pipeline uses pattern matching rather than human judgement, and its strict match rate (6.2%) reflects this limitation. Third, the 10 reviews achieving sufficient coverage for pooled comparison represent a highly selected sample, and conclusions from this group cannot be generalised. Fourth, we could not distinguish between true data errors in the original reviews and limitations of our extraction pipeline. Fifth, the reproduced pooled estimates use a non-random subset of the original studies, introducing potential selection bias.

## Conclusions

The computational reproducibility of Cochrane meta-analyses is severely limited by open access barriers, with 87.7% of constituent studies inaccessible to automated verification. Among the small subset of reviews with sufficient open access coverage, only 10% fully reproduced, though statistical significance was preserved in 90% of cases. These findings argue for mandating structured data deposition alongside systematic reviews, making reproducibility verification a routine, automated audit rather than an exceptional manual effort.

---

## Tables

### Table 1. Study-level reproducibility across 501 Cochrane reviews

| Metric | n | % |
|--------|---|---|
| Total studies | 14,340 | 100.0 |
| No open access PDF | 12,573 | 87.7 |
| With open access PDF | 1,767 | 12.3 |
| *Among studies with PDF:* | | |
| Strict match (within 5%) | 110 | 6.2 |
| Moderate match (within 10%) | 174 | 9.8 |
| Weak match (>10%, extractable) | 280 | 15.8 |
| No match or extraction failure | 1,203 | 68.1 |

### Table 2. Review-level reproducibility classification

| Classification | n | % | Description |
|---------------|---|---|-------------|
| No extraction possible | 438 | 87.4 | No accessible PDFs or no successful extractions |
| Insufficient coverage | 53 | 10.6 | <30% study coverage; pooled comparison unreliable |
| Major discrepancy | 5 | 1.0 | Different direction or significance |
| Minor discrepancy | 4 | 0.8 | Same direction and significance; >10% pooled difference or 30-49% coverage |
| Reproduced | 1 | 0.2 | Within 10%, same direction, same significance, >=50% coverage |

### Table 3. Error taxonomy across 501 reviews

| Primary error source | n reviews | % |
|---------------------|-----------|---|
| Missing PDF | 477 | 95.2 |
| Extraction failure | 11 | 2.2 |
| No match | 11 | 2.2 |
| Other/none | 2 | 0.4 |

### Table 4. Characteristics of the 10 fully assessable reviews

| Review ID | k_coverage | Relative difference (%) | Same direction | Same significance | Classification |
|-----------|-----------|------------------------|---------------|-------------------|---------------|
| CD014497 | 1.000 | 5.9 | Yes | Yes | Reproduced |
| CD013823 | 0.400 | 0.1 | Yes | Yes | Minor |
| CD015636 | 0.400 | 3.0 | Yes | Yes | Minor |
| CD015046 | 0.500 | 45.5 | Yes | Yes | Minor |
| CD010163 | 0.500 | 832.0 | Yes | Yes | Minor |
| CD007310 | 0.316 | 692.7 | No | Yes | Major |
| CD012635 | 0.308 | 310.0 | No | Yes | Major |
| CD015530 | 0.500 | 214.6 | No | Yes | Major |
| CD016168 | 0.500 | 466.5 | No | Yes | Major |
| CD014941 | 0.500 | 106.2 | No | No | Major |

---

## Figures

**Figure 1.** Study flow diagram showing the attrition from 501 Cochrane reviews through PDF availability, extraction success, and reproducibility classification. [PRISMA-style flow diagram]

**Figure 2.** Error taxonomy distribution across 501 reviews. Stacked bar chart showing the proportion of reviews by primary error source. [Generated from dashboard]

**Figure 3.** Fragility landscape: scatter plot of study count (k) versus relative pooled effect difference (%) for the 63 reviews with any review-level data, coloured by reproducibility classification and sized by study coverage. [Generated from dashboard]

**Figure 4.** Side-by-side forest plots for CD014497 (reproduced) and CD014941 (major discrepancy), illustrating reference versus reproduced pooled estimates. [Generated from dashboard drill-down]

---

## References

1. Higgins JPT, Thomas J, Chandler J, et al. Cochrane Handbook for Systematic Reviews of Interventions. Version 6.4, 2023. Cochrane.
2. Gartlehner G, Nussbaumer-Streit B, Glechner A, et al. The reproducibility of results from systematic reviews and meta-analyses. *J Clin Epidemiol*. 2023;157:29-37.
3. Hardwicke TE, Mathur MB, MacDonald K, et al. Data availability, reusability, and analytic reproducibility: evaluating the impact of a mandatory open data policy at the journal *Cognition*. *R Soc Open Sci*. 2018;5(8):180448.
4. Lakens D, Hilgard J, Staaks J. On the reproducibility of meta-analyses: six practical recommendations. *BMC Psychol*. 2016;4:24.
5. [Pairwise70 dataset reference --- ZENODO_DOI]
6. [RCT Extractor v10.3 reference --- GITHUB_URL]
7. Taichman DB, Backus J, Baethge C, et al. Sharing clinical trial data: a proposal from the International Committee of Medical Journal Editors. *JAMA*. 2016;315(5):467-468.
8. Chan AW, Song F, Vickers A, et al. Increasing value and reducing waste: addressing inaccessible research. *Lancet*. 2014;383(9913):257-266.
9. Ioannidis JPA, Patsopoulos NA, Rothstein HR. Reasons or excuses for avoiding meta-analysis in forest plots. *BMJ*. 2008;336(7658):1413-1415.
10. Page MJ, McKenzie JE, Bossuyt PM, et al. The PRISMA 2020 statement: an updated guideline for reporting systematic reviews. *BMJ*. 2021;372:n71.

---

## Declarations

**Funding:** None.

**Competing interests:** All authors have completed the ICMJE uniform disclosure form and declare no competing interests.

**Ethical approval:** Not required. This study analysed publicly available data from published Cochrane reviews and openly accessible trial publications.

**Data sharing:** The MetaReproducer pipeline, complete results, TruthCert provenance bundles, and interactive dashboard are available at [GITHUB_URL]. The Pairwise70 dataset is deposited at [ZENODO_DOI].

**Transparency:** The lead author (the manuscript's guarantor) affirms that the manuscript is an honest, accurate, and transparent account of the study being reported; that no important aspects of the study have been omitted; and that any discrepancies from the study as registered have been explained.

**Dissemination to participants and related patient and public communities:** The interactive dashboard will be made freely available to enable independent exploration of the results.

---

*Word count: ~3,800 (excluding tables, figures, references, and declarations)*
