## Template submission

- Publisher/template/version:
- Source repository and full commit SHA:
- Digest-qualified Artifact Registry URI:
- Data provider and license:
- Requested connections and permissions:
- Destination and audience bindings:
- Expected action frequency:
- Content provenance and moderation behavior:

## Checklist

- [ ] This adds a new immutable semantic version.
- [ ] The source repository is registered to the publisher.
- [ ] The source revision is a full Git commit, not a branch or tag.
- [ ] The OCI reference is digest-qualified and matches the declared digest.
- [ ] Dependencies are locked in the source repository.
- [ ] No credentials, recipient IDs, bot IDs, or application IDs are present.
- [ ] Normal, duplicate, malformed, and adversarial fixtures exist upstream.
- [ ] Permissions and network hosts are minimal.
- [ ] `registry/catalog.json` was regenerated and validation passes.
- [ ] The artifact will have a signature, SLSA provenance, and SPDX SBOM.
