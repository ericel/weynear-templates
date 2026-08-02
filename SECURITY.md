# Security

Do not report vulnerabilities in public issues.

Report suspected template, artifact, signature, provenance, or capability
boundary problems privately to the Weynear repository owner. Include the
publisher/template/version coordinate, artifact digest, and evidence.

Never commit credentials, service-account keys, API tokens, personal data, or
subscriber identifiers. GitHub Actions authenticates to Google Cloud only
through repository-scoped Workload Identity Federation.

Secret requirements belong in the reviewed template contract. Credential
values are entered only through the Weynear developer console and must never be
used in fixtures, pull-request variables, catalog records, or manifests.

Published coordinates are immutable. A compromised version is revoked rather
than silently replaced.

Contributor workflows are deliberately credential-free. Untrusted source build
instructions run in a separate job with read-only repository access and no
GitHub OIDC permission. A protected downstream job receives only the exported
image and SBOM before acquiring its short-lived cloud identity. Only the index
repository may push artifacts, generate provenance, sign with KMS, or publish
the installable catalog.
