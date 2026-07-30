#!/usr/bin/env bash
# Bind the public template index to the registry publisher identity.
# Shared GAR/KMS/Storage resources are normally created by
# wahalao-automation/gcloud_cloudrun_service.sh.
set -euo pipefail

PROJECT_ID="${PROJECT_ID:-wahalao}"
REGION="${REGION:-us-central1}"
GAR_REPOSITORY="${GAR_REPOSITORY:-wahalao-automations}"
CATALOG_BUCKET="${CATALOG_BUCKET:-${PROJECT_ID}-automation-template-catalog}"
KMS_LOCATION="${KMS_LOCATION:-global}"
KMS_KEY_RING="${KMS_KEY_RING:-automation-registry}"
KMS_KEY="${KMS_KEY:-catalog-signing}"
KMS_KEY_VERSION="${KMS_KEY_VERSION:-1}"

PUBLISHER_SA_NAME="${PUBLISHER_SA_NAME:-gh-publisher-automation}"
POOL_ID="${POOL_ID:-github-actions}"
PROVIDER_ID="${PROVIDER_ID:-github}"
GITHUB_OWNER="${GITHUB_OWNER:-ericel}"
GITHUB_REPO="${GITHUB_REPO:-weynear-templates}"

die() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 1
}

command -v gcloud >/dev/null 2>&1 || die "gcloud is required"
[[ "$PUBLISHER_SA_NAME" =~ ^[a-z][a-z0-9-]{4,28}[a-z0-9]$ ]] ||
  die "invalid publisher service-account name"

gcloud config set project "$PROJECT_ID" >/dev/null
gcloud services enable \
  artifactregistry.googleapis.com \
  iam.googleapis.com \
  iamcredentials.googleapis.com \
  sts.googleapis.com \
  cloudkms.googleapis.com \
  storage.googleapis.com \
  --project="$PROJECT_ID" >/dev/null

gcloud artifacts repositories describe "$GAR_REPOSITORY" \
  --project="$PROJECT_ID" \
  --location="$REGION" >/dev/null 2>&1 ||
  die "missing Artifact Registry repository ${GAR_REPOSITORY} in ${REGION}; run the Automation provisioner first"

gcloud storage buckets describe "gs://${CATALOG_BUCKET}" \
  --project="$PROJECT_ID" >/dev/null 2>&1 ||
  die "missing catalog bucket ${CATALOG_BUCKET}; run the Automation provisioner first"

gcloud kms keys describe "$KMS_KEY" \
  --project="$PROJECT_ID" \
  --location="$KMS_LOCATION" \
  --keyring="$KMS_KEY_RING" >/dev/null 2>&1 ||
  die "missing catalog KMS key; run the Automation provisioner first"

PUBLISHER_SA_EMAIL="${PUBLISHER_SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
if ! gcloud iam service-accounts describe "$PUBLISHER_SA_EMAIL" \
  --project="$PROJECT_ID" >/dev/null 2>&1; then
  gcloud iam service-accounts create "$PUBLISHER_SA_NAME" \
    --project="$PROJECT_ID" \
    --display-name="GitHub Actions Weynear template catalog publisher" >/dev/null
fi

if ! gcloud iam workload-identity-pools describe "$POOL_ID" \
  --project="$PROJECT_ID" \
  --location=global >/dev/null 2>&1; then
  gcloud iam workload-identity-pools create "$POOL_ID" \
    --project="$PROJECT_ID" \
    --location=global \
    --display-name="GitHub Actions" >/dev/null
fi
if ! gcloud iam workload-identity-pools providers describe "$PROVIDER_ID" \
  --project="$PROJECT_ID" \
  --location=global \
  --workload-identity-pool="$POOL_ID" >/dev/null 2>&1; then
  gcloud iam workload-identity-pools providers create-oidc "$PROVIDER_ID" \
    --project="$PROJECT_ID" \
    --location=global \
    --workload-identity-pool="$POOL_ID" \
    --display-name="GitHub Actions OIDC provider" \
    --issuer-uri="https://token.actions.githubusercontent.com" \
    --attribute-mapping="google.subject=assertion.sub,attribute.repository=assertion.repository,attribute.repository_owner=assertion.repository_owner,attribute.ref=assertion.ref" \
    --attribute-condition="assertion.repository_owner == '${GITHUB_OWNER}'" >/dev/null
fi

PROJECT_NUMBER="$(
  gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)'
)"
WIF_POOL="projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${POOL_ID}"
WIF_PROVIDER="${WIF_POOL}/providers/${PROVIDER_ID}"
REPOSITORY_PRINCIPAL="principalSet://iam.googleapis.com/${WIF_POOL}/attribute.repository/${GITHUB_OWNER}/${GITHUB_REPO}"

gcloud iam service-accounts add-iam-policy-binding "$PUBLISHER_SA_EMAIL" \
  --project="$PROJECT_ID" \
  --member="$REPOSITORY_PRINCIPAL" \
  --role=roles/iam.workloadIdentityUser \
  --quiet >/dev/null

gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${PUBLISHER_SA_EMAIL}" \
  --role=roles/artifactregistry.reader \
  --condition=None \
  --quiet >/dev/null

gcloud kms keys add-iam-policy-binding "$KMS_KEY" \
  --project="$PROJECT_ID" \
  --location="$KMS_LOCATION" \
  --keyring="$KMS_KEY_RING" \
  --member="serviceAccount:${PUBLISHER_SA_EMAIL}" \
  --role=roles/cloudkms.signerVerifier \
  --quiet >/dev/null

for role in roles/storage.objectCreator roles/storage.objectViewer; do
  gcloud storage buckets add-iam-policy-binding "gs://${CATALOG_BUCKET}" \
    --member="serviceAccount:${PUBLISHER_SA_EMAIL}" \
    --role="$role" \
    --quiet >/dev/null
done

cat <<EOF

Publisher binding complete for ${GITHUB_OWNER}/${GITHUB_REPO}.

Create these GitHub repository or protected-environment variables:
  REGISTRY_PUBLISHING_ENABLED=false
  REGISTRY_GCP_PROJECT_ID=${PROJECT_ID}
  REGISTRY_GCP_REGION=${REGION}
  REGISTRY_GAR_REPOSITORY=${GAR_REPOSITORY}
  REGISTRY_CATALOG_BUCKET=${CATALOG_BUCKET}
  REGISTRY_KMS_LOCATION=${KMS_LOCATION}
  REGISTRY_KMS_KEY_RING=${KMS_KEY_RING}
  REGISTRY_KMS_KEY=${KMS_KEY}
  REGISTRY_KMS_KEY_VERSION=${KMS_KEY_VERSION}
  REGISTRY_WIF_PROVIDER=${WIF_PROVIDER}
  REGISTRY_PUBLISHER_SERVICE_ACCOUNT=${PUBLISHER_SA_EMAIL}

Keep REGISTRY_PUBLISHING_ENABLED=false until every catalog artifact has a real
digest, Cosign signature, SLSA provenance, and SPDX SBOM.
EOF
