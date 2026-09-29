version 19
set more off
set scheme stcolor

* DID example: official Stata hospdd repeated cross-sectional data.
* Optional argument: output directory (must already exist).
* Example: do examples/demo.do "C:/analysis/did-output"
args outdir
if `"`outdir'"' == "" local outdir "."
preserve
use "https://www.stata-press.com/data/r19/hospdd.dta", clear
describe satis procedure hospital month

* Hospital and month fixed effects; hospital-clustered standard errors.
didregress (satis) (procedure), group(hospital) time(month)
matrix did_table = r(table)
matrix list did_table
estimates save "`outdir'/didregress_model.ster", replace

* Failure to reject these tests does not prove identification assumptions.
estat ptrends
estat granger
estat trendplots
graph export "`outdir'/didregress_trendplots.png", width(2200) replace
graph save "`outdir'/didregress_trendplots.gph", replace
restore
