# Data Engine - ETL & Intelligence Pipeline

## Overview
This directory contains the core data pipelines and AI integration logic for the Housing Dashboard. It handles ingesting raw data from various sources, preprocessing it, storing it in Google BigQuery, and interacting with Vertex AI for market intelligence.

## Architecture Pipeline

1. **Ingestion (`fetch_*.py`)**: Pulls raw data from APIs (FRED, PullPush for Reddit, Google Trends) and saves as JSON/CSV in `*_raw/` folders. Zillow data is manually downloaded monthly as CSV.
2. **Preprocessing (`preprocess_*.py`)**: Cleans, normalizes, and enriches data (e.g., coordinate mapping, text extraction), saving as optimized Parquet files in `*_processed/` folders.
3. **Storage (`upload_*_to_bigquery.py`)**: Loads processed data into BigQuery tables with appropriate schemas, partitioning, and clustering.
4. **Intelligence (`generate_insights.py`)**: Queries BigQuery to build market context, prompts Vertex AI Gemini, and caches audience-specific Weekly Briefings securely back into BigQuery.

## Setup Instructions

### 1. Install Dependencies
Ensure you have the required Python packages:
```powershell
pip install -r requirements.txt
```

### 2. Configure Environment Variables
Copy `.env.example` to `.env` and set your credentials:
```env
GCP_PROJECT_ID=your-gcp-project-id
GCP_DATASET_ID=db

# AI Configuration
GEMINI_MODEL=gemini-1.5-flash
VERTEX_LOCATION=us-central1
MAX_QA_PER_DAY=5

# Pipeline Security
PIPELINE_SECRET=your_secure_secret_here
```

### 3. BigQuery Setup
Initialize all required tables (if not already created):
```powershell
# Create base metrics tables
python upload_to_bigquery.py        # Zillow
python upload_fred_to_bigquery.py   # FRED
python upload_trends_to_bigquery.py # Google Trends
python upload_reddit_to_bigquery.py # Reddit

# Create AI cache & log tables
python generate_insights.py --create-tables
```

## Running Pipelines Locally

You can run individual pipeline steps manually. For fully automated updates, the dashboard's `/api/run-pipeline` endpoint orchestrates the daily Reddit and Google Trends updates using Cloud Scheduler.

### Zillow & FRED (Monthly)
```powershell
python preprocess_zillow.py
python upload_to_bigquery.py

python fetch_fred.py
python preprocess_fred.py
python upload_fred_to_bigquery.py
```

### Google Trends & Reddit (Daily/Weekly)
```powershell
# Trends
python fetch_trends.py
python preprocess_trends.py
python upload_trends_to_bigquery.py

# Reddit
python fetch_reddit.py
python preprocess_reddit.py
python upload_reddit_to_bigquery.py
```

### AI Intelligence (Vertex AI)
You can test the AI briefing logic locally via the CLI:
```powershell
# Generate a briefing for homebuyers
python generate_insights.py --audience homebuyer

# Perform a dry-run (builds BQ context but skips Gemini API call)
python generate_insights.py --audience re_investor --dry-run

# Test the Q&A fallback system
python generate_insights.py --qa "What markets look stressed?" --audience homebuyer
```

## Security & Maintenance
- **Never commit `.env` or service account keys to git.**
- BigQuery schemas are defined in the `create_*_schema.sql` files.
- The Reddit pipeline uses the free PullPush API to avoid Reddit API rate limits and credential management. 
- AI Briefings use caching (`ai_insights` table) to heavily reduce Vertex AI costs on repeated dashboard loads.
