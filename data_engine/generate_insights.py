"""
generate_insights.py

Vertex AI Gemini-powered AI briefing and Q&A module for the Housing Dashboard.

Features:
- On-demand AI Weekly Briefings per audience type (homebuyer / re_investor / reit_investor)
- 24-hour BigQuery cache: same briefing is served from BQ, not a new Gemini call
- Q&A chatbox support with configurable daily cap (default: 5 calls/day)
- Context is built from aggregated BQ data — NOT raw posts (keeps token count low)
- CLI --dry-run flag for testing without calling Gemini

Usage:
    python generate_insights.py --audience homebuyer
    python generate_insights.py --audience re_investor --dry-run
    python generate_insights.py --qa "What markets look stressed?" --audience homebuyer
    python generate_insights.py --create-tables  # Run BigQuery schema creation
"""

import os
import json
import hashlib
import uuid
import argparse
import logging
from datetime import datetime, date, timedelta
from typing import Optional, Dict, Any
from pathlib import Path

from dotenv import load_dotenv
from google.cloud import bigquery

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

PROJECT_ID = os.getenv('GCP_PROJECT_ID', 'vant-486316')
DATASET_ID = os.getenv('GCP_DATASET_ID', 'db')
MAX_QA_PER_DAY = int(os.getenv('MAX_QA_PER_DAY', '5'))
GEMINI_MODEL = os.getenv('GEMINI_MODEL', 'gemini-1.5-flash')
VERTEX_LOCATION = os.getenv('VERTEX_LOCATION', 'us-central1')

AUDIENCE_LABELS = {
    'homebuyer': 'First-Time & Move-Up Homebuyer',
    're_investor': 'Real Estate Investor',
    'reit_investor': 'REIT / Institutional Investor',
}

SIGNAL_WEIGHTS = {
    'Foreclosure Auctions': 0.40,
    'Home Insurance': 0.30,
    'Estate Sales': 0.20,
    'Mortgage Assumption': 0.10,
}

# ---------------------------------------------------------------------------
# BigQuery helpers
# ---------------------------------------------------------------------------

def get_bq_client() -> bigquery.Client:
    return bigquery.Client(project=PROJECT_ID)


def create_tables(client: bigquery.Client):
    """Run the create_insights_schema.sql file to create BQ tables."""
    sql_path = Path(__file__).parent / 'create_insights_schema.sql'
    with open(sql_path, 'r') as f:
        sql = f.read()

    for stmt in sql.split(';'):
        stmt = stmt.strip()
        if not stmt or stmt.startswith('--'):
            continue
        stmt = stmt.replace('{project_id}', PROJECT_ID).replace('{dataset_id}', DATASET_ID)
        try:
            client.query(stmt).result()
            logger.info("Table created/verified.")
        except Exception as e:
            logger.warning(f"Table creation warning (may already exist): {e}")


# ---------------------------------------------------------------------------
# Context builder: aggregated BQ data for the briefing prompt
# ---------------------------------------------------------------------------

