Research Report

**Interpreting Dual-Use Biology Benchmarks for Frontier AI**

Measurement, saturation, and generational analysis

Grant Ellison, Jeffrey Lee, Barbara Del Castello, Sunishchal Dev, Kyle Brady

RAND Global Emerging Risks

[Doc. number] PR-X000-0

[Date] Month Year

Prepared for [Sponsor organization]

Not Cleared for Public Release

This document has not been formally reviewed, edited, or cleared for public release. It should not be cited. RAND's publications do not necessarily reflect the opinions of its research clients and sponsors. ![RandLogo](data:image/png;base64...) is a registered trademark.

![Logo  Description automatically generated](data:image/jpeg;base64...)

## About This Report

This report continues prior efforts to evaluate the biological knowledge and problem-solving performance of frontier AI systems. Benchmarking has become a common method for comparing models, tracking progress over time, and identifying areas of advancing performance. However, as performance has advanced, benchmark scores have become harder to interpret. Aggregate accuracy can mask important differences in item difficulty, construct coverage, and measurement quality. Some benchmarks are now considered saturated—no longer distinguishing between more and less capable AI—while others remain informative only on smaller subsets of samples. As a result, higher scores do not, by themselves, show what newer systems can do that earlier systems could not, nor do they directly indicate what benchmark gains imply for real-world risks.

This report is for evaluators and analysts who want to understand what existing benchmark data can still reveal about performance, coverage, and quality. We present an analytic strategy for interpreting existing benchmark data. It treats samples from multiple benchmarks as a single dataset, places AI systems and expert baselines on a common scale using item response theory, and labels items with a common taxonomy to support analysis of task type. These methods are used to identify which portions of the benchmark corpus remain discriminating, where recent model gains have occurred, and how observed benchmark performance may be interpreted in relation to biological risk.

Center on AI, Security, and Technology

RAND Global and Emerging Risks is a division of RAND that delivers rigorous and objective public policy research on the most consequential challenges to civilization and global security. This work was undertaken by the division’s Center on AI, Security, and Technology, which aims to examine the opportunities and risks of rapid technological change, focusing on artificial intelligence, security, and biotechnology. For more information, contact cast@rand.org.

Funding

This research was independently initiated and conducted within the Center on AI, Security, and Technology using income from operations and gifts and grants from philanthropic supporters. It was made possible thanks to generous contributions from Chris Anderson and Jacqueline Novogratz, Coefficient Giving, High Tide Foundation, The Pew Charitable Trusts, Sea Grape Foundation, Jaan Tallinn, and Valhalla Foundation as part of The Audacious Project.

