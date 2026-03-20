"""
Housing Market Dashboard - Plotly Dash Application

A professional dashboard for analyzing housing market data from multiple sources:
- FRED: Macro economic indicators
- Zillow: Housing market metrics with US map visualization
"""

import io
import dash
from dash import dcc, html, Input, Output, State
import dash_bootstrap_components as dbc
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from google.cloud import bigquery
from datetime import datetime, timedelta
from pathlib import Path
import os
import sys
import json
import subprocess
from dotenv import load_dotenv

# Add data_engine to path for generate_insights
sys.path.insert(0, str(Path(__file__).parent.parent / 'data_engine'))
try:
    import generate_insights
    AI_AVAILABLE = True
except ImportError:
    AI_AVAILABLE = False
    print("WARNING: generate_insights not importable — AI features will be disabled")

# Load environment variables
load_dotenv()

# Initialize Dash app with Bootstrap theme
app = dash.Dash(
    __name__,
    external_stylesheets=[dbc.themes.BOOTSTRAP],
    suppress_callback_exceptions=True
)

# Custom CSS for professional dark theme
app.index_string = '''
<!DOCTYPE html>
<html>
    <head>
        {%metas%}
        <title>{%title%}</title>
        {%favicon%}
        {%css%}
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
        <style>
            :root {
                --primary-accent: #A7D129;
                --bg-dark: #000000;
                --bg-card: #1a1a1a;
                --text-primary: #ededed;
                --text-secondary: rgba(237, 237, 237, 0.8);
            }
            
            * {
                font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            }
            
            body {
                background-color: var(--bg-dark);
                color: var(--text-primary);
                margin: 0;
                padding: 0;
            }
            
            .main-container {
                max-width: 1400px;
                margin: 0 auto;
                padding: 2rem;
            }
            
            .header {
                text-align: center;
                margin-bottom: 3rem;
                padding: 2rem 0;
            }
            
            .header h1 {
                font-size: 2.5rem;
                font-weight: 700;
                color: var(--primary-accent);
                margin-bottom: 0.5rem;
            }
            
            .header p {
                font-size: 1.2rem;
                color: var(--text-secondary);
                margin: 0;
            }
            
            .metric-card {
                background: var(--bg-card);
                border-radius: 8px;
                padding: 1.5rem;
                margin-bottom: 1.5rem;
                border-left: 4px solid var(--primary-accent);
                box-shadow: 0 4px 6px rgba(0, 0, 0, 0.3);
            }
            
            .metric-card h3 {
                color: var(--text-primary);
                font-size: 1.1rem;
                font-weight: 600;
                margin-bottom: 1rem;
            }
            
            .section-title {
                font-size: 1.8rem;
                font-weight: 600;
                color: var(--primary-accent);
                margin: 2rem 0 1rem 0;
                padding-bottom: 0.5rem;
                border-bottom: 2px solid var(--primary-accent);
            }
            
            .filter-section {
                background: var(--bg-card);
                border-radius: 8px;
                padding: 1.5rem;
                margin-bottom: 2rem;
                box-shadow: 0 4px 6px rgba(0, 0, 0, 0.3);
            }
            
            .Select-control, .Select-menu-outer {
                background-color: var(--bg-card) !important;
                color: var(--text-primary) !important;
            }
            
            .chart-container {
                background: var(--bg-card);
                border-radius: 8px;
                padding: 1rem;
                margin-bottom: 1.5rem;
                box-shadow: 0 4px 6px rgba(0, 0, 0, 0.3);
            }
            
            /* Modern Dash Dropdown styling - black text on white background */
            .dash-dropdown .Select-control,
            #city-search .Select-control,
            #map-metric .Select-control,
            div[class*="css-"][class*="control"] {
                background-color: #ffffff !important;
                border: 1px solid #cccccc !important;
            }
            
            /* Single value and placeholder - DARK GRAY TEXT */
            .dash-dropdown .Select-value-label,
            .dash-dropdown .Select-placeholder,
            .dash-dropdown .Select-value,
            #city-search .Select-value-label,
            #city-search .Select-placeholder,
            #city-search .Select-value,
            #map-metric .Select-value-label,
            #map-metric .Select-placeholder,
            #map-metric .Select-value,
            div[class*="css-"][class*="singleValue"],
            div[class*="css-"][class*="placeholder"],
            div[class*="css-"] div[class*="Value"],
            .Select--single > .Select-control .Select-value {
                color: #333333 !important;
            }
            
            /* Input field when typing */
            .dash-dropdown input,
            #city-search input,
            #map-metric input {
                color: #333333 !important;
            }
            
            /* Dropdown menu - WHITE BACKGROUND */
            .dash-dropdown .Select-menu-outer,
            #city-search .Select-menu-outer,
            #map-metric .Select-menu-outer,
            div[class*="css-"][class*="menu"] {
                background-color: #ffffff !important;
                border: 1px solid #cccccc !important;
            }
            
            /* Menu options - WHITE BACKGROUND, DARK GRAY TEXT */
            .dash-dropdown .Select-option,
            #city-search .Select-option,
            #map-metric .Select-option,
            div[class*="css-"][class*="option"] {
                background-color: #ffffff !important;
                color: #333333 !important;
            }
            
            /* Focused/hover option - LIGHT GRAY BACKGROUND */
            .dash-dropdown .Select-option.is-focused,
            #city-search .Select-option.is-focused,
            #map-metric .Select-option.is-focused,
            div[class*="css-"][class*="option"]:hover {
                background-color: #f0f0f0 !important;
                color: #333333 !important;
            }
            
            /* Selected option - LIGHTER GRAY */
            .dash-dropdown .Select-option.is-selected,
            #city-search .Select-option.is-selected,
            #map-metric .Select-option.is-selected {
                background-color: #e0e0e0 !important;
                color: #333333 !important;
            }
            
            /* Arrow indicator */
            .dash-dropdown svg,
            #city-search svg,
            #map-metric svg {
                fill: #333333 !important;
            }
            
            /* Tab styling */
            .tab--selected {
                background-color: var(--bg-card) !important;
                border-bottom: 3px solid var(--primary-accent) !important;
                color: var(--text-primary) !important;
            }
            
            .tab {
                background-color: var(--bg-dark) !important;
                border: none !important;
                color: rgba(237, 237, 237, 0.6) !important;
                padding: 1rem 2rem !important;
                font-weight: 500 !important;
                transition: all 0.3s ease !important;
            }
            
            .tab:hover {
                background-color: rgba(26, 26, 26, 0.5) !important;
                color: var(--text-primary) !important;
            }
            
            .tabs {
                background-color: var(--bg-dark) !important;
                border-bottom: 1px solid #333 !important;
                margin-bottom: 2rem !important;
            }
            /* AI Briefing panel */
            .briefing-panel {
                background: linear-gradient(135deg, #1a1a2e 0%, #1a1a1a 100%);
                border: 1px solid #2a2a4a;
                border-radius: 12px;
                padding: 1.5rem;
                margin-bottom: 1.5rem;
            }
            .audience-btn {
                background: transparent;
                border: 1px solid #444;
                color: rgba(237,237,237,0.7);
                padding: 0.4rem 1rem;
                border-radius: 20px;
                cursor: pointer;
                transition: all 0.2s ease;
                font-size: 0.85rem;
            }
            .audience-btn.active, .audience-btn:hover {
                background: var(--primary-accent);
                border-color: var(--primary-accent);
                color: #000;
                font-weight: 600;
            }
            .sentiment-badge {
                display: inline-block;
                padding: 0.2rem 0.8rem;
                border-radius: 20px;
                font-size: 0.8rem;
                font-weight: 700;
                letter-spacing: 0.05em;
            }
            .sentiment-bullish { background: rgba(39,174,96,0.2); color: #27ae60; border: 1px solid #27ae60; }
            .sentiment-bearish { background: rgba(231,76,60,0.2); color: #e74c3c; border: 1px solid #e74c3c; }
            .sentiment-neutral  { background: rgba(241,196,15,0.2); color: #f1c40f; border: 1px solid #f1c40f; }
            .theme-pill {
                display: inline-block;
                background: rgba(167,209,41,0.1);
                border: 1px solid rgba(167,209,41,0.3);
                color: var(--primary-accent);
                padding: 0.2rem 0.7rem;
                border-radius: 12px;
                font-size: 0.78rem;
                margin: 0.2rem;
            }
            /* Q&A chatbox */
            .qa-box {
                background: #111;
                border: 1px solid #333;
                border-radius: 8px;
                padding: 1rem;
            }
            .qa-answer {
                background: rgba(167,209,41,0.06);
                border-left: 3px solid var(--primary-accent);
                border-radius: 0 8px 8px 0;
                padding: 0.8rem 1rem;
                color: var(--text-secondary);
                font-size: 0.9rem;
                line-height: 1.6;
                white-space: pre-wrap;
            }
            .qa-input {
                background: #222 !important;
                border: 1px solid #444 !important;
                color: var(--text-primary) !important;
                border-radius: 6px;
                padding: 0.5rem 0.8rem;
            }
            .generate-btn {
                background: var(--primary-accent) !important;
                color: #000 !important;
                font-weight: 700 !important;
                border: none !important;
                border-radius: 8px !important;
                padding: 0.6rem 1.5rem !important;
                cursor: pointer;
                transition: opacity 0.2s ease;
            }
            .generate-btn:hover { opacity: 0.85; }
            .csi-gauge-card {
                background: var(--bg-card);
                border-radius: 12px;
                padding: 1.2rem;
                text-align: center;
                border: 1px solid #2a2a2a;
            }
            .freshness-bar {
                background: #111;
                border: 1px solid #252525;
                border-radius: 6px;
                padding: 0.5rem 1rem;
                font-size: 0.8rem;
                color: rgba(237,237,237,0.5);
                margin-bottom: 1.5rem;
                display: flex;
                gap: 2rem;
                align-items: center;
            }
        </style>
    </head>
    <body>
        {%app_entry%}
        <footer>
            {%config%}
            {%scripts%}
            {%renderer%}
        </footer>
    </body>
</html>
'''

