# ITF planning benchmark

## Environment

| what | value |
|---|---|
| python | 3.10.12 |
| machine | x86_64, 8 CPUs |
| system | Linux-6.8.0-138-generic-x86_64-with-glibc2.35 |
| repetitions (warm) | 5 |
| artifacts | none |

## Summary

| target | roles | steps | warm ms | cold s | max gate ms | peak MiB | thresholds | note |
|---|---|---|---|---|---|---|---|---|
| test/integration/targets/localhost.itf.yaml | 4 | 1 | 2.81 | 0.21 | 0.13 | 0.24 | ok |  |
| test/integration/targets/serial/serial.itf.yaml | 2 | 1 | 1.88 | 0.16 | 0.11 | 0.13 | ok |  |
| test/integration/targets/observability/qnx.itf.yaml | 12 | 6 | 8.82 | 0.34 | 0.28 | 0.57 | ok |  |
| scopes-10 | 42 | 11 | 4.38 | 0.18 | 0.70 | 0.15 | ok |  |
| scopes-50 | 202 | 51 | 12.28 | 0.20 | 2.60 | 0.66 | ok |  |
| scopes-100 | 402 | 101 | 27.38 | 0.22 | 6.34 | 1.32 | ok |  |
| chain-10 | 1 | 10 | 2.18 | 0.18 | 0.31 | 0.24 | ok |  |
| chain-50 | 1 | 50 | 7.02 | 0.17 | 1.70 | 1.06 | ok |  |
| chain-100 | 1 | 100 | 14.17 | 0.20 | 5.22 | 2.13 | ok |  |
| deep-10 | 10 | 0 | 2.75 | 0.21 | 0.21 | 0.25 | ok |  |
| deep-50 | 50 | 0 | 11.79 | 0.25 | 1.33 | 1.23 | ok |  |
| deep-100 | 100 | 0 | 17.47 | 0.22 | 2.20 | 2.52 | ok |  |
| wide-10 | 11 | 10 | 3.02 | 0.23 | 0.30 | 0.22 | ok |  |
| wide-50 | 51 | 50 | 10.61 | 0.19 | 1.73 | 0.92 | ok |  |
| wide-100 | 101 | 100 | 17.36 | 0.20 | 2.74 | 1.84 | ok |  |

## Warm plan by phase (median ms)

| target | load | declare | compile | octo_gate1 | octo_gate2 | dry_run | artifacts |
|---|---|---|---|---|---|---|---|
| test/integration/targets/localhost.itf.yaml | 0.34 | 1.86 | 0.05 | 0.13 | 0.10 | 0.06 | 0.00 |
| test/integration/targets/serial/serial.itf.yaml | 0.32 | 1.01 | 0.05 | 0.10 | 0.11 | 0.04 | 0.00 |
| test/integration/targets/observability/qnx.itf.yaml | 0.93 | 6.28 | 0.36 | 0.28 | 0.25 | 0.19 | 0.01 |
| scopes-10 | 0.96 | 0.99 | 0.24 | 0.70 | 0.44 | 0.42 | 0.01 |
| scopes-50 | 2.85 | 0.86 | 0.92 | 2.60 | 1.48 | 1.88 | 0.01 |
| scopes-100 | 6.33 | 1.09 | 2.03 | 6.34 | 2.94 | 3.97 | 0.01 |
| chain-10 | 0.29 | 0.98 | 0.07 | 0.07 | 0.31 | 0.14 | 0.01 |
| chain-50 | 0.28 | 3.88 | 0.18 | 0.10 | 1.70 | 0.60 | 0.01 |
| chain-100 | 0.35 | 6.95 | 0.36 | 0.13 | 5.22 | 1.33 | 0.01 |
| deep-10 | 0.47 | 1.47 | 0.06 | 0.21 | 0.05 | 0.08 | 0.01 |
| deep-50 | 1.02 | 7.51 | 0.47 | 1.33 | 0.07 | 0.39 | 0.01 |
| deep-100 | 1.54 | 10.57 | 0.47 | 2.20 | 0.08 | 0.89 | 0.01 |
| wide-10 | 0.59 | 1.22 | 0.10 | 0.28 | 0.30 | 0.15 | 0.01 |
| wide-50 | 1.10 | 5.02 | 0.42 | 0.84 | 1.73 | 0.94 | 0.01 |
| wide-100 | 1.42 | 9.21 | 0.97 | 1.27 | 2.74 | 1.23 | 0.01 |

| phase | what it does |
|---|---|
| load | read the YAML, merge includes and overrides, expand ${NAME} |
| declare | load the packs and the policy, publish their parts |
| compile | turn the target file into claims |
| octo_gate1 | OCTO gate 1: what must exist |
| octo_gate2 | OCTO gate 2: what must happen |
| dry_run | resolve every implementation reference, construct nothing |
| artifacts | write the run directory (per --artifacts) |

## Median share of a warm plan

| phase | share |
|---|---|
| load | 12.1% |
| declare | 53.1% |
| compile | 3.4% |
| octo_gate1 | 7.7% |
| octo_gate2 | 10.1% |
| dry_run | 6.4% |
| artifacts | 0.1% |

## Fresh process (imports included)

| target | import core ms | wall s | peak RSS MiB |
|---|---|---|---|
| test/integration/targets/localhost.itf.yaml | 110.35 | 0.21 | 27.0 |
| test/integration/targets/serial/serial.itf.yaml | 87.89 | 0.16 | 27.1 |
| test/integration/targets/observability/qnx.itf.yaml | 108.38 | 0.34 | 36.6 |
| scopes-10 | 106.85 | 0.18 | 36.6 |
| scopes-50 | 96.91 | 0.20 | 38.1 |
| scopes-100 | 85.44 | 0.22 | 40.6 |
| chain-10 | 91.37 | 0.18 | 40.6 |
| chain-50 | 87.75 | 0.17 | 40.7 |
| chain-100 | 90.96 | 0.20 | 41.8 |
| deep-10 | 121.59 | 0.21 | 41.8 |
| deep-50 | 125.72 | 0.25 | 41.8 |
| deep-100 | 97.63 | 0.22 | 43.2 |
| wide-10 | 131.20 | 0.23 | 43.2 |
| wide-50 | 90.41 | 0.19 | 43.2 |
| wide-100 | 85.62 | 0.20 | 44.2 |

## Thresholds

| measure | warn above | what |
|---|---|---|
| cold_s | 2 | a fresh process plans one target file |
| warm_ms | 250 | a running process plans one target file |
| gate_ms | 100 | one OCTO gate |
| peak_mib | 50 | memory allocated while planning |

No threshold exceeded.
