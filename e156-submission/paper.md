Mahmood Ahmad
Tahir Heart Institute
mahmood.ahmad2@nhs.net

Computational Reproducibility Audit of 501 Cochrane Meta-Analyses

Can Cochrane meta-analyses be computationally reproduced when an automated pipeline re-extracts effect sizes from source trial publications? We audited 501 Cochrane systematic reviews encompassing 14,340 individual studies using MetaReproducer, a deterministic pipeline that parses RevMan data files, retrieves open-access PDFs, extracts effects via RCT Extractor v10.3, and re-pools results using inverse-variance random-effects models. The pipeline infers effect type by back-computing candidate log-odds and log-risk ratios from two-by-two tables, matching against Cochrane reference values within 0.0001 tolerance on the log scale. Only 1,688 of 14,340 studies had accessible PDFs, yielding an open-access prevalence of 11.8 percent (95% CI 11.3-12.3), leaving most evidence computationally unverifiable. Among six reviews with sufficient coverage for classification, two showed major discrepancies including one complete direction change. The primary barrier to reproducibility is infrastructural access rather than methodology, suggesting that mandating structured data deposition could transform verification. This fundamental limitation of open-access coverage constrains any automated reproducibility audit of the published evidence base.

Outside Notes

Type: methods
Primary estimand: Prevalence
App: MetaReproducer v1.0
Data: 501 Cochrane systematic reviews, 14,340 studies, Pairwise70 dataset
Code: https://github.com/mahmood726-cyber/meta-reproducer
Version: 1.0
Validation: DRAFT

References

1. Barendregt JJ, Doi SA, Lee YY, Norman RE, Vos T. Meta-analysis of prevalence. J Epidemiol Community Health. 2013;67(11):974-978.
2. Nyaga VN, Arbyn M, Aerts M. Metaprop: a Stata command to perform meta-analysis of binomial data. Arch Public Health. 2014;72:39.
3. Borenstein M, Hedges LV, Higgins JPT, Rothstein HR. Introduction to Meta-Analysis. 2nd ed. Wiley; 2021.
