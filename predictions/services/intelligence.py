"""
Intelligence Service for SmartAcca
Integrates with API-Football and Google Gemini AI to analyze match predictions
"""
import requests
import json
import logging
import time
import random
from django.conf import settings
from google import genai

logger = logging.getLogger(__name__)


class APIFootballClient:
    """
    Client for API-Football to fetch match statistics and data.
    """

    def __init__(self):
        self.api_key = settings.API_FOOTBALL_KEY
        self.base_url = "https://v3.football.api-sports.io"
        self.headers = {
            'x-rapidapi-key': self.api_key,
            'x-rapidapi-host': 'v3.football.api-sports.io'
        }
        # Top European and international leagues
        self.leagues = {
            # Top 5 European leagues
            'Premier League': 39,
            'La Liga': 140,
            'Serie A': 135,
            'Bundesliga': 78,
            'Ligue 1': 61,

            # Additional European leagues
            'Championship': 40,  # England's second tier
            'Scottish Premiership': 179,
            'Eredivisie': 88,  # Netherlands
            'Primeira Liga': 94,  # Portugal
            'Belgian Pro League': 144,
            'Super Lig': 203,  # Turkey
            'Serie B': 136,  # Italy second tier
            'La Liga 2': 141,  # Spain second tier
            'Austrian Bundesliga': 218,
            'Swiss Super League': 207,
            'Danish Superliga': 119,
            'Norwegian Eliteserien': 103,
            'Swedish Allsvenskan': 113,

            # South American leagues
            'Brasileirao Serie A': 71,  # Brazil
            'Brasileirao Serie B': 72,  # Brazil second tier
            'Argentine Primera Division': 128,  # Argentina
            'Chilean Primera Division': 265,
            'Colombian Primera A': 239,
            'Ecuadorian Serie A': 242,

            # North & Central American leagues
            'MLS': 253,  # USA/Canada
            'Liga MX': 262,  # Mexico
            'USL Championship': 255,  # USA second tier

            # Asian leagues
            'J1 League': 98,  # Japan
            'K League 1': 292,  # South Korea
            'Chinese Super League': 169,
            'Saudi Pro League': 307,
            'UAE Pro League': 301,

            # African leagues
            'Egyptian Premier League': 233,
            'South African Premier Division': 288,

            # Other competitive leagues
            'Australian A-League': 188,
            'Russian Premier League': 235,
        }

    def get_todays_fixtures(self, date=None):
        """
        Fetch today's fixtures from top European leagues.

        Args:
            date: Date string in YYYY-MM-DD format. Defaults to today.

        Returns:
            list: List of fixtures with match information
        """
        from datetime import datetime

        if date is None:
            date = datetime.now().strftime('%Y-%m-%d')

        fixtures = []

        try:
            # Fetch fixtures for all leagues
            url = f"{self.base_url}/fixtures"
            params = {'date': date}

            logger.debug(f"API-Football Request: URL={url}, Params={params}")

            response = requests.get(url, headers=self.headers, params=params, timeout=10)
            response.raise_for_status()

            data = response.json()

            logger.debug(f"API-Football Response: {data.get('results', 0)} results returned")

            if data.get('response'):
                for fixture in data['response']:
                    league_id = fixture['league']['id']

                    # Only include matches from our tracked leagues
                    if league_id in self.leagues.values():
                        match_info = {
                            'fixture_id': fixture['fixture']['id'],
                            'home_team': fixture['teams']['home']['name'],
                            'away_team': fixture['teams']['away']['name'],
                            'home_team_id': fixture['teams']['home']['id'],
                            'away_team_id': fixture['teams']['away']['id'],
                            'league_name': fixture['league']['name'],
                            'league_id': league_id,
                            'season': fixture['league']['season'],
                            'match_date': fixture['fixture']['date'],
                            'venue': fixture['fixture']['venue']['name'] if fixture['fixture'].get('venue') else 'TBD',
                        }
                        fixtures.append(match_info)

                logger.info(f"Fetched {len(fixtures)} fixtures for {date}")
            else:
                logger.warning(f"No fixtures returned from API for {date}. No mock data fallback is active.")

        except requests.RequestException as e:
            logger.error(f"Error fetching fixtures from API-Football: {str(e)}")
            # No mock data fallback is active. Fixtures list will be empty.

        return fixtures

    def get_match_stats(self, match_data):
        """
        Fetch detailed match statistics for the given fixture.

        FREE TIER MODE: Only fetches injury data due to API restrictions.
        Blocked endpoints: team statistics (season restricted), recent results (last parameter),
        and head-to-head (last parameter).

        Args:
            match_data: Dictionary containing fixture information including:
                - fixture_id, home_team, away_team, home_team_id, away_team_id,
                  league_id, season

        Returns:
            dict: Match statistics with injuries only (free tier compatible)
        """
        home_team = match_data['home_team']
        away_team = match_data['away_team']

        try:
            # FREE TIER: Only fetch injury data (the only endpoint that works)
            stats = {
                'home_team': {
                    'name': home_team,
                    'injuries': self._get_team_injuries_from_api(match_data, 'home')
                },
                'away_team': {
                    'name': away_team,
                    'injuries': self._get_team_injuries_from_api(match_data, 'away')
                }
            }

            logger.info(f"Retrieved injury data for {home_team} vs {away_team} (free tier mode)")
            return stats

        except Exception as e:
            logger.error(f"Error fetching API-Football data: {str(e)}")
            return self._get_default_stats(home_team, away_team)

    def _get_team_form_from_api(self, match_data, team_type):
        """
        Fetch team form from API using /teams/statistics endpoint.

        Args:
            match_data: Dictionary containing match information
            team_type: 'home' or 'away'

        Returns:
            str: Team form description or unavailability message
        """
        try:
            team_id = match_data.get(f'{team_type}_team_id')
            league_id = match_data.get('league_id')
            season = match_data.get('season')

            if not all([team_id, league_id, season]):
                logger.warning(f"Missing required data for team statistics")
                return "Data unavailable - missing parameters"

            url = f"{self.base_url}/teams/statistics"
            params = {
                'team': team_id,
                'league': league_id,
                'season': season
            }

            response = requests.get(url, headers=self.headers, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            # Check for season restriction error (free tier limitation)
            if data.get('errors'):
                error_msg = data['errors'].get('plan', '')
                if 'Free plans do not have access to this season' in error_msg:
                    logger.info(f"Season {season} not available on free tier for team {team_id}")
                    return f"Data unavailable - API free tier only supports seasons 2021-2023 (requested: {season})"
                else:
                    logger.error(f"API error: {data['errors']}")
                    return f"Data unavailable - API error"

            if data.get('response'):
                stats = data['response']
                form = stats.get('form', 'N/A')

                # Calculate form quality from recent matches
                if form and form != 'N/A':
                    wins = form.count('W')
                    draws = form.count('D')
                    losses = form.count('L')

                    if wins >= 4:
                        return f"Excellent form ({form})"
                    elif wins >= 3:
                        return f"Good form ({form})"
                    elif wins >= 2:
                        return f"Decent form ({form})"
                    elif losses >= 3:
                        return f"Poor form ({form})"
                    else:
                        return f"Mixed form ({form})"

                return "Data unavailable - no form data in response"

            logger.warning("No team statistics returned from API")
            return "Data unavailable - empty API response"

        except requests.RequestException as e:
            logger.error(f"Error fetching team form: {str(e)}")
            return f"Data unavailable - API request failed"

    def _get_team_injuries_from_api(self, match_data, team_type):
        """
        Fetch team injuries from API using /injuries endpoint.

        Args:
            match_data: Dictionary containing match information
            team_type: 'home' or 'away'

        Returns:
            list: List of injured players or unavailability messages
        """
        try:
            fixture_id = match_data.get('fixture_id')

            if not fixture_id:
                logger.warning(f"Missing fixture_id for injury check")
                return ["Data unavailable - missing fixture ID"]

            url = f"{self.base_url}/injuries"
            params = {'fixture': fixture_id}

            response = requests.get(url, headers=self.headers, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            # Check for API errors
            if data.get('errors'):
                error_msg = str(data['errors'])
                logger.warning(f"Injury API error: {error_msg}")
                return [f"Data unavailable - API error: {error_msg}"]

            if data.get('response'):
                injuries = []
                team_name = match_data.get(f'{team_type}_team')

                for injury in data['response']:
                    # Filter by team
                    if injury.get('team', {}).get('name') == team_name:
                        player = injury.get('player', {}).get('name', 'Unknown')
                        injury_type = injury.get('player', {}).get('reason', 'Unknown injury')
                        injuries.append(f"{player} ({injury_type})")

                if not injuries:
                    return ["No major injuries reported"]

                return injuries[:5]  # Limit to top 5 injuries

            return ["Data unavailable - empty API response"]

        except requests.RequestException as e:
            logger.error(f"Error fetching injuries: {str(e)}")
            return [f"Data unavailable - API request failed: {str(e)}"]

    def _get_recent_results(self, match_data, team_type):
        """
        Get recent match results using /fixtures endpoint.

        Args:
            match_data: Dictionary containing match information
            team_type: 'home' or 'away'

        Returns:
            list: List of recent results (W/D/L) or unavailability messages
        """
        try:
            team_id = match_data.get(f'{team_type}_team_id')
            season = match_data.get('season')

            if not team_id or not season:
                logger.warning(f"Missing team_id or season for recent results")
                return ['Data unavailable - missing parameters']

            url = f"{self.base_url}/fixtures"
            params = {
                'team': team_id,
                'season': season,
                'last': 5,
                'status': 'FT'  # Only finished matches
            }

            response = requests.get(url, headers=self.headers, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            # Check for API errors (including season restrictions)
            if data.get('errors'):
                error_msg = data['errors'].get('plan', str(data['errors']))
                if 'Free plans do not have access to this season' in error_msg:
                    logger.info(f"Recent results for season {season} not available on free tier")
                    return [f'Data unavailable - API free tier only supports seasons 2021-2023']
                logger.warning(f"Recent results API error: {error_msg}")
                return [f'Data unavailable - API error']

            if data.get('response'):
                results = []

                for fixture in data['response'][:5]:  # Last 5 matches
                    home_goals = fixture['goals']['home']
                    away_goals = fixture['goals']['away']
                    is_home = fixture['teams']['home']['id'] == team_id

                    if home_goals is None or away_goals is None:
                        continue

                    if home_goals == away_goals:
                        results.append('D')
                    elif (is_home and home_goals > away_goals) or (not is_home and away_goals > home_goals):
                        results.append('W')
                    else:
                        results.append('L')

                if results:
                    return results

                return ['Data unavailable - no recent matches found']

            return ['Data unavailable - empty API response']

        except requests.RequestException as e:
            logger.error(f"Error fetching recent results: {str(e)}")
            return [f'Data unavailable - API request failed']

    def _get_h2h_stats(self, match_data):
        """
        Get head-to-head statistics using /fixtures/headtohead endpoint.

        Args:
            match_data: Dictionary containing match information

        Returns:
            dict: Head-to-head statistics or unavailability messages
        """
        try:
            home_team_id = match_data.get('home_team_id')
            away_team_id = match_data.get('away_team_id')

            if not home_team_id or not away_team_id:
                logger.warning(f"Missing team IDs for H2H stats")
                return {'last_5_matches': ['Data unavailable - missing team IDs']}

            url = f"{self.base_url}/fixtures/headtohead"
            params = {
                'h2h': f"{home_team_id}-{away_team_id}",
                'last': 5
            }

            response = requests.get(url, headers=self.headers, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            # Check for API errors
            if data.get('errors'):
                error_msg = str(data['errors'])
                logger.warning(f"H2H API error: {error_msg}")
                return {'last_5_matches': [f'Data unavailable - API error']}

            if data.get('response'):
                matches = []

                for fixture in data['response'][:5]:  # Last 5 H2H matches
                    home_goals = fixture['goals']['home']
                    away_goals = fixture['goals']['away']
                    home_name = fixture['teams']['home']['name']
                    away_name = fixture['teams']['away']['name']

                    if home_goals is None or away_goals is None:
                        continue

                    if home_goals == away_goals:
                        matches.append('Draw')
                    elif home_goals > away_goals:
                        matches.append(f'{home_name} Win')
                    else:
                        matches.append(f'{away_name} Win')

                if matches:
                    return {'last_5_matches': matches}

                return {'last_5_matches': ['No previous meetings found']}

            return {'last_5_matches': ['Data unavailable - empty API response']}

        except requests.RequestException as e:
            logger.error(f"Error fetching H2H stats: {str(e)}")
            return {'last_5_matches': [f'Data unavailable - API request failed']}

    def _get_default_stats(self, home_team, away_team):
        """Return default stats structure when API call fails (free tier compatible)"""
        return {
            'home_team': {
                'name': home_team,
                'injuries': ['Data unavailable - API error']
            },
            'away_team': {
                'name': away_team,
                'injuries': ['Data unavailable - API error']
            }
        }


class FootballDataOrgClient:
    """
    Client for Football-Data.org API to fetch league standings and recent results.
    FREE TIER: 10 requests per minute, major European leagues only.
    """

    def __init__(self):
        self.api_key = settings.FOOTBALL_DATA_API_KEY
        self.base_url = "https://api.football-data.org/v4"
        self.headers = {
            'X-Auth-Token': self.api_key
        }
        # League mapping: API-Football league ID -> Football-Data.org competition code
        self.league_mapping = {
            39: 'PL',    # Premier League
            140: 'PD',   # La Liga
            135: 'SA',   # Serie A
            78: 'BL1',   # Bundesliga
            61: 'FL1',   # Ligue 1
            2: 'CL',     # Champions League
            3: 'EC',     # Europa League/Conference
        }

    def get_league_standings(self, league_id):
        """
        Get current league standings from Football-Data.org.

        Args:
            league_id: API-Football league ID

        Returns:
            dict: League standings or None if unavailable
        """
        if not self.api_key or self.api_key == 'YOUR_API_KEY_HERE':
            logger.warning("Football-Data.org API key not configured")
            return None

        competition_code = self.league_mapping.get(league_id)
        if not competition_code:
            logger.debug(f"League {league_id} not supported by Football-Data.org")
            return None

        try:
            url = f"{self.base_url}/competitions/{competition_code}/standings"
            response = requests.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()
            data = response.json()

            if data.get('standings'):
                standings = data['standings'][0]['table']  # Get main standings table
                logger.info(f"Retrieved standings for competition {competition_code}")
                return standings

            return None

        except requests.RequestException as e:
            logger.error(f"Error fetching standings from Football-Data.org: {str(e)}")
            return None

    def get_team_recent_matches(self, team_name, league_id):
        """
        Get recent matches for a team.

        Args:
            team_name: Name of the team
            league_id: API-Football league ID

        Returns:
            list: Recent match results or None
        """
        if not self.api_key or self.api_key == 'YOUR_API_KEY_HERE':
            return None

        competition_code = self.league_mapping.get(league_id)
        if not competition_code:
            return None

        try:
            # Get current season matches for the competition
            url = f"{self.base_url}/competitions/{competition_code}/matches"
            params = {'status': 'FINISHED'}

            response = requests.get(url, headers=self.headers, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            if data.get('matches'):
                # Filter matches for this specific team
                team_matches = [
                    match for match in data['matches']
                    if match['homeTeam']['name'] == team_name or match['awayTeam']['name'] == team_name
                ]

                # Get last 5 matches
                recent_matches = sorted(team_matches, key=lambda x: x['utcDate'], reverse=True)[:5]

                results = []
                for match in recent_matches:
                    home_score = match['score']['fullTime']['home']
                    away_score = match['score']['fullTime']['away']
                    is_home = match['homeTeam']['name'] == team_name

                    if home_score is None or away_score is None:
                        continue

                    if home_score == away_score:
                        results.append('D')
                    elif (is_home and home_score > away_score) or (not is_home and away_score > home_score):
                        results.append('W')
                    else:
                        results.append('L')

                logger.info(f"Retrieved {len(results)} recent matches for {team_name}")
                return results

            return None

        except requests.RequestException as e:
            logger.error(f"Error fetching recent matches from Football-Data.org: {str(e)}")
            return None

    def get_team_position(self, team_name, league_id):
        """
        Get team's position in league table.

        Args:
            team_name: Name of the team
            league_id: API-Football league ID

        Returns:
            dict: Team position info (position, points, form) or None
        """
        standings = self.get_league_standings(league_id)
        if not standings:
            return None

        for team in standings:
            if team['team']['name'] == team_name:
                return {
                    'position': team['position'],
                    'points': team['points'],
                    'played': team['playedGames'],
                    'won': team['won'],
                    'draw': team['draw'],
                    'lost': team['lost'],
                    'form': team.get('form', 'N/A')
                }

        return None


class GeminiAnalyzer:
    """
    Google Gemini AI analyzer for match predictions.
    """

    def __init__(self):
        self.client = genai.Client(api_key=settings.GEMINI_API_KEY)
        # Use Gemini 2.5 Flash - much higher rate limits than flash-lite
        self.model_name = 'models/gemini-2.5-flash'  # Higher limits than flash-lite
        self.max_retries = 3
        self.base_delay = 1  # Base delay in seconds

    def analyze_match(self, match_data, api_stats):
        """
        Analyze a match using Gemini AI with Google Search grounding and retry logic.

        Args:
            match_data: Dictionary with match information
            api_stats: Statistics from API-Football

        Returns:
            dict: Analysis with confidence score and rationale
        """
        prompt = self._build_analysis_prompt(match_data, api_stats)
        
        for attempt in range(self.max_retries + 1):
            try:
                # Add small delay between requests to prevent hitting rate limits
                if attempt > 0:
                    delay = self._calculate_exponential_backoff(attempt)
                    logger.info(f"Retrying Gemini analysis for {match_data['home_team']} vs {match_data['away_team']} (attempt {attempt + 1}) after {delay:.1f}s delay")
                    time.sleep(delay)
                
                # Enable Google Search grounding for real-time data
                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=prompt,
                    config={
                        'tools': [{'google_search': {}}]  # Enable Google Search grounding
                    }
                )
                analysis_text = response.text

                # Log grounding metadata if available
                if hasattr(response, 'candidates') and len(response.candidates) > 0:
                    candidate = response.candidates[0]
                    if hasattr(candidate, 'grounding_metadata') and candidate.grounding_metadata:
                        logger.info(f"Gemini used Google Search grounding for {match_data['home_team']} vs {match_data['away_team']}")
                        if hasattr(candidate.grounding_metadata, 'search_entry_point'):
                            logger.debug(f"Search queries executed: {candidate.grounding_metadata.search_entry_point}")

                # Parse the response to extract confidence score and rationale
                result = self._parse_gemini_response(analysis_text)

                logger.info(f"Gemini analysis completed for {match_data['home_team']} vs {match_data['away_team']} (attempt {attempt + 1})")
                return result

            except Exception as e:
                error_str = str(e)
                is_rate_limit = '429' in error_str or 'RESOURCE_EXHAUSTED' in error_str or 'quota' in error_str.lower()
                
                if is_rate_limit:
                    # Extract retry delay from error message if available
                    retry_delay = self._extract_retry_delay_from_error(error_str)
                    
                    if attempt < self.max_retries:
                        if retry_delay:
                            logger.warning(f"Rate limit hit for {match_data['home_team']} vs {match_data['away_team']}. API suggests waiting {retry_delay}s. Will retry in {retry_delay + 1}s (attempt {attempt + 1}/{self.max_retries + 1})")
                            time.sleep(retry_delay + 1)  # Add 1 second buffer
                        else:
                            delay = self._calculate_exponential_backoff(attempt + 1)
                            logger.warning(f"Rate limit hit for {match_data['home_team']} vs {match_data['away_team']}. Will retry in {delay:.1f}s (attempt {attempt + 1}/{self.max_retries + 1})")
                            time.sleep(delay)
                        continue
                    else:
                        logger.error(f"Max retries exceeded for {match_data['home_team']} vs {match_data['away_team']} due to rate limiting: {error_str}")
                        return self._get_fallback_analysis(f"Rate limit exceeded after {self.max_retries} retries")
                else:
                    # Non-rate-limit error, fail immediately
                    logger.error(f"Error in Gemini analysis for {match_data['home_team']} vs {match_data['away_team']}: {error_str}")
                    return self._get_fallback_analysis(f"Analysis error: {error_str}")
        
        # This should never be reached, but just in case
        return self._get_fallback_analysis("Unexpected retry loop exit")

    def _build_analysis_prompt(self, match_data, api_stats):
        """
        Build the prompt for Gemini AI.

        Args:
            match_data: Match information
            api_stats: API-Football statistics

        Returns:
            str: Formatted prompt for Gemini
        """
        # Extract available data
        home_injuries = ', '.join(api_stats['home_team']['injuries']) if api_stats['home_team'].get('injuries') else 'No injury data available'
        away_injuries = ', '.join(api_stats['away_team']['injuries']) if api_stats['away_team'].get('injuries') else 'No injury data available'

        home_position = api_stats['home_team'].get('league_position')
        away_position = api_stats['away_team'].get('league_position')

        home_recent = api_stats['home_team'].get('recent_results')
        away_recent = api_stats['away_team'].get('recent_results')

        prompt = f"""
You are an expert football analyst tasked with evaluating matches for accumulator bets.

MATCH DETAILS:
- Home Team: {match_data['home_team']}
- Away Team: {match_data['away_team']}
- League: {match_data.get('league_name', 'Unknown')}
- Date: {match_data.get('match_date', 'TBD')}
- Venue: {match_data.get('venue', 'Unknown')}

AVAILABLE DATA FROM APIs:

Injury Reports (from API-Football):
- Home Team ({api_stats['home_team']['name']}): {home_injuries}
- Away Team ({api_stats['away_team']['name']}): {away_injuries}"""

        # Add Football-Data.org data if available
        if home_position or away_position:
            prompt += f"""

League Standings (from Football-Data.org):"""
            if home_position:
                prompt += f"""
- Home Team: Position {home_position['position']}, {home_position['points']} points ({home_position['won']}W-{home_position['draw']}D-{home_position['lost']}L), Form: {home_position.get('form', 'N/A')}"""
            if away_position:
                prompt += f"""
- Away Team: Position {away_position['position']}, {away_position['points']} points ({away_position['won']}W-{away_position['draw']}D-{away_position['lost']}L), Form: {away_position.get('form', 'N/A')}"""

        if home_recent or away_recent:
            prompt += f"""

Recent Results (from Football-Data.org):"""
            if home_recent:
                prompt += f"""
- Home Team: {', '.join(home_recent)} (most recent first)"""
            if away_recent:
                prompt += f"""
- Away Team: {', '.join(away_recent)} (most recent first)"""

        prompt += f"""

TASK - USE GOOGLE SEARCH TO ENHANCE ANALYSIS:

You have access to Google Search! Use it to supplement the data above with:

1. **Latest Team News & Suspensions**: Beyond the injury data provided, search for:
   - Search: "{match_data['home_team']} vs {match_data['away_team']} preview"
   - Search: "{match_data['home_team']} team news suspensions latest"
   - Search: "{match_data['away_team']} team news suspensions latest"

2. **Head-to-Head History**: Look up recent meetings between these teams
   - Search: "{match_data['home_team']} vs {match_data['away_team']} head to head"
   - Search: "{match_data['home_team']} vs {match_data['away_team']} last match"

3. **Expert Predictions & Analysis**: Find what experts are saying
   - Search: "{match_data['home_team']} vs {match_data['away_team']} prediction {match_data.get('match_date', '')}"
   - Search: "{match_data['home_team']} vs {match_data['away_team']} betting tips"

4. **Additional Context** (if needed): Fill in any missing data
   - If league standings not available above, search for: "{match_data.get('league_name')} table standings"
   - If recent results not available, search for team form

ANALYSIS REQUIREMENTS:

Analyze the match considering ALL available data:
1. **League Position & Form**: Use standings data provided above (if available) or search for it
2. **Recent Results**: Use recent match data provided above (if available) or search for it
3. **Injury & Suspension Impact**: Use injury data provided + search for suspensions
4. **Head-to-Head Record**: Search for this information
5. **Expert Opinions**: Search for expert predictions and betting trends
6. **Home Advantage**: Consider venue and home team advantage
7. **Current Season Context**: Look for any recent momentum shifts or tactical changes

CONFIDENCE SCORING:
- With complete data (standings + form + injuries + H2H + expert analysis): 6.0-8.5/10.0 confidence
- With good data but some gaps: 5.0-7.0/10.0 confidence
- With partial data: 3.0-5.0/10.0 confidence
- With minimal data: max 3.0/10.0 confidence

RISK LEVELS:
- Low Risk: Clear favorite, strong form, comprehensive data, expert consensus
- Medium Risk: Moderate certainty, some data gaps, mixed expert opinions
- High Risk: Unpredictable match, limited data, conflicting signals

Provide a specific betting recommendation (e.g., "Home Win", "Over 2.5 Goals", "Both Teams to Score", "Draw") based on all available data. Only suggest "N/A" if you cannot find sufficient information even after searching.

Provide your response in the following JSON format:
{{
    "confidence_score": <float between 0.0 and 10.0, where 10 is highest confidence>,
    "risk_level": "<Low Risk|Medium Risk|High Risk>",
    "suggested_bet": "<specific betting recommendation>",
    "rationale": "<2-3 sentence explanation of your assessment and why this bet is recommended>"
}}

Return ONLY the JSON object, no additional text.
"""
        return prompt

    def _parse_gemini_response(self, response_text):
        """
        Parse Gemini's response to extract structured data.

        Args:
            response_text: Raw text response from Gemini

        Returns:
            dict: Parsed analysis with confidence score and rationale
        """
        try:
            # Remove markdown code blocks if present
            cleaned = response_text.strip()
            if cleaned.startswith('```json'):
                cleaned = cleaned[7:]
            if cleaned.startswith('```'):
                cleaned = cleaned[3:]
            if cleaned.endswith('```'):
                cleaned = cleaned[:-3]

            cleaned = cleaned.strip()

            # Parse JSON
            parsed = json.loads(cleaned)

            return {
                'confidence_score': float(parsed.get('confidence_score', 0.0)),
                'risk_level': parsed.get('risk_level', 'High Risk'),
                'suggested_bet': parsed.get('suggested_bet', 'N/A'),
                'rationale': parsed.get('rationale', 'No rationale provided.')
            }

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Gemini response as JSON: {str(e)}")
            logger.debug(f"Response text: {response_text}")

            # Fallback: extract information from plain text
            return {
                'confidence_score': 5.0,
                'risk_level': 'Medium Risk',
                'suggested_bet': 'N/A',
                'rationale': response_text[:200] if response_text else 'Unable to parse analysis.'
            }
    
    def _calculate_exponential_backoff(self, attempt):
        """
        Calculate exponential backoff delay with jitter.
        
        Args:
            attempt: Current retry attempt number (starting from 1)
        
        Returns:
            float: Delay in seconds
        """
        # Exponential backoff: base_delay * (2 ^ attempt) + random jitter
        delay = self.base_delay * (2 ** attempt)
        # Add jitter to prevent thundering herd
        jitter = random.uniform(0, min(delay * 0.1, 1.0))
        return delay + jitter
    
    def _extract_retry_delay_from_error(self, error_str):
        """
        Extract retry delay from Gemini API error message.
        
        Args:
            error_str: Error message string
        
        Returns:
            float or None: Suggested retry delay in seconds
        """
        import re
        
        # Look for retry delay patterns in the error message
        # Pattern: "retry in 14.26332542s" or "retryDelay: '14s'"
        patterns = [
            r'retry in (\d+(?:\.\d+)?)s',
            r"retryDelay['\"]:\s*['\"](\d+(?:\.\d+)?)s?['\"]",
            r'Please retry in (\d+(?:\.\d+)?)s'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, error_str, re.IGNORECASE)
            if match:
                try:
                    return float(match.group(1))
                except ValueError:
                    continue
        
        return None
    
    def _get_fallback_analysis(self, reason):
        """
        Return fallback analysis when Gemini API fails.
        
        Args:
            reason: Reason for fallback
        
        Returns:
            dict: Fallback analysis structure
        """
        return {
            'confidence_score': 0.0,
            'rationale': f'Analysis unavailable: {reason}',
            'risk_level': 'High Risk',
            'suggested_bet': 'N/A'
        }


class MatchIntelligenceService:
    """
    Combined service that uses API-Football, Football-Data.org, and Gemini to analyze matches.
    """

    def __init__(self):
        self.api_football = APIFootballClient()
        self.football_data = FootballDataOrgClient()
        self.gemini = GeminiAnalyzer()

    def get_todays_matches(self, date=None):
        """
        Get today's fixtures from API-Football.

        Args:
            date: Date string in YYYY-MM-DD format

        Returns:
            list: List of fixtures
        """
        return self.api_football.get_todays_fixtures(date)

    def analyze_match_for_acca(self, match_data):
        """
        Complete analysis of a match for accumulator betting.

        Args:
            match_data: Dictionary containing match data from API-Football

        Returns:
            dict: Complete analysis with API stats and Gemini insights
        """
        home_team = match_data['home_team']
        away_team = match_data['away_team']
        fixture_id = match_data.get('fixture_id', 0)
        league_id = match_data.get('league_id')

        # Step 1: Fetch injury data from API-Football
        api_stats = self.api_football.get_match_stats(match_data)

        # Step 2: Enhance with Football-Data.org data (standings and recent results)
        if league_id:
            # Get team positions in league table
            home_position = self.football_data.get_team_position(home_team, league_id)
            away_position = self.football_data.get_team_position(away_team, league_id)

            # Get recent match results
            home_recent = self.football_data.get_team_recent_matches(home_team, league_id)
            away_recent = self.football_data.get_team_recent_matches(away_team, league_id)

            # Add Football-Data.org data to stats
            if home_position:
                api_stats['home_team']['league_position'] = home_position
            if away_position:
                api_stats['away_team']['league_position'] = away_position
            if home_recent:
                api_stats['home_team']['recent_results'] = home_recent
            if away_recent:
                api_stats['away_team']['recent_results'] = away_recent

        # Step 3: Get Gemini AI analysis with Google Search grounding
        gemini_analysis = self.gemini.analyze_match(match_data, api_stats)

        # Step 3: Combine results
        result = {
            'home_team': home_team,
            'away_team': away_team,
            'match_date': match_data['match_date'],
            'league_name': match_data.get('league_name', 'Unknown'),
            'fixture_id': fixture_id,
            'api_stats': api_stats,
            'gemini_analysis': gemini_analysis['rationale'],
            'confidence_score': gemini_analysis['confidence_score'],
            'risk_level': gemini_analysis['risk_level'],
            'suggested_bet': gemini_analysis.get('suggested_bet', 'N/A')
        }

        return result


def get_fixtures(date=None):
    """
    Convenience function to get today's fixtures.

    Args:
        date: Date string in YYYY-MM-DD format

    Returns:
        list: List of fixtures
    """
    service = MatchIntelligenceService()
    return service.get_todays_matches(date)


def analyze_match(match_data):
    """
    Convenience function to analyze a match.

    Args:
        match_data: Match information dictionary

    Returns:
        dict: Complete analysis result
    """
    service = MatchIntelligenceService()
    return service.analyze_match_for_acca(match_data)