# Initialize BigQuery client
def get_bigquery_client():
    """Initialize BigQuery client"""
    try:
        project_id = os.getenv('GCP_PROJECT_ID', 'vant-486316')
        return bigquery.Client(project=project_id)
    except Exception as e:
        print(f"Failed to initialize BigQuery client: {e}")
        return None

# Data fetching functions
def fetch_fred_data():
    """Fetch FRED macro indicators"""
    client = get_bigquery_client()
    if not client:
        return pd.DataFrame()
    
    dataset_id = os.getenv('GCP_DATASET_ID', 'db')
    query = f"""
    SELECT 
        series_id,
        series_name,
        date,
        value,
        units
    FROM `{client.project}.{dataset_id}.fred_metrics`
    WHERE date >= DATE_SUB(CURRENT_DATE(), INTERVAL 5 YEAR)
    ORDER BY series_id, date
    """
    
    try:
        return client.query(query).to_dataframe()
    except Exception as e:
        print(f"Error fetching FRED data: {e}")
        return pd.DataFrame()

def fetch_zillow_data(states=None):
    """Fetch Zillow housing metrics - FIXED: Cast TIMESTAMP to DATE"""
    client = get_bigquery_client()
    if not client:
        return pd.DataFrame()
    
    dataset_id = os.getenv('GCP_DATASET_ID', 'db')
    
    # Build state filter
    state_filter = ""
    if states and len(states) > 0:
        state_list = "', '".join(states)
        state_filter = f"AND state_name IN ('{state_list}')"
    
    # FIX: Cast date to DATE type to avoid TIMESTAMP vs DATE comparison error
    query = f"""
    SELECT 
        region_id,
        region_name,
        region_type,
        state_name,
        metric_type,
        CAST(date AS DATE) as date,
        value
    FROM `{client.project}.{dataset_id}.zillow_metrics`
    WHERE CAST(date AS DATE) >= DATE_SUB(CURRENT_DATE(), INTERVAL 5 YEAR)
    {state_filter}
    ORDER BY metric_type, region_name, date
    """
    
    try:
        return client.query(query).to_dataframe()
    except Exception as e:
        print(f"Error fetching Zillow data: {e}")
        return pd.DataFrame()

def get_available_states():
    """Get list of available states from Zillow data"""
    client = get_bigquery_client()
    if not client:
        return []
    
    dataset_id = os.getenv('GCP_DATASET_ID', 'db')
    query = f"""
    SELECT DISTINCT state_name
    FROM `{client.project}.{dataset_id}.zillow_metrics`
    WHERE state_name IS NOT NULL
    ORDER BY state_name
    """
    
    try:
        df = client.query(query).to_dataframe()
        return df['state_name'].tolist()
    except Exception as e:
        print(f"Error fetching states: {e}")
        return []

def get_state_aggregated_data():
    """Get pre-computed state-level data (OPTIMIZED)"""
    client = get_bigquery_client()
    if not client:
        return pd.DataFrame()
    
    dataset_id = os.getenv('GCP_DATASET_ID', 'db')
    
    # Simple query - no window functions, no aggregation!
    # Data is pre-computed during preprocessing
    query = f"""
    SELECT *
    FROM `{client.project}.{dataset_id}.zillow_state_aggregated`
    """
    
    try:
        df = client.query(query).to_dataframe()
        
        # Fill NaN with 0
        for col in df.columns:
            if col not in ['state_name', 'city_count', 'latest_date']:
                df[col] = df[col].fillna(0)
        
        return df
    except Exception as e:
        print(f"Error fetching state data: {e}")
        return pd.DataFrame()

