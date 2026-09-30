# Alert runbooks

Evaluate conditions every minute using UTC event time. `duration` means the
condition stays true at every evaluation for that period. The sample minimum
avoids paging on tiny lab workloads. Map `#llmops-alerts` to an actual Slack
channel before enabling notification delivery.

## Alert 1

- **Name:** Fast successful request SLO burn
- **Severity / owner / Slack:** critical · on-call application engineer · `#llmops-alerts`
- **Condition / duration:** At least 20 received requests in rolling 30 minutes; more than 0.5% are not successful within 3000 ms; sustained for 10 minutes.
- **SLO / impact:** 99.5% fast successful requests over 28 days. Users see slow or missing answers.
- **First checks:** (1) Compare request count, P95/P99 latency and failures. (2) Find slow or failed `correlation_id` values in `data/logs.jsonl`. (3) Open matching traces and inspect retrieval and generation spans.
- **Mitigation:** Reduce concurrency or roll back a recently changed prompt/model after confirming the affected span; verify latency recovers.

## Alert 2

- **Name:** Elevated request failure rate
- **Severity / owner / Slack:** high · on-call application engineer · `#llmops-alerts`
- **Condition / duration:** At least 20 received requests in rolling 10 minutes; `request_failed / request_received > 2%`; sustained for 5 minutes.
- **Guardrail / impact:** `error_rate_pct_max: 2`. Users receive errors instead of answers.
- **First checks:** (1) Review the `error_type` breakdown. (2) Compare failed request IDs with recent changes. (3) Inspect matching traces for the first failing span.
- **Mitigation:** Roll back the implicated change or route to a known working model/provider; verify the error rate recovers.

## Alert 3

- **Name:** Retrieval answer availability degraded
- **Severity / owner / Slack:** high · on-call RAG engineer · `#llmops-alerts`
- **Condition / duration:** At least 20 retrieval attempts in rolling 15 minutes; fewer than 90% have `tool_success=true`; sustained for 10 minutes. An attempt is a `response_sent` event with `tool_name=retrieval` and boolean `tool_success`.
- **Guardrail / impact:** `retrieval_success_rate_pct_min: 90`. Answers can lack relevant context.
- **First checks:** (1) Compare retrieval success and quality proxy. (2) Inspect affected request IDs and retrieval spans. (3) Check index freshness and retrieval service availability.
- **Mitigation:** Restore the last healthy index or retrieval configuration; verify recovery with fresh requests.

## Error budget

For the 28-day window, let `N` be `request_received` events and `G` be requests
with a correlated `response_sent` within 3000 ms. Target: `G/N >= 0.995`.
Allowed bad requests: `floor(N × 0.005)`. Actual bad requests: `N − G`.
Remaining budget: `floor(N × 0.005) − (N − G)`. For 10,000 requests, 50 can
be bad; if 35 are bad, 15 remain. Wait for in-flight requests to finish before
counting them as bad. The short alert window warns of rapid budget use; final
SLO compliance uses the full 28-day window.
