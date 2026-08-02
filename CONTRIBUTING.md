# Contributing automation templates

## Before opening a pull request

1. Register the publisher through a separate owner-approved change.
2. Push the executable source and reproducible Docker build definition to a
   public, immutable Git commit.
3. Add a source-only `preview` recipe with `spec.build`; do not declare an
   artifact URI or digest.
4. Add a new semantic-version directory. Never edit a released version.
5. Declare the smallest possible connections, permissions, bindings, quotas,
   and content class.
6. Add fixtures and tests to the source repository.
7. Validate the contribution. Pull-request CI checks out the declared commit
   and builds it without credentials.

After review, a Weynear maintainer invokes the central builder. The index—not
the contributor—publishes the OCI image, creates the SBOM and SLSA provenance,
signs the artifact, and opens the promotion PR containing the resulting digest.

## Recipe rules

- Publisher, template name, and version must match the directory path.
- Source repositories must appear in the protected publisher record.
- Source revisions are full lowercase 40-character Git commit SHAs.
- Contributor previews omit `spec.artifact`. Only the trusted central builder
  may add the digest-qualified `REGION-docker.pkg.dev/...@sha256:...` artifact.
- Recipe fields cannot contain secrets, user IDs, recipient lists, bot IDs, or
  application IDs.
- Provider credentials are declared with `secret: true`, a supported
  `secret_type`, and `required_environments`. The key must match a declared
  connection's `secret_name`. Pull requests contain only this metadata;
  installers bind their own app/environment credential in the console.
- Manifests may contain only the typed installation placeholders documented by
  the schema.
- `custom` audiences are selected by the installer and checked by Weynear;
  templates never receive subscriber profile IDs.

## Review

Changes to publisher authority, CI trust policy, schemas, or signing policy
require repository-owner review through CODEOWNERS. Approval of a pull request
does not bypass artifact verification in the trusted release workflow.

Contributor repositories never receive Weynear Artifact Registry, KMS,
service-account, catalog, or pull-request credentials.