def get_city_data_with_coords():
    """Get pre-computed city data with coordinates for all MSAs"""
    client = get_bigquery_client()
    if not client:
        print("ERROR: BigQuery client initialization failed")
        return pd.DataFrame()
    
    dataset_id = os.getenv('GCP_DATASET_ID', 'db')
    
    # Query for all cities with MSA data
    query = f"""
    SELECT *
    FROM `{client.project}.{dataset_id}.zillow_city_latest`
    WHERE region_type = 'msa'
    AND zhvi IS NOT NULL
    """
    
    try:
        print("INFO: Querying zillow_city_latest for top 5 cities per state...")
        zillow_df = client.query(query).to_dataframe()
        print(f"INFO: Retrieved {len(zillow_df)} cities from BigQuery")
        
        if zillow_df.empty:
            print("WARNING: No city data returned from BigQuery!")
            return pd.DataFrame()
        
        # Load coordinates from CSV (now in dashboard folder for self-contained deployment)
        cities_csv_path = Path(__file__).parent / 'uscities.csv'
        if not cities_csv_path.exists():
            print(f"ERROR: Cities CSV file not found at {cities_csv_path}")
            return pd.DataFrame()
            
        coords_df = pd.read_csv(cities_csv_path, usecols=['city', 'state_id', 'lat', 'lng'])
        print(f"INFO: Loaded {len(coords_df)} cities with coordinates from CSV")
        
        # Show sample data for debugging
        print(f"SAMPLE Zillow data:")
        print(f"  region_name: {zillow_df['region_name'].iloc[0]}")
        print(f"  state_name: {zillow_df['state_name'].iloc[0]}")
        print(f"SAMPLE CSV data:")
        print(f"  city: {coords_df['city'].iloc[0]}")
        print(f"  state_id: {coords_df['state_id'].iloc[0]}")
        
        # Extract city name from "City, ST" format
        zillow_df['city_clean'] = zillow_df['region_name'].str.split(',').str[0].str.strip()
        print(f"SAMPLE cleaned city: {zillow_df['city_clean'].iloc[0]}")

        # Override mismatched Zillow MSA city names to match uscities.csv
        city_name_overrides = {
            'Boise City':       'Boise',
            'Urban Honolulu':   'Honolulu',
            'Barnstable Town':  'Barnstable',
            'Winston':          'Winston-Salem',
            'Winston-Salem':    'Winston-Salem',
            'Davenport':        'Davenport',   # handled via state override below
            'Grand Forks':      'Grand Forks', # handled via state override below
        }
        # State overrides for MSAs where Zillow assigns cross-state anchor city
        state_overrides = {
            ('Davenport', 'IL'): ('Davenport', 'IA'),
            ('Grand Forks', 'MN'): ('Grand Forks', 'ND'),
        }
        zillow_df['city_clean'] = zillow_df['city_clean'].replace(city_name_overrides)
        for (city, wrong_state), (_, correct_state) in state_overrides.items():
            mask = (zillow_df['city_clean'] == city) & (zillow_df['state_name'] == wrong_state)
            zillow_df.loc[mask, 'state_name'] = correct_state
        # Merge on city name and state code
        # Zillow: city_clean (e.g., "Anchorage"), state_name (e.g., "AK")
        # CSV: city (e.g., "Anchorage"), state_id (e.g., "AK")
        merged_df = zillow_df.merge(
            coords_df,
            left_on=['city_clean', 'state_name'],
            right_on=['city', 'state_id'],
            how='left'
        )
        
        # Check merge results
        total_rows = len(merged_df)
        rows_with_coords = merged_df['lat'].notna().sum()
        rows_without_coords = merged_df['lat'].isna().sum()
        
        print(f"MERGE RESULTS:")
        print(f"  Total rows: {total_rows}")
        print(f"  Rows with coordinates: {rows_with_coords}")
        print(f"  Rows WITHOUT coordinates: {rows_without_coords}")
        
        if rows_without_coords > 0:
            print(f"WARNING: {rows_without_coords} cities failed to match coordinates!")
            print("Sample unmatched cities:")
            unmatched = merged_df[merged_df['lat'].isna()][['city_clean', 'state_name']].head(10)
            for _, row in unmatched.iterrows():
                print(f"  - {row['city_clean']}, {row['state_name']}")
        
        # Drop rows without coordinates
        merged_df = merged_df.dropna(subset=['lat', 'lng'])
        print(f"INFO: Final dataset has {len(merged_df)} cities with coordinates")
        
        if merged_df.empty:
            print("ERROR: No cities have coordinates after merge!")
            return pd.DataFrame()
        
        # Fill NaN for metrics
        metric_cols = [col for col in merged_df.columns if col not in 
                      ['region_name', 'state_name', 'city_clean', 'city', 
                       'state_id', 'lat', 'lng', 'date', 'region_type', 'region_id']]
        for col in metric_cols:
            if col in merged_df.columns:
                merged_df[col] = merged_df[col].fillna(0)
        
        # Select final columns
        result_cols = ['region_name', 'state_name', 'lat', 'lng'] + [col for col in metric_cols if col in merged_df.columns]
        return merged_df[result_cols]
        
    except Exception as e:
        print(f"ERROR fetching city data: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return pd.DataFrame()


def fetch_trends_data():
    """Fetch Google Trends market signals data"""
    client = get_bigquery_client()
    if not client:
        return pd.DataFrame()
    
    dataset_id = os.getenv('GCP_DATASET_ID', 'db')
    
    query = f"""
    SELECT 
        week_start_date,
        search_term,
        category,
        avg_interest_score,
        region
    FROM `{client.project}.{dataset_id}.google_search_trends`
    ORDER BY search_term, week_start_date
    """
    
    try:
        df = client.query(query).to_dataframe()
        # Ensure week_start_date is parsed as datetime
        if not df.empty and 'week_start_date' in df.columns:
            df['week_start_date'] = pd.to_datetime(df['week_start_date'])
        return df
    except Exception as e:
        print(f"Error fetching Google Trends data: {e}")
        return pd.DataFrame()


# Layout
app.layout = html.Div(children=[
    # Location component for page load detection
    dcc.Location(id='url', refresh=False),
    
    # Hidden stores
    html.Div(style={'display': 'none'}, children=[
        dcc.Store(id='fred-data-store'),
        dcc.Store(id='zillow-data-store'),
        dcc.Store(id='city-data-store'),
        dcc.Store(id='data-date-store'),
        dcc.Store(id='trends-data-store'),
        dcc.Store(id='ai-briefing-store'),       # Cached briefing response
        dcc.Store(id='qa-count-store'),           # Daily Q&A usage count
        dcc.Store(id='audience-store', data='homebuyer'),  # Active audience
        dcc.Store(id='session-id-store'),         # Per-session UUID
    ]),

    # Main visible content
    html.Div(className='main-container', children=[
    
    # Header
    html.Div(className='header', children=[
        html.H1('Vant'),
        html.P('Housing Market Intelligence Platform'),
        html.P(id='data-date-display', style={'fontSize': '0.9rem', 'color': 'rgba(237, 237, 237, 0.6)', 'marginTop': '0.5rem'})
    ]),
    
    # Tabs
    dcc.Tabs(id='main-tabs', value='market-signals', children=[

        # Tab 1: Market Signals — Intelligence Panel (LEFT, auto-selected)
        dcc.Tab(label='Market Signals', value='market-signals', children=[

        # ── Freshness banner ──────────────────────────────────────────────────
        html.Div(id='freshness-bar', className='freshness-bar', children=[
            html.Span('📡 Data freshness: loading...'),
        ], style={'marginTop': '1.5rem'}),

        # ── Composite Stress Index ────────────────────────────────────────────
        html.Div(className='section-title', children='Composite Stress Index'),
        dbc.Row([
            dbc.Col([
                html.Div(className='csi-gauge-card', style={'height': '260px'}, children=[
                    dcc.Loading(type='circle', children=[
                        dcc.Graph(id='csi-gauge', config={'displayModeBar': False}, style={'height': '240px', 'width': '100%'})
                    ])
                ])
            ], md=4),
            dbc.Col([
                html.Div(className='chart-container', style={'height': '260px', 'padding': '0.5rem'}, children=[
                    dcc.Loading(type='default', children=[
                        dcc.Graph(id='csi-sparkline', config={'displayModeBar': False}, style={'height': '240px'})
                    ])
                ])
            ], md=8),
        ], style={'marginBottom': '1.5rem'}),

        # ── 4-Signal Trends chart ─────────────────────────────────────────────
        html.Div(className='section-title', children='Forward-Looking Market Indicators'),

        dbc.Row([
            dbc.Col([
                html.Div(className='metric-card', style={'borderLeftColor': '#8B4789', 'minHeight': '100px', 'height': '100%'}, children=[
                    html.H4('Estate Sales', style={'color': '#8B4789', 'marginBottom': '0.5rem'}),
                    html.P('Involuntary supply from inheritance/estates',
                           style={'fontSize': '0.85rem', 'color': 'rgba(237,237,237,0.7)', 'margin': '0'})
                ])
            ], md=3),
            dbc.Col([
                html.Div(className='metric-card', style={'borderLeftColor': '#E74C3C', 'minHeight': '100px', 'height': '100%'}, children=[
                    html.H4('Foreclosure Auctions', style={'color': '#E74C3C', 'marginBottom': '0.5rem'}),
                    html.P('Forced selling / market distress',
                           style={'fontSize': '0.85rem', 'color': 'rgba(237,237,237,0.7)', 'margin': '0'})
                ])
            ], md=3),
            dbc.Col([
                html.Div(className='metric-card', style={'borderLeftColor': '#F39C12', 'minHeight': '100px', 'height': '100%'}, children=[
                    html.H4('Home Insurance', style={'color': '#F39C12', 'marginBottom': '0.5rem'}),
                    html.P('Rising homeowner carry costs',
                           style={'fontSize': '0.85rem', 'color': 'rgba(237,237,237,0.7)', 'margin': '0'})
                ])
            ], md=3),
            dbc.Col([
                html.Div(className='metric-card', style={'borderLeftColor': '#3498DB', 'minHeight': '100px', 'height': '100%'}, children=[
                    html.H4('Mortgage Assumption', style={'color': '#3498DB', 'marginBottom': '0.5rem'}),
                    html.P('Buyers seeking rate relief',
                           style={'fontSize': '0.85rem', 'color': 'rgba(237,237,237,0.7)', 'margin': '0'})
                ])
            ], md=3)
        ], align='stretch', style={'marginBottom': '1.5rem'}),

        html.Div(className='chart-container', children=[
            dcc.Loading(id='loading-trends', type='default',
                        children=dcc.Graph(id='trends-chart', config={'displayModeBar': True}))
        ]),

        html.P('Source: Google Trends (pytrends) | Weekly search interest 0–100 | Updated daily',
               style={'textAlign': 'center', 'color': 'rgba(237,237,237,0.4)', 'fontSize': '0.8rem', 'margin': '0.5rem 0 2rem'}),

        # ── AI Weekly Briefing ────────────────────────────────────────────────
        html.Div(className='section-title', children='AI Weekly Briefing'),

        html.Div(className='briefing-panel', children=[

            # Audience toggle row
            dbc.Row([
                dbc.Col([
                    html.Div([
                        html.Span('Audience: ', style={'color': 'rgba(237,237,237,0.6)', 'fontSize': '0.85rem', 'marginRight': '0.5rem'}),
                        html.Button('🏠 Homebuyer',    id='btn-audience-homebuyer',   n_clicks=0,
                                    className='audience-btn active', style={'marginRight': '0.4rem'}),
                        html.Button('📈 RE Investor',  id='btn-audience-re_investor',  n_clicks=0,
                                    className='audience-btn', style={'marginRight': '0.4rem'}),
                        html.Button('🏦 REIT Investor', id='btn-audience-reit_investor', n_clicks=0,
                                    className='audience-btn'),
                    ])
                ], md=8),
                dbc.Col([
                    html.Button(
                        id='generate-briefing-btn',
                        children='✨ Generate Briefing',
                        n_clicks=0,
                        className='generate-btn',
                        style={'float': 'right'}
                    )
                ], md=4),
            ], style={'marginBottom': '1.2rem'}),

            # Briefing output
            dcc.Loading(id='loading-briefing', type='dot', children=[
                html.Div(id='briefing-output', children=[
                    html.P(
                        'Select an audience and click Generate Briefing to get an AI-powered market analysis.',
                        style={'color': 'rgba(237,237,237,0.4)', 'fontStyle': 'italic', 'textAlign': 'center',
                               'padding': '2rem 0'}
                    )
                ])
            ]),
        ]),

        # ── Q&A Chatbox ───────────────────────────────────────────────────────
        html.Div(className='section-title', children='Ask the Market'),

        html.Div(className='qa-box', children=[
            dbc.Row([
                dbc.Col([
                    dcc.Input(
                        id='qa-input',
                        type='text',
                        placeholder='Ask about the current market... (e.g., "What markets look stressed?")',
                        className='qa-input',
                        style={'width': '100%'},
                        debounce=False,
                        n_submit=0,
                    )
                ], md=9),
                dbc.Col([
                    html.Button(
                        id='qa-submit-btn',
                        children='Ask →',
                        n_clicks=0,
                        style={
                            'background': '#2a2a2a', 'color': 'var(--primary-accent)',
                            'border': '1px solid var(--primary-accent)',
                            'borderRadius': '6px', 'padding': '0.5rem 1.2rem',
                            'cursor': 'pointer', 'width': '100%', 'fontWeight': '600'
                        }
                    )
                ], md=3)
            ], style={'marginBottom': '0.8rem'}),

            dcc.Loading(id='loading-qa', type='default', children=[
                html.Div(id='qa-answer-output')
            ]),

            # Usage counter
            html.Div(id='qa-usage-display', style={
                'marginTop': '0.8rem',
                'color': 'rgba(237,237,237,0.4)',
                'fontSize': '0.78rem',
                'textAlign': 'right'
            }),
        ]),

        html.Div(style={'height': '2rem'}),

        ]),  # End Market Signals Tab

        # Tab 2: Fundamentals (RIGHT)
        dcc.Tab(label='Fundamentals', value='fundamentals', children=[
    
    # Filters
    html.Div(className='filter-section', style={'marginTop': '1.5rem'}, children=[
        dbc.Row([
            dbc.Col([
                html.Label('Search City:', style={'color': '#ededed', 'fontWeight': '500', 'marginBottom': '0.5rem'}),
                dcc.Dropdown(
                    id='city-search',
                    options=[],
                    placeholder='Search for a city...',
                    className='dash-dropdown',
                    clearable=True,
                    style={'color': '#333333', 'backgroundColor': '#ffffff'},
                )
            ], md=6),
            dbc.Col([
                html.Label('Map Metric:', style={'color': '#ededed', 'fontWeight': '500', 'marginBottom': '0.5rem'}),
                dcc.Dropdown(
                    id='map-metric',
                    options=[
                        {'label': 'Home Value Index (ZHVI)', 'value': 'zhvi'},
                        {'label': 'Median Sale Price', 'value': 'median_sale_price'},
                        {'label': 'Active Listings', 'value': 'active_listings'},
                        {'label': 'Market Heat Index', 'value': 'market_heat_index'},
                        {'label': 'New Listings', 'value': 'new_listings'},
                        {'label': 'Sales Count', 'value': 'sales_count'},
                        {'label': 'New Construction - Median Sale Price', 'value': 'new_construction_median_sale_price'},
                        {'label': 'New Construction - Sales Count', 'value': 'new_construction_sales_count'},
                        {'label': 'New Homeowner Affordability', 'value': 'new_homeowner_affordability'}
                    ],
                    value='zhvi',
                    clearable=False,
                    className='dash-dropdown',
                    style={'color': '#333333', 'backgroundColor': '#ffffff'},
                )
            ], md=6)
        ])
    ]),
    
    # US Map Section
    html.Div(className='section-title', children='Housing Market by State & City'),
    html.Div(className='chart-container', children=[
        dcc.Loading(
            id='loading-map',
            type='default',
            children=dcc.Graph(id='us-map', config={'displayModeBar': False})
        )
    ]),
    
    
    # City Time Series Section
    html.Div(className='section-title', children='City Historical Trends', style={'marginTop': '3rem'}),
    
    # Time Series Filters
    html.Div(className='filter-section', children=[
        dbc.Row([
            dbc.Col([
                html.Label('Select City', style={'marginBottom': '0.5rem', 'display': 'block'}),
                dcc.Dropdown(
                    id='timeseries-city-search',
                    options=[],
                    placeholder='Search for a city...',
                    className='dash-dropdown',
                    style={'color': '#333333', 'backgroundColor': '#ffffff'},
                )
            ], md=6),
            dbc.Col([
                html.Label('Select Metric', style={'marginBottom': '0.5rem', 'display': 'block'}),
                dcc.Dropdown(
                    id='timeseries-metric',
                    options=[
                        {'label': 'ZHVI (Home Value Index)', 'value': 'zhvi'},
                        {'label': 'Median Sale Price', 'value': 'median_sale_price'},
                        {'label': 'Median List Price', 'value': 'median_list_price'},
                        {'label': 'Active Listing Count', 'value': 'active_listing_count'},
                        {'label': 'Median Days to Pending', 'value': 'median_days_to_pending'},
                        {'label': 'New Homeowner Affordability', 'value': 'new_homeowner_affordability'},
                    ],
                    value='zhvi',
                    clearable=False,
                    className='dash-dropdown',
                    style={'color': '#333333', 'backgroundColor': '#ffffff'},
                )
            ], md=6)
        ])
    ]),
    
    # Time Series Chart
    html.Div(className='chart-container', children=[
        dcc.Graph(id='city-timeseries', config={'displayModeBar': False})
    ]),
    
    # Economic Indicators Section
    html.Div(className='section-title', children='Economic Indicators', style={'marginTop': '3rem'}),
    dbc.Row([
        dbc.Col([
            html.Div(className='chart-container', children=[
                dcc.Loading(
                    id='loading-mortgage',
                    type='default',
                    children=dcc.Graph(id='mortgage-chart')
                )
            ])
        ], md=6),
        dbc.Col([
            html.Div(className='chart-container', children=[
                dcc.Loading(
                    id='loading-cpi',
                    type='default',
                    children=dcc.Graph(id='cpi-chart')
                )
            ])
        ], md=6)
    ]),

        ]),  # End Fundamentals Tab


    ]),  # End Tabs

    ]),  # End of main-container
])


# Callbacks
@app.callback(
    Output('city-search', 'options'),
    Input('city-search', 'id')
)
def update_city_options(_):
    """Populate city search dropdown with all available cities"""
    client = get_bigquery_client()
    if not client:
        return []
    
    dataset_id = os.getenv('GCP_DATASET_ID', 'db')
    query = f"""
    SELECT DISTINCT region_name, state_name
    FROM `{client.project}.{dataset_id}.zillow_metrics`
    WHERE region_type = 'msa'
    ORDER BY region_name
    """
    
    try:
        df = client.query(query).to_dataframe()
        return [{'label': f"{row['region_name']}", 'value': row['region_name']} 
                for _, row in df.iterrows()]
    except Exception as e:
        print(f"Error fetching cities: {e}")
        return []

@app.callback(
    [Output('fred-data-store', 'data'),
     Output('zillow-data-store', 'data'),
     Output('city-data-store', 'data'),
     Output('data-date-store', 'data'),
     Output('trends-data-store', 'data')],
    Input('url', 'pathname')  # Changed from city-search to url - fetch once on page load
)
def fetch_data_on_load(pathname):
    """Fetch all data once on page load - city filtering happens client-side"""
    fred_df = fetch_fred_data()
    zillow_df = fetch_zillow_data(None)
    trends_df = fetch_trends_data()
    
    # Get both state aggregated data and city data with coordinates (top 5 per state)
    state_df = get_state_aggregated_data()
    city_df = get_city_data_with_coords()
    
    # Store data without selected_city - filtering happens in map callback
    combined_data = {
        'state': state_df.to_json(date_format='iso', orient='split') if not state_df.empty else None,
        'city': city_df.to_json(date_format='iso', orient='split') if not city_df.empty else None,
    }
    
    # Extract latest date for display
    data_date = None
    if not city_df.empty and 'date' in city_df.columns:
        data_date = pd.to_datetime(city_df['date']).max().isoformat()
    
    return (
        fred_df.to_json(date_format='iso', orient='split') if not fred_df.empty else None,
        zillow_df.to_json(date_format='iso', orient='split') if not zillow_df.empty else None,
        combined_data,
        data_date,
        trends_df.to_json(date_format='iso', orient='split') if not trends_df.empty else None
    )

@app.callback(
    Output('data-date-display', 'children'),
    Input('data-date-store', 'data')
)
def update_data_date(date_str):
    """Display the data release date"""
    if not date_str:
        return ''
    try:
        date_obj = pd.to_datetime(date_str)
        return f"Data as of {date_obj.strftime('%B %Y')}"
    except:
        return ''


@app.callback(
    Output('us-map', 'figure'),
    [Input('city-data-store', 'data'),
     Input('map-metric', 'value'),
     Input('city-search', 'value')]  # Added city-search for filtering
)
def update_map(combined_data, metric, selected_city):
    """Update US map with state choropleth and city scatter overlay, with city zoom"""
    if not combined_data or not combined_data.get('state'):
        # Return empty map
        fig = go.Figure()
        fig.update_layout(
            title='No data available',
            template='plotly_dark',
            plot_bgcolor='#000000',
            paper_bgcolor='#1a1a1a',
            font=dict(color='#ededed'),
            geo=dict(
                scope='usa',
                projection_type='albers usa',
                showland=True,
                landcolor='#2a2a2a',
                coastlinecolor='#444',
                showlakes=True,
                lakecolor='#1a1a1a'
            )
        )
        return fig
    
    # Load state data
    state_df = pd.read_json(io.StringIO(combined_data['state']), orient='split')
    
    # Check if metric exists in state data
    has_state_data = metric in state_df.columns
    
    # Filter out states with 0 values (from NaN filling) only if we have the metric
    if has_state_data:
        state_df_filtered = state_df[state_df[metric] > 0].copy()
    else:
        state_df_filtered = pd.DataFrame()  # No state data for this metric
    
    # Create figure with state choropleth
    fig = go.Figure()
    
    # Add state choropleth layer only if we have data
    if not state_df_filtered.empty and has_state_data:
        fig.add_trace(go.Choropleth(
            locations=state_df_filtered['state_name'],
            z=state_df_filtered[metric],
            locationmode='USA-states',
            colorscale=[[0, '#1a1a1a'], [0.5, '#A7D129'], [1, '#d4ff00']],
            colorbar=dict(
                title=metric.replace('_', ' ').title(),
                tickprefix='$' if ('price' in metric or 'zhvi' in metric) and 'affordability' not in metric else '',
                tickformat=',.0%' if 'affordability' in metric else ',.0f',
                bgcolor='#1a1a1a',
                tickfont=dict(color='#ededed')
            ),
            hovertemplate='<b>%{location}</b><br>' +
                          f'{metric.replace("_", " ").title()}: ' +
                          ('%{z:.1%}' if 'affordability' in metric else ('$%{z:,.0f}' if 'price' in metric or 'zhvi' in metric else '%{z:,.0f}')) +
                          '<br>Cities: %{customdata[0]}<extra></extra>',
            customdata=state_df_filtered[['city_count']].values,
            marker_line_color='#444',
            marker_line_width=0.5,
            showscale=True
        ))
    
    # Add city scatter layer if coordinates are available
    if combined_data.get('city'):
        city_df = pd.read_json(io.StringIO(combined_data['city']), orient='split')
        
        # Check if metric exists in city data
        has_city_data = metric in city_df.columns
        
        if has_city_data:
            # Filter out cities with 0 values to avoid black markers
            # But always include selected city if one is chosen
            if selected_city:
                # Include selected city + cities with values > 0
                city_df_filtered = city_df[
                    (city_df['region_name'] == selected_city) | (city_df[metric] > 0)
                ].copy()
            else:
                # Only show cities with values > 0 (this prevents black markers)
                city_df_filtered = city_df[city_df[metric] > 0].copy()
        else:
            city_df_filtered = pd.DataFrame()
        
        if not city_df_filtered.empty and has_city_data:
            # Normalize sizes for better visualization
            max_val = city_df_filtered[metric].max()
            min_val = city_df_filtered[metric].min()
            if max_val > min_val:
                city_df_filtered['size'] = 5 + 15 * (city_df_filtered[metric] - min_val) / (max_val - min_val)
            else:
                city_df_filtered['size'] = 10
            
            # Highlight selected city in gold
            if selected_city:
                # Create separate color column for display
                city_df_filtered['marker_color'] = city_df_filtered.apply(
                    lambda row: '#FFD700' if row['region_name'] == selected_city else None,
                    axis=1
                )
                city_df_filtered['size'] = city_df_filtered.apply(
                    lambda row: 25 if row['region_name'] == selected_city else row['size'],
                    axis=1
                )
                # For non-selected cities, use the metric value for color
                mask = city_df_filtered['marker_color'].isna()
                city_df_filtered.loc[mask, 'marker_color'] = city_df_filtered.loc[mask, metric]
            else:
                city_df_filtered['marker_color'] = city_df_filtered[metric]
            
            # Create custom hover data with metric values
            city_df_filtered['hover_value'] = city_df_filtered[metric]
            
            fig.add_trace(go.Scattergeo(
                lon=city_df_filtered['lng'],
                lat=city_df_filtered['lat'],
                text=city_df_filtered['region_name'],
                mode='markers',
                marker=dict(
                    size=city_df_filtered['size'],
                    color=city_df_filtered['marker_color'],
                    colorscale=[[0, '#A7D129'], [1, '#d4ff00']],
                    line=dict(width=0.5, color='#000'),
                    sizemode='diameter',
                    showscale=False,
                    cmin=city_df_filtered[metric].min() if not selected_city else None,
                    cmax=city_df_filtered[metric].max() if not selected_city else None
                ),
                customdata=city_df_filtered[['hover_value']].values,
                hovertemplate='<b>%{text}</b><br>' +
                              f'{metric.replace("_", " ").title()}: ' +
                              ('%{customdata[0]:.1%}' if 'affordability' in metric else ('$%{customdata[0]:,.0f}' if 'price' in metric or 'zhvi' in metric else '%{customdata[0]:,.0f}')) +
                              '<extra></extra>',
                name='Cities'
            ))
    
    # Get latest date for title
    latest_date_str = ''
    if combined_data.get('city'):
        city_df = pd.read_json(io.StringIO(combined_data['city']), orient='split')
        if 'date' in city_df.columns and not city_df.empty:
            latest_date = pd.to_datetime(city_df['date']).max()
            latest_date_str = f" (Data as of {latest_date.strftime('%B %Y')})"
    
    # Set zoom and center if city is selected
    geo_settings = dict(
        scope='usa',
        projection_type='albers usa',
        showland=True,
        landcolor='#2a2a2a',
        coastlinecolor='#444',
        showlakes=True,
        lakecolor='#1a1a1a',
        bgcolor='#000000'
    )
    
    if selected_city and combined_data.get('city'):
        city_df = pd.read_json(combined_data['city'], orient='split')
        selected_city_data = city_df[city_df['region_name'] == selected_city]
        if not selected_city_data.empty:
            lat = selected_city_data.iloc[0]['lat']
            lon = selected_city_data.iloc[0]['lng']
            geo_settings.update({
                'center': {'lat': lat, 'lon': lon},
                'projection_scale': 8  # Reduced zoom for better view
            })
    
    fig.update_layout(
        title=f'US Housing Market - {metric.replace("_", " ").title()}' + 
              (f' (Focused on {selected_city})' if selected_city else '') +
              latest_date_str,
        template='plotly_dark',
        plot_bgcolor='#000000',
        paper_bgcolor='#1a1a1a',
        font=dict(color='#ededed'),
        geo=geo_settings,
        height=600,
        showlegend=False
    )
    
    return fig

@app.callback(
    Output('mortgage-chart', 'figure'),
    Input('fred-data-store', 'data')
)
def update_mortgage_chart(fred_data_json):
    """Update mortgage rate chart"""
    if not fred_data_json:
        return go.Figure().update_layout(
            title='No FRED data available',
            template='plotly_dark',
            plot_bgcolor='#000000',
            paper_bgcolor='#1a1a1a',
            font=dict(color='#ededed')
        )
    
    fred_df = pd.read_json(io.StringIO(fred_data_json), orient='split')
    mortgage_data = fred_df[fred_df['series_id'] == 'MORTGAGE30US'].copy()
    
    if mortgage_data.empty:
        return go.Figure().update_layout(
            title='No mortgage rate data available',
            template='plotly_dark',
            plot_bgcolor='#000000',
            paper_bgcolor='#1a1a1a',
            font=dict(color='#ededed')
        )
    
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=mortgage_data['date'],
        y=mortgage_data['value'],
        mode='lines',
        name='30-Year Mortgage Rate',
        line=dict(color='#A7D129', width=2),
        fill='tozeroy',
        fillcolor='rgba(167, 209, 41, 0.1)'
    ))
    
    fig.update_layout(
        title='30-Year Mortgage Rate',
        xaxis_title='Date',
        yaxis_title='Rate (%)',
        template='plotly_dark',
        hovermode='x unified',
        plot_bgcolor='#000000',
        paper_bgcolor='#1a1a1a',
        font=dict(color='#ededed'),
        xaxis=dict(gridcolor='#333'),
        yaxis=dict(gridcolor='#333')
    )
    
    return fig

