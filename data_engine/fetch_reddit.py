"""
Reddit Data Fetcher using PullPush API

Fetches individual posts from r/FirstTimeHomeBuyer and r/SameGrassButGreener.
Uses PullPush.io API (no authentication required).

API Documentation: https://pullpush.io/
"""

import requests
import json
import time
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import logging
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class RedditFetcher:
    """Handles fetching Reddit posts from PullPush API"""
    
    # Subreddits to track
    SUBREDDITS = {
        'FirstTimeHomeBuyer': {
            'name': 'r/FirstTimeHomeBuyer',
            'description': 'First-time home buyer posts with location and price data',
            'focus': 'Extract location and purchase price for market tracking'
        },
        'SameGrassButGreener': {
            'name': 'r/SameGrassButGreener',
            'description': 'City comparison and relocation discussions',
            'focus': 'Extract city mentions for sentiment and recommendations'
        },
        'RealEstate': {
            'name': 'r/RealEstate',
            'description': 'General real estate investor discussions',
            'focus': 'Market trends, investment signals, geographic mentions'
        },
        'realestateinvesting': {
            'name': 'r/realestateinvesting',
            'description': 'Real estate investor community - deals, strategies, markets',
            'focus': 'Investment strategies, distress signals, market opportunities'
        },
        'personalfinance': {
            'name': 'r/personalfinance',
            'description': 'Personal finance discussions including home buying',
            'focus': 'Affordability concerns, mortgage discussion, buy vs rent sentiment'
        },
        'moving': {
            'name': 'r/moving',
            'description': 'Relocation discussions and destination recommendations',
            'focus': 'Migration patterns, geographic demand signals'
        }
    }
    
    BASE_URL = 'https://api.pullpush.io/reddit/search/submission/'
    COMMENTS_URL = 'https://api.pullpush.io/reddit/search/comment/'
    RATE_LIMIT_DELAY = 1.0  # 1 second between requests (60 req/min limit)
    MAX_RETRIES = 3
    BACKOFF_FACTOR = 2
    MAX_COMMENTS_PER_POST = 5  # Top comments to store for AI context
    
    def __init__(self, raw_dir: str):
        """
        Initialize Reddit fetcher
        
        Args:
            raw_dir: Directory to save raw JSON data
        """
        self.raw_dir = Path(raw_dir)
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        
        # Track last request time for rate limiting
        self.last_request_time = 0
        
    def _rate_limit(self):
        """Enforce rate limiting between API requests"""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.RATE_LIMIT_DELAY:
            time.sleep(self.RATE_LIMIT_DELAY - elapsed)
        self.last_request_time = time.time()
    
    def _make_request(self, params: Dict, retry_count: int = 0, url: Optional[str] = None) -> List[Dict]:
        """
        Make API request with rate limiting and error handling
        
        Args:
            params: Query parameters
            retry_count: Current retry attempt
            url: Optional override URL (defaults to BASE_URL)
            
        Returns:
            List of submissions or comments
        """
        self._rate_limit()
        
        request_url = url or self.BASE_URL
        
        try:
            response = requests.get(request_url, params=params, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            
            # PullPush returns data in 'data' field
            if 'data' in data:
                return data['data']
            else:
                logger.warning(f"Unexpected response format: {data.keys()}")
                return []
                
        except requests.exceptions.RequestException as e:
            if retry_count < self.MAX_RETRIES:
                wait_time = self.BACKOFF_FACTOR ** retry_count
                logger.warning(f"Request failed: {e}. Retrying in {wait_time}s...")
                time.sleep(wait_time)
                return self._make_request(params, retry_count + 1, url=url)
            else:
                logger.error(f"API request failed after {self.MAX_RETRIES} retries: {e}")
                raise

    def fetch_comments(self, post_id: str) -> List[str]:
        """
        Fetch top comments for a given post via PullPush comments endpoint.
        Returns a list of comment body strings (up to MAX_COMMENTS_PER_POST).
        Silently returns [] on failure to avoid breaking the main fetch loop.
        """
        try:
            params = {
                'link_id': f't3_{post_id}',
                'size': self.MAX_COMMENTS_PER_POST,
                'sort': 'desc',
                'sort_type': 'score',
            }
            comments = self._make_request(params, url=self.COMMENTS_URL)
            return [
                c.get('body', '') for c in comments
                if c.get('body') and c.get('body') not in ('[deleted]', '[removed]')
            ][:self.MAX_COMMENTS_PER_POST]
        except Exception as e:
            logger.debug(f"Could not fetch comments for {post_id}: {e}")
            return []

    
    def get_last_fetch_date(self, subreddit: str) -> Optional[int]:
        """
        Get the timestamp of the last fetched post for a subreddit
        
        Args:
            subreddit: Subreddit name
            
        Returns:
            Unix timestamp of last post or None if no data exists
        """
        metadata_file = self.raw_dir / f"{subreddit}_metadata.json"
        
        if not metadata_file.exists():
            return None
        
        try:
            with open(metadata_file, 'r', encoding='utf-8') as f:
                metadata = json.load(f)
                return metadata.get('last_created_utc')
        except Exception as e:
            logger.warning(f"Could not read metadata for {subreddit}: {e}")
            return None
    
    def save_posts(self, subreddit: str, posts: List[Dict], metadata: Dict):
        """
        Save posts and metadata to JSON files
        
        Args:
            subreddit: Subreddit name
            posts: List of post dictionaries
            metadata: Fetch metadata
        """
        # Save posts
        posts_file = self.raw_dir / f"{subreddit}_posts.json"
        
        # Load existing posts if file exists
        existing_posts = []
        if posts_file.exists():
            try:
                with open(posts_file, 'r', encoding='utf-8') as f:
                    existing_posts = json.load(f)
            except Exception as e:
                logger.warning(f"Could not load existing posts: {e}")
        
        # Merge and deduplicate by post ID
        all_posts = existing_posts + posts
        seen_ids = set()
        unique_posts = []
        for post in all_posts:
            post_id = post.get('id')
            if post_id and post_id not in seen_ids:
                unique_posts.append(post)
                seen_ids.add(post_id)
        
        # Sort by created_utc (oldest first)
        unique_posts.sort(key=lambda x: x.get('created_utc', 0))
        
        # Save merged posts
        with open(posts_file, 'w', encoding='utf-8') as f:
            json.dump(unique_posts, f, indent=2, ensure_ascii=False)
        
        # Save metadata
        metadata_file = self.raw_dir / f"{subreddit}_metadata.json"
        
        # Find last post timestamp
        last_created_utc = max([p.get('created_utc', 0) for p in unique_posts]) if unique_posts else None
        
        metadata_to_save = {
            'subreddit': subreddit,
            'name': self.SUBREDDITS[subreddit]['name'],
            'description': self.SUBREDDITS[subreddit]['description'],
            'last_created_utc': last_created_utc,
            'total_posts': len(unique_posts),
            'fetched_at': datetime.now().isoformat(),
            'fetch_metadata': metadata
        }
        
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(metadata_to_save, f, indent=2, ensure_ascii=False)
        
        logger.info(f"  Saved {len(unique_posts)} total posts to {posts_file}")
    
    def fetch_subreddit(
        self, 
        subreddit: str, 
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        incremental: bool = True,
        limit: int = 100
    ):
        """
        Fetch posts from a single subreddit
        
        Args:
            subreddit: Subreddit name (without r/)
            start_date: Start date (YYYY-MM-DD), defaults to last fetch or 30 days ago
            end_date: End date (YYYY-MM-DD), defaults to now
            incremental: If True, fetch only new posts since last update
            limit: Number of posts to fetch per request (max 100)
        """
        logger.info(f"\n{'='*60}")
        logger.info(f"Fetching r/{subreddit}")
        logger.info(f"{'='*60}")
        
        # Determine time range
        if incremental:
            last_utc = self.get_last_fetch_date(subreddit)
            if last_utc:
                # Fetch from last post + 1 second
                after_timestamp = last_utc + 1
                logger.info(f"Incremental update from {datetime.fromtimestamp(after_timestamp)}")
            else:
                # No previous data, fetch last 30 days
                after_timestamp = int((datetime.now() - timedelta(days=30)).timestamp())
                logger.info(f"No previous data, fetching last 30 days")
        else:
            # Full fetch from start_date or default
            if start_date:
                after_timestamp = int(datetime.strptime(start_date, '%Y-%m-%d').timestamp())
            else:
                after_timestamp = int((datetime.now() - timedelta(days=365)).timestamp())
            logger.info(f"Full fetch from {datetime.fromtimestamp(after_timestamp)}")
        
        # End timestamp
        if end_date:
            before_timestamp = int(datetime.strptime(end_date, '%Y-%m-%d').timestamp())
        else:
            before_timestamp = int(datetime.now().timestamp())
        
        # Fetch posts in batches
        all_posts = []
        current_after = after_timestamp
        
        while current_after < before_timestamp:
            params = {
                'subreddit': subreddit,
                'after': current_after,
                'before': before_timestamp,
                'size': limit,
                'sort': 'asc',  # Oldest first
                'sort_type': 'created_utc'
            }
            
            logger.info(f"  Fetching batch (after={datetime.fromtimestamp(current_after)})...")
            
            try:
                posts = self._make_request(params)
                
                if not posts:
                    logger.info("  No more posts found")
                    break
                
                all_posts.extend(posts)
                logger.info(f"  Retrieved {len(posts)} posts (total: {len(all_posts)})")
                
                # Update current_after to last post's timestamp + 1
                last_post_time = max([p.get('created_utc', 0) for p in posts])
                current_after = last_post_time + 1
                
                # If we got fewer posts than limit, we've reached the end
                if len(posts) < limit:
                    break
                    
            except Exception as e:
                logger.error(f"Error fetching batch: {e}")
                break
        
        if not all_posts:
            logger.info("  No new posts")
            return
        
        # Fetch top comments for posts that have them (≥3 comments)
        # This enriches AI context without over-fetching for low-engagement posts
        posts_with_comments = [p for p in all_posts if p.get('num_comments', 0) >= 3]
        logger.info(f"  Fetching comments for {len(posts_with_comments)} posts with ≥3 comments...")
        for post in posts_with_comments:
            post_id = post.get('id')
            if post_id:
                post['top_comments'] = self.fetch_comments(post_id)
        
        # Save posts
        metadata = {
            'after_timestamp': after_timestamp,
            'before_timestamp': before_timestamp,
            'posts_fetched': len(all_posts)
        }
        
        self.save_posts(subreddit, all_posts, metadata)
    
    def fetch_all(self, incremental: bool = True):
        """
        Fetch all configured subreddits
        
        Args:
            incremental: If True, only fetch new posts since last update
        """
        logger.info("Starting Reddit data fetch...")
        logger.info(f"Mode: {'Incremental' if incremental else 'Full download'}")
        logger.info(f"Subreddits to fetch: {len(self.SUBREDDITS)}")
        
        for subreddit in self.SUBREDDITS.keys():
            try:
                self.fetch_subreddit(subreddit, incremental=incremental)
            except Exception as e:
                logger.error(f"Error fetching r/{subreddit}: {e}")
                # Continue with other subreddits
        
        logger.info("\n✅ Reddit data fetch complete!")


def main():
    """Main execution function"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Fetch Reddit data from PullPush API')
    parser.add_argument('--subreddit', choices=['FirstTimeHomeBuyer', 'SameGrassButGreener', 'all'], 
                       default='all', help='Subreddit to fetch')
    parser.add_argument('--incremental', action='store_true', default=True,
                       help='Fetch only new posts since last update')
    parser.add_argument('--full', action='store_true',
                       help='Full fetch (override incremental)')
    parser.add_argument('--start-date', type=str,
                       help='Start date (YYYY-MM-DD) for full fetch')
    parser.add_argument('--end-date', type=str,
                       help='End date (YYYY-MM-DD)')
    parser.add_argument('--test', action='store_true',
                       help='Test mode: fetch last 7 days only')
    
    args = parser.parse_args()
    
    # Define paths
    raw_dir = Path(__file__).parent / 'reddit_raw'
    
    # Create fetcher
    fetcher = RedditFetcher(raw_dir=str(raw_dir))
    
    # Test mode
    if args.test:
        logger.info("TEST MODE: Fetching last 7 days")
        start_date = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
        if args.subreddit == 'all':
            for subreddit in fetcher.SUBREDDITS.keys():
                fetcher.fetch_subreddit(subreddit, start_date=start_date, incremental=False)
        else:
            fetcher.fetch_subreddit(args.subreddit, start_date=start_date, incremental=False)
        return
    
    # Determine incremental vs full
    incremental = args.incremental and not args.full
    
    # Fetch data
    if args.subreddit == 'all':
        fetcher.fetch_all(incremental=incremental)
    else:
        fetcher.fetch_subreddit(
            args.subreddit, 
            start_date=args.start_date,
            end_date=args.end_date,
            incremental=incremental
        )


if __name__ == '__main__':
    main()
