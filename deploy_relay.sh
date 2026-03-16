#!/usr/bin/env bash
set -euo pipefail
PROJECT_ID="${GCP_PROJECT_ID:?Set GCP_PROJECT_ID}"
REGION="us-central1"
SERVICE="network-relay"
ALLOWED_ORIGINS="${RELAY_ALLOWED_ORIGINS:?Set RELAY_ALLOWED_ORIGINS}"

echo "Building container image..."
gcloud builds submit --tag "gcr.io/$PROJECT_ID/$SERVICE"

echo "Deploying to Cloud Run..."
gcloud run deploy "$SERVICE" \
  --image "gcr.io/$PROJECT_ID/$SERVICE" \
  --region "$REGION" \
  --platform managed \
  --allow-unauthenticated \
  --max-instances 1 \
  --timeout 3600 \
  --session-affinity \
  --set-env-vars "RELAY_ENV=production,RELAY_ALLOWED_ORIGINS=$ALLOWED_ORIGINS"

echo "Deployed: $(gcloud run services describe $SERVICE --region $REGION --format 'value(status.url)')"
