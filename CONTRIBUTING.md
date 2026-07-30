# Contributing automation templates

## Before opening a pull request

1. Register the publisher through a separate owner-approved change.
2. Build the executable from a reviewed, full Git commit with locked
   dependencies.
3. Push an immutable `linux/amd64` OCI artifact to the publisher's approved
   Google Artifact Registry namespace.
4. Sign the artifact and attach SLSA provenance and an SPDX SBOM.
5. Add a new semantic-version directory. Never edit a released version.
6. Declare the smallest possible connections, permissions, bindings, quotas,
   and content class.
7. Add fixtures and tests to the source repository.
8. Regenerate and validate the catalog.

## Recipe rules

- Publisher, template name, and version must match the directory path.
- Source repositories must appear in the protected publisher record.
- Source revisions are full lowercase 40-character Git commit SHAs.
- Artifact references use `REGION-docker.pkg.dev/...@sha256:...`; tags are not
  accepted.
- Recipe fields cannot contain secrets, user IDs, recipient lists, bot IDs, or
  application IDs.
- Manifests may contain only the typed installation placeholders documented by
  the schema.
- `custom` audiences are selected by the installer and checked by Weynear;
  templates never receive subscriber profile IDs.

## Review

Changes to publisher authority, CI trust policy, schemas, or signing policy
require repository-owner review through CODEOWNERS. Approval of a pull request
does not bypass artifact verification in the trusted release workflow.