def build_context(client: bigquery.Client) -> Dict[str, Any]:
    """
    Pull last 4 weeks of Trends scores + last 7 days of Reddit summaries.
    Returns a compact dict suitable for embedding in a Gemini prompt.
    Target: < 1,500 tokens total.
    """
    context = {}

    # 1. Google Trends — weekly averages for last 4 weeks
    try:
        trends_query = f"""
        SELECT
            search_term,
            category,
            ROUND(AVG(avg_interest_score), 1) AS avg_score,
            ROUND(MAX(avg_interest_score), 1) AS peak_score,
            ROUND(MIN(avg_interest_score), 1) AS low_score
        FROM `{PROJECT_ID}.{DATASET_ID}.google_search_trends`
        WHERE week_start_date >= DATE_SUB(CURRENT_DATE(), INTERVAL 28 DAY)
        GROUP BY search_term, category
        ORDER BY category, search_term
        """
        trends_df = client.query(trends_query).to_dataframe()
        context['trends_4wk'] = trends_df.to_dict(orient='records') if not trends_df.empty else []
    except Exception as e:
        logger.warning(f"Could not fetch Trends context: {e}")
        context['trends_4wk'] = []

    # 2. Compute Composite Stress Index from last 4 weeks
    try:
        csi_query = f"""
        WITH recent AS (
            SELECT search_term, avg_interest_score
            FROM `{PROJECT_ID}.{DATASET_ID}.google_search_trends`
            WHERE week_start_date >= DATE_SUB(CURRENT_DATE(), INTERVAL 28 DAY)
        ),
        baseline AS (
            SELECT search_term,
                   MAX(avg_interest_score) AS max_score,
                   MIN(avg_interest_score) AS min_score
            FROM `{PROJECT_ID}.{DATASET_ID}.google_search_trends`
            WHERE week_start_date >= DATE_SUB(CURRENT_DATE(), INTERVAL 365 DAY)
            GROUP BY search_term
        )
        SELECT
            r.search_term,
            AVG(
                CASE
                    WHEN (b.max_score - b.min_score) > 0
                    THEN (r.avg_interest_score - b.min_score) / (b.max_score - b.min_score) * 100
                    ELSE 50
                END
            ) AS normalized_score
        FROM recent r
        JOIN baseline b ON r.search_term = b.search_term
        GROUP BY r.search_term
        """
        csi_df = client.query(csi_query).to_dataframe()
        csi = 0.0
        for _, row in csi_df.iterrows():
            weight = SIGNAL_WEIGHTS.get(row['search_term'], 0)
            csi += row['normalized_score'] * weight
        context['composite_stress_index'] = round(csi, 1)
    except Exception as e:
        logger.warning(f"Could not compute CSI: {e}")
        context['composite_stress_index'] = None

    # 3. Reddit — top 20 posts from last 7 days, summarized
    try:
        reddit_query = f"""
        SELECT
            subreddit,
            title,
            location AS area,
            score,
            num_comments
        FROM `{PROJECT_ID}.{DATASET_ID}.reddit_posts`
        WHERE created_date >= DATE_SUB(CURRENT_DATE(), INTERVAL 7 DAY)
        ORDER BY score DESC
        LIMIT 25
        """
        reddit_df = client.query(reddit_query).to_dataframe()

        # Summarize: top titles + subreddit distribution
        if not reddit_df.empty:
            top_posts = reddit_df[['subreddit', 'title', 'area', 'score']].head(15).to_dict(orient='records')
            subreddit_counts = reddit_df['subreddit'].value_counts().to_dict()
            context['reddit_7d'] = {
                'top_posts': top_posts,
                'subreddit_counts': subreddit_counts,
                'total_posts': len(reddit_df),
            }
        else:
            context['reddit_7d'] = {'top_posts': [], 'subreddit_counts': {}, 'total_posts': 0}
    except Exception as e:
        logger.warning(f"Could not fetch Reddit context: {e}")
        context['reddit_7d'] = {'top_posts': [], 'subreddit_counts': {}, 'total_posts': 0}

    context['as_of_date'] = date.today().isoformat()
    return context


# ---------------------------------------------------------------------------
# Prompt builder
# ---------------------------------------------------------------------------

AUDIENCE_PROMPTS = {
    'homebuyer': """
You are a housing market analyst briefing first-time and move-up homebuyers.
Focus on: home affordability, inventory levels, mortgage rate environment,
buyer competition, and whether now is a good time to buy or wait.
Highlight any geographic areas showing unusual opportunity or risk.
""",
    're_investor': """
You are a housing market analyst briefing real estate investors.
Focus on: distress signals (foreclosures, estate sales), price momentum,
relocation and migration trends, carry cost pressures (insurance),
and opportunities in specific metro areas or asset types.
""",
    'reit_investor': """
You are a housing market analyst briefing REIT and institutional real estate investors.
Focus on: macro supply/demand dynamics, sector-level trends (SFR, multifamily),
leading indicators of price changes, and systemic risk signals.
Be concise and data-driven.
""",
}


