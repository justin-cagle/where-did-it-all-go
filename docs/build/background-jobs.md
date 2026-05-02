# Background Jobs

> Source: `DECISIONS.md` — R7 (Background Jobs)

---

## Worker Stack

**ARQ** — Redis-backed, async-native Python worker queue.

---

## Two Worker Pools

| Pool | Workload | Concurrency |
|------|----------|-------------|
| `worker-fast` | Short jobs: event handlers, projection cache invalidation, single-transaction processing | High |
| `worker-slow` | Long jobs: statement parsing, historical imports, AI provider calls, recurrence detection sweeps | Low |

Both pools share the same Redis instance and codebase. The difference is configuration only.

---

## Job Design Rules (All Jobs Must Follow)

**Idempotent.** Every job is safe to run twice. Use upsert-by-source-ID; check existence before creating. A job that cannot tolerate a duplicate run is a bug.

**Bounded.** Hard timeouts per job class. A job that can run forever will eventually run forever.

**Observable.** Structured start/finish/error events emitted via structlog. Results stored for 24 hours for debugging.

**Decoupled from request handlers.** API endpoints enqueue and return immediately with a job ID. No work happens in the request thread.

---

## Job Categories

### Scheduled (Recurring on a Timer)

| Job | Schedule |
|-----|----------|
| SimpleFIN polling | Configured interval (per household sync settings) |
| FX rate fetch | Daily |
| Recurrence detection sweep | Daily |
| Goal/budget status recalc | Daily |
| Nightly backup | Daily (configurable time) |
| Audit retention sweep | Daily |

### Triggered (Fired by Domain Events)

| Job | Trigger |
|-----|---------|
| Recurrence pattern update | New transaction reconciled to a recurrence |
| Projection cache invalidation | Any input change (balance, recurrence, budget, debt, goal) |
| AI insight generation | New transactions ingested, HITL queue threshold reached |
| Statement parsing | Statement file uploaded |
| Refund pairing | New transactions ingested |

### User-Initiated (Long-Running)

| Job | Notes |
|-----|-------|
| Historical statement import | Progress reported back via job status endpoint |
| Full re-categorization | Runs rules engine over all historical transactions |
| Scenario projection | Compute a named scenario; stored as a named projection if saved |

All three report progress via a job status endpoint the frontend polls or receives via SSE.
