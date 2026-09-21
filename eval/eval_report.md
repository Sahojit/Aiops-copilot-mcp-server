# diagnose_incident eval report

Ran 18 labeled synthetic incidents against the mocked RCA service (`http://localhost:8001`), calling it directly over HTTP (bypassing MCP transport).

**Overall accuracy: 22.2%** (4/18 correct)

## Per-class precision / recall

| Root cause | Precision | Recall | Support |
|---|---|---|---|
| bad_deploy_config_change | n/a | 0.00 | 2 |
| cache_stampede | 0.00 | 0.00 | 2 |
| cpu_throttling | 0.00 | 0.00 | 2 |
| database_connection_pool_exhaustion | 0.50 | 0.67 | 3 |
| disk_io_saturation | 0.00 | 0.00 | 2 |
| dns_resolution_failure | 1.00 | 0.50 | 2 |
| downstream_service_timeout | 0.00 | 0.00 | 3 |
| memory_leak | 0.33 | 0.50 | 2 |

## Discussion

This eval measures `rca_mock.py`, not a real classifier — and it shows. With 8 root-cause classes, random guessing would score about 12.5% accuracy, and the observed 22.2% is in that same range, because the mock picks `root_cause` via `random.choice()` and never looks at the `metrics` payload at all. The per-class numbers bounce around based on which labels happened to get lucky matches in this run, not because the mock is better at diagnosing some root causes than others.

This result is expected and, per the project's ground rules, reported honestly rather than reframed to look better: at this stage there is no real signal to evaluate. This eval becomes meaningful once `RCA_SERVICE_URL` points at the real upstream RCA service — rerunning it then, unmodified, is the actual test of whether diagnose_incident works.