def build_prompt(context: Dict[str, Any], audience: str) -> str:
    audience_instruction = AUDIENCE_PROMPTS.get(audience, AUDIENCE_PROMPTS['homebuyer'])
    context_json = json.dumps(context, indent=2, default=str)

    return f"""
{audience_instruction.strip()}

## Weekly Housing Market Data (as of {context.get('as_of_date', 'recent')})

```json
{context_json}
```

## Your Task

Based on the data above, provide a housing market briefing with:

1. **Composite Stress Index Reading**: Interpret the CSI score ({context.get('composite_stress_index', 'N/A')}/100).
   - 0–30: Low stress (seller's market)
   - 31–55: Moderate stress  
   - 56–75: Elevated stress
   - 76–100: High distress

2. **Market Narrative** (2–3 paragraphs): What do the Google Trends signals and Reddit conversations tell us about the current market? Be specific about which signals are moving and what they imply.

3. **Key Themes** (3–5 bullet points): The most actionable takeaways for a {AUDIENCE_LABELS.get(audience, audience)}.

4. **Sentiment**: End with a single word: BULLISH, NEUTRAL, or BEARISH overall for this audience.

Keep the total response under 400 words. Be direct and actionable — avoid hedging language.
    """.strip()


def build_qa_prompt(question: str, briefing_text: str) -> str:
    return f"""
You are a housing market AI assistant. The user has already seen this briefing:

---
{briefing_text[:2000]}
---

Answer this follow-up question in 2–4 sentences. Be specific and cite the data from the briefing where possible.
Do NOT make up data not in the briefing. If you don't know, say so.

Question: {question}
    """.strip()


# ---------------------------------------------------------------------------
# BigQuery: cache check + store
# ---------------------------------------------------------------------------

def get_cached_briefing(client: bigquery.Client, audience: str) -> Optional[Dict]:
    """Return today's cached briefing for this audience, or None if not found."""
    query = f"""
    SELECT *
    FROM `{PROJECT_ID}.{DATASET_ID}.ai_insights`
    WHERE generated_date = CURRENT_DATE()
      AND audience_type = @audience
    ORDER BY generated_at DESC
    LIMIT 1
    """
    job_config = bigquery.QueryJobConfig(
        query_parameters=[bigquery.ScalarQueryParameter('audience', 'STRING', audience)]
    )
    try:
        rows = list(client.query(query, job_config=job_config).result())
        if rows:
            row = rows[0]
            return {
                'narrative': row.narrative,
                'sentiment_score': row.sentiment_score,
                'key_themes': json.loads(row.key_themes) if row.key_themes else [],
                'composite_stress_index': row.composite_stress_index,
                'generated_at': row.generated_at.isoformat() if row.generated_at else None,
                'from_cache': True,
            }
    except Exception as e:
        logger.warning(f"Cache check failed: {e}")
    return None


def store_briefing(
    client: bigquery.Client,
    audience: str,
    narrative: str,
    sentiment_score: float,
    key_themes: list,
    csi: Optional[float],
    context: Dict,
    token_count: int,
):
    row = {
        'generated_date': date.today().isoformat(),
        'audience_type': audience,
        'narrative': narrative,
        'sentiment_score': sentiment_score,
        'key_themes': json.dumps(key_themes),
        'composite_stress_index': csi,
        'source_signals': json.dumps(context, default=str)[:10000],  # cap size
        'model_version': GEMINI_MODEL,
        'generated_at': datetime.utcnow().isoformat(),
        'token_count': token_count,
    }
    table_ref = f"{PROJECT_ID}.{DATASET_ID}.ai_insights"
    errors = client.insert_rows_json(table_ref, [row])
    if errors:
        logger.error(f"BQ insert errors: {errors}")
    else:
        logger.info(f"Briefing stored in BQ for audience={audience}")


def get_qa_count_today(client: bigquery.Client) -> int:
    query = f"""
    SELECT COUNT(*) AS cnt
    FROM `{PROJECT_ID}.{DATASET_ID}.ai_insights_qa_log`
    WHERE call_date = CURRENT_DATE()
    """
    try:
        rows = list(client.query(query).result())
        return rows[0].cnt if rows else 0
    except Exception as e:
        logger.warning(f"Q&A count check failed: {e}")
        return 0


