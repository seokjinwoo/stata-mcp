version 19
clear all
set more off
sysuse auto, clear
summarize price mpg weight
regress price mpg weight
twoway scatter price weight, title("Auto data: price and weight")