@app.callback(
    Output('cpi-chart', 'figure'),
    Input('fred-data-store', 'data')
)
def update_cpi_chart(fred_data_json):
    """Update CPI chart"""
    if not fred_data_json:
        return go.Figure().update_layout(
            title='No FRED data available',
            template='plotly_dark',
            plot_bgcolor='#000000',
            paper_bgcolor='#1a1a1a',
            font=dict(color='#ededed')
        )
    
    fred_df = pd.read_json(fred_data_json, orient='split')
    cpi_data = fred_df[fred_df['series_id'] == 'CPIAUCSL'].copy()
    
    if cpi_data.empty:
        return go.Figure().update_layout(
            title='No CPI data available',
            template='plotly_dark',
            plot_bgcolor='#000000',
            paper_bgcolor='#1a1a1a',
            font=dict(color='#ededed')
        )
    
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=cpi_data['date'],
        y=cpi_data['value'],
        mode='lines',
        name='Consumer Price Index',
        line=dict(color='#A7D129', width=2),
        fill='tozeroy',
        fillcolor='rgba(167, 209, 41, 0.1)'
    ))
    
    fig.update_layout(
        title='Consumer Price Index (CPI)',
        xaxis_title='Date',
        yaxis_title='Index Value',
        template='plotly_dark',
        hovermode='x unified',
        plot_bgcolor='#000000',
        paper_bgcolor='#1a1a1a',
        font=dict(color='#ededed'),
        xaxis=dict(gridcolor='#333'),
        yaxis=dict(gridcolor='#333')
    )
    
    return fig

