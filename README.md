# Weynear Templates

The public, reviewed index for automation templates installable on Weynear.
This repository is the contribution surface; it does not contain the private
Weynear control plane, credentials, customer data, or runtime infrastructure.

## Repository shape

```text
registry/
  publishers/<publisher>.yaml
  recipes/<publisher>/<template>/<version>/
    template.yaml
    manifest.yaml
    README.md
  catalog.json
schemas/
scripts/
tests/
```

Each published version is immutable and identified by:

```text
<publisher>/<template>@<semantic-version>
```

Executable artifacts remain private, digest-qualified OCI images in Google
Artifact Registry. Merging a recipe does not grant its code arbitrary access:
Weynear validates the requested connections, permissions, quotas, bot binding,
and destination bindings before importing the signed catalog.

## Local validation

```bash
python3.12 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python scripts/build_catalog.py --check
.venv/bin/python -m pytest -q
```

To regenerate the deterministic catalog after an intentional recipe change:

```bash
.venv/bin/python scripts/build_catalog.py --write
```

Trusted artifact builders promote an existing preview recipe with:

```bash
.venv/bin/python scripts/promote_template.py \
  --publisher weynear \
  --name sports-live-scores \
  --version 1.0.0 \
  --source-commit <full-git-sha> \
  --artifact-digest sha256:<oci-manifest-digest>
.venv/bin/python scripts/build_catalog.py --write
```

Promotion is still submitted as a pull request. The helper accepts only a
digest-qualified artifact in the recipe's existing publisher namespace and
only transitions `preview` to `approved`.

## Submitting a template

Read [CONTRIBUTING.md](CONTRIBUTING.md), add a new immutable semantic-version
directory, regenerate `registry/catalog.json`, and open a pull request.
Pull-request jobs receive no Google Cloud credentials.

The initial sports recipe is a preview bootstrap entry. Before signed
publication, replace its source commit and artifact digest with real reviewed
and attested values.

## Cloud publisher binding

After the private Automation provisioner creates the shared GAR, KMS, bucket,
and publisher service account, bind this public repository to that identity:

```bash
./gcloud_registry_publisher.sh
```

The script prints the GitHub `REGISTRY_*` variables used by the gated release
workflow. Keep `REGISTRY_PUBLISHING_ENABLED=false` during scaffolding.

Each immutable catalog release increments
`registry/catalog-version.txt`. The release workflow signs the canonical
catalog, verifies every artifact/signature/SLSA/SPDX attestation, and uploads
the catalog plus its declared install manifests to a versioned private bucket
prefix.

## Trust boundary

- GitHub pull requests review metadata and capability declarations.
- Protected publisher records map Weynear publisher IDs to approved source
  repositories and Artifact Registry namespaces.
- Trusted main-branch CI verifies artifacts and attestations.
- Cloud KMS signs the complete release index.
- `wahalao-automation` verifies and imports the signed release.

See [SECURITY.md](SECURITY.md) for reporting and supply-chain requirements.
