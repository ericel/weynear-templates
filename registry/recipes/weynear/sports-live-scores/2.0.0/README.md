# Live Sports Scores 2.0

The first sports recipe sourced and built from `ericel/wahalao-template-maker`.
It preserves the `sports-live-scores-v1` runtime-adapter contract so existing
Weynear installations can upgrade without changing their bot or topic bindings.

The Post and Messaging bindings must select the same saved bot-topic audience.
The runtime broadcasts only significant transitions: match started, goal,
half-time, full-time, postponed, and cancelled. Clock-only changes and unchanged
provider snapshots do not create messages.

The all-zero source commit marks this as an unreleased local candidate. The
secretless contribution exporter replaces it with the repository's real commit.
`weynear-templates` performs the trusted build and supplies the artifact digest;
contributors never receive Weynear registry or signing credentials.