@app.callback(
    Output('trends-chart', 'figure'),
    Input('trends-data-store', 'data')
)
def update_trends_chart(trends_data_json):
    """Update Google Trends multi-line time series chart"""
    if not trends_data_json:
        return go.Figure().update_layout(
            title='No Google Trends data available',
            template='plotly_dark',
            plot_bgcolor='#000000',
            paper_bgcolor='#1a1a1a',
            font=dict(color='#ededed')
        )
    
    trends_df = pd.read_json(io.StringIO(trends_data_json), orient='split')
    
    if trends_df.empty:
        return go.Figure().update_layout(
            title='No data available',
            template='plotly_dark',
            plot_bgcolor='#000000',
            paper_bgcolor='#1a1a1a',
            font=dict(color='#ededed')
        )
    
    # Define colors for each metric
    metric_colors = {
        'Estate Sales': '#8B4789',  # Purple
        'Foreclosure Auctions': '#E74C3C',  # Red
        'Home Insurance': '#F39C12',  # Orange
        'Mortgage Assumption': '#3498DB'  # Blue
    }
    
    fig = go.Figure()
    
    # Add a line for each metric
    for search_term in trends_df['search_term'].unique():
        term_data = trends_df[trends_df['search_term'] == search_term].copy()
        
        # Get category for description
        category = term_data['category'].iloc[0] if not term_data.empty else ''
        
        fig.add_trace(go.Scatter(
            x=term_data['week_start_date'],
            y=term_data['avg_interest_score'],
            mode='lines',
            name=search_term,
            line=dict(color=metric_colors.get(search_term, '#A7D129'), width=2.5),
            hovertemplate=f'<b>{search_term}</b><br>' +
                          f'{category}<br>' +
                          'Week: %{x|%b %d, %Y}<br>' +
                          'Interest Score: %{y}<extra></extra>'
        ))
    
    fig.update_layout(
        title='Google Trends Market Signals (5-Year Trend)',
        xaxis_title='Date',
        yaxis_title='Search Interest Score (0-100)',
        template='plotly_dark',
        hovermode='x unified',
        plot_bgcolor='#000000',
        paper_bgcolor='#1a1a1a',
        font=dict(color='#ededed'),
        xaxis=dict(
            gridcolor='#333',
            rangeslider=dict(visible=True, bgcolor='#1a1a1a'),
            rangeselector=dict(
                buttons=list([
                    dict(count=3, label="3m", step="month", stepmode="backward"),
                    dict(count=6, label="6m", step="month", stepmode="backward"),
                    dict(count=1, label="1y", step="year", stepmode="backward"),
                    dict(count=2, label="2y", step="year", stepmode="backward"),
                    dict(step="all", label="All")
                ]),
                bgcolor='#1a1a1a',
                activecolor='#A7D129',
                font=dict(color='#ededed')
            )
        ),
        yaxis=dict(gridcolor='#333', range=[0, 105]),
        legend=dict(
            orientation='h',
            yanchor='bottom',
            y=1.02,
            xanchor='right',
            x=1,
            bgcolor='rgba(0,0,0,0.5)',
            bordercolor='#444',
            borderwidth=1
        ),
        height=600
    )
    
    return fig

