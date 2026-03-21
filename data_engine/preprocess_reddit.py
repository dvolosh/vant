"""
Reddit Data Preprocessor

Transforms raw Reddit JSON into post-level CSV with extracted metadata.
- Extracts location and purchase price from r/FirstTimeHomeBuyer posts
- Extracts city mentions from r/SameGrassButGreener posts
- Preserves full text for LLM analysis
"""

import json
import re
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import logging
import pandas as pd

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class RedditPreprocessor:
    """Handles preprocessing of raw Reddit data"""
    
    def __init__(self, raw_dir: str, processed_dir: str):
        """
        Initialize preprocessor
        
        Args:
            raw_dir: Directory with raw JSON files
            processed_dir: Directory to save processed CSV
        """
        self.raw_dir = Path(raw_dir)
        self.processed_dir = Path(processed_dir)
        self.processed_dir.mkdir(parents=True, exist_ok=True)
        
        # Load US cities data from CSV
        self._load_cities_data()
    
    def _load_cities_data(self):
        """Load US cities data from uscities.csv"""
        cities_file = Path(__file__).parent / 'uscities.csv'
        
        if not cities_file.exists():
            logger.warning(f"uscities.csv not found at {cities_file}, using fallback city list")
            # Fallback to basic list
            self.cities_df = None
            self.us_states = {
                'AL', 'AK', 'AZ', 'AR', 'CA', 'CO', 'CT', 'DE', 'FL', 'GA',
                'HI', 'ID', 'IL', 'IN', 'IA', 'KS', 'KY', 'LA', 'ME', 'MD',
                'MA', 'MI', 'MN', 'MS', 'MO', 'MT', 'NE', 'NV', 'NH', 'NJ',
                'NM', 'NY', 'NC', 'ND', 'OH', 'OK', 'OR', 'PA', 'RI', 'SC',
                'SD', 'TN', 'TX', 'UT', 'VT', 'VA', 'WA', 'WV', 'WI', 'WY', 'DC'
            }
            self.city_to_state = {}
            return
        
        try:
            # Load cities CSV
            df = pd.read_csv(cities_file)
            
            # Filter to cities with population >= 200,000 for faster processing
            # This reduces from ~31K cities to ~226 major cities
            self.cities_df = df[df['population'] >= 200000].copy()
            
            logger.info(f"Loaded {len(self.cities_df)} US cities (population >= 200K) from uscities.csv")
            logger.info(f"Filtered from {len(df)} total cities")
            
            # Create set of valid state abbreviations
            self.us_states = set(self.cities_df['state_id'].unique())
            
            # Create city-to-state mapping (city_ascii -> state_id)
            # Use city_ascii for better matching (handles special characters)
            self.city_to_state = dict(zip(
                self.cities_df['city_ascii'].str.lower(),
                self.cities_df['state_id']
            ))
            
        except Exception as e:
            logger.error(f"Error loading uscities.csv: {e}")
            self.cities_df = None
            self.us_states = set()
            self.city_to_state = {}
    
    def normalize_text(self, text: str) -> str:
        """
        Normalize text for CSV compatibility
        
        Removes or replaces problematic characters:
        - Emojis and non-ASCII characters
        - Null bytes
        - Control characters
        - Smart quotes -> regular quotes
        
        Args:
            text: Input text
            
        Returns:
            Normalized text (ASCII only)
        """
        if not text or not isinstance(text, str):
            return text
        
        # Remove null bytes
        text = text.replace('\x00', '')
        
        # Replace smart quotes with regular quotes (before ASCII conversion)
        text = text.replace('\u201c', '"').replace('\u201d', '"')  # Double quotes
        text = text.replace('\u2018', "'").replace('\u2019', "'")  # Single quotes
        text = text.replace('\u2032', "'").replace('\u2033', '"')  # Prime marks
        
        # Replace other common Unicode characters
        text = text.replace('\u2013', '-').replace('\u2014', '--')  # En/em dashes
        text = text.replace('\u2026', '...')  # Ellipsis
        text = text.replace('\u00a0', ' ')  # Non-breaking space
        
        # Remove all non-ASCII characters (including emojis)
        # Keep only: letters, numbers, punctuation, spaces, newlines, tabs
        text = ''.join(char for char in text if ord(char) < 128)
        
        # Remove control characters (except newlines and tabs)
        text = ''.join(char for char in text if ord(char) >= 32 or char in '\n\t')
        
        return text
    
    def extract_price(self, text: str) -> Optional[float]:
        """
        Extract purchase price from text
        
        Handles formats like:
        - $450,000
        - $450K
        - $450k
        - 450k
        - $1.2M
        
        Args:
            text: Post text
            
        Returns:
            Price as float or None
        """
        if not text:
            return None
        
        # Pattern for prices with K/M suffix
        # Matches: $450K, $450k, 450K, $1.2M, etc.
        pattern_km = r'\$?\s*(\d+(?:\.\d+)?)\s*([KkMm])'
        
        # Pattern for full prices
        # Matches: $450,000 or $450000
        pattern_full = r'\$\s*(\d{1,3}(?:,\d{3})+|\d{5,})'
        
        # Try K/M format first
        match = re.search(pattern_km, text)
        if match:
            amount = float(match.group(1))
            suffix = match.group(2).upper()
            
            if suffix == 'K':
                return amount * 1000
            elif suffix == 'M':
                return amount * 1000000
        
        # Try full format
        match = re.search(pattern_full, text)
        if match:
            # Remove commas and convert
            amount_str = match.group(1).replace(',', '')
            amount = float(amount_str)
            
            # Sanity check: reasonable house price range (50K - 50M)
            if 50000 <= amount <= 50000000:
                return amount
        
        return None
    
    def extract_location(self, text: str) -> Optional[str]:
        """
        Extract location (city, state) from text
        
        Looks for patterns like:
        - Austin, TX
        - Phoenix
        - San Francisco, CA
        
        Args:
            text: Post text
            
        Returns:
            Location string or None
        """
        if not text:
            return None
        
        # Pattern for "City, ST" format (most reliable)
        pattern_city_state = r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*),\s*([A-Z]{2})\b'
        
        match = re.search(pattern_city_state, text)
        if match:
            city = match.group(1)
            state = match.group(2)
            
            # Validate state abbreviation
            if state in self.us_states:
                return f"{city}, {state}"
        
        # If we have cities data, try to match city names and look up their states
        if self.city_to_state:
            # Look for city names in the text
            # Try multi-word cities first (e.g., "San Francisco", "New York")
            for city_name, state_abbr in self.city_to_state.items():
                # Create pattern for city name (case-insensitive, word boundaries)
                # Handle multi-word cities properly
                city_pattern = r'\b' + re.escape(city_name) + r'\b'
                if re.search(city_pattern, text, re.IGNORECASE):
                    # Return properly capitalized city name with state
                    # Find the actual city name from the dataframe for proper capitalization
                    if self.cities_df is not None:
                        city_row = self.cities_df[
                            self.cities_df['city_ascii'].str.lower() == city_name
                        ].iloc[0]
                        return f"{city_row['city_ascii']}, {state_abbr}"
                    else:
                        return f"{city_name.title()}, {state_abbr}"
        
        return None
    
    def extract_city_mentions(self, text: str) -> List[str]:
        """
        Extract all city mentions from text
        
        Args:
            text: Post text
            
        Returns:
            List of city names mentioned
        """
        if not text:
            return []
        
        cities = []
        seen_cities = set()  # Track to avoid duplicates
        
        # Check for "City, ST" format first (most reliable)
        pattern_city_state = r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*),\s*([A-Z]{2})\b'
        matches = re.finditer(pattern_city_state, text)
        
        for match in matches:
            city = match.group(1)
            state = match.group(2)
            
            if state in self.us_states:
                city_state = f"{city}, {state}"
                if city_state.lower() not in seen_cities:
                    cities.append(city_state)
                    seen_cities.add(city_state.lower())
        
        # If we have cities data, look for city names
        if self.city_to_state:
            # Sort cities by length (longest first) to match multi-word cities first
            sorted_cities = sorted(self.city_to_state.items(), 
                                 key=lambda x: len(x[0]), 
                                 reverse=True)
            
            for city_name, state_abbr in sorted_cities:
                city_pattern = r'\b' + re.escape(city_name) + r'\b'
                if re.search(city_pattern, text, re.IGNORECASE):
                    # Get proper capitalization from dataframe
                    if self.cities_df is not None:
                        city_row = self.cities_df[
                            self.cities_df['city_ascii'].str.lower() == city_name
                        ].iloc[0]
                        city_state = f"{city_row['city_ascii']}, {state_abbr}"
                    else:
                        city_state = f"{city_name.title()}, {state_abbr}"
                    
                    if city_state.lower() not in seen_cities:
                        cities.append(city_state)
                        seen_cities.add(city_state.lower())
        
        return cities
    
    def _extract_state_mentioned(self, text: str) -> Optional[str]:
        """
        Extract the most prominent US state abbreviation from text.
        Returns the first state code found (e.g., 'TX', 'CA', 'FL').
        """
        if not text:
            return None
        # Match state codes that appear after common location prepositions or standalone
        pattern = r'\b(in|to|from|near|around|moving to|relocating to|buying in)\s+(?:[A-Z][a-z]+,?\s+)?([A-Z]{2})\b'
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            state = match.group(2).upper()
            if state in self.us_states:
                return state
        # Fallback: "City, ST" pattern
        pattern2 = r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*,\s*([A-Z]{2})\b'
        match2 = re.search(pattern2, text)
        if match2:
            state = match2.group(1).upper()
            if state in self.us_states:
                return state
        return None

    def _format_top_comments(self, post: Dict) -> str:
        """
        Format top_comments list from raw post dict into a concatenated string for BQ storage.
        Returns empty string if no comments available.
        """
        comments = post.get('top_comments', [])
        if not comments:
            return ''
        # Join with separator, truncate to 2000 chars to avoid BQ row size issues
        joined = ' | '.join(c.strip().replace('\n', ' ') for c in comments if c.strip())
        return joined[:2000]

    def process_firsttimehomebuyer_post(self, post: Dict) -> Dict:
        """
        Process a single r/FirstTimeHomeBuyer post
        
        Args:
            post: Raw post dictionary
            
        Returns:
            Processed post dictionary
        """
        # Combine title and selftext for analysis
        title = self.normalize_text(post.get('title', ''))
        selftext = self.normalize_text(post.get('selftext', ''))
        full_text = f"{title}\n\n{selftext}"
        
        # Extract metadata
        location = self.extract_location(full_text)
        purchase_price = self.extract_price(full_text)
        
        return {
            'post_id': post.get('id'),
            'subreddit': 'FirstTimeHomeBuyer',
            'created_utc': post.get('created_utc'),
            'created_date': datetime.fromtimestamp(post.get('created_utc', 0)).strftime('%Y-%m-%d'),
            'title': title,
            'selftext': selftext,
            'score': post.get('score', 0),
            'num_comments': post.get('num_comments', 0),
            'author': post.get('author', '[deleted]'),
            'location': location,
            'purchase_price': purchase_price,
            'city_mentions': None,
            'top_comments_text': self._format_top_comments(post),
            'state_mentioned': self._extract_state_mentioned(full_text),
            'permalink': f"https://reddit.com{post.get('permalink', '')}"
        }
    
    def process_samegrassbutgreener_post(self, post: Dict) -> Dict:
        """
        Process a single r/SameGrassButGreener post
        
        Args:
            post: Raw post dictionary
            
        Returns:
            Processed post dictionary
        """
        # Combine title and selftext for analysis
        title = self.normalize_text(post.get('title', ''))
        selftext = self.normalize_text(post.get('selftext', ''))
        full_text = f"{title}\n\n{selftext}"
        
        # Extract city mentions
        city_mentions = self.extract_city_mentions(full_text)
        
        return {
            'post_id': post.get('id'),
            'subreddit': 'SameGrassButGreener',
            'created_utc': post.get('created_utc'),
            'created_date': datetime.fromtimestamp(post.get('created_utc', 0)).strftime('%Y-%m-%d'),
            'title': title,
            'selftext': selftext,
            'score': post.get('score', 0),
            'num_comments': post.get('num_comments', 0),
            'author': post.get('author', '[deleted]'),
            'location': None,
            'purchase_price': None,
            'city_mentions': '|'.join(city_mentions) if city_mentions else None,
            'top_comments_text': self._format_top_comments(post),
            'state_mentioned': self._extract_state_mentioned(full_text),
            'permalink': f"https://reddit.com{post.get('permalink', '')}"
        }
    
    def process_generic_post(self, post: Dict, subreddit: str) -> Dict:
        """
        Generic processor for new subreddits (RealEstate, realestateinvesting, personalfinance, moving).
        Extracts city mentions and state for AI context.
        """
        title = self.normalize_text(post.get('title', ''))
        selftext = self.normalize_text(post.get('selftext', ''))
        full_text = f"{title}\n\n{selftext}"
        city_mentions = self.extract_city_mentions(full_text)
        return {
            'post_id': post.get('id'),
            'subreddit': subreddit,
            'created_utc': post.get('created_utc'),
            'created_date': datetime.fromtimestamp(post.get('created_utc', 0)).strftime('%Y-%m-%d'),
            'title': title,
            'selftext': selftext,
            'score': post.get('score', 0),
            'num_comments': post.get('num_comments', 0),
            'author': post.get('author', '[deleted]'),
            'location': self.extract_location(full_text),
            'purchase_price': self.extract_price(full_text),
            'city_mentions': '|'.join(city_mentions) if city_mentions else None,
            'top_comments_text': self._format_top_comments(post),
            'state_mentioned': self._extract_state_mentioned(full_text),
            'permalink': f"https://reddit.com{post.get('permalink', '')}"
        }

    def process_subreddit(self, subreddit: str) -> pd.DataFrame:
        """
        Process all posts from a subreddit
        
        Args:
            subreddit: Subreddit name
            
        Returns:
            DataFrame with processed posts
        """
        logger.info(f"\n{'='*60}")
        logger.info(f"Processing r/{subreddit}")
        logger.info(f"{'='*60}")
        
        # Load raw posts
        posts_file = self.raw_dir / f"{subreddit}_posts.json"
        
        if not posts_file.exists():
            logger.warning(f"No data file found: {posts_file}")
            return pd.DataFrame()
        
        with open(posts_file, 'r', encoding='utf-8') as f:
            raw_posts = json.load(f)
        
        logger.info(f"Loaded {len(raw_posts)} raw posts")
        
        # Process each post
        processed_posts = []
        
        for post in raw_posts:
            # Skip deleted/removed posts
            if post.get('selftext') in ['[deleted]', '[removed]']:
                continue
            
            # Process based on subreddit
            if subreddit == 'FirstTimeHomeBuyer':
                processed = self.process_firsttimehomebuyer_post(post)
            elif subreddit == 'SameGrassButGreener':
                processed = self.process_samegrassbutgreener_post(post)
            else:
                # Generic processor for new subreddits
                processed = self.process_generic_post(post, subreddit)
            
            processed_posts.append(processed)
        
        logger.info(f"Processed {len(processed_posts)} posts")
        
        # Create DataFrame
        df = pd.DataFrame(processed_posts)
        
        # Log extraction stats
        if subreddit == 'FirstTimeHomeBuyer':
            location_count = df['location'].notna().sum()
            price_count = df['purchase_price'].notna().sum()
            logger.info(f"  Extracted locations: {location_count} ({location_count/len(df)*100:.1f}%)")
            logger.info(f"  Extracted prices: {price_count} ({price_count/len(df)*100:.1f}%)")
        elif subreddit == 'SameGrassButGreener':
            city_count = df['city_mentions'].notna().sum()
            logger.info(f"  Posts with city mentions: {city_count} ({city_count/len(df)*100:.1f}%)")
        
        return df
    
    def process_all(self) -> pd.DataFrame:
        """
        Process all subreddits and combine into single DataFrame
        
        Returns:
            Combined DataFrame with all posts
        """
        logger.info("Starting Reddit data preprocessing...")
        
        all_dfs = []
        
        # Process FirstTimeHomeBuyer
        df_ftb = self.process_subreddit('FirstTimeHomeBuyer')
        if not df_ftb.empty:
            all_dfs.append(df_ftb)
        
        # Process SameGrassButGreener
        df_sgg = self.process_subreddit('SameGrassButGreener')
        if not df_sgg.empty:
            all_dfs.append(df_sgg)
        
        # Combine
        if not all_dfs:
            logger.warning("No data to process")
            return pd.DataFrame()
        
        combined_df = pd.concat(all_dfs, ignore_index=True)
        
        # Sort by created_utc
        combined_df = combined_df.sort_values('created_utc')
        
        # Ensure new columns exist with empty string default (for BQ schema compatibility)
        for col in ['top_comments_text', 'state_mentioned']:
            if col not in combined_df.columns:
                combined_df[col] = ''
            else:
                combined_df[col] = combined_df[col].fillna('')
        
        # Save to CSV
        # Use doublequote (quotes within quotes are escaped as "") instead of backslash
        output_file = self.processed_dir / 'reddit_posts.csv'
        combined_df.to_csv(
            output_file, 
            index=False, 
            encoding='utf-8',
            quoting=1,  # QUOTE_ALL - quote all fields
            doublequote=True,  # Escape quotes by doubling them ("")
            lineterminator='\n'  # Use Unix line endings for consistency
        )
        
        logger.info(f"\n✅ Preprocessing complete!")
        logger.info(f"Total posts: {len(combined_df)}")
        logger.info(f"Output: {output_file}")
        
        return combined_df


def main():
    """Main execution function"""
    # Define paths
    raw_dir = Path(__file__).parent / 'reddit_raw'
    processed_dir = Path(__file__).parent / 'reddit_processed'
    
    # Create preprocessor
    preprocessor = RedditPreprocessor(
        raw_dir=str(raw_dir),
        processed_dir=str(processed_dir)
    )
    
    # Process all data
    preprocessor.process_all()


if __name__ == '__main__':
    main()