def log_qa_call(
    client: bigquery.Client,
    audience: str,
    question: str,
    response_length: int,
    token_count: int,
    session_id: str,
):
    row = {
        'call_date': date.today().isoformat(),
        'called_at': datetime.utcnow().isoformat(),
        'audience_context': audience,
        'question_hash': hashlib.sha256(question.encode()).hexdigest(),
        'response_length': response_length,
        'token_count': token_count,
        'session_id': session_id,
    }
    table_ref = f"{PROJECT_ID}.{DATASET_ID}.ai_insights_qa_log"
    errors = client.insert_rows_json(table_ref, [row])
    if errors:
        logger.warning(f"Q&A log insert error: {errors}")


# ---------------------------------------------------------------------------
# Gemini caller
# ---------------------------------------------------------------------------

def parse_sentiment(text: str) -> float:
    """Extract sentiment score from model response."""
    text_upper = text.upper()
    if 'BULLISH' in text_upper[-100:]:
        return 0.8
    elif 'BEARISH' in text_upper[-100:]:
        return -0.8
    else:
        return 0.0


def parse_key_themes(text: str) -> list:
    """Extract bullet point themes from model response."""
    themes = []
    for line in text.split('\n'):
        line = line.strip()
        if line.startswith(('- ', '* ', '• ')) or (len(line) > 3 and line[0].isdigit() and line[1] == '.'):
            theme = line.lstrip('-*•0123456789. ').strip()
            if theme and len(theme) > 10:
                themes.append(theme)
    return themes[:5]


def call_gemini(prompt: str, dry_run: bool = False) -> Dict[str, Any]:
    """Call Vertex AI Gemini. Returns dict with text, token_count."""
    if dry_run:
        logger.info("DRY RUN — Gemini not called. Prompt preview:")
        logger.info(prompt[:500] + "...")
        return {
            'text': "[DRY RUN] This is a simulated briefing. The market shows moderate stress with rising foreclosure search trends and elevated home insurance costs, suggesting buyers should approach with caution in high-cost metros. NEUTRAL",
            'token_count': 0,
        }

    try:
        import vertexai
        from vertexai.generative_models import GenerativeModel, GenerationConfig

        vertexai.init(project=PROJECT_ID, location=VERTEX_LOCATION)
        model = GenerativeModel(GEMINI_MODEL)

        config = GenerationConfig(
            max_output_tokens=600,
            temperature=0.4,
        )
        response = model.generate_content(prompt, generation_config=config)
        text = response.text
        token_count = response.usage_metadata.total_token_count if hasattr(response, 'usage_metadata') else 0
        return {'text': text, 'token_count': token_count}

    except ImportError:
        raise RuntimeError(
            "Vertex AI SDK not installed. Run: pip install google-cloud-aiplatform"
        )
    except Exception as e:
        logger.error(f"Gemini call failed: {e}")
        raise


# ---------------------------------------------------------------------------
# Public API functions (called by Dash callbacks)
# ---------------------------------------------------------------------------

def generate_briefing(audience: str, dry_run: bool = False) -> Dict[str, Any]:
    """
    Main entry point for generating an AI briefing.
    Checks BQ cache first; calls Gemini only on cache miss.

    Returns dict with:
        narrative, sentiment_score, key_themes, composite_stress_index,
        generated_at, from_cache, qa_count_today, qa_limit
    """
    client = get_bq_client()

    if not dry_run:
        cached = get_cached_briefing(client, audience)
        if cached:
            logger.info(f"Cache hit for audience={audience}")
            cached['qa_count_today'] = get_qa_count_today(client)
            cached['qa_limit'] = MAX_QA_PER_DAY
            return cached

    logger.info(f"Cache miss — building context for audience={audience}")
    context = build_context(client)
    prompt = build_prompt(context, audience)

    result = call_gemini(prompt, dry_run=dry_run)
    text = result['text']
    token_count = result['token_count']

    sentiment_score = parse_sentiment(text)
    key_themes = parse_key_themes(text)
    csi = context.get('composite_stress_index')

    if not dry_run:
        store_briefing(client, audience, text, sentiment_score, key_themes, csi, context, token_count)

    qa_count = get_qa_count_today(client) if not dry_run else 0

    return {
        'narrative': text,
        'sentiment_score': sentiment_score,
        'key_themes': key_themes,
        'composite_stress_index': csi,
        'generated_at': datetime.utcnow().isoformat(),
        'from_cache': False,
        'qa_count_today': qa_count,
        'qa_limit': MAX_QA_PER_DAY,
    }