@app.callback(
    Output('timeseries-city-search', 'options'),
    Input('timeseries-city-search', 'id')
)
def update_timeseries_city_options(_):
    """Populate time series city search dropdown with all available cities"""
    client = get_bigquery_client()
    if not client:
        return []
    
    dataset_id = os.getenv('GCP_DATASET_ID', 'db')
    query = f"""
    SELECT DISTINCT region_name, state_name
    FROM `{client.project}.{dataset_id}.zillow_metrics`
    WHERE region_type = 'msa'
    ORDER BY region_name
    """
    
    try:
        df = client.query(query).to_dataframe()
        return [{'label': f"{row['region_name']}", 'value': row['region_name']}
                for _, row in df.iterrows()]
    except Exception as e:
        print(f"Error fetching cities: {e}")
        return []

@app.callback(
    Output('city-timeseries', 'figure'),
    [Input('timeseries-city-search', 'value'),
     Input('timeseries-metric', 'value')]
)
def update_city_timeseries(selected_city, selected_metric):
    """Update time series chart for selected city and metric"""
    
    # Return empty chart if no city selected
    if not selected_city:
        fig = go.Figure()
        fig.update_layout(
            title='Select a city to view historical data',
            template='plotly_dark',
            plot_bgcolor='#000000',
            paper_bgcolor='#1a1a1a',
            font=dict(color='#ededed'),
            height=400
        )
        return fig
    
    # Fetch data from BigQuery
    client = get_bigquery_client()
    if not client:
        return go.Figure()
    
    dataset_id = os.getenv('GCP_DATASET_ID', 'db')
    
    # Map UI metric names to database metric_type values
    metric_mapping = {
        'zhvi': 'zhvi',
        'median_sale_price': 'median_sale_price',
        'median_list_price': 'median_list_price',
        'active_listing_count': 'active_listing_count',
        'median_days_to_pending': 'median_days_to_pending',
        'new_homeowner_affordability': 'new_homeowner_affordability'
    }
    
    metric_type = metric_mapping.get(selected_metric, selected_metric)
    
    query = f"""
    SELECT date, value
    FROM `{client.project}.{dataset_id}.zillow_metrics`
    WHERE region_name = @city_name
    AND metric_type = @metric_type
    AND region_type = 'msa'
    ORDER BY date ASC
    """
    
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("city_name", "STRING", selected_city),
            bigquery.ScalarQueryParameter("metric_type", "STRING", metric_type)
        ]
    )
    
    try:
        df = client.query(query, job_config=job_config).to_dataframe()
        
        if df.empty:
            fig = go.Figure()
            fig.update_layout(
                title=f'No data available for {selected_city} - {selected_metric.replace("_", " ").title()}',
                template='plotly_dark',
                plot_bgcolor='#000000',
                paper_bgcolor='#1a1a1a',
                font=dict(color='#ededed'),
                height=400
            )
            return fig
        
        # Convert timestamp to datetime
        df['date'] = pd.to_datetime(df['date'])
        
        # Create line chart
        fig = go.Figure()
        
        fig.add_trace(go.Scatter(
            x=df['date'],
            y=df['value'],
            mode='lines',
            line=dict(color='#A7D129', width=2),
            fill='tozeroy',
            fillcolor='rgba(167, 209, 41, 0.1)',
            name=selected_metric.replace('_', ' ').title(),
            hovertemplate='<b>%{x|%b %Y}</b><br>' +
                         ('Value: %{y:.1%}' if 'affordability' in selected_metric else 
                          ('Value: $%{y:,.0f}' if 'price' in selected_metric or 'zhvi' in selected_metric 
                           else 'Value: %{y:,.0f}')) +
                         '<extra></extra>'
        ))
        
        fig.update_layout(
            title=f'{selected_city} - {selected_metric.replace("_", " ").title()}',
            template='plotly_dark',
            plot_bgcolor='#000000',
            paper_bgcolor='#1a1a1a',
            font=dict(color='#ededed'),
            xaxis=dict(
                title='Date',
                gridcolor='#333',
                showgrid=True
            ),
            yaxis=dict(
                title=selected_metric.replace('_', ' ').title(),
                gridcolor='#333',
                showgrid=True,
                tickprefix='$' if ('price' in selected_metric or 'zhvi' in selected_metric) and 'affordability' not in selected_metric else '',
                tickformat=',.0%' if 'affordability' in selected_metric else ',.0f'
            ),
            height=400,
            hovermode='x unified',
            margin=dict(l=60, r=20, t=60, b=60)
        )
        
        return fig
        
    except Exception as e:
        print(f"Error fetching time series data: {e}")
        fig = go.Figure()
        fig.update_layout(
            title=f'Error loading data for {selected_city}',
            template='plotly_dark',
            plot_bgcolor='#000000',
            paper_bgcolor='#1a1a1a',
            font=dict(color='#ededed'),
            height=400
        )
        return fig

