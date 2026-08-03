# Live Sports Scores 2.2

This version decouples the API-Football data source from audience topic names.
At installation time, the application supplies a numeric API-Football league ID;
the trusted runtime constructs the fixed fixtures URL
`https://v3.football.api-sports.io/fixtures?live=all&league={LEAGUE_ID}`.

The Post and Messaging bindings still select the same saved bot audience, but
the audience's human-readable name and topic no longer determine the provider
league. The runtime broadcasts only significant match transitions.

The contribution exporter injects the repository commit. `weynear-templates`
performs the trusted build and supplies the artifact digest; contributors never
receive Weynear registry or signing credentials.
