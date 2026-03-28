Mahmood Ahmad
Tahir Heart Institute
mahmood.ahmad2@nhs.net

Computational Reproducibility Audit of 501 Cochrane Meta-Analyses

Can Cochrane meta-analyses be computationally reproduced when an automated pipeline re-extracts effect sizes from source trial publications? We audited 501 Cochrane systematic reviews encompassing 14,340 individual studies using MetaReproducer, a deterministic pipeline that parses RevMan data files, retrieves open-access PDFs, extracts effects via RCT Extractor v10.3, and re-pools results using inverse-variance random-effects models. The pipeline infers effect type by back-computing candidate log-odds and log-risk ratios from two-by-two tables, matching against Cochrane reference values within 0.0001 tolerance on the log scale. Only 1,688 of 14,340 studies had accessible PDFs, yielding an open-access prevalence of 11.8 percent (95% CI 11.3-12.3), leaving most evidence computationally unverifiable. Among six reviews with sufficient coverage for classification, two showed major discrepancies including one complete direction reversal. The primary barrier to reproducibility is infrastructural access rather than methodology, suggesting that mandating structured data deposition could transform verification. This fundamental limitation of open-access coverage constrains any automated reproducibility audit of the published evidence base.

Outside Notes

Type: methods
Primary estimand: Prevalence
App: MetaReproducer v1.0
Data: 501 Cochrane systematic reviews, 14,340 studies, Pairwise70 dataset
Code: https://github.com/mahmood726-cyber/meta-reproducer
Version: 1.0
Validation: DRAFT

References

1. Marshall IJ, Noel-Storr A, Kuber J, et al. Machine learning for identifying randomized controlled trials: an evaluation and practitioner's guide. Res Synth Methods. 2018;9(4):602-614.
2. Jonnalagadda SR, Goyal P, Huffman MD. Automating data extraction in systematic reviews: a systematic review. Syst Rev. 2015;4:78.
3. Borenstein M, Hedges LV, Higgins JPT, Rothstein HR. Introduction to Meta-Analysis. 2nd ed. Wiley; 2021.

AI Disclosure

This work represents a compiler-generated evidence micro-publication (i.e., a structured, pipeline-based synthesis output). AI is used as a constrained synthesis engine operating on structured inputs and predefined rules, rather than as an autonomous author. Deterministic components of the pipeline, together with versioned, reproducible evidence capsules (TruthCert), are designed to support transparent and auditable outputs. All results and text were reviewed and verified by the author, who takes full responsibility for the content. The workflow operationalises key transparency and reporting principles consistent with CONSORT-AI/SPIRIT-AI, including explicit input specification, predefined schemas, logged human-AI interaction, and reproducible outputs.