# ===========================================================================
# NEW CALLBACKS — Market Signals Tab 2
# ===========================================================================

# ---------------------------------------------------------------------------
# CSI Gauge + Sparkline
# ---------------------------------------------------------------------------
@app.callback(
    [Output('csi-gauge', 'figure'),
     Output('csi-sparkline', 'figure'),
     Output('freshness-bar', 'children')],
    Input('trends-data-store', 'data')
)
def update_csi_charts(trends_json):
    """Compute Composite Stress Index from Trends data and render gauge + sparkline."""
    SIGNAL_WEIGHTS = {
        'Foreclosure Auctions': 0.40,
        'Home Insurance':       0.30,
        'Estate Sales':         0.20,
        'Mortgage Assumption':  0.10,
    }
    SIGNAL_COLORS = {
        'Estate Sales':         '#8B4789',
        'Foreclosure Auctions': '#E74C3C',
        'Home Insurance':       '#F39C12',
        'Mortgage Assumption':  '#3498DB',
    }

    empty_gauge = go.Figure(go.Indicator(
        mode='gauge+number', value=0,
        title={'text': 'No data', 'font': {'color': '#ededed'}},
        gauge={'axis': {'range': [0, 100]}, 'bar': {'color': '#444'}},
    ))
    empty_gauge.update_layout(
        paper_bgcolor='#1a1a1a', font_color='#ededed', margin=dict(l=20, r=20, t=40, b=20))

    empty_spark = go.Figure()
    empty_spark.update_layout(
        template='plotly_dark', paper_bgcolor='#1a1a1a', plot_bgcolor='#000',
        margin=dict(l=10, r=10, t=20, b=20))

    if not trends_json:
        return empty_gauge, empty_spark, [html.Span('📡 No Trends data available')]

    try:
        df = pd.read_json(io.StringIO(trends_json), orient='split')
        df['week_start_date'] = pd.to_datetime(df['week_start_date'])
    except Exception:
        return empty_gauge, empty_spark, [html.Span('📡 Error reading Trends data')]

    # Normalize each signal using rolling 52-week window
    signals = df['search_term'].unique()
    csi_series = None

    for term in signals:
        weight = SIGNAL_WEIGHTS.get(term, 0)
        if weight == 0:
            continue
        term_df = df[df['search_term'] == term].set_index('week_start_date')['avg_interest_score'].sort_index()

        # 52-week rolling min/max normalization
        roll_max = term_df.rolling(52, min_periods=4).max()
        roll_min = term_df.rolling(52, min_periods=4).min()
        rng = (roll_max - roll_min).replace(0, 1)
        normalized = ((term_df - roll_min) / rng * 100).clip(0, 100)

        weighted = normalized * weight
        csi_series = weighted if csi_series is None else csi_series.add(weighted, fill_value=0)

    if csi_series is None or csi_series.empty:
        return empty_gauge, empty_spark, [html.Span('📡 Cannot compute CSI')]

    csi_series = csi_series.dropna().sort_index()
    current_csi = round(csi_series.iloc[-1], 1)

    # Determine stress level
    if current_csi < 30:
        bar_color, stress_label = '#27ae60', "Low Stress — Seller's Market"
    elif current_csi < 55:
        bar_color, stress_label = '#f1c40f', 'Moderate Stress'
    elif current_csi < 75:
        bar_color, stress_label = '#e67e22', 'Elevated Distress'
    else:
        bar_color, stress_label = '#e74c3c', 'High Distress'

    # Gauge
    gauge_fig = go.Figure(go.Indicator(
        mode='gauge+number+delta',
        value=current_csi,
        delta={'reference': round(csi_series.iloc[-5], 1) if len(csi_series) >= 5 else current_csi,
               'valueformat': '.1f'},
        title={'text': f'<b>{stress_label}</b>', 'font': {'size': 13, 'color': '#ededed'}},
        number={'font': {'color': bar_color, 'size': 36}},
        gauge={
            'axis': {'range': [0, 100], 'tickfont': {'color': '#aaa'}, 'tickwidth': 1},
            'bar': {'color': bar_color, 'thickness': 0.3},
            'steps': [
                {'range': [0,  30], 'color': 'rgba(39,174,96,0.12)'},
                {'range': [30, 55], 'color': 'rgba(241,196,15,0.12)'},
                {'range': [55, 75], 'color': 'rgba(230,126,34,0.12)'},
                {'range': [75, 100], 'color': 'rgba(231,76,60,0.12)'},
            ],
            'threshold': {'line': {'color': bar_color, 'width': 3}, 'thickness': 0.85, 'value': current_csi},
        }
    ))
    gauge_fig.update_layout(
        paper_bgcolor='#1a1a1a', font_color='#ededed',
        margin=dict(l=10, r=10, t=50, b=10), height=220
    )

    # Sparkline — CSI over time with 4-week rolling avg
    csi_smooth = csi_series.rolling(4, min_periods=1).mean()
    spark_fig = go.Figure()
    spark_fig.add_trace(go.Scatter(
        x=csi_series.index, y=csi_series.values,
        mode='lines', line=dict(color='rgba(167,209,41,0.3)', width=1),
        showlegend=False, name='Weekly CSI'
    ))
    spark_fig.add_trace(go.Scatter(
        x=csi_smooth.index, y=csi_smooth.values,
        mode='lines', line=dict(color='#A7D129', width=2),
        showlegend=False, name='4-week avg'
    ))
    spark_fig.add_hline(y=55, line_dash='dot', line_color='rgba(230,126,34,0.5)', annotation_text='Elevated')
    spark_fig.add_hline(y=75, line_dash='dot', line_color='rgba(231,76,60,0.4)', annotation_text='High')
    spark_fig.update_layout(
        title={'text': 'CSI History (52-week normalized)', 'font': {'size': 12, 'color': '#aaa'}},
        template='plotly_dark', paper_bgcolor='#1a1a1a', plot_bgcolor='#000',
        xaxis=dict(gridcolor='#222', showgrid=True),
        yaxis=dict(gridcolor='#222', range=[0, 100], title='Score'),
        margin=dict(l=40, r=10, t=40, b=20), height=200, hovermode='x unified'
    )

    # Freshness bar
    last_date = df['week_start_date'].max()
    freshness = [
        html.Span('📡', style={'marginRight': '0.4rem'}),
        html.Span(f'Trends last updated: {last_date.strftime("%b %d, %Y")}',
                  style={'marginRight': '2rem'}),
        html.Span(f'CSI: {current_csi:.1f} / 100 — {stress_label}',
                  style={'color': bar_color, 'fontWeight': '600'}),
    ]
    return gauge_fig, spark_fig, freshness


# ---------------------------------------------------------------------------
# Audience store — track which audience is selected
# ---------------------------------------------------------------------------
@app.callback(
    [Output('audience-store', 'data'),
     Output('btn-audience-homebuyer', 'className'),
     Output('btn-audience-re_investor', 'className'),
     Output('btn-audience-reit_investor', 'className')],
    [Input('btn-audience-homebuyer', 'n_clicks'),
     Input('btn-audience-re_investor', 'n_clicks'),
     Input('btn-audience-reit_investor', 'n_clicks')],
    prevent_initial_call=True
)
def update_audience(n_home, n_rei, n_reit):
    """Track the active audience and update button visual state."""
    from dash import ctx
    triggered = ctx.triggered_id
    mapping = {
        'btn-audience-homebuyer':    'homebuyer',
        'btn-audience-re_investor':  're_investor',
        'btn-audience-reit_investor': 'reit_investor',
    }
    active = mapping.get(triggered, 'homebuyer')
    classes = {
        'btn-audience-homebuyer':    'audience-btn active' if active == 'homebuyer'    else 'audience-btn',
        'btn-audience-re_investor':  'audience-btn active' if active == 're_investor'  else 'audience-btn',
        'btn-audience-reit_investor':'audience-btn active' if active == 'reit_investor'else 'audience-btn',
    }
    return active, classes['btn-audience-homebuyer'], classes['btn-audience-re_investor'], classes['btn-audience-reit_investor']


