#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BOOTSTRAP_DIR="$REPO_ROOT/projects/infra/bootstrap"
MTG_GLUE_DIR="$REPO_ROOT/projects/infra/mtg_glue"

usage() {
  echo "Usage: $0 --state-bucket <name> [--region <region>]"
  echo ""
  echo "  --state-bucket  Name of the S3 bucket bootstrap will create for Terraform state"
  echo "  --region        AWS region (default: us-east-1)"
  exit 1
}

REGION="us-east-1"
STATE_BUCKET=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --state-bucket=*) STATE_BUCKET="${1#*=}"; shift ;;
    --state-bucket)   STATE_BUCKET="$2";      shift 2 ;;
    --region=*)       REGION="${1#*=}";        shift ;;
    --region)         REGION="$2";             shift 2 ;;
    --profile=*)      PROFILE="${1#*=}";       shift ;;
    --profile)        PROFILE="$2";            shift 2 ;;
    *) usage ;;
  esac
done

[[ -z "$STATE_BUCKET" ]] && usage

echo "==> [1/3] Initialising bootstrap..."
terraform -chdir="$BOOTSTRAP_DIR" init

echo "==> [2/3] Applying bootstrap..."
terraform -chdir="$BOOTSTRAP_DIR" apply \
  -var="state_bucket_name=$STATE_BUCKET" \
  -var="aws_region=$REGION" \
  -auto-approve

echo "==> [3/3] Initialising mtg_glue remote backend..."
REMOTE_BUCKET=$(terraform -chdir="$BOOTSTRAP_DIR" output -raw state_bucket_name)
LOCK_TABLE=$(terraform -chdir="$BOOTSTRAP_DIR" output -raw lock_table_name)
echo "      -> state bucket:  $REMOTE_BUCKET"
echo "      -> lock table:    $LOCK_TABLE"

terraform -chdir="$MTG_GLUE_DIR" init \
  -backend-config="bucket=$REMOTE_BUCKET" \
  -backend-config="region=$REGION" \
  -backend-config="dynamodb_table=$LOCK_TABLE"

echo ""
echo "Done. mtg_glue is ready — run 'terraform -chdir=projects/infra/mtg_glue apply' to deploy."
