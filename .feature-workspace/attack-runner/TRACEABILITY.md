# TRACEABILITY — invariant → computation owner → oracle

> Status (WP1): all E1 (offline) rows implemented and gated by `attack-runner/planner/` (47 fixtures + committed mutation test, 0 unexpected survivors). E2/Release rows pending the (now-cleared) PM gate and live runtime evidence.

Work packets are defined in the approved plan. This maps each invariant to the packet
that owns its computation and the acceptance criteria that judge it.

| Invariant                                                                          | Computation owner (packet) | Test oracle (acceptance IDs)                     |
| ---------------------------------------------------------------------------------- | -------------------------- | ------------------------------------------------ |
| Shared normalized I/O contract; status mapped at adapter boundary                  | WP0.1                      | schema review; fixtures exercise every E1 branch |
| One ticket per causal exploit, repo-independent                                    | WP1.1, WP1.2               | E1-01, E1-10, E1-17                              |
| Stable exploit identity survives fingerprint version change                        | WP1.1                      | E1-20                                            |
| Five reconciliation outcomes; ambiguous → triage; party ≠ production               | WP1.2                      | E1-01…E1-05, E1-11, E1-14, E1-18                 |
| One confirmed count per run; replay no-op; eligibility once                        | WP1.3                      | E1-08, E1-09, E1-19                              |
| Valid positive survives non-observation + invalid peers; resolved ticket untouched | WP1.4                      | E1-04, E1-05, E1-06, E1-07, E1-12, E1-13         |
| Determinism; zero side effects                                                     | WP1.5                      | E1-15                                            |
| Unattended ordinary magic-link auth + DKIM pre-redemption suite                    | WP2.1                      | I-01, I-18, I-19, I-20, I-21                     |
| Verified non-admin ordinary session gates attack tools                             | WP2.1, WP2.2               | I-20, I-22                                       |
| Cookie session maintained beyond 15m through full duration                         | WP2.3                      | I-02                                             |
| Settings independently replaceable; unsupported → explicit fail; no secret leak    | WP2.4                      | I-03, I-07, I-12                                 |
| Real spend/time enforcement with reserved reporting time                           | WP2.5                      | I-04                                             |
| Edge block classified; unresolved access = visible failure; no ticket from block   | WP2.6                      | I-16, I-23                                       |
| Linear delivery, reopen, counts, uncertain-write recovery, no duplicate            | WP2.7                      | I-05, I-06, I-09, I-11                           |
| Private evidence store; fail-closed; no public fallback; retention                 | WP2.8                      | I-15, I-17                                       |
| Summary persists every run; bounded reporting; failure ≠ success                   | WP2.9                      | I-10, I-13, I-14                                 |
| One ticket/exploit + one count/run under concurrency and lost ack                  | WP2.10                     | handoff "Concurrent delivery"                    |
| Scheduled/manual workflow, DST, operator coverage, timeout budget                  | WP3.1                      | I-08                                             |
| Final-revision re-run + operational qualification                                  | WP3.2                      | E1-16 + all integration criteria                 |