# ---------------------------------------------------------------------------
# Generate Briefing — calls Vertex AI (or cache)
# ---------------------------------------------------------------------------
@app.callback(
    [Output('briefing-output', 'children'),
     Output('ai-briefing-store', 'data'),
     Output('qa-count-store', 'data')],
    Input('generate-briefing-btn', 'n_clicks'),
    State('audience-store', 'data'),
    prevent_initial_call=True
)
def generate_briefing_callback(n_clicks, audience):
    """On-demand AI briefing: checks BQ cache first, then calls Gemini if needed."""
    audience = audience or 'homebuyer'

    if not AI_AVAILABLE:
        return [html.P('AI module not available. Check server logs.', style={'color': '#e74c3c'})], None, 0

    try:
        result = generate_insights.generate_briefing(audience)
    except Exception as e:
        return [html.P(f'Error generating briefing: {str(e)[:200]}', style={'color': '#e74c3c'})], None, 0

    # Parse sentiment
    score = result.get('sentiment_score', 0)
    if score > 0.3:
        sentiment_class, sentiment_text = 'sentiment-bullish', 'BULLISH'
    elif score < -0.3:
        sentiment_class, sentiment_text = 'sentiment-bearish', 'BEARISH'
    else:
        sentiment_class, sentiment_text = 'sentiment-neutral', 'NEUTRAL'

    # Cache age
    gen_at = result.get('generated_at', '')
    cache_note = '(from cache)' if result.get('from_cache') else '(freshly generated)'
    if gen_at:
        try:
            gen_dt = datetime.fromisoformat(gen_at.replace('Z', ''))
            age_min = int((datetime.utcnow() - gen_dt).total_seconds() / 60)
            cache_note = f'Generated {age_min}m ago {cache_note}'
        except Exception:
            pass

    # CSI reading
    csi = result.get('composite_stress_index')
    csi_text = f'{csi:.1f} / 100' if csi is not None else 'N/A'

    # Key themes
    themes = result.get('key_themes', [])
    theme_pills = [html.Span(t, className='theme-pill') for t in themes]

    output = html.Div([
        # Header row
        dbc.Row([
            dbc.Col([
                html.Span(f'Composite Stress Index: ', style={'color': 'rgba(237,237,237,0.6)', 'fontSize': '0.85rem'}),
                html.Span(csi_text, style={'color': '#A7D129', 'fontWeight': '700', 'fontSize': '0.95rem'}),
            ], md=6),
            dbc.Col([
                html.Span(sentiment_text, className=f'sentiment-badge {sentiment_class}'),
                html.Span(f'  {cache_note}',
                          style={'color': 'rgba(237,237,237,0.4)', 'fontSize': '0.75rem', 'marginLeft': '0.5rem'}),
            ], md=6, style={'textAlign': 'right'}),
        ], style={'marginBottom': '1rem'}),

        # Narrative
        html.Div(
            result.get('narrative', ''),
            style={'color': 'rgba(237,237,237,0.88)', 'lineHeight': '1.75', 'fontSize': '0.92rem',
                   'whiteSpace': 'pre-wrap', 'marginBottom': '1rem'}
        ),

        # Key themes
        html.Div([
            html.Span('Key Themes: ', style={'color': 'rgba(237,237,237,0.5)', 'fontSize': '0.82rem'}),
            *theme_pills
        ]) if themes else None,
    ])

    qa_count = result.get('qa_count_today', 0)
    qa_limit = result.get('qa_limit', 5)

    return output, result, {'count': qa_count, 'limit': qa_limit}


# ---------------------------------------------------------------------------
# Q&A Submit
# ---------------------------------------------------------------------------
@app.callback(
    [Output('qa-answer-output', 'children'),
     Output('qa-usage-display', 'children'),
     Output('qa-count-store', 'data', allow_duplicate=True)],
    [Input('qa-submit-btn', 'n_clicks'),
     Input('qa-input', 'n_submit')],
    [State('qa-input', 'value'),
     State('audience-store', 'data'),
     State('qa-count-store', 'data'),
     State('session-id-store', 'data')],
    prevent_initial_call=True
)
def submit_qa(n_clicks, n_submit, question, audience, qa_data, session_id):
    """Submit a Q&A question, check daily rate limit, call Gemini."""
    if not question or not question.strip():
        return None, '', qa_data

    audience = audience or 'homebuyer'
    qa_data = qa_data or {'count': 0, 'limit': 5}
    count = qa_data.get('count', 0)
    limit = qa_data.get('limit', 5)

    if not AI_AVAILABLE:
        usage = html.Span(f'AI unavailable', style={'color': '#e74c3c'})
        return html.Div('AI module not available.', style={'color': '#e74c3c'}), usage, qa_data

    try:
        result = generate_insights.ask_question(
            question=question.strip(),
            audience=audience,
            session_id=session_id,
        )
    except Exception as e:
        return html.Div(f'Error: {str(e)[:200]}', style={'color': '#e74c3c'}), '', qa_data

    new_count = result.get('qa_count_today', count)
    new_limit = result.get('qa_limit', limit)

    answer_div = html.Div(result.get('answer', ''), className='qa-answer')
    usage_color = '#e74c3c' if new_count >= new_limit else 'rgba(237,237,237,0.4)'
    usage_text = f'{new_count} / {new_limit} questions used today'
    if new_count >= new_limit:
        usage_text += ' — limit reached, resets tomorrow'

    return answer_div, html.Span(usage_text, style={'color': usage_color}), {'count': new_count, 'limit': new_limit}


# ---------------------------------------------------------------------------
# Initialize session ID on load
# ---------------------------------------------------------------------------
@app.callback(
    Output('session-id-store', 'data'),
    Input('url', 'pathname'),
    State('session-id-store', 'data')
)
def init_session_id(pathname, existing):
    if existing:
        return existing
    import uuid
    return str(uuid.uuid4())


# ===========================================================================
# /api/run-pipeline  — Cloud Scheduler endpoint
# ===========================================================================
import flask

@app.server.route('/api/run-pipeline', methods=['POST'])
def run_pipeline():
    """
    Cloud Scheduler calls this endpoint daily to run the data fetch pipeline.
    Protected by X-Pipeline-Secret header.
    """
    secret = os.getenv('PIPELINE_SECRET', '')
    if secret and flask.request.headers.get('X-Pipeline-Secret') != secret:
        return flask.jsonify({'error': 'Unauthorized'}), 401

    data_engine_dir = str(Path(__file__).parent.parent / 'data_engine')
    results = {}

    steps = [
        ('fetch_trends',    ['python', 'fetch_trends.py', '--incremental']),
        ('preprocess_trends', ['python', 'preprocess_trends.py']),
        ('upload_trends',   ['python', 'upload_trends_to_bigquery.py']),
        ('fetch_reddit',    ['python', 'fetch_reddit.py', '--incremental']),
        ('preprocess_reddit', ['python', 'preprocess_reddit.py']),
        ('upload_reddit',   ['python', 'upload_reddit_json.py']),
    ]

    for step_name, cmd in steps:
        try:
            proc = subprocess.run(
                cmd, cwd=data_engine_dir,
                capture_output=True, text=True, timeout=300
            )
            results[step_name] = {
                'returncode': proc.returncode,
                'stdout': proc.stdout[-500:] if proc.stdout else '',
                'stderr': proc.stderr[-300:] if proc.stderr else '',
            }
        except subprocess.TimeoutExpired:
            results[step_name] = {'error': 'timeout'}
        except Exception as e:
            results[step_name] = {'error': str(e)}

    return flask.jsonify({
        'status': 'complete',
        'updated_at': datetime.utcnow().isoformat() + 'Z',
        'steps': results,
    })


# Expose the Flask server for gunicorn (required for Cloud Run)
server = app.server

# Run the app
if __name__ == '__main__':
    # This runs when you execute the script locally
    # For production (Cloud Run), gunicorn will use the 'server' variable above
    app.run(debug=True, host='127.0.0.1', port=8050)
