# Live Sports Scores 2.1

The first app-scoped sports recipe sourced and built from
`ericel/wahalao-template-maker`. It preserves the
`sports-live-scores-v1` runtime-adapter contract so existing installations can
upgrade without changing their bot or topic bindings.

The Post and Messaging bindings must select the same saved bot-topic audience.
The runtime broadcasts only significant transitions: match started, goal,
half-time, full-time, postponed, and cancelled. Clock-only changes and unchanged
provider snapshots do not create messages.

The contribution exporter injects the repository commit and the opaque private
submission ID supplied by the owning application. `weynear-templates` performs
the trusted build and supplies the artifact digest; contributors never receive
Weynear registry or signing credentials.