def ask_question(question: str, audience: str, session_id: Optional[str] = None, dry_run: bool = False) -> Dict[str, Any]:
    """
    Answer a follow-up question using today's briefing as context.
    Rate-limited to MAX_QA_PER_DAY calls per day.

    Returns dict with: answer, qa_count_today, qa_limit, rate_limited
    """
    if not session_id:
        session_id = str(uuid.uuid4())

    client = get_bq_client()

    # Check daily cap
    qa_count = get_qa_count_today(client)
    if qa_count >= MAX_QA_PER_DAY and not dry_run:
        return {
            'answer': f"Daily question limit reached ({MAX_QA_PER_DAY} questions/day). Come back tomorrow!",
            'qa_count_today': qa_count,
            'qa_limit': MAX_QA_PER_DAY,
            'rate_limited': True,
        }

    # Get briefing context (from cache)
    cached = get_cached_briefing(client, audience)
    if not cached:
        return {
            'answer': "Please generate a briefing first before asking questions.",
            'qa_count_today': qa_count,
            'qa_limit': MAX_QA_PER_DAY,
            'rate_limited': False,
        }

    prompt = build_qa_prompt(question, cached['narrative'])
    result = call_gemini(prompt, dry_run=dry_run)
    answer = result['text']
    token_count = result['token_count']

    if not dry_run:
        log_qa_call(client, audience, question, len(answer), token_count, session_id)
        qa_count += 1

    return {
        'answer': answer,
        'qa_count_today': qa_count,
        'qa_limit': MAX_QA_PER_DAY,
        'rate_limited': False,
    }


def get_composite_stress_index() -> Optional[float]:
    """Fetch current CSI from BQ for dashboard display without generating a full briefing."""
    client = get_bq_client()
    context = build_context(client)
    return context.get('composite_stress_index')


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description='Generate AI housing market briefings using Vertex AI Gemini')
    parser.add_argument('--audience', choices=['homebuyer', 're_investor', 'reit_investor'],
                        default='homebuyer', help='Audience type for the briefing')
    parser.add_argument('--qa', type=str, help='Ask a Q&A question instead of generating a briefing')
    parser.add_argument('--dry-run', action='store_true',
                        help='Build context and prompt but do NOT call Gemini')
    parser.add_argument('--create-tables', action='store_true',
                        help='Run the BigQuery schema creation SQL and exit')
    args = parser.parse_args()

    if args.create_tables:
        client = get_bq_client()
        create_tables(client)
        logger.info("Tables created/verified successfully.")
        return

    if args.qa:
        logger.info(f"Q&A mode | audience={args.audience} | question='{args.qa}'")
        result = ask_question(args.qa, args.audience, dry_run=args.dry_run)
        print("\n" + "="*60)
        print("ANSWER:")
        print(result['answer'])
        print(f"\nQ&A usage today: {result['qa_count_today']} / {result['qa_limit']}")
        print("="*60)
    else:
        logger.info(f"Generating briefing | audience={args.audience} | dry_run={args.dry_run}")
        result = generate_briefing(args.audience, dry_run=args.dry_run)
        print("\n" + "="*60)
        print(f"BRIEFING (audience={args.audience})")
        print(f"From cache: {result.get('from_cache', False)}")
        print(f"Composite Stress Index: {result.get('composite_stress_index', 'N/A')}")
        print(f"Sentiment: {result.get('sentiment_score', 0)}")
        print(f"Key Themes: {result.get('key_themes', [])}")
        print("="*60)
        print(result['narrative'])
        print("="*60)


if __name__ == '__main__':
    main()
