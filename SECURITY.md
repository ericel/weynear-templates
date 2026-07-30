# Security

Do not report vulnerabilities in public issues.

Report suspected template, artifact, signature, provenance, or capability
boundary problems privately to the Weynear repository owner. Include the
publisher/template/version coordinate, artifact digest, and evidence.

Never commit credentials, service-account keys, API tokens, personal data, or
subscriber identifiers. GitHub Actions authenticates to Google Cloud only
through repository-scoped Workload Identity Federation.

Published coordinates are immutable. A compromised version is revoked rather
than silently replaced.
