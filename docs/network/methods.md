# Method definitions and boundaries

## Functional connectivity

Pearson and Spearman are sample correlations across time. Partial correlation uses a shrinkage covariance estimator through Nilearn. Covariance inputs are normalized by their positive diagonal standard deviations. Fisher-z conversion is explicit. No hidden nuisance regression, GSR, filtering or temporal interpolation is performed on supplied time series; inputs should already have the intended preprocessing.

## Signed graphs

Graph construction retains signed FC. Absolute strength is used for threshold/density/kNN edge selection and maximum spanning forest selection; selected edges retain their original signs. Self-loops are excluded. Cutoff ties are included, so reported realized density may exceed the requested density. MST ties use stable ROI-ID order, not array position.

Strength reports positive, negative and net sums separately. Path-based metrics use positive weights, length=1/weight. Disconnected pairs contribute zero efficiency; reachable mean path length is explicitly labeled. Clustering uses positive Onnela weights normalized by the maximum positive weight. Louvain uses positive edges, resolution 1 and seed 0 with canonical ROI iteration order. This is descriptive community structure.

Exact weighted betweenness is bounded to at most 300 nodes and 10000 positive edges; above that it is explicitly null with a definition explaining why. A missing statistic is not zero.

## Native hypergraphs

FC-profile kNN uses the complete signed FC row with the diagonal set to zero and cosine similarity. A hyperedge comprises its center ROI and selected neighbors; tied cutoff neighbors are retained. Multiscale construction repeats this for declared k values. Identical generated member sets are consolidated with scales and centers preserved.

Custom and template hyperedges retain separate identities even if their memberships coincide. Payloads include binary native incidence in sparse COO, edge records, and per-ROI memberships. Hyperdegree, signed weighted hyperdegree, edge-size distribution, incidence connected components and mean pairwise edge overlap are descriptive metrics. Participation fraction is membership frequency, not a community participation coefficient.

A constructed multi-ROI hyperedge is a representation. It does not establish an irreducible physiological interaction. No causal, biomarker or disease-probability claim is generated.

## Cohort statistics

Every row must represent an independent participant, with a unique ID. Two-group unadjusted comparisons use Welch inference; adjusted comparisons use OLS with HC3 robust standard errors. Complete-case exclusions are reported. BH-FDR is applied across the supplied feature family. Single-participant reports contain no invented group comparison or normative percentile.

## Reproducibility

Each result saves the numeric input hash, source-file hash, actual column selection, matrix meaning, analysis parameters, software version, warnings and ROI identity. The timestamp is expected to differ between runs; numerical arrays and structure metrics should agree. Original anatomy coordinates are stored separately from display layouts.
