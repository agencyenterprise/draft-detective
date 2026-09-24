---
name: reproducibility-check
description: Use this skill to extract a research document's main results and classify how reproducible each one is (fully reproducible, reproducible with web search, reproducible with external uploads, or not reproducible) from the information in the paper. Invoke when the user asks whether their results could be reproduced from the document alone, or to assess the reproducibility of a paper's findings.
---

# Task
You are an expert scientific reader and results analyst. You will be given a research document (or a long excerpt of one), and must extract the main results of the document AND determine whether these each of these main results is reproducible given the information provided in the paper.

"Results" are defined as any qualitative, mathematical, or quantitative end-points of an analysis. Things that aren't included in results are assumptions or initial conditions.

The document may be long (e.g., 10,000+ words) and may NOT be cleanly structured into sections labeled as "Results."

## Your goals

1. Read the document holistically, end to end, including any appendices, annexes or supplementary sections. Do not rely solely on section headers.
2. Identify the main results of the paper. "Results" are defined as any qualitative, mathematical, or quantitative end-points of an analysis. Things that aren't included in results are assumptions or initial conditions.
3. Determine the reproducibility class of the result, using the criteria below. Each result gets exactly one of these labels:
    - Fully Reproducible
    - Reproducible with Web Search
    - Reproducible with External Uploads
    - Not Reproducible

   Provide a rationale for this categorization and explain what would be needed to make the result fully reproducible.
4. Describe the result in no more than five sentences
5. Provide the location of the result. This should be a description of the page number, figure number, table number, equation number, etc
6. Provide a descriptive title for the result


## Results extraction guidelines

Results take whatever form the document gives them: a figure, a table, a final equation, an algorithm in pseudo-code, or a numerical statement made in the running text. In general, they are defined as the end-points of some quantitative or qualitative analysis.

An equation counts as a result when the document presents it as an output of its own work — a model, relationship, or expression this work derived, fitted, or calibrated — even when the document then uses it to fit or predict something else. A standard formula taken from elsewhere and used purely as a tool does not.

For the results extraction, we want to extract results and put them within the same section according to their natural grouping within the paper. For example, a table could contain dozens of values, but it should represent a single result. Similarly with figures. Each of these particular results should have a reproducibility category.

Group by the document's own structure, and extract **every** result you find. A figure, a table, and a derived equation each stand as separate results even when they describe one phenomenon between them: a fitted model and the empirical comparison drawn from it are two results, not one. Only merge what the document itself presents as a single unit — a table of dozens of values is one result, as is a multi-panel figure. When you are unsure whether something is a result or part of the method, extract it and let its reproducibility classification carry the judgment; a result omitted from the inventory is invisible to the reader, while one that was arguably methodological is still informative.

## Reproducibility Criteria

- Fully Reproducible (Definition): Methodologies where the logic is fully explained and the necessary data (parameters, equations, prompts, or rubrics) is provided directly within the text or appendices. A coding agent or researcher could replicate these results immediately without external data additions. These studies primarily consist of mathematical models, simulations, and algorithmic pipelines where the "data" consists of algebraic formulas or specific parameters explicitly recorded in the report.

- Reproducible with Web Search (Definition): Methodologies where the logic is fully explained but the necessary data (parameters, equations, prompts, or rubrics) is not provided directly within the text or appendices. However, the data can be easily retrieved with web search.

- Reproducible with External Uploads (Definition): Methodologies where the logic is fully explained but the necessary data (parameters, equations, prompts, or rubrics) is not provided directly within the text or appendices. However, the data consists of public laws, historical documents, or open public datasets that a researcher can easily retrieve with data additions. These studies are largely legal reviews, historical analyses, or quantitative models using large public datasets (like ISO interconnection queues).

- Not Reproducible (Definition): Methodologies where the logic is not fully explained and/or the necessary data (parameters, equations, prompts, or rubrics) or the data cannot be easily obtained. Methodologies that cannot be reproduced even with web search capabilities because they rely on confidential, proprietary, or paid-access data that is not released.

## Choosing between the four classes

Take each result in turn and work in this order.

1. **Is the logic explained well enough to redo the analysis?** Read the whole
   document before deciding, including appendices, annexes and supplementary
   sections: parameters, data tables and generator settings are often deferred
   there on purpose, and a methods section that says "see Appendix A" is not an
   omission. If the procedure is not explained anywhere in the document, the
   result is **Not Reproducible** whatever its data situation.
2. **List what is still missing** to regenerate the result: data, parameters,
   equations, prompts, rubrics.
3. **If nothing is missing, the result is Fully Reproducible.**
4. **Decide what kind of thing is missing.** A missing *procedural detail* is
   not the same as missing data, and it is where this classification most often
   goes wrong:
   - If the step is defined in a source the document cites *and that source is
     openly accessible* -- a published method, the documented default of a named
     package or version, a clause of a freely available standard -- then it can
     be looked up, and the result is at worst **Reproducible with Web Search**.
     A cited source that is itself paid-access or otherwise restricted does not
     settle the step: route it through the availability rule below, the same way
     as any other ingredient a reader cannot obtain.
   - If the step is a convention a competent practitioner in the field would
     resolve the same way -- a unit conversion, a standard estimator's default,
     the usual treatment of a boundary case -- it does not lower the class at
     all. Note it as a caveat in the rationale and classify on the substance.
   - Only a step that is genuinely undetermined, and that no cited source or
     shared convention settles, makes the result **Not Reproducible**.
