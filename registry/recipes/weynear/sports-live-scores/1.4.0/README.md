# Live Sports Scores 1.4

League-filtered API-Football score cards and consent-aware topic broadcasts.
The Post and Messaging bindings must select the same saved bot-topic audience.

The runner broadcasts only significant transitions: match started, goal,
half-time, full-time, postponed, and cancelled. Clock-only changes and unchanged
provider snapshots do not create messages. Broadcast requests use deterministic
event idempotency keys and Messaging rechecks subscription consent for every
recipient immediately before fan-out.
