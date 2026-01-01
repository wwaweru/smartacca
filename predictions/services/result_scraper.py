"""
Web scraper for fetching match results from free sources when API quota is exhausted.
"""

import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from difflib import SequenceMatcher
import re


class ResultScraper:
    """Scrapes match results from publicly available sources"""

    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }

    def get_match_result(self, home_team, away_team, match_date, league_name=None):
        """
        Try multiple sources to find match result

        Args:
            home_team: Home team name
            away_team: Away team name
            match_date: Match date (datetime object)
            league_name: League name (optional, helps with filtering)

        Returns:
            dict with home_score, away_score, status or None
        """
        # Try ESPN first (static HTML, reliable)
        result = self._try_espn(home_team, away_team, match_date, league_name)
        if result:
            return result

        # Try BBC Sport (may require JS)
        result = self._try_bbc_sport(home_team, away_team, match_date, league_name)
        if result:
            return result

        # Try FlashScore as final fallback
        result = self._try_flashscore(home_team, away_team, match_date)
        if result:
            return result

        return None

    def _try_espn(self, home_team, away_team, match_date, league_name):
        """Scrape ESPN for match result (best for static HTML)"""
        try:
            # ESPN league slugs
            league_slugs = {
                'Championship': 'eng.2',
                'Premier League': 'eng.1',
                'League One': 'eng.3',
                'League Two': 'eng.4',
                'La Liga': 'esp.1',
                'Serie A': 'ita.1',
                'Bundesliga': 'ger.1',
                'Ligue 1': 'fra.1',
            }

            league_slug = league_slugs.get(league_name, 'eng.2')  # Default to Championship

            # ESPN uses date format: YYYYMMDD
            date_str = match_date.strftime('%Y%m%d')

            url = f"https://www.espn.com/soccer/scoreboard/_/league/{league_slug}/date/{date_str}"

            response = requests.get(url, headers=self.headers, timeout=10)

            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')

                # Find all match containers
                matches = soup.find_all('section', class_='Scoreboard')

                for match_elem in matches:
                    # Get team names
                    teams = match_elem.find_all('div', class_='ScoreCell__TeamName')
                    if len(teams) < 2:
                        continue

                    scraped_home = teams[0].get_text(strip=True)
                    scraped_away = teams[1].get_text(strip=True)

                    # Check if teams match
                    if (self._teams_match(home_team, scraped_home) and
                        self._teams_match(away_team, scraped_away)):

                        # Get scores
                        scores = match_elem.find_all('div', class_='ScoreCell__Score')
                        if len(scores) >= 2:
                            try:
                                home_score = int(scores[0].get_text(strip=True))
                                away_score = int(scores[1].get_text(strip=True))

                                # Check status
                                status_elem = match_elem.find('span', class_='ScoreboardScoreCell__NetworkGameState')
                                status = 'FT'
                                if status_elem:
                                    status_text = status_elem.get_text(strip=True).upper()
                                    if 'HALF' in status_text:
                                        status = 'HT'
                                    elif 'LIVE' in status_text or "'" in status_text:
                                        status = 'LIVE'

                                return {
                                    'home_score': home_score,
                                    'away_score': away_score,
                                    'status': status,
                                    'source': 'ESPN'
                                }
                            except (ValueError, AttributeError):
                                continue

            return None

        except Exception as e:
            print(f"ESPN scraper error: {str(e)}")
            return None

    def _try_bbc_sport(self, home_team, away_team, match_date, league_name):
        """Scrape BBC Sport for match result"""
        try:
            # BBC Sport URL structure for different leagues
            league_urls = {
                'Championship': 'https://www.bbc.com/sport/football/championship/scores-fixtures',
                'Premier League': 'https://www.bbc.com/sport/football/premier-league/scores-fixtures',
                'League One': 'https://www.bbc.com/sport/football/league-one/scores-fixtures',
                'League Two': 'https://www.bbc.com/sport/football/league-two/scores-fixtures',
                'Scottish Premiership': 'https://www.bbc.com/sport/football/scottish-premiership/scores-fixtures',
                'La Liga': 'https://www.bbc.com/sport/football/spanish-la-liga/scores-fixtures',
                'Serie A': 'https://www.bbc.com/sport/football/italian-serie-a/scores-fixtures',
                'Bundesliga': 'https://www.bbc.com/sport/football/german-bundesliga/scores-fixtures',
                'Ligue 1': 'https://www.bbc.com/sport/football/french-ligue-one/scores-fixtures',
            }

            # Determine URL based on league
            url = league_urls.get(league_name)
            if not url:
                # Try Championship as default for unknown leagues
                url = 'https://www.bbc.com/sport/football/championship/scores-fixtures'

            # Add date parameter
            date_str = match_date.strftime('%Y-%m-%d')
            url_with_date = f"{url}/{date_str}"

            # Fetch page
            response = requests.get(url_with_date, headers=self.headers, timeout=10)

            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')

                # Find all match containers
                matches = soup.find_all('div', class_='sp-c-fixture')

                for match_elem in matches:
                    # Extract team names
                    teams = match_elem.find_all('span', class_='sp-c-fixture__team-name')
                    if len(teams) < 2:
                        continue

                    scraped_home = teams[0].get_text(strip=True)
                    scraped_away = teams[1].get_text(strip=True)

                    # Check if teams match (using fuzzy matching)
                    if (self._teams_match(home_team, scraped_home) and
                        self._teams_match(away_team, scraped_away)):

                        # Extract scores
                        scores = match_elem.find_all('span', class_='sp-c-fixture__number')
                        if len(scores) >= 2:
                            try:
                                home_score = int(scores[0].get_text(strip=True))
                                away_score = int(scores[1].get_text(strip=True))

                                # Check match status
                                status_elem = match_elem.find('span', class_='sp-c-fixture__status')
                                status = 'FT'  # Default
                                if status_elem:
                                    status_text = status_elem.get_text(strip=True).upper()
                                    if 'HALF' in status_text or 'HT' in status_text:
                                        status = 'HT'
                                    elif 'LIVE' in status_text or "'" in status_text:
                                        status = 'LIVE'

                                return {
                                    'home_score': home_score,
                                    'away_score': away_score,
                                    'status': status,
                                    'source': 'BBC Sport'
                                }
                            except (ValueError, AttributeError):
                                continue

            return None

        except Exception as e:
            print(f"BBC Sport scraper error: {str(e)}")
            return None

    def _try_flashscore(self, home_team, away_team, match_date):
        """Scrape FlashScore for match result (fallback)"""
        try:
            # FlashScore uses dynamic content, so this is a simplified version
            # In production, you'd use Selenium or similar for JS-heavy sites

            # Format date for FlashScore
            date_str = match_date.strftime('%d.%m.%Y')

            # FlashScore URL structure
            url = f"https://www.flashscore.com/football/england/championship/"

            response = requests.get(url, headers=self.headers, timeout=10)

            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')

                # FlashScore structure varies, this is a basic implementation
                # Look for match divs
                matches = soup.find_all('div', class_='event__match')

                for match_elem in matches:
                    # Extract team names
                    home_elem = match_elem.find('div', class_='event__participant--home')
                    away_elem = match_elem.find('div', class_='event__participant--away')

                    if not home_elem or not away_elem:
                        continue

                    scraped_home = home_elem.get_text(strip=True)
                    scraped_away = away_elem.get_text(strip=True)

                    if (self._teams_match(home_team, scraped_home) and
                        self._teams_match(away_team, scraped_away)):

                        # Extract scores
                        score_elem = match_elem.find('div', class_='event__scores')
                        if score_elem:
                            scores = score_elem.find_all('span')
                            if len(scores) >= 2:
                                try:
                                    home_score = int(scores[0].get_text(strip=True))
                                    away_score = int(scores[1].get_text(strip=True))

                                    return {
                                        'home_score': home_score,
                                        'away_score': away_score,
                                        'status': 'FT',
                                        'source': 'FlashScore'
                                    }
                                except ValueError:
                                    continue

            return None

        except Exception as e:
            print(f"FlashScore scraper error: {str(e)}")
            return None

    def _teams_match(self, team1, team2, threshold=0.75):
        """
        Check if two team names match using fuzzy matching

        Args:
            team1: First team name
            team2: Second team name
            threshold: Similarity threshold (0-1)

        Returns:
            bool: True if teams match
        """
        # Normalize team names
        t1 = self._normalize_team_name(team1)
        t2 = self._normalize_team_name(team2)

        # Exact match after normalization
        if t1 == t2:
            return True

        # Check if one contains the other
        if t1 in t2 or t2 in t1:
            return True

        # Fuzzy match using SequenceMatcher
        similarity = SequenceMatcher(None, t1, t2).ratio()

        return similarity >= threshold

    def _normalize_team_name(self, team_name):
        """
        Normalize team name for better matching

        Examples:
            "Manchester United" -> "manchester united"
            "Man Utd" -> "man united"
            "Newcastle Jets FC" -> "newcastle jets"
        """
        name = team_name.lower().strip()

        # Common replacements
        replacements = {
            ' fc': '',
            ' afc': '',
            ' united': ' utd',
            ' city': '',
            ' town': '',
            'manchester utd': 'man utd',
            'manchester city': 'man city',
            'tottenham hotspur': 'tottenham',
            'brighton & hove albion': 'brighton',
            'wolverhampton wanderers': 'wolves',
            'west bromwich albion': 'west brom',
            'queens park rangers': 'qpr',
        }

        for old, new in replacements.items():
            name = name.replace(old, new)

        # Remove common suffixes
        name = re.sub(r'\s+(fc|afc|cf|sc)$', '', name)

        return name.strip()

    def get_league_results(self, league_name, date):
        """
        Get all results for a specific league and date

        Args:
            league_name: League name (e.g., "Championship")
            date: Date (datetime object)

        Returns:
            list of dict with match results
        """
        try:
            league_urls = {
                'Championship': 'https://www.bbc.com/sport/football/championship/scores-fixtures',
                'Premier League': 'https://www.bbc.com/sport/football/premier-league/scores-fixtures',
            }

            url = league_urls.get(league_name)
            if not url:
                return []

            date_str = date.strftime('%Y-%m-%d')
            url_with_date = f"{url}/{date_str}"

            response = requests.get(url_with_date, headers=self.headers, timeout=10)

            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                results = []

                matches = soup.find_all('div', class_='sp-c-fixture')

                for match_elem in matches:
                    teams = match_elem.find_all('span', class_='sp-c-fixture__team-name')
                    scores = match_elem.find_all('span', class_='sp-c-fixture__number')

                    if len(teams) >= 2 and len(scores) >= 2:
                        try:
                            results.append({
                                'home_team': teams[0].get_text(strip=True),
                                'away_team': teams[1].get_text(strip=True),
                                'home_score': int(scores[0].get_text(strip=True)),
                                'away_score': int(scores[1].get_text(strip=True)),
                                'status': 'FT'
                            })
                        except ValueError:
                            continue

                return results

            return []

        except Exception as e:
            print(f"Error fetching league results: {str(e)}")
            return []


# Convenience function for quick testing
def test_scraper():
    """Test the scraper with sample matches"""
    scraper = ResultScraper()

    # Test Championship matches from today
    test_date = datetime.now()

    test_matches = [
        ("Watford", "Birmingham", "Championship"),
        ("Bristol City", "Portsmouth", "Championship"),
        ("Preston", "Sheffield Wednesday", "Championship"),
    ]

    print("Testing Result Scraper")
    print("=" * 70)

    for home, away, league in test_matches:
        print(f"\nSearching for: {home} vs {away} ({league})")
        result = scraper.get_match_result(home, away, test_date, league)

        if result:
            print(f"✓ Found: {home} {result['home_score']}-{result['away_score']} {away}")
            print(f"  Status: {result['status']}")
            print(f"  Source: {result['source']}")
        else:
            print(f"✗ No result found")


if __name__ == '__main__':
    test_scraper()
