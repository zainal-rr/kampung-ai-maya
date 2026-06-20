# Serverless Event-Driven Architecture

## Intent

Design an event-driven workload (APIs, pipelines, async processing) on managed
serverless services so cost tracks usage and there are no servers to operate.

## Inputs Required

- EVENT sources: HTTP requests, file uploads, queue messages, schedules, streams.
- VOLUME: events/day and burstiness; payload sizes.
- LATENCY tolerance: synchronous (user waiting) vs asynchronous (eventually).
- Per-step WORK duration (functions have execution time limits).
- IDEMPOTENCY tolerance: can a step safely run twice?

## Method

1. Map each flow as: event source → router (queue/topic/bus) → function →
   store/next event. Functions stay single-purpose and short.
2. Choose the coupling primitive deliberately:
   - **Queue** (SQS / Cloud Tasks / Service Bus): one consumer, buffering,
     retry with backoff — the default for work distribution.
   - **Pub/sub topic** (SNS / Pub/Sub / Event Grid): fan-out to many consumers.
   - **Event bus** (EventBridge / Eventarc / Event Grid): routing on content,
     cross-service choreography.
   - **Stream** (Kinesis / Pub/Sub / Event Hubs): ordered, replayable, high
     volume.
3. Make every consumer IDEMPOTENT (dedupe key or conditional write) — all
   these systems deliver at-least-once.
4. Attach a DEAD-LETTER QUEUE to every consumer; alarm on DLQ depth. A failed
   event must land somewhere visible, never vanish.
5. For multi-step flows with branching/compensation, use the orchestrator
   (Step Functions / Workflows / Durable Functions) instead of function-calls-
   function chains.
6. Store state in serverless stores (DynamoDB / Firestore / Cosmos DB, object
   storage); keep functions stateless.

## Worked Example

Requirement: receipt images uploaded by users → OCR → categorize → notify;
~20k uploads/day, bursty; user does not wait (async).

- Flow: upload to object storage → storage event → queue → OCR function →
  result event → categorize function → write to NoSQL table → notify topic →
  push/email function. DLQ on each queue; idempotency key = object path.
- Service mapping:
  - AWS: S3 → EventBridge → SQS → Lambda → DynamoDB → SNS
  - GCP: GCS → Eventarc → Pub/Sub → Cloud Run functions → Firestore → Pub/Sub
  - Azure: Blob → Event Grid → Service Bus → Functions → Cosmos DB → Event Grid
- Why serverless fits: 20k/day ≈ 0.7/sec average with bursts — paying for idle
  servers would be waste; per-invocation pricing tracks the workload. Cost
  must be modeled in the provider's calculator at the real volumes.

## Interpretation

- This design guarantees: elastic scale per burst, no idle cost, isolated
  failure per step with visible DLQs, replayable flows.
- It does not guarantee: low cold-start latency for synchronous paths (check
  the current cold-start behavior per runtime), exactly-once delivery (design
  for at-least-once), or ordering unless a stream/FIFO primitive is chosen.

## Red Flags

- Function A directly invoking function B synchronously in a chain — an outage
  amplifier; put a queue or orchestrator between steps.
- No DLQ ("retries forever" = silent data loss with extra cost).
- Non-idempotent consumers on at-least-once delivery — duplicate side effects.
- A function doing 14 minutes of work at the timeout edge — that step wants a
  container (Fargate / Cloud Run / Container Apps) instead.
- Serverless chosen for a steady high-volume 24/7 load without a cost model —
  at constant high utilization, provisioned compute is often cheaper.

## Limitations

Vendor coupling is real: the primitives differ enough that porting is a
rebuild. Long-running, latency-critical, or specialized-hardware work doesn't
fit. Observability must be built deliberately (tracing across events), or
debugging becomes archaeology.