A complete list of donors and funders is available at [www.rand.org/CAST](http://www.rand.org/CAST). RAND clients, donors, and grantors have no influence over research findings or recommendations.

## Acknowledgments

The authors thank Lee Nilsson for providing operational support throughout this project. We thank Gary Cecchine for quality assurance. We would also like to thank Li Ang Zhang and Jasper Götting for their thoughtful reviews, which strengthened the rigor and insight of our analysis. We would also like to thank the team at SecureBio for sharing their benchmarks and expert baseline data, which we highlight in our analysis.

## Contents

[About This Report i](#_Toc235180935)

[Acknowledgments ii](#_Toc235180936)

[Contents iii](#_Toc235180937)

[Figures and Tables iv](#_Toc235180938)

[Key Findings v](#_Toc235180939)

[Recommendations vi](#_Toc235180940)

[Introduction 1](#_Toc235180941)

[Validity 2](#_Toc235180942)

[Contamination and Refusal 3](#_Toc235180943)

[Structure of the Report 4](#_Toc235180944)

[Methods 4](#_Toc235180945)

[Item Response Theory 5](#_Toc235180946)

[Results 6](#_Toc235180947)

[Summary Results 6](#_Toc235180948)

[Dataset Composition 9](#_Toc235180949)

[SecureBio Dual-Use Biology Benchmarks with Expert Baselines 11](#_Toc235180950)

[Interpreting Frontier Performance 15](#_Toc235180951)

[Saturation 15](#_Toc235180952)

[More Efficient Assessments 17](#_Toc235180953)

[Generational Analysis of Gemini 18](#_Toc235180954)

[Discussion 20](#_Toc235180955)

[A Theoretical Framework for Interpreting Capability-Relevant Constructs 20](#_Toc235180956)

[Theories of Human Uplift 20](#_Toc235180957)

[Limitations 22](#_Toc235180958)

[Conclusion 23](#_Toc235180959)

[Appendix A: Methods 24](#_Toc235180960)

[The Item-Response Framework 24](#_Toc235180961)

[A Taxonomy for Assessing Benchmark Items 28](#_Toc235180962)

[Applying the Taxonomy 30](#_Toc235180963)

[Appendix B: Additional Results 33](#_Toc235180964)

[Abbreviations 41](#_Toc235180965)

[References 42](#_Toc235180966)

[About the Authors 43](#_Toc235180967)

## Figures and Tables

### Figures

[Figure 1. Performance of 45 Frontier AI Models 7](#_Toc234921187)

[Figure 2. Average Accuracy and Difficulty of 26 Benchmarks 8](#_Toc234921188)

[Figure 3. Item Difficulty and Model Ability by Construct 10](#_Toc234921189)

[Figure 4. Item Difficulty and Model Ability by Discrimination 11](#_Toc234921191)

[Figure 5. SecureBio Dual-Use Biological Benchmarks with Expert Baselines 12](#_Toc234921192)

[Figure 6. Frontier vs. Expert Performance Over Time 14](#_Toc234921193)

[Figure 7. SecureBio Benchmarks: AI and Expert Correct Response 15](#_Toc234921194)

[Figure 8. Saturation Level, by Threshold, of Top 3 Models from Every Provider 16](#_Toc234921195)

[Figure 9. Projecting Future Saturation of the Existing Benchmark Data 17](#_Toc234921196)

[Figure 10. Estimating IRT Parameters from Highest-Information Items 18](#_Toc234921197)

[Figure 11. Gemini Generational Accuracy by Item Difficulty 19](#_Toc234921198)

[Figure 12. Gemini Pro Generational Gains 19](#_Toc234921199)

[Figure A.1. Item Response Curve Example 26](#_Toc234921200)

[Figure B.1. Estimated Accuracy by Ability and Difficulty 33](#_Toc234921201)

[Figure B.2. Wright Map Stacked by Benchmark 35](#_Toc234921202)

[Figure B.3. Taxonomy Accuracy by Domain 36](#_Toc234921203)

[Figure B.4. Taxonomy Item Count by Domain 36](#_Toc234921204)

[Figure B.5. Inferential Direction x Input and Output Modalities Accuracy 37](#_Toc234921205)

[Figure B.6. Inferential Direction x Input and Output Modalities Item Counts 37](#_Toc234921206)

### Tables

[Table 1. Biological Risk Interpretation v](#_Toc235180968)

[Table 2. Label Distribution Summary 9](#_Toc235180969)

[Table 3. Theoretical Mapping of Benchmark Constructs to Bio Risk Pathways 21](#_Toc235180970)

[Table A.1. Inter-Rater Reliability Study Summary 30](#_Toc235180971)

[Table A.2. Inter-Rater Reliability Study One-Hot Binary Metrics 31](#_Toc235180972)

[Table A.3. Taxonomy Regression Analysis Coefficient Table 33](#_Toc235180973)

[Table B.1. Gemini Generation Delta by Construct 34](#_Toc235180974)

[Table B.2. Benchmark Release Dates and Public Availability 38](#_Toc235180975)

[Table B.3. AI Model Release Dates 39](#_Toc235180976)

## Key Findings

* **Benchmark samples vary in difficulty and information.** While frontier AI has saturated much of our dataset, it still contains an informative set of difficult samples that remain beyond the current frontier of AI performance.
* **Item-response theory can be used to better understand generational improvement.** Compared with *2.5 Pro*, *Gemini 3.0 Pro* demonstrates progress on harder items, and Gemini 3.1 Pro continues this trend. Gemini 3.1 Pro has improved on highly informative samples we find relevant to expert troubleshooting and failure identification.
* **10 percent of the dataset can be used to estimate frontier model performance.** Ability estimates are 99 percent correlated with their full values when items are selected based on estimated information.
* **We identify a taxonomy that provides interpretative separation between samples.** *Inferential direction* theorizes about the relationship between the input and the expected output and corresponds to distinct stages of biological work. Table 1 presents an interpretation map linking inferential direction and difficulty to theoretical risk relevance.
* *Forward:* causes, conditions, or antecedents effects, outcomes, or consequences.
* *Backward:* effects, outcomes, or observations causes, conditions, or antecedents.
* *Undirected:* associative, classificatory, or recognitional.

Table 1. Biological Risk Interpretation

|  |  |  |  |
| --- | --- | --- | --- |
|  | Forward | Backward | Undirected |
| Easy | Execution for novices carrying out known procedures. | Troubleshooting for novices recovering from common failures rather than abandoning the task. | Background knowledge and information retrieval for novices. |
| Medium | Planning and optimization for users who already have some procedural understanding. | Troubleshooting for middling actors when procedures fail. | Domain-literacy for middling actors doing knowledge and information retrieval and navigating technical documents. |
| Hard | Design and experimental support for advanced actors in planning and executing difficult tasks. | Interpretation for advanced actors supporting interpretation of surprising or accidental results. | Expert-knowledge compression, supplying rare background knowledge to support experts. |
|  | | | |

## Recommendations

* **Measure and report difficulty, discrimination, coverage, and saturation.[[1]](#footnote-2)** Reporting makes benchmark results more interpretable and helps target future evaluation development toward areas of high information and underrepresentation. Saturation should be reported at multiple probability thresholds for correct responses.
* **Publish item-response data.** Item-level response tables should be shared whenever possible in a form that preserves item identity across solvers, while avoiding disclosure of underlying benchmark content when needed. For private or non-releasable benchmarks, this can be done using anonymized item IDs. Published item-response data would allow the community to:
  + Assess where frontier performance is on a single common scale
  + Estimate where future systems are likely to saturate existing benchmarks
  + Identify which assessments remain most discriminating
  + Support external replication, recalibration, and meta-analysis across evaluations
* **Perform cross-benchmark, item-level analysis.** Evaluators should identify whether performance reflects broad movement across the dataset or is concentrated in identifiable constructs. Scaled taxonomies can be used to identify subsets of samples across and within benchmarks associated with constructs of interest.
* **Future benchmark development should extend to more discriminating tasks** that lie beyond the ability range of current frontier models and, where appropriate, beyond the range observed in current expert baselines. The focus should be on expanding underrepresented areas such as *backward* inference and open-ended assessments.

# Introduction

Work assessing the dual-use biological knowledge and problem-solving ability of AI has yielded a growing dataset of benchmarks for benign, dual-use, and dangerous biological tasks. As AI systems have improved, scores on many benchmarks have improved, some human comparisons have been surpassed, and questions remain about what benchmark scores mean for real-world risk. The motivating question addressed in this report is: *What can benchmark data reveal about what AI can do now that it couldn't before?*

Benchmark accuracy alone poses several interpretability challenges.

* *Self-reference:* Benchmark scores often lack an external object of comparison, so they typically validate performance relative to the benchmark itself.
* *Item heterogeneity:* Benchmark items vary in difficulty, construct, and quality; aggregate accuracy treats them as if they were equivalent.[[2]](#footnote-3)
* *Item insufficiency:* Many benchmarks are too small to support statistical inference.
* *Response heterogeneity:* Two models may have similar accuracy while differing in which types of items they correctly solve, or a single model may respond differently to the same question on separate occurrences.

While benchmarks cannot directly measure real-world risk, we can utilize them as evidence for biological knowledge and problem-solving ability, which may inform assessments of dual-use capability and risk. We distinguish four related concepts:

* *Biological knowledge:* generation of biological facts, concepts, and relationships.
* *Problem-solving ability:* use of knowledge to infer, diagnose, predict, troubleshoot, or design under constraints.
* *Dual-use:* the extent to which a task has both benign and risky applications.
* *Risk:* downstream potential for harm, shaped by capability, access, safeguards, intent, context, and opportunity for misuse.

Biological knowledge and problem-solving ability are not directly observed in benchmark data, either. Instead, each must be inferred from the performance on a set of items within the evaluation environment. Thus, the same observed performance may support different claims depending on what items are assessed, how responses are scored, and how far the analyst seeks to generalize beyond the benchmark.

Rather than presenting a new assessment or focusing only on the latest frontier systems, this report draws on existing longitudinal benchmark data to address its motivating question. It is intended for analysts and evaluators interested in developing better methods for interpreting benchmark results, improving evaluation design, and understanding the limits of current benchmarking practice. The analytic strategies presented here are meant both to support the empirical findings of the report and to assess the usefulness of the methods themselves. In that sense, the report takes a meta-assessment perspective on dual-use biological benchmarking.

## Validity

What would be required for a benchmark to entail validity? Borsboom et al. argue that a test is valid for measuring an attribute if the attribute exists and its variation causally produces variation in measurement outcomes (Borsboom, Mellenbergh, & Heerden, 2004)*.* Thus, validity is the claim that something real is being measured and that the observed performance is attributable to it. Cronbach and Meehl's work on validity distinguishes the types of validity (Cronbach & Meehl, 1955).

* *Predictive Validity*: performance predicts a future criterion
* *Concurrent Validity:* performance correlates with a simultaneously obtained criterion
* *Content Validity*: items sampled from a well-defined universe of interest
* *Construct Validity*: items measure an attribute that cannot be directly observed

Dual-use biological knowledge and problem-solving benchmarks (referred to, from here on, only as “dual-use benchmarks”) have not been shown to possess predictive validity against real-world criteria. Human uplift studies, which aim to measure whether access to large language models improves human ability to perform real-world biological wet-lab work, have largely been inconclusive or have shown statistically insignificant results (SecureBio, 2026). Other potential external criteria for dual-use benchmarks are difficult to measure because evaluating them may itself pose risks. As a result, interpretation often depends on a theoretical bridge between a model’s stated benchmark performance and its potential real-world relevance.

The lack of an external criterion means that the benchmark's accuracy has generally been compared only to itself, another benchmark, or to another AI. That is, if AI continues to improve its accuracy on a benchmark, the accuracy is compared to prior generations and interpreted accordingly. If scores stop improving, interpretation falls back on the validity of an item’s content and comparisons between one AI and another.

Others have also raised concerns about construct validity in benchmarking. Raji et al. argue that general-purpose ML benchmarks frequently lack construct validity because the items are developed without an underlying theory of cognitive ability (Raji, Bender, Paullada, Denton, & Hanna, 2021). Jacobs and Wallach draw on Item Response Theory (IRT) and show that the gap between constructs and measurements is a source of much of the interpretive difficulty in measuring fairness in computational systems. Salaudeen et al. argue that validity is claim-dependent: the larger the inferential leap from observed benchmark performance to the capability or risk claim being made, the stronger the evidence required to support it (Salaudeen, et al., 2025).

The lack of external validation does not by itself negate the possibility of content validity. Benchmarks are designed to measure the relevance of performance; for instance, an item that requires an AI to retrieve a biological fact may be measured because the retrieved fact could be used to perform dangerous biological work. This theoretical connection between benchmark performance and a real-world risk is often difficult to interpret or requires expertise to understand. Thus, simplifying taxonomies are intended as a theoretical interpretive framework for extrapolating the logic of how benchmark content relates to real-world risks; they do not constitute empirical validation that benchmark performance translates into real-world risk.

## Contamination and Refusal

Concerns may arise in benchmarking about the “contamination” of data; if an AI model has been trained on a benchmark question, a correct response may be due to its ability to regurgitate its training data. While this problem is critical for the purpose of understanding the true performance of a system, we argue here that contamination does not necessarily undermine the risk relevance of our assessment for dual-use biosecurity considerations. If a correct answer results from contamination, we still consider it relevant, as a system capable of compressing significant chains of biological reasoning or factual recall may still pose risks. For transparency, we provide the release date of models and benchmarks in tables B.2 and B.3 in *Appendix B Additional Results.* We also emphasize the private benchmarks by SecureBio as a focus of our analysis, in part to ameliorate concerns about contamination.

We make a similar argument about the presence of “refusals” in our evaluation. A refusal occurs when a system declines to respond to a request due to the model's training or design, or to an additional safeguard implemented during its deployment. An AI system refusing to answer a question with potentially harmful applications may, in one sense, reflect the model’s ability to recognize the implications of an answer. However, our theories of risk require that a material solution be provided; in this sense, the presence of a refusal may reduce risk. Thus, the performance estimates in this report should be interpreted as measures of expressed benchmark performance under the current model and deployment policies, and they should not be considered measurements of ability.

## Structure of the Report

In this report, we apply a framework to interpret benchmark data for dual-use biological sciences. We treat benchmark results as item-response observations in which solvers produce answers to structured tasks. By placing items, AI, and expert baselines on a common scale, and decomposing items by a task-relevant taxonomy, we aim to improve interpretation of benchmark data and its relevance to dual-use biological risk.

The *Introduction* has outlined the interpretive challenges posed by existing benchmarks and discussed benchmark validity. The *Methods* section describes our analytic framework, including cross-benchmark item-level analysis, taxonomy-based labeling, item response theory, generational comparison, and expert-baseline comparison. The *Results* section presents the main empirical findings, beginning with summary model- and benchmark-level results, then examines dataset composition, and compares frontier AI systems with expert baselines on the SecureBio benchmark data. The section on *Interpreting Frontier Performance* examines saturation, the use of smaller high-information item subsets for efficient assessment, and generational comparisons across Gemini models. The *Discussion* connects these findings to the theoretical interpretation of dual-use risk. *Appendix A* frames our analysis within an item-response framework and develops a taxonomy for labeling benchmark items. *Appendix B* presents supplementary results and figures.

# Methods

We develop a measurement and interpretation framework for dual-use biological benchmark data, using five analytic strategies:

1. *Cross-benchmark item-level analysis:* We treat the aggregation of all samples from 26 benchmarks as a single dataset with 8,146 items. The purpose of pooling benchmarks into a single corpus is to estimate item difficulty, discrimination, and solver ability on a common scale, increase statistical power, and enable cross-benchmark comparisons of performance, saturation, and construct coverage that would be difficult to support from any single benchmark.
2. *Taxonomized items:* We label items by an expert-validated taxonomy to examine subsets of the dataset that share associated constructs. This taxonomy provides a common descriptive framework across heterogeneous benchmarks, helping identify whether model gains are concentrated in particular types of items—such as those requiring backward inference or open-ended generation—rather than distributed uniformly across the corpus.
3. *Item-Response Theory (IRT):* We estimate model ability and item difficulty on a common logit scale. This allows us to compare models, benchmark items, and expert baselines directly, identify which items remain discriminating, and separate differences in raw accuracy from differences in the difficulty of the items solved.
4. *Generational analysis:* We compare three successive generations of the Gemini model family on the same set of items to identify what has changed in AI performance over time.
5. *Expert-baseline comparison:* We compare AI to expert baselines at the item level. This situates frontier model performance relative to observed expert performance and identifies what kinds of items AI can solve that experts miss.

We analyze existing benchmark response data from 49 frontier AI models across 8,146 items, spanning 26 benchmarks, including both public and private benchmarks developed by SecureBio, such as the Virology Capabilities Test (VCT) (Götting, et al., 2025). Four models with coverage below 75 percent were excluded, leaving 45 models in the analysis. The underlying response data come from ongoing benchmark evaluations that extend the work previously done at the RAND Corporation (Dev, et al., 2025).

## Item Response Theory

Item response time (IRT) is a measurement framework that models benchmark performance as the relation between solvers and items.[[3]](#footnote-4) Rather than treating all questions as equally informative, IRT estimates latent parameters that describe how difficult an item is, how well it distinguishes stronger solvers from weaker ones, and where each solver lies on the underlying ability scale. This is useful in benchmark analysis because two models with similar raw accuracy may have succeeded on very different sets of items: one may answer mostly easy items correctly, while another may answer fewer items overall but succeed on more difficult ones. IRT provides a way to represent these differences on a common scale and to interpret benchmark results in terms of both solver ability and item characteristics. We utilize the two-parameter logistic (2PL) model in this report. The main text provides a brief introduction to IRT for interpreting the results, while *Appendix A* presents the fuller methodological treatment and formal specification.

Three parameters are estimated by 2PL:

* *θ (theta), solver ability:* the estimated latent ability of a model or human solver on the common logit scale. Higher θ indicates a greater probability of correctly answering more-difficult items.
* *β (beta), item difficulty:* the estimated difficulty of an item on the same logit scale. Higher β indicates that stronger solvers are required to have a high probability of answering the item correctly.
* *α (alpha), item discrimination:* the extent to which an item separates stronger solvers from weaker ones near its difficulty level. Higher α indicates that the item is more informative because performance changes more sharply as ability increases.

Notably, and are measured in the same units, so they can be directly compared. A model with an ability equal to the difficulty of the question is expected to answer correctly 50% of the time.

# Results

We begin reporting results using aggregated distributions by benchmark and model. While this summary provides a high-level view of our results, it is still confounded by the same dilemma raised in the introduction: the aggregation of any measure of performance collapses the constructs and variations in difficulty present in the subset that has been aggregated over.

## Summary Results

Figure 1 provides the mean accuracy and ability, for each frontier model tested. In the right panel, we observe the reordering of several models by estimated ability, indicating that they performed well on more difficult items. Since the metric expresses the relation between a model’s performance and an item’s difficulty, a model that achieves a lower ordinal accuracy ranking underperformed on questions it would be estimated to have correctly solved. Thus, the re-ordering of a model’s performance when expressed by may also indicate something about the presence of refusals. This is consistent with the author’s observation that the Anthropic models, particularly the Opus family, were both highly capable and had a high presence of refusals.

Figure 1. Performance of 45 Frontier AI Models![](data:image/png;base64...)![](data:image/png;base64...)

Figure 2 summarizes aggregate accuracy and aggregate difficulty, , for each benchmark in the dataset. As in the model summary, estimates reorder several benchmarks relative to raw accuracy, indicating that accuracy can obscure differences in difficulty. One descriptive feature of the dataset is that benchmarks were internally categorized by RAND biosecurity experts as *benign*, *dual-use*, or *risky* based on their assessed relevance to biosecurity concerns. These labels are used only as an internal descriptive classification and do not constitute a formally validated taxonomy.

Figure 2. Average Accuracy and Difficulty of 26 Benchmarks![Chart, bar chart  AI-generated content may be incorrect.](data:image/png;base64...)![Chart, bar chart  AI-generated content may be incorrect.](data:image/png;base64...)

Table 2 summarizes performance by taxonomy label and shows that *inferential direction* exhibits the largest performance spread of any label. Current models perform best on *undirected* items, somewhat worse on *forward* items, and much worse on backward items, suggesting that frontier systems are relatively strong at recognition, retrieval, and following known causal structure, but weaker at reasoning backward from outcomes to causes, especially in tasks requiring explanation or diagnosis. *Appendix A—Applying the Taxonomy* estimates the adjusted taxonomy associations, controlling for other item characteristics. We find statistical significance for *backward* and *forward* inference items, *posterior*-informationitems, and *generation*-output items.

Table 2. Label Distribution Summary

|  |  |  |  |  |  |  |
| --- | --- | --- | --- | --- | --- | --- |
| Label | Label | Accuracy | Standard Error | N |  |  |
| Inferential Direction | Forward only | 0.64 | 0.00 | 1666 | -0.26 | 1.67 |
|  | Backward only | 0.56 | 0.00 | 316 | 0.45 | 1.43 |
|  | Forward and backward | 0.44 | 0.00 | 3244 | 1.27 | 1.24 |
|  | Undirected | 0.69 | 0.00 | 2892 | -1.32 | 1.37 |
| Information Modality | Text | 0.58 | 0.00 | 8113 | 0.00 | 1.39 |
|  | Image | 0.50 | 0.00 | 637 | 0.97 | 0.99 |
|  | Table | 0.61 | 0.01 | 37 | -0.40 | 1.61 |
| Information Loci | Prior | 0.58 | 0.00 | 7905 | -0.01 | 1.40 |
|  | Given | 0.51 | 0.00 | 4943 | 0.76 | 1.39 |
|  | Posterior | 0.39 | 0.00 | 550 | 1.90 | 0.65 |
| Output Modality | Selection | 0.54 | 0.00 | 4316 | 0.30 | 1.11 |
|  | Generation | 0.56 | 0.00 | 2082 | -0.09 | 1.55 |
|  | Value | 0.69 | 0.00 | 1717 | -0.66 | 1.86 |
|  | Artifact | 0.51 | 0.04 | 4 | 0.65 | 1.09 |
| Domain | Biology | 0.55 | 0.00 | 5797 | 0.16 | 1.28 |
|  | Chemistry | 0.65 | 0.00 | 1615 | -0.44 | 1.67 |
|  | Physics | 0.64 | 0.00 | 553 | -0.23 | 1.57 |
|  | Math | 0.75 | 0.01 | 90 | -0.99 | 1.47 |
|  | Other | 0.65 | 0.01 | 64 | -0.56 | 1.61 |

NOTE: N size, accuracy, standard error, difficulty, and discrimination are reported as the mean value of the subset.

## Dataset Composition

Figure 3 is a Wright Map visualization that represents each item and solver on the same logit scale (the vertical axis). is the average difficulty of the entire dataset (left panel), and the average ability of the entire solver cohort (right panel). The left panel shows the distribution of benchmark items by inferential direction: *forward only*, *include backward*, and *undirected*. The right panel places evaluated models on the same axis, colored by model provider. The shaded horizontal band marks the range of model cohort ability. *Backward*-inference items are disproportionately represented at higher difficulty levels. *Forward* and *undirected* items also span the scale, but the upper-difficulty region contains a concentration of *backward* inference.

The range “Below Cohort’s Ability” indicates the items in which every single model in the tested cohort is expected to solve at least 50% of the time. The range “Above Cohort’s Ability” indicates the items in which no model in the tested cohort is expected to solve 50% of the time and thus represents the frontier of benchmarking data that still challenges existing frontier AI.

Figure 3. Item Difficulty and Model Ability by Construct**![](data:image/png;base64...)**

Figure 4 uses the same common item difficulty and model ability scale but colors the item distribution by . Higher-discrimination regions indicate items that better separate stronger models from weaker models. The right panel again places models on the same scale, comparing model ability and the item pool's difficulty and discrimination. Several regions of the item distribution contain a concentration of highly discriminating items, including a band above the current frontier’s ability.

Figure 4. Item Difficulty and Model Ability by Discrimination![](data:image/png;base64...)

High-Information

There are bands of highly discriminating items around -2 logits and -5 logits, both in areas that most of the tested model cohort are expected to answer correctly with high frequency. These bands suggest a qualitative difference between items that are answered correctly nearly all the time and items that are answered correctly only some of the time. The band of highly discriminating items between 5 and 6 logits represents the pool of benchmark data that remains highly informative for our continued assessment of frontier AI systems.

## SecureBio Dual-Use Biology Benchmarks with Expert Baselines

Three benchmarks in our dataset are privately developed by our research partners, SecureBio: Human Pathogen Capabilities Test (HPCT), Molecular Biology Capabilities Test (MBCT), and Virology Capabilities Test (VCT). Solver performance on these benchmarks was conducted by RAND in the same manner as all other benchmarks in our dataset, while expert performance data were captured by SecureBio. SecureBio’s benchmarks are especially important, as they have limited public availability and thus are far less likely to be contaminated. Figure 5 compares SecureBio’s benchmark items, AI solvers, and human expert solvers on the same latent difficulty/ability scale. The item distribution is stacked by benchmark; the center panel shows model performance, while the right panel shows individual expert subject performance grouped by benchmark. The vertical scale is the same scale used in Figures 3 and 4, so a like-for-like comparison can be made.

Figure 5. SecureBio Dual-Use Biological Benchmarks with Expert Baselines![](data:image/png;base64...)

The top-performing model, Gemini 3.1 Pro, has approximately the same performance as the best-performing expert. The lowest-performing model in our cohort, Llama 3.2 1B, performs higher than the lowest-performing experts on HPCT and VCT.

Figure 6 compares the time trend in frontier AI capability against expert baselines on the same 2PL ability scale. Each model is placed by its release date and estimated model ability, on the SecureBio benchmark items. To summarize the upper edge of model performance over time, the left panel fits a nonlinear 90th-quantile regression to model ability as a function of release date.[[4]](#footnote-5) The band reflects the sensitivity of the estimated upper-tail trend to the observed set of models. The expert baselines in the right panel are point estimates of subject ability on the same 2PL scale. We utilize the frontier regression for two purposes: (1) to trace the trends of the frontier of AI systems’ performance on our assessment, and (2) to extrapolate the current trend into the future to describe the range of possible gains on our assessment that may occur one year into the future. Because the regression was fitted to sparse data, the extrapolated curve may be sensitive to individual data points and modeling assumptions. Additionally, the upper end of the observed difficulty scale may reflect limitations in benchmark quality or answer-key reliability rather than a pure ceiling of real-world task difficulty.

Figure 6. Frontier vs. Expert Performance Over Time![](data:image/png;base64...)[[5]](#footnote-6)

Currently, frontier AI is performing at approximately the level of the highest-performing expert subject. Under a continuation of the recent frontier trend, additional gains on this assessment would place frontier systems above the observed expert range, potentially by up to roughly two logits on the same scale. This is best interpreted as a descriptive upper-bound scenario on the present benchmark scale.

Figure 7 compares the difficulty of SecureBio items solved by AI systems and by expert baseline subjects across HPCT, MBCT, and VCT. The top three performing closed-weight models are plotted: Gemini 3.1 Pro, Gemini 3.0 Pro, and GPT 5; and the top three performing open-weight models are plotted: DeepSeek V3.1, Llama 4 Maverick 17B, and DeepSeek V3. Each point represents an item-response with a solution rate above 50%, placed according to its item difficulty, .

Figure 7. SecureBio Benchmarks: AI and Expert Correct Response![](data:image/png;base64...)

# Interpreting Frontier Performance

## Saturation

We define saturation as the share of items a model is expected to solve with at least a chosen level of reliability. Figure 8 varies that reliability threshold and shows, for each model, what fraction of the dataset would count as saturated. To simplify the figure, we plot only the top three models from each provider.

Figure 8. Saturation Level, by Threshold, of Top 3 Models from Every Provider![](data:image/png;base64...)

The current benchmark corpus is not exhausted at the frontier. Even the best-performing models fail to achieve full reliability on most items. Saturation is concentrated in the low-threshold region, while the remaining benchmark signal lies in the intermediate- and high-reliability bands. As a result, progress across successive model generations will appear primarily as a rightward shift of the curves.

Figure 9 shows the same capability frontiers as Figure 6 but projects the 90th quantile regression onto the current dataset distribution of item difficulty on the vertical axis. By extrapolating the current trend, we expect future gains to concentrate further on a small set of highly difficult items. The dataset's future usefulness depends on whether discriminating items remain above the advancing frontier to prevent full saturation, or whether the benchmark corpus can be enhanced with more difficult items that remain discriminating.

Figure 9. Projecting Future Saturation of the Existing Benchmark Data![](data:image/png;base64...)

## More Efficient Assessments

To evaluate whether future model scoring can be made less expensive, we performed a post hoc analysis using the existing full-dataset IRT fit. Figure 10 represents the correlation of IRT estimates from a subset of data with the full estimate obtained from our entire dataset. The bottom axis retains a growing share of items, with information descending. We held item difficulty and discrimination fixed, re-estimated each solver’s ability from only the retained items, and compared those short-form ability estimates with the full-dataset estimates.

Figure 10. Estimating IRT Parameters from Highest-Information Items![](data:image/png;base64...)

Ability recovery improves rapidly when items are retained by information. The result motivates using a compact high-information item set for future model evaluation, while preserving the full calibrated item dataset for item calibration, audit, and periodic scale refresh.

## Generational Analysis of Gemini

To directly address the motivating research question, *"What can benchmark data reveal about what AI can do now that it couldn't before?"* this section analyzes the results of a comparison among successive generations of Gemini models: Gemini 2.5 Pro, Gemini 3.0 Pro, and Gemini 3.1 Pro. We focus on the Gemini family because it represented the highest-performing provider-specific model lineage in our tested cohort, making it the clearest case for examining within-family generational change. Between the releases of Gemini 2.5 Pro and 3.0 Pro, just one benchmark in our analysis was released, VCT, and between 3.0 and 3.1 Pro, no benchmarks in our analysis were released.

Figure 11 plots Gemini’s generational accuracy against item difficulty. Gemini 3.0 Pro and 3.1 Pro differ from Gemini 2.5 Pro, especially in the moderate-to-hard region, as shown by the highlighted orange and red portions, respectively.

Figure 12 isolates the items newly solved by each later Gemini generation and breaks down the gains by their inferential direction. Gemini 3.0 Pro made the larger absolute jump, solving 718 items over 2.5 Pro, but 3.1 Pro’s smaller gain set was harder on average: its newly solved items had gains nearly one logit higher than 3.0 Pro. Gemini 3.1 Pro’s gains were also more concentrated in *backward* inference.

Figure 11. Gemini Generational Accuracy by Item Difficulty

![Chart  AI-generated content may be incorrect.](data:image/png;base64...)

Figure 12. Gemini Pro Generational Gains![](data:image/png;base64...)

Figures 11 and 12 suggest that generational improvement within the Gemini family is not simply a matter of solving more items overall, as later models improve performance on harder regions of the benchmark corpus. Gemini 3.0 Pro achieves the larger increase in the number of newly solved items relative to 2.5 Pro, but Gemini 3.1 Pro’s gains are concentrated on a smaller set of more difficult items. The composition of those gains also changes—later improvement is increasingly concentrated in items involving *backward* inference, which are overrepresented among the harder items in the dataset. On this benchmark scale, the most recent Gemini generation therefore appears not only broader in performance but also stronger on items intended to assess diagnostic and troubleshooting ability.

# Discussion

## A Theoretical Framework for Interpreting Capability-Relevant Constructs

Inferential direction is used here as a theoretical interpretive construct for describing what kind of reasoning an item appears to demand and, by extension, what kind of capability it may be probing. The purpose is to provide a structured way of interpreting heterogeneous benchmark content. Not all benchmark items measure the same thing. Some ask solvers to identify or classify, some to reason forward from inputs to outcomes, and others to reason backward from outcomes to causes. These distinctions map to different stages of practical biological work.

For example, *undirected* questions are typically asked such that they do not require meaningful inference from either direction. This can include asking about direct facts or categorization that rely on recognition of information and map to any stage within the biological workflow or risk chain. *Forward* questions can provide starting materials, DNA sequences, or conditions, and inquire about their effects, likely roles in a system, or clear consequences. These types of questions are often found early in individual workflows or stages of a risk chain. And finally, in *backward* items, outcomes or observations are provided, and the question asks for the explanations or conditions that would result in those observations. Such questions may often be found at middle or later points within an individual stage. These distinctions are useful not because they have been externally validated as stages of real-world misuse, but because they offer a simplified way to organize benchmark items by the kind of reasoning they appear to require.

## Theories of Human Uplift

The common scale provides a basis for theoretically interpreting potential actor uplift along two dimensions: task difficulty and task construct. Difficulty locates a model relative to human and frontier-AI performance, indicating which kinds of actors might plausibly benefit from its assistance. Inferential Direction indicates what kind of help the model is providing—whether recognition and recall, forward prediction and execution, or backward diagnosis and troubleshooting. [[6]](#footnote-7)

Within this interpretive framework, gains on easier, undirected items may be read as more consistent with support for actors aiming to recreate existing chemical or biological agents rather than design entirely novel ones—a profile likely applicable to a novice or non-expert, as those items reflect background knowledge, classification, and factual retrieval. Gains on backward-inference items can be interpreted as potentially more consequential within this framework to helping actors plan, execute, and optimize known procedures, or to helping them when confronted with known inputs and conditions. Gains on backward-inference items are potentially more consequential because they bear on troubleshooting, diagnosis, and adaptation when standard procedures fail. In addition, backward inference could be useful for better understanding novel systems and effects. That kind of assistance is more likely to matter for middling or sophisticated actors confronting real technical bottlenecks and novel design challenges. Still, it may also apply to novices and non-experts as they work their way through unfamiliar experiments.

On this interpretation, a model below the average expert baseline could still provide uplift to a novice, while a model that overlaps with or exceeds stronger human performers may be more relevant to actors with prior expertise. The construct decomposition adds an important qualifier: two models with similar overall ability may imply different forms of uplift depending on whether their strengths lie in *undirected*, *forward*, or *backward* tasks.

Table 3. Theoretical Mapping of Benchmark Constructs to Bio Risk Pathways

|  |  |  |  |
| --- | --- | --- | --- |
| Inferential Direction | Difficulty Level | Bio-Risk Pathway | Uplift Interpretation |
| Undirected | Easy | Lowers barriers to entry by helping users understand basic biological terms, entities, methods, organisms, reagents, or safety concepts. | Novice orientation: helps nonexperts acquire background knowledge but is less directly tied to execution or troubleshooting. |
| Undirected | Moderate | Helps users identify relevant biological mechanisms, protocols, assay types, or risk-relevant concepts that would otherwise require domain familiarity. | Domain-literacy: helps semi-informed users navigate technical material and recognize what matters. |
| Undirected | Hard | Gives users access to tacit or hard-to-find expert knowledge, including specialized methods, failure modes, or pathogen-relevant concepts. | Expert-knowledge compression: narrows the gap between nonexperts and specialists by supplying rare background knowledge. |
| Forward | Easy | Helps users follow standard protocols, anticipate basic outcomes, or choose among obvious procedural options. | Basic execution: supports carrying out known procedures more reliably. |
| Forward | Moderate | Helps users optimize parameters, anticipate assay outcomes, select conditions, or reduce trial and error in routine experimental work. | Planning and optimization: improves efficiency for users who already have some procedural understanding. |
| Forward | Hard | Helps users generate useful hypotheses, forecast the effects of nontrivial modifications, assist in complicated design choices, or model experimental conditions and effects on complex systems before testing them. | Advanced design and experimental: supports more capable actors in planning and executing difficult experiments or optimizing biological systems. |
| Backward | Easy | Helps users diagnose simple technical mistakes, contamination reasons, failed controls, or other common protocol errors. | Basic troubleshooting: helps novices recover from common failures rather than abandoning the task. |
| Backward | Moderate | Helps users identify likely failure modes, hidden variables, assay artifacts, or protocol bottlenecks. | Adaptive troubleshooting: helps users continue making progress when standard procedures fail. |
| Backward | Hard | Helps users resolve difficult technical bottlenecks, infer latent protocol errors, interpret unexpected phenotypes, identify and prioritize tasks, or recover from sophisticated experimental failure. | Expert-like failure recovery: potentially consequential for middling or sophisticated actors because it supplies the kind of tacit judgment that often gates real biological progress. |

## Limitations

*Item Quality:* Ambiguous wording, underspecified scoring rubrics, inconsistent autograding, and items with multiple defensible answers all suppress discrimination and inflate difficulty estimates without reflecting a coherent latent construct. The discrimination parameter α partially absorbs item-quality variation, but it cannot fully separate difficulty from defects in item construction, if any exist in the corpus.

*Taxonomy granularity:* The five-axis taxonomy is intentionally coarse to permit scalable LLM-based annotation across heterogeneous benchmarks. The taxonomy identifies broad performance gradients but should not be interpreted as a fine-grained cognitive decomposition of item demands.

*Predictive validity:* No external criterion links benchmark performance to real-world outcomes, such as observed rates of successful pathogen acquisition, synthesis, or facilitation of misuse. The framework establishes construct representation but cannot confirm that gains on hard backward-inference items translate into measurably increased biological risk. All interpretive claims connecting benchmark performance to risk pathways remain theoretical and have not been empirically validated against behavioral or operational evidence.

*Coverage and selection:* The corpus is limited to publicly available benchmarks and SecureBio's proprietary benchmarks. It excludes agentic evaluations, wet-lab task completion, multi-step planning assessments, and classified government evaluation sets. The resulting difficulty distribution may not represent the full space of risk-relevant tasks, particularly those requiring extended tool use, iterative experimentation, or the integration of tacit procedural knowledge that is not expressible in text-based items.

*Limited generalizability of generational analysis:* Our results assessing the generational differences of models is limited to the Gemini family. This analysis was conducted to demonstrate how such an analysis can be done and what it can show. Our findings based on the generational analysis are strictly limited in scope to the Gemini family.

*Contamination:* There is the potential that performance increases on public benchmarks which predate the release of an AI model may present a significant confound on estimations of performance.

## Conclusion

Existing dual-use biology benchmark data still contain useful measurement signals, but the signals are unevenly distributed. Across the 8,146-item corpus, benchmark samples vary substantially in difficulty and information content. Many items are now easy for frontier systems, and saturation is concentrated in lower-difficulty regions. But the corpus is not fully exhausted: a smaller set of difficult and highly discriminating items remain beyond the ability of current models and continues to separate frontier systems from one another. In practice, this means benchmark data can still show where advancement is occurring, despite limitations on the external validity of its meaning.

Our analysis estimated item difficulty, frontier AI ability, and expert ability on a common IRT scale and labeled items using a shared taxonomy. We found that score variance was related to both item difficulty and the results of labeling. The clearest example is *inferential direction*. *Undirected* items are generally easier, *forward* items are harder, and *backward* items are hardest. In this corpus, backward-inference items are concentrated in the upper-difficulty range and are theorized to be related to diagnosis, troubleshooting, explanation, and adaptation. This provides a basis for interpreting which aspects of support newer models may be improving, even if benchmark performance alone does not establish real-world uplift or operational risk.

Our generational analysis found that relative to Gemini 2.5 Pro, Gemini 3.0 Pro improved on more difficult items, and Gemini 3.1 Pro continued that pattern. Gemini 3.0 Pro made the larger absolute gain, but the newly solved items for Gemini 3.1 Pro were harder on average and more concentrated in *backward* inference. On the SecureBio benchmarks, current frontier systems also solve many items that expert baseline subjects miss, and Gemini 3.1 Pro ranks at the top of the tested cohort. Recent gains are concentrated in more difficult parts of our dataset.

We also found that only 10 percent of the dataset was necessary to estimate the model's ability, achieving 99 percent correlation with full estimates. This result supports the use of compact, high-information evaluation sets for routine model assessment, while preserving the full dataset for calibration, auditing, and periodic refresh.

These findings support several implications for evaluation practice. Evaluators should report difficulty, discrimination, coverage, and saturation alongside accuracy. Whenever possible, evaluators should publish item-level results in a form that preserves sample identity. For private or otherwise non-releasable benchmarks, this can be done using anonymized item IDs rather than underlying content. This would enable calibration, replication, and meta-analysis. Evaluators should also distinguish broad performance gains from gains concentrated in particular areas. Finally, future benchmark development should prioritize more discriminating tasks that remain above the current frontier, especially underrepresented items such as backward inference and open-ended assessments.

This framework may also extend to the next generation of biological evaluations. Although the present analysis focuses on scored benchmark items, the same item-response logic can be extended to agent evaluations in which systems use tools, act in environments, and complete multistep tasks before producing a scored outcome.

# Appendix A: Methods

Our methods build on prior infrastructure for biological benchmark execution and grading; we use a version of the same implementation and model-evaluation pipeline used to generate the underlying biological benchmark response data (Dev, et al., 2025). We extend prior benchmarking work by reanalyzing the resulting data using an item-response theory framework. We likewise rely on the UK AI Security Institute’s Inspect AI framework as the underlying evaluation software for benchmark execution, logging, and standardized task orchestration across models and datasets (UK AI Security Institute, 2026).

## The Item-Response Framework

### Items and Solvers

We represent benchmark inputs and outputs as items, AI as solvers, and scored outputs as observed responses from which latent capability may be inferred. This item-response framework provides the conceptual foundation for the analysis that follows, linking observed benchmark performance to latent ability, item difficulty, and construct interpretation, and extends naturally to agentic solvers.

An item, is defined by its input, , and its expected output, , and a condition which constitutes a satisfactory response—a scoring rule. The solver, , is any process that takes the item’s input and provides a candidate solution, , which is then compared with the expected answer to determine whether the solver has satisfied the item’s scoring rule.

A solver may take many forms, such as an algorithm, a stochastic process, or a human, and some solvers may provide different candidate solutions upon repeated attempts. The scorer may consist of an exact match, an auto-grader, or some other computable assessment process (Dev, et al., 2026). The observed performance of solver on item is

where is the number of epochs, and is 1 if the candidate solution satisfies the scoring rule, and 0 otherwise.

### Agentic Solvers

The solver is often an unobserved phenomenon. A classic algorithm can be evaluated by techniques such as consistency, completeness, and complexity, but a solver whose internal process has been learned is often inscrutable to the analyst. This similarity is shared with psychometric assessments, in which an evaluator attempts to assess a person's capability by observing only their performance on assessment items.

Efforts to resolve the opacity of solvers, such as examining a solver’s code, tool calls, or intermediate reasoning in natural language, are frequently termed “agent evaluations.” To illustrate, consider an item that requires the generation of a protein structure. This could feasibly be done directly through autoregressive token generation from a language model, by writing a Python program, or by utilizing a biological tool in a virtual environment.

An agentic solver can be thought of as a sequence of intermediate states in which the solver performs a sequence of intermediate actions before producing a final output, and the final candidate solution is then generated from the terminal state. A transition between intermediate states may be constituted by a variety of computational processes, such as planning in natural language, writing a program in a programming language, or using a tool. The agentic solver can be thought of as a solver with a partially observable internal process.

Recent work by Paskov et al. develops a set of practical considerations for designing and interpreting agentic biological evaluations, addressing the upstream question of how evaluations should be structured to produce meaningful evidence; we address the complementary downstream question of how the evidence produced by existing evaluations should be measured and reported on a common scale (Paskov, Lee, Brady, & Worland, 2026).

### Measuring Difficulty and Ability with IRT

Item response theory was established in educational and psychological measurement and has recently been applied to the evaluation of LLM. Lalor et al. showed that IRT can be adapted from psychometrics to AI evaluation by estimating latent item difficulty and subject ability on language benchmarks, establishing a measurement-based alternative to raw accuracy . Lalor et al. further demonstrated that these latent difficulty estimates can be recovered from artificial crowds of neural models and used to identify more informative benchmark items, motivating our extension of IRT to dual-use biological capability evaluation .(Lalor, Wu, & Yu, 2016)(Lalor, Wu, & Yu, 2019)

The foundational model in item response theory is the one-parameter logistic model (1PL), which assumes that the probability of a correct response is a function of a single item parameter, difficulty, and a single solver parameter, ability. The 1PL model assumes that all items discriminate equally. Under this assumption, the sufficient statistic for item difficulty is the marginal proportion correct, transformed to the logit scale.

The two-parameter logistic model (2PL) relaxes the equal-discrimination assumption by introducing a discrimination parameter for each item. Items with high discrimination have steep response curves and contribute more information to the ability estimate. Solvers just below the difficulty threshold fail, while models just above it succeed. Items with low discrimination are noisy: even weak models sometimes pass, and strong models sometimes fail. When the 2PL differs from the 1PL, the difference reflects how strongly items separate stronger models from weaker ones. 1PL is a special case of 2PL, with all discriminations set to 1. 2PL imposes stronger assumptions on the data but yields more information.

Figure A.1. Item Response Curve Example

![](data:image/png;base64...)

For each model and item , we compute the share of epochs that produced the expected correct answer, binarized with a 0.5 cutoff, . This cutoff is a practical choice to compare models that have been run on differing numbers of epochs, and all results are interpreted accordingly. Aggregate accuracy treats all items as equivalent.

Under this aggregation, all items contribute the same measurement, even though they may provide different information as to both the item’s difficulty and the solver’s ability. Item response theory improves on this by placing items and models on a common latent scale. The one-parameter logistic model (1PL),

where is the ability of model and is the difficulty of item , and is the logistic function. When , the solveris expected to answer the item correctly with probability 0.5. This makes it possible to compare models directly to items and even when they were not evaluated on identical subsets of items, provided the shared items anchor the scale.

A difficulty estimate, however, still leaves an important confound: an item may appear difficult because it is poorly written, ambiguously scored, underspecified, or infeasible for any solver. For that reason, this paper emphasizes the two-parameter logistic (2PL) model.

)

where the discrimination parameter, captures how the probability of a correct response changes as model ability increases near the item’s difficulty level. An item with a higher probability of success for stronger models than for weaker ones produces a steeper response curve and thus higher discrimination. By contrast, an item that is ambiguous, incoherent, poorly scored, or otherwise weakly related to the latent capability will tend to have lower discrimination, because differences in model ability translate less consistently into differences in observed performance.

We score refusals as incorrect because they do not produce the expected solution and therefore do not satisfy the item’s scoring rule. A refusal can reflect several different underlying processes: lack of capability, lack of confidence, safety training, prompt sensitivity, or recognition that the requested task is hazardous. As a result, refusals introduce variance into the response matrix. They may bias downward the estimated ability of models that are more likely to withhold answers, particularly on dangerous-capability items. At the same time, a refusal may itself contain information relevant to dangerous capability, indicating recognition of a biologically hazardous request.

The estimates reported here should be interpreted as measures of expressed benchmark performance under current model policies. The two-parameter logistic (2PL) model is fit using *py-irt’s* hierarchical Bayesian specification, with parameters estimated by stochastic variational inference under the evidence lower bound objective (Lalor & Rodriguez, 2023). See Lalor et al. for variational inference for IRT estimation (Lalor, Wu, & Yu, 2019).

One of the assumptions in a unidimensional IRT model, as described above, is the assumption that the dataset only contains a single latent dimension. This assumption maintains the logical coherence of the model—if a dataset were to be measuring multiple latent traits, the confounding latent measurement could not cleanly measure either trait. While our pooled benchmark corpus is undoubtedly heterogeneous, we use the IRT model in a descriptive rather than strongly psychometric sense. We do not interpret the latent parameters as measuring a single kind of biological capability; rather, we use them to summarize relative performance on this dataset. The common scale is a practical measurement device for comparing models, items, and baselines within the pooled corpus, not as evidence that all items reflect a single underlying real-world trait—which, following our validity argument, cannot be validated anyway. We retain a unidimensional specification because it provides a simpler and more interpretable model for descriptive benchmarking, while the taxonomy and supplementary analyses are used to expose important heterogeneity within the corpus.

## A Taxonomy for Assessing Benchmark Items

In this section, we propose item labels that are associated with variation in observed performance in ways that improve the interpretability of benchmarks. Labels should be sufficiently generalizable to apply to every item while maintaining sufficient separability and relevance to provide the analyst with interpretable information. For instance, a label that is fully separable but requires domain-specific information to apply will not provide a generalizable structure. Likewise, a label that is not separable (applying broadly to all or most items) will provide little or no discriminating information about the item. A further consideration is the role of the labeling procedure itself. We seek to develop a procedure that uses an LLM to generate reproducible, scalable taxonomy labels, with the synthesis and judgment provided by the analyst downstream of the LLM-derived text-based evidence.[[7]](#footnote-8)

The following taxonomy provides labels for item input and output: *Information Loci*, *Information Modality*, and *Output Modality*. It also provides a theoretical framework for measuring solvers' latent abilities using the label “*Inferential Direction”*. Inferential Direction is a hypothesized requirement of the solver to provide a solution.

### Inferential Direction

*Inferential Direction* characterizes the logical relationship between the input, , and the expected output, . The Inferential Direction label hypothesizes the reasoning structure a solver must follow to provide a solution.

* *Forward:*the item supplies causes, conditions, inputs, or antecedents and asks the AI to predict effects, outcomes, products, or consequences.
* *Backward:*the item provides effects, outcomes, observations, or end states and asks the AI to identify causes, conditions, inputs, or antecedents.
* *Undirected:* the item does not require traversal of a directional relationship or execution of a defined procedure. The operation is associative, classificatory, or recognitional.

The distinction between reasoning from causes to effects and reasoning from effects to causes has been explored in several contexts. In the cognitive science of expertise, Larkin, McDermott, Simon, and Simon demonstrated that experts and novices in physics differ in the direction in which they reason: experts work forward from givens to unknowns, while novices work backward from unknowns to givens (Larkin, McDermott, Simon, & Simon, 1980). More recently, Ren et al. showed that large language models exhibit a directional asymmetry in planning tasks, performing worse when required to reason backward from a goal state than forward from an initial state—a bias the authors attribute to the autoregressive structure of token generation (Ren, Ichter, & Majumdar, 2024). *Inferential direction* is a hypothesized requirement of items that may influence the performance variance across solvers of varying capability and on items of varying difficulty.

### Information Loci

The second label, Information Locus, distinguishes where the information required for a correct answer is located. Categories are not mutually exclusive, as a given item may require information from multiple loci.

* *Given:*information is contained in the input
* *Prior:* information must be available a priori
* *Posterior:* information must be retrieved from an outside source

### Information Modality

Next, *Information Modality* captures how information is represented.

* *Text*
* *Image*
* *Table*

### Output Modality

Finally, *Output Modality* describes the output that constitutes a solution to the item. Four types are identified and are treated as mutually exclusive; the same input requiring different output should be considered a distinct item.

* *Selection:* choose from provided options (multiple choice, true/false, matching, ranking).
* *Value:* produce a specific factual or numeric answer (short answer, a computed quantity).
* *Generation:* produce output whose semantic content constitutes the answer.
* *Artifact:* produce an output which has certain characteristics (image, file, protein).

## Applying the Taxonomy

Multiple output types can be applied to an input type. For example, an *Extraction* task may take the form of *Selection* (choose from a list of options)OR *Value* (provide the exact answer) OR *Generation* (generate text that means the same thing as the answer) OR *Artifact* (generate a file whose attributes are sufficient for the answer). However, not every output type is appropriate for every input type. For instance, requiring a solver to generate an *Artifact* (say, a file) containing the answer to an *Undirected* item may entail unnecessary steps for the solver and partly assess its ability to handle file I/O. The inclusion of *Artifact* is intended to encompass agent evaluations that assess agents' ability to carry out a task and score the outcomes of their work. However, the dataset of analysis in this report does not include any instances of *Artifacts*.

Each item in the corpus therefore receives five labels: an *Inferential Direction*, *Information Loci*, *Information Modality*, *Output Modality,* and *Domain*.

Each of the 8,146 items was labeled with an ensemble of GPT-5.5 and Gemini 3.1 Pro. Both models returned two structured taxonomy assessments per item (four responses total), which were merged by majority vote—with backward inferential direction kept if tagged by any response—before converting the consensus record into final taxonomy labels.

### Inter-Rater Reliability Study

To verify the quality of the labels generated by the LLM, we conducted an inter-rater reliability study. Two experts, selected for their experience in biosecurity and AI evaluation, labeled 101 items stratified by benchmark and binned IRT difficulty. The experts were blind to all other aspects of each item, including each other’s labels, and were asked to assign *Inferential Direction* *and Information Loci*, based on the item’s complete input and expected output, according to the definitions and logic developed in this section. The taxonomy, schema, and prompt design were developed through iterative refinement on a stratified sample of benchmark items, with successive revisions informed by failure analysis of ambiguous or inconsistently labeled cases and targeted adjustments to reduce over-labeling and improve category consistency through manual review.

Table A.1. Inter-Rater Reliability Study Summary

|  |  |  |  |  |  |
| --- | --- | --- | --- | --- | --- |
| Comparison | Dimension | Overlap Agreement | Macro Jaccard | Exact  Agreement | Exact- Kappa |
| RATER 1 vs RATER 2 | Information source | 94.4% | 91.6% | 83.2% | 0.887 |
| RATER 1 vs RATER 2 | Inferential direction | 94.4% | 92.1% | 85.1% | 0.888 |
| RATER 1 vs LLM | Information source | 92.1% | 88.8% | 78.2% | 0.841 |
| RATER 1 vs LLM | Inferential direction | 82.2% | 76.2% | 66.3% | 0.644 |
| RATER 2 vs LLM | Information source | 90.4% | 86.3% | 73.3% | 0.807 |
| RATER 2 vs LLM | Inferential direction | 82.5% | 76.7% | 68.3% | 0.650 |

Table A.1 reports overlap agreement, macro Jaccard similarity, exact agreement, and exact kappa to capture both partial and exact correspondence between labels. Overlap agreement measures the share of item-label assignments that overlap across raters, while macro Jaccard summarizes average set overlap at the item level. Exact agreement reports the share of items for which the full label set matches exactly. Exact kappa adjusts that exact-match rate for chance agreement and is therefore our most stringent summary of correspondence. Agreement between the two expert raters provides the benchmark for human consistency, while lower agreement between experts and the LLM reflects the fact that the model applies the taxonomy without the full contextual judgment, domain background, and case-specific interpretation available to trained human annotators.

Table A.2. Inter-Rater Reliability Study One-Hot Binary Metrics

|  |  |  |  |  |  |  |
| --- | --- | --- | --- | --- | --- | --- |
| Comparison | Dimension | Human Positives | LLM Positives | Kappa | F1 | Accuracy |
| RATER 1 vs LLM | Inferential direction: Forward | 52 | 60 | 0.562 | 0.804 | 0.782 |
| RATER 2 vs LLM | Inferential direction: Forward | 59 | 60 | 0.611 | 0.840 | 0.812 |
| RATER 1 vs LLM | Inferential direction: Backward | 61 | 57 | 0.593 | 0.831 | 0.802 |
| RATER 2 vs LLM | Inferential direction: Backward | 64 | 57 | 0.569 | 0.826 | 0.792 |
| RATER 1 vs LLM | Inferential direction: Undirected | 31 | 35 | 0.730 | 0.818 | 0.881 |
| RATER 2 vs LLM | Inferential direction: Undirected | 30 | 35 | 0.706 | 0.800 | 0.871 |
| RATER 1 vs LLM | Information source: Given | 71 | 59 | 0.702 | 0.892 | 0.861 |
| RATER 2 vs LLM | Information source: Given | 73 | 59 | 0.657 | 0.879 | 0.842 |

Table A.2 reports accuracy, F1, and Cohen’s kappa for each one-hot taxonomy label to characterize agreement between each human rater and the LLM at the binary category level. Accuracy is the proportion of items on which the human rater and the LLM give the same binary label. F1 summarizes agreement on the positive class by combining precision and recall and is useful when positive labels are less common than negatives. Cohen’s kappa adjusts observed agreement for the level of agreement expected by chance given the marginal label frequencies, but it can be sensitive to prevalence and marginal imbalance. These metrics distinguish raw agreement from agreement on positive cases and from agreement beyond chance, providing a more complete view of label correspondence than any single statistic alone. Table A.2 reveals heterogeneity in the correspondence between human and LLM labels, particularly by inferential direction. Notably *backward* and *forward* inference achieved lower kappa numbers than *undirected,* which indicates a noisier signal, and more a conservative interpretation of these labels.

### Testing Statistical Significance of Taxonomy Labels

To test whether inferential direction contributes information beyond other item characteristics, we estimate item-level ordinary least squares regressions with accuracy, 2PL discrimination, , and 2PL difficulty, , as outcomes. Forward and backward are non-exclusive binary indicators, so items labeled with both have both indicators set to one; undirected is the omitted reference category. Information loci and modality are also modeled as non-exclusive indicators. Selection is the reference output modality, Biology is the reference domain, and standard errors are clustered by benchmark. Coefficients are interpreted directly in the units of each outcome, conditional on the other included taxonomy labels and domain.

Where we set . We use a linear regression so that the coefficients can be interpreted directly in units.[[8]](#footnote-9) Table 2 provides an overview of the regression coefficients. The results indicate that inferential direction remains associated with item performance even after accounting for information locus, modality, output form, and domain. Relative to undirected items, forward items are associated with lower accuracy and greater estimated difficulty, and backward items are associated with an even larger decrease in accuracy and a larger increase in difficulty. This pattern is consistent with the descriptive result that backward-inference items occupy a harder region of the benchmark landscape for current models. The regression also suggests that posterior-information items are associated with lower accuracy, greater difficulty, and lower discrimination, while value-output items are associated with higher accuracy, lower difficulty, and higher discrimination relative to selection outputs. Overall, these results support the interpretation that inferential direction remains a meaningful descriptive dimension of item variation, with backward inference corresponding to the most challenging items in the corpus after conditioning on the other observed item characteristics.

Table A.3. Taxonomy Regression Analysis Coefficient Table

|  |  |  |  |  |
| --- | --- | --- | --- | --- |
| Taxonomy | Label | Accuracy | 2PL Beta | 2PL Alpha |
| Inferential Direction | Forward vs Undirected | \*\*\* -0.073 | \*\*\* 0.716 | -0.090 |
|  | Backward vs Undirected | \* -0.103 | \* 0.915 | -0.056 |
| Information Loci | Prior | -0.042 | 0.280 | \*\* 0.474 |
|  | Posterior | \* -0.183 | \* 1.972 | \*\*\* -0.555 |
|  | Text | -0.287 | \* 3.139 | -0.463 |
| Information Modality | Image | -0.000 | 0.166 | -0.225 |
|  | Table | 0.020 | -0.176 | 0.207 |
|  | Generation vs Selection | 0.007 | -0.232 | \* 0.358 |
| Output Modality | Value vs Selection | \* 0.093 | \* -0.631 | \*\*\* 0.629 |
|  | Artifact vs Selection | 0.016 | -0.186 | 0.027 |
|  | Chemistry vs Biology | 0.056 | -0.301 | 0.112 |
| Domain | Physics vs Biology | \* 0.076 | -0.488 | 0.104 |
|  | Math vs Biology | \*\*\* 0.168 | \*\*\* -1.211 | -0.011 |

NOTE: Coefficients of each taxonomy-labeled subset’s association with accuracy, , and , and pertain to p-values less than or equal to 0.1, 0.05, and 0.01, respectively.

# Appendix B: Additional Results

Figure B.1. Estimated Accuracy by Ability and Difficulty![](data:image/png;base64...)

Table B.1. Gemini Generation Delta by Construct

|  |  |  |  |  |  |  |  |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Label | Label | N | 2.5 Pro | 3.0 Pro | 3.1 Pro |  |  |
| Inferential Direction | Forward only | 1666 | 0.83 | 0.85 | 0.86 | 0.02 | 0.01 |
|  | Backward only | 316 | 0.65 | 0.71 | 0.74 | 0.06 | 0.03 |
|  | Forward and backward | 3244 | 0.61 | 0.66 | 0.71 | 0.05 | 0.04 |
|  | Undirected | 2892 | 0.78 | 0.79 | 0.81 | 0.01 | 0.03 |
| Information Loci | Prior | 7905 | 0.72 | 0.75 | 0.78 | 0.03 | 0.03 |
|  | Given | 4943 | 0.69 | 0.73 | 0.77 | 0.04 | 0.04 |
|  | Posterior | 550 | 0.46 | 0.48 | 0.58 | 0.02 | 0.10 |
| Information Modality | Text | 8113 | 0.72 | 0.75 | 0.78 | 0.03 | 0.03 |
|  | Image | 637 | 0.65 | 0.70 | 0.72 | 0.05 | 0.02 |
|  | Table | 37 | 0.83 | 0.82 | 0.84 | -0.01 | 0.01 |
| Output Modality | Selection | 4316 | 0.68 | 0.73 | 0.76 | 0.05 | 0.04 |
|  | Generation | 2082 | 0.68 | 0.68 | 0.72 | 0.00 | 0.04 |
|  | Value | 1717 | 0.87 | 0.88 | 0.89 | 0.01 | 0.01 |
|  | Artifact | 4 | 0.82 | 0.60 | 0.80 | -0.23 | 0.20 |

Figure B.2. Wright Map Stacked by Benchmark![Chart, surface chart  AI-generated content may be incorrect.](data:image/png;base64...)

Figure B.3. Taxonomy Accuracy by Domain![](data:image/png;base64...)

Figure B.4. Taxonomy Item Count by Domain![](data:image/png;base64...)

Figure B.5. Inferential Direction x Input and Output Modalities Accuracy ![](data:image/png;base64...)

Figure B.6. Inferential Direction x Input and Output Modalities Item Counts![](data:image/png;base64...)

Table B.2. Benchmark Release Dates and Public Availability

|  |  |  |  |
| --- | --- | --- | --- |
| Benchmark | Release Date | Public Availability | Models Postdating Benchmark |
| MMLU Bio | 9/7/20 | Public | 45 |
| MMLU Chem | 9/7/20 | Public | 45 |
| GPQA Bio | 11/20/23 | Public | 44 |
| GPQA Diamond Physics | 11/20/23 | Public | 44 |
| GPQA Diamond Bio | 11/20/23 | Public | 44 |
| GPQA Physics | 11/20/23 | Public | 44 |
| GPQA Diamond Chem | 11/20/23 | Public | 44 |
| GPQA Chem | 11/20/23 | Public | 44 |
| WMDP Bio | 3/5/24 | Public | 43 |
| WMDP Chem | 3/5/24 | Public | 43 |
| MMLU Pro Bio | 5/15/24 | Public | 38 |
| MMLU Pro Chem | 5/15/24 | Public | 38 |
| Lab-Bench Table | 7/14/24 | Public | 38 |
| Lab-Bench Protocol | 7/14/24 | Public | 38 |
| Lab-Bench Sequence | 7/14/24 | Public | 38 |
| Lab-Bench Figure | 7/14/24 | Public | 38 |
| Lab-Bench Cloning | 7/14/24 | Public | 38 |
| Lab-Bench LitQA | 7/14/24 | Public | 38 |
| Lab-Bench DBQA | 7/14/24 | Public | 38 |
| Lab-Bench Supp | 7/14/24 | Public | 38 |
| BioLP Bench | 8/8/24 | Public | 34 |
| VCT Multimodal | 4/21/25 | Public | 17 |
| VCT | 4/21/25 | Public | 17 |
| WCBB |  | Private |  |
| MBCT |  | Private |  |
| HPCT |  | Private |  |

Table B.3. AI Model Release Dates

|  |  |
| --- | --- |
| Model | Release Date |
| GPT-4 | 3/14/23 |
| GPT-3.5 Turbo | 1/25/24 |
| Claude 3 Haiku | 3/7/24 |
| GPT-4 Turbo | 4/9/24 |
| Llama 3 70B | 4/18/24 |
| Llama 3 8B | 4/18/24 |
| GPT-4o | 5/13/24 |
| GPT-4o Mini | 7/18/24 |
| Llama 3.1 405B | 7/23/24 |
| Llama 3.1 70B | 7/23/24 |
| Llama 3.1 8B | 7/23/24 |
| DeepSeek V3.1 (API) | 8/21/24 |
| Claude 3.5 Haiku | 10/22/24 |
| Llama 3.2 90B | 10/24/24 |
| Llama 3.2 11B | 10/24/24 |
| Llama 3.2 3B | 10/24/24 |
| Llama 3.2 1B | 10/24/24 |
| Llama 3.3 70B | 12/6/24 |
| o1 | 12/17/24 |
| o3-mini | 1/31/25 |
| DeepSeek V3 | 3/24/25 |
| Gemini 2.5 Pro | 3/25/25 |
| Llama 4 Maverick 17B | 4/5/25 |
| Llama 4 Scout 17B | 4/5/25 |
| Claude Sonnet 4 | 4/14/25 |
| GPT-4.1 | 4/14/25 |
| o3 | 4/16/25 |
| o4-mini | 4/16/25 |
| Claude Opus 4 | 5/14/25 |
| DeepSeek R1 | 5/28/25 |
| Gemini 2.5 Flash | 6/17/25 |
| Claude Opus 4.1 | 8/5/25 |
| GPT-5 | 8/7/25 |
| GPT-5 Nano | 8/7/25 |
| GPT-5 Mini | 8/7/25 |
| GPT-OSS 120B | 8/13/25 |
| Claude Sonnet 4.5 | 9/29/25 |
| Claude Haiku 4.5 | 10/15/25 |
| GPT-5.1 | 11/12/25 |
| Gemini 3.0 Pro | 11/18/25 |
| GPT-5.2 | 12/11/25 |
| Claude Opus 4.6 | 2/5/26 |
| GPT-5.3 Codex | 2/5/26 |
| Gemini 3.1 Pro | 2/19/26 |
| GPT-5.4 | 3/5/26 |

# Abbreviations

AI — artificial intelligence

LLM — large language model

NLP — natural language processing

IRT — item response theory

1PL — one-parameter logistic model

2PL — two-parameter logistic model

— item information as estimated by 2PL

— item difficulty as estimated by 2PL

— model ability as estimated by 2PL

VCT — Virology Capabilities Test

HPCT — Human Pathogen Capabilities Test

MBCT — Molecular Biology Capabilities Test

# References

Borsboom, D. J., Mellenbergh, G., & Heerden, J. v. (2004). The concept of validity. *Psychological Review*.

Cronbach, L. J., & Meehl, P. E. (1955). Construct Validity in Psychological Tests. *Psychological Bulletin*, 52(4):281–302.

Dev, S., Paskov, P., Sloan, A., Wei, K., Nascimento de Lima, P., Chowdhury, S., . . . Marcellino, W. (2026). Simpler Is Better for Autograders. *RAND Corporation*.

Dev, S., Teague, C., Ellison, G., Brady, K., Lee, Y.-C. J., Gebauer, S. L., . . . Salas, A. (2025). *Toward Comprehensive Benchmarking of the Biological Knowledge of Frontier Large Language Models.* RAND Corporation.

Götting, J., Medeiros, P., Sanders, J. G., Li, N., Phan, L., Elabd, K., . . . Donoughe, S. (2025). *Virology Capabilities Test (VCT): A Multimodal Virology Q&A Benchmark.* Retrieved from https://www.virologytest.ai

Haupt, A., & Brynjolfsson, E. (2025). AI Should Not Be An Imitation Game: Centaur Evaluations. *42nd International Conference on Machine Learning*.

Jacobs, A. Z., & Wallach, H. (2021). Measurement and Fairness. *Proceedings of the 2021 ACM Conference on Fairness, Accountability, and Transparency (FAccT ’21)*.

Lalor, J. P., & Rodriguez, P. (2023). py‑irt: A Scalable Item Response Theory Library for Python. *INFORMS Journal on Computing*, 5–13.

Lalor, J. P., Wu, H., & Yu, H. (2016). Building an Evaluation Scale using Item Response Theory. *Proceedings of the 2016 Conference on Empirical Methods in Natural Language Processing (EMNLP 2016)*, 648–657.

Lalor, J. P., Wu, H., & Yu, H. (2019). Learning Latent Parameters without Human Response Patterns: Item Response Theory with Artificial Crowds. *Proceedings of the 2019 Conference on Empirical Methods in Natural Language Processing and the 9th International Joint Conference on Natural Language Processing (EMNLP‑IJCNLP 2019).*

Larkin, J., McDermott, J., Simon, D. P., & Simon, H. A. (1980). EXPERT and NOVICE PERFORMANCE in SOLVING PHYSICS PROBLEMS. *Science 208(4450)*, 1335–1342.

Paskov, P., Lee, J., Brady, K., & Worland, A. (2026). Measuring Biological Capabilities and Risks of AI Agents. *RAND Corporation*.

Raji, I. D., Bender, E. M., Paullada, A., Denton, E., & Hanna, A. (2021). AI and the Everything in the Whole Wide World Benchmark. *Advances in Neural Information Processing Systems (NeurIPS)*.

Ren, A. Z., Ichter, B., & Majumdar, A. (2024). Thinking Forward and Backward: Effective Backward Planning with Large Language Models. *arXiv:2411.01790v1*.

Salaudeen, O., Reuel, A., Ahmed, A., Bedi, S., Robertson, Z., Sundar, S., . . . Koyejo, S. (2025). Measurement to Meaning: A Validity-Centered Framework for AI Evaluation. *NeurIPS 2025 Workshop on Evaluating the Evolving LLM Lifecycle*.

SecureBio. (2026). *Uplift Studies*. Retrieved from https://securebio.org/benchmarks/uplift/

UK AI Security Institute. (2026). *Inspect AI: Framework for Large Language Model Evaluations*. Retrieved from Inspect: https://inspect.aisi.org.uk

# About the Authors

*Grant Ellison* is a research assistant at RAND. He conducts research on emerging technologies, assessing the applications of artificial intelligence in science and research. He holds a BS in economics.

*Jeffrey Lee* is a research scientist at RAND. He conducts research on risks at the intersection of artificial intelligence and biology. He holds a Ph.D. in molecular biology.

*Barbara Del Castello* is an associate physical scientist at RAND. She conducts research at the intersection of biotechnology, emerging technology, and security. She holds a Ph.D. in genetics.

*Sunishchal Dev* is a researcher at RAND. He conducts research on AI capability evaluations for governance and safety. He holds a BBA in business administration.

*Kyle Brady* is a technical researcher at RAND focused on AI evaluations. He holds a Ph.D. in electrical engineering.

1. A saturated benchmark is solved at high reliability and therefore provides less discriminating information. We define saturation as the share of samples a model is expected to solve with at least a chosen level of reliability. [↑](#footnote-ref-2)
2. The terms item and sample are used interchangeably, with a preference for the word item. [↑](#footnote-ref-3)
3. We will hereafter refer to AI interchangeably with “solver” to clarify the relation between AI and a benchmark item, as well as to refer to different types of solvers under one unifying term. [↑](#footnote-ref-4)
4. Release date is converted to years since the earliest model release, and the conditional 90th percentile of model ability is modeled as a monotone saturating exponential curve: $Q\_{0.90}\left(θ\_{j} \right| t\_{i}) = b + A (1 -σ(-r (t\_{i} - t\_{0})))$, where $θ\_{j} $is the model’s estimated 2PL ability, $t\_{i}$ is release time in years, $b $is the baseline level, $A>0$ is the total saturating gain, and $r>0 $is the rate of improvement. The parameters are estimated by minimizing the 90th-quantile quantile loss. This curve is therefore a smoothed estimate of the upper tail of the model distribution: roughly, the level below which 90% of models fall at a given release date. The solid portion of the curve shows the fitted 90th-percentile frontier over the observed release-date range. The dashed segment extends the same fitted curve one year beyond the latest observed model release. The uncertainty band around the frontier is calculated by a nonparametric bootstrap over models. The model-release-date and ability pairs are resampled with replacement, the same 90th-quantile saturating-exponential model is refit to each bootstrap sample, and the fitted frontier is evaluated across the plotting grid. The displayed band is the pointwise 2.5th to 97.5th percentile range of those bootstrap frontier curves. [↑](#footnote-ref-5)
5. Although the fitted frontier is somewhat influenced by a low-ability 2023 observation, the broader upward pattern remains evident across the full set of post-2023 frontier models, so this point should be interpreted as contributing uncertainty at the left edge of the trend rather than driving the substantive conclusion. Removal of this point provided a steeper curve, with higher one-year extrapolative estimates. [↑](#footnote-ref-6)
6. Inferential directions are not mutually exclusive—multiple often apply to the same question. [↑](#footnote-ref-7)
7. Other approaches to taxonomy labelling could readily be conceived and validated according to many purposes. [↑](#footnote-ref-8)
8. For example, Forward is associated with an increase of 0.716 $β\_{2PL}$ logits, adjusting for other taxonomized characteristics of each item, on average, over all 45 AI models. [↑](#footnote-ref-9)