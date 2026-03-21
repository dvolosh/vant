# Housing Dashboard - Cloud Run Deployment Script (Windows PowerShell)
# This script builds and deploys your Dash application to Google Cloud Run

$ErrorActionPreference = "Stop"

# Configuration - Set these environment variables before running
$PROJECT_ID = $env:GCP_PROJECT_ID
$SERVICE_NAME = "housing-dashboard"
$REGION = "us-central1"
$IMAGE_NAME = "gcr.io/$PROJECT_ID/$SERVICE_NAME"

Write-Host "Deploying Housing Dashboard to Cloud Run..." -ForegroundColor Green
Write-Host "Project: $PROJECT_ID"
Write-Host "Service: $SERVICE_NAME"
Write-Host "Region: $REGION"
Write-Host ""

# Validate required environment variables
if (-not $env:GCP_PROJECT_ID) {
    Write-Host "ERROR: GCP_PROJECT_ID environment variable is not set" -ForegroundColor Red
    Write-Host "Set it with: `$env:GCP_PROJECT_ID='your-project-id'"
    exit 1
}

if (-not $env:GCP_DATASET_ID) {
    Write-Host "ERROR: GCP_DATASET_ID environment variable is not set" -ForegroundColor Red
    Write-Host "Set it with: `$env:GCP_DATASET_ID='your-dataset-id'"
    exit 1
}

# Check if gcloud is installed
if (-not (Get-Command gcloud -ErrorAction SilentlyContinue)) {
    Write-Host "ERROR: gcloud CLI is not installed" -ForegroundColor Red
    Write-Host "Install it from: https://cloud.google.com/sdk/docs/install"
    exit 1
}

# Set the project
Write-Host "Setting project to $PROJECT_ID..." -ForegroundColor Cyan
gcloud config set project $PROJECT_ID

# Enable required APIs
Write-Host "Enabling required Google Cloud APIs..." -ForegroundColor Cyan
gcloud services enable cloudbuild.googleapis.com run.googleapis.com artifactregistry.googleapis.com

# Build the Docker image using Cloud Build
Write-Host "Building Docker image..." -ForegroundColor Cyan
gcloud builds submit --tag $IMAGE_NAME

# Deploy to Cloud Run
Write-Host "Deploying to Cloud Run..." -ForegroundColor Cyan
gcloud run deploy $SERVICE_NAME `
    --image $IMAGE_NAME `
    --platform managed `
    --region $REGION `
    --allow-unauthenticated `
    --memory 1Gi `
    --cpu 1 `
    --timeout 300 `
    --max-instances 10 `
    --set-env-vars "GCP_PROJECT_ID=$PROJECT_ID,GCP_DATASET_ID=$env:GCP_DATASET_ID,PIPELINE_SECRET=$env:PIPELINE_SECRET"

# Get the service URL
$SERVICE_URL = gcloud run services describe $SERVICE_NAME --region $REGION --format='value(status.url)'

Write-Host ""
Write-Host "Deployment complete!" -ForegroundColor Green
Write-Host "Your dashboard is live at: $SERVICE_URL" -ForegroundColor Yellow
Write-Host ""
Write-Host "View logs: gcloud run logs tail $SERVICE_NAME --region $REGION"
Write-Host "Redeploy: .\deploy.ps1"
