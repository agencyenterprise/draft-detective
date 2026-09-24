# Fare-Free Transit in Mid-Sized Cities: Early Evidence from Four Pilots

## About This Report

This report examines fare-free bus pilots that four mid-sized U.S. cities ran between 2022 and 2025. It should be of interest to policymakers and other stakeholders. The work was funded by a philanthropic foundation and conducted by the Mobility Policy Center.

## Summary

Ridership rose in all four cities after fares were removed, by between 18 and 31 percent in the first year. Operating budgets absorbed the lost fare revenue in three cities; in the fourth, the transit agency cut evening service to cover it. Riders who gained the most were those who made more than ten trips a week.

## Chapter 1: Introduction

Several mid-sized cities have removed bus fares to raise ridership and cut costs for low-income riders. This report is written for policymakers and practitioners. We asked three questions: how much ridership changed, who gained, and what the pilots cost.

Chapter 2 describes our data and approach. Chapter 3 reports what we found, and Chapter 4 sets out what the findings mean for cities considering a pilot.

## Chapter 2: Data and Approach

We drew on automatic passenger counts for every route in the four cities, a survey of 1,840 riders, and interviews with 22 transit agency staff. We compared ridership on each city's routes before and after fares were removed with ridership over the same months in eight similar cities that kept their fares.

To estimate the effect of fare removal, we fit a difference-in-differences model with route and month fixed effects, clustering standard errors at the city level. The identifying assumption is that ridership in treated and comparison cities would have followed parallel trends absent the pilots, which we test with an event-study specification including leads of the treatment indicator.

We estimate log ridership as a function of the treatment indicator and a vector of covariates, where the coefficient β on the treatment indicator gives the proportional change in ridership. Robustness checks re-estimate the model with synthetic control weights and with a Poisson pseudo-maximum-likelihood estimator; the point estimates move by less than two percentage points.

## Chapter 3: Findings

Ridership rose between 18 and 31 percent in the first year, with the largest rise in the city with the most frequent service. The estimates are statistically significant at the 1 percent level, and the 95 percent confidence intervals exclude zero in all four cities.

Riders who made more than ten trips a week saved an average of $46 a month. In the survey, 62 percent of riders said they had made trips they would not otherwise have made, most often to medical appointments and job interviews.

Transit agency staff told us that boarding times fell once drivers no longer handled fares. Two agencies reported more disputes on board in the first months, which fell as riders grew used to the change.

## Chapter 4: Implications

Cities considering a pilot should budget for the lost fare revenue before they start, since the one agency that did not had to cut evening service. Appendix B describes the model and reports the full estimates for each city.

The gains were largest where buses already came often. A city with infrequent service may see a smaller rise in ridership from removing fares than from running more buses.

## Appendix B: Model Details

The estimating equation is ln(R_rt) = α_r + γ_t + βD_rt + X_rt'δ + ε_rt, where R_rt is ridership on route r in month t and D_rt indicates a fare-free month. Standard errors are clustered by city; with four treated clusters we also report wild cluster bootstrap p-values.
