# Validation benchmarks

The current repository benchmark was run on 100,000 synthetic financial rows with seed `20261031`. On Windows 11, Python 3.15.2 and pandas 3.1.0 it completed in **119.724 seconds** (835 rows/second), with **202.9 MiB** peak traced Python memory, 100,000 accepted rows, zero rejected rows, and zero duplicates. The finance pipeline computes individual check outcomes and timings in the measured run. It uses a hash set for expected O(1) duplicate identity lookups.

Earlier runs of successive code states on Python 3.15.2 recorded **152.975 seconds** with per-row dictionary metrics and timings, **108.737 seconds** before per-check timing was added, and **62.019 seconds** before finance per-check evidence. These single-run measurements are not a controlled comparison. Project documentation also records an older Python 3.14.2 run at **15.436 seconds** (6,478 rows/second, 203.0 MiB). This benchmark covers parsing, profiling, finance validation, and transformation; it does not cover database persistence of per-check validation results.

A reproducible 1k/10k/100k benchmark that isolates validation applicability and per-check persistence, in addition to the existing engine phases, remains to be implemented after the full validation matrix is available.