5. **Otherwise the class is decided by how the missing ingredient can be
   obtained**, not by the fact that something is missing:
   - Individual published values that any reader can reach -- a coefficient from
     an open-access paper, a figure from a public statistical release, a table in
     a freely published standard -- can be looked up: **Reproducible with Web
     Search**. A value that exists only behind a paywall or a restricted licence
     is not "published" in this sense; it belongs in the last bullet.
   - A bulk dataset that is open to any reader -- a public register, a
     government microdata release, an open research dataset -- has to be
     downloaded and loaded: **Reproducible with External Uploads**. Naming the
     source is enough; the document does not have to reproduce the data.
   - Something no reader outside the author team can obtain -- confidential,
     proprietary, paid-access, withheld, or never recorded in the first place:
     **Not Reproducible**.

6. **Say which route you took.** Every result's rationale names what is missing
   and how a reader would obtain it: looked up from a named source, downloaded
   as a dataset, or not obtainable at all. A rationale that stops at "the data
   is not in the document" has not made the classification.

Classify each result against the ingredients that result actually needs. Where
several results share an input, a genuine gap in that input does carry to all of
them -- but say, for each result, which specific ingredient it is missing.
"derived from the preceding unreproducible calculation" is not a classification;
it is one verdict being carried across results by association, and it turns a
single arguable call into a verdict on the whole document.

Not Reproducible means nobody outside the author team could regenerate the
result. It is not the default for a result that depends on something the
document does not itself contain.

## What does not, on its own, make a result irreproducible

These come up often and none of them is a reproducibility deficit:

- **A figure or table that is not rendered.** If you are reading a text
  conversion of the document, images may be absent and a table may have been
  flattened. Judge whether the *result* could be regenerated from the data and
  procedure available, not whether the artifact is displayed to you. When you
  have a way to view images, look at a figure that carries a result before
  classifying it: its axes, legend and annotations often state the values,
  units and conditions the running text leaves out. Say a
  figure's underlying values are missing only when the document neither supplies
  nor points to the data behind it. A plot of something the document's own model
  produces -- a simulated trace, a fitted curve -- is regenerated by running
  that model, so it is as reproducible as the model is.
- **No code.** Analysis code, scripts and notebooks are not required by any of
  the four classes. A procedure described well enough for a competent researcher
  to reimplement is explained, even if no code is published.
- **Reported values being rounded.** The bar is regenerating the result to the
  precision the document reports it at. Rounded coefficients, percentages and
  intervals are how results are normally written up.
- **Effort.** A reader having to fetch sources, rebuild a pipeline, or re-run a
  long simulation does not lower the class. Only what they cannot obtain or
  cannot work out does.
- **A method artifact being evaluated on data you cannot get.** When the result
  *is* a method the document contributes -- an algorithm, a derived equation, a
  fitted model -- classify it on whether a reader could reimplement it from the
  text. Its reproducibility is separate from that of the benchmark or dataset it
  was measured on: a fully specified algorithm evaluated on a confidential
  corpus is a reproducible algorithm and an irreproducible accuracy figure, and
  they are two results with two classes.
- **Stochastic output that cannot be matched bit for bit**, where the document
  fixes the generator, its parameters and its seed. That is reproducible; an
  unstated seed makes the exact draw irreproducible but usually leaves the
  reported summary statistics reproducible.

Conversely, do not talk yourself out of Not Reproducible when it is right: an
unexplained procedure, a withheld dataset, or a control set described only as
"the usual controls" are genuine failures however professional the write-up.

## Reproducibility Requirements

If the result is fully reproducible, it should be detailed enough that a technically literate researcher could reproduce the work. This means:

- **Step-by-step procedures**: Document the exact sequence of steps taken, in order
- **Specific values**: Include exact parameters, hyperparameters, and configurations when available
- **Software specifications**: Note software versions, library versions, and tool specifications when mentioned in the document
- **Data details**: Include specific information about data preprocessing, transformations, and handling
- **Implementation details**: Document any randomization seeds, initialization procedures, or stochastic elements
- **Evaluation specifics**: Include exact definitions of metrics, evaluation procedures, and statistical tests

When important details are truly missing from the provided text (e.g., sample size, exact hyperparameters, full experimental conditions, software versions), explicitly indicate this with phrases like:
- "The exact sample size is not specified in the provided text."
- "Details of the optimization procedure are not specified in the provided text."
- "The software version used is not specified in the provided text."

Do **not** invent or guess specific values or procedures that are not clearly supported by the document.

## Reporting

Report one issue per extracted result, following the conventions defined in the `issues` skill. Title each `Result: <descriptive title> (<reproducibility label>)`, using the labels exactly as written above — e.g. `Result: Canopy vs. surface temperature (Not Reproducible)`.

Every result is reported, reproducible or not, so the issue list is the full inventory. Severity separates the two cases:

- A result that is reproducible — including one reproducible only with web search or with external uploads — is informational: **severity `none`**.
- A result that is **not reproducible** gets a real severity, and you choose it by how much the document's overall goal rests on that result. A central finding the document's conclusions depend on is `high`; a supporting result is `medium`; an incidental one is `low`.

## Report

Write an overall report covering every result:

1. A one-paragraph summary of the document's reproducibility, with counts per class.
2. A table of every result: title, location, and reproducibility label.
3. A short section per result that is not fully reproducible, stating what is missing.
