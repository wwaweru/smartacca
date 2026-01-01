from django.core.management.base import BaseCommand
from django.utils import timezone
from predictions.models import Match
from predictions.services.intelligence import APIFootballClient, GeminiAnalyzer
from predictions.services.result_scraper import ResultScraper
from datetime import datetime, timedelta
import time


class Command(BaseCommand):
    help = 'Fetches actual match results and generates post-mortem analysis'

    def add_arguments(self, parser):
        parser.add_argument(
            '--date',
            type=str,
            help='Fetch results for specific date (YYYY-MM-DD)',
        )
        parser.add_argument(
            '--days-back',
            type=int,
            default=1,
            help='Number of days to look back (default: 1)',
        )
        parser.add_argument(
            '--match-id',
            type=int,
            help='Fetch result for specific match ID',
        )

    def handle(self, *args, **options):
        self.stdout.write('=== SmartAcca Post-Mortem Generator ===\n')

        api_client = APIFootballClient()
        gemini = GeminiAnalyzer()
        scraper = ResultScraper()

        # Determine which matches to process
        if options['match_id']:
            matches = Match.objects.filter(id=options['match_id'])
        elif options['date']:
            target_date = datetime.strptime(options['date'], '%Y-%m-%d').date()
            matches = Match.objects.filter(match_date__date=target_date)
        else:
            days_back = options['days_back']
            cutoff_date = timezone.now() - timedelta(days=days_back)
            matches = Match.objects.filter(
                match_date__gte=cutoff_date,
                match_date__lte=timezone.now(),
                result_fetched=False
            )

        if not matches.exists():
            self.stdout.write(self.style.WARNING('No matches found to process.'))
            return

        self.stdout.write(f'Found {matches.count()} match(es) to process.\n')

        successful = 0
        failed = 0

        for match in matches:
            self.stdout.write(f'\nProcessing: {match.home_team} vs {match.away_team}')

            try:
                # Fetch match result from API (with scraper fallback)
                result = self._fetch_match_result(api_client, match, scraper)

                if result:
                    # Update match with actual results
                    match.home_score = result['home_score']
                    match.away_score = result['away_score']
                    match.match_status = result['status']
                    match.result_fetched = True
                    match.result_fetched_at = timezone.now()

                    self.stdout.write(
                        f"  Result: {match.home_team} {match.home_score} - "
                        f"{match.away_score} {match.away_team} ({match.match_status})"
                    )

                    # Determine if prediction was correct
                    if match.suggested_bet and match.match_status == 'FT':
                        prediction_result = self._evaluate_prediction(match)
                        match.prediction_correct = prediction_result['correct']
                        match.prediction_outcome = prediction_result['outcome']

                        outcome_icon = '✅' if prediction_result['correct'] else '❌'
                        self.stdout.write(
                            f"  Prediction: {outcome_icon} {prediction_result['outcome']}"
                        )

                        # Generate post-mortem analysis
                        if match.is_in_daily_acca:
                            self.stdout.write(f"  Generating AI post-mortem analysis...")
                            post_mortem = self._generate_post_mortem(gemini, match)

                            if post_mortem:
                                match.post_mortem_analysis = post_mortem
                                match.post_mortem_generated = True
                                match.post_mortem_generated_at = timezone.now()
                                self.stdout.write(self.style.SUCCESS('  ✓ Post-mortem generated'))

                    match.save()
                    successful += 1

                else:
                    self.stdout.write(self.style.WARNING('  ⚠ Result not available yet'))
                    failed += 1

                # Rate limiting
                time.sleep(1)

            except Exception as e:
                self.stdout.write(self.style.ERROR(f'  ✗ Error: {str(e)}'))
                failed += 1
                continue

        # Summary
        self.stdout.write('\n' + '='*60)
        self.stdout.write(self.style.SUCCESS(f'\n✓ Successfully processed: {successful}'))
        if failed > 0:
            self.stdout.write(self.style.WARNING(f'⚠ Failed: {failed}'))

        # Show accuracy stats for acca matches
        self._show_accuracy_stats()

    def _fetch_match_result(self, api_client, match, scraper):
        """Fetch actual match result from API-Football with scraper fallback"""
        try:
            import requests

            url = f"{api_client.base_url}/fixtures"
            params = {
                'id': match.api_football_id
            }
            headers = {
                'x-rapidapi-key': api_client.api_key,
                'x-rapidapi-host': 'v3.football.api-sports.io'
            }

            response = requests.get(url, params=params, headers=headers, timeout=10)

            if response.status_code == 200:
                data = response.json()

                # Check for API quota error
                if data.get('errors') and 'request limit' in str(data.get('errors')).lower():
                    self.stdout.write(self.style.WARNING('    ⚠ API quota exhausted, using web scraper...'))
                    return self._fetch_from_scraper(scraper, match)

                if data and 'response' in data and len(data['response']) > 0:
                    fixture = data['response'][0]

                    return {
                        'home_score': fixture['goals']['home'],
                        'away_score': fixture['goals']['away'],
                        'status': fixture['fixture']['status']['short'],
                        'source': 'API-Football'
                    }
            else:
                self.stdout.write(self.style.WARNING(f'    API returned status {response.status_code}'))
                # Try scraper as fallback
                return self._fetch_from_scraper(scraper, match)

            return None

        except Exception as e:
            self.stdout.write(self.style.WARNING(f'    API Error: {str(e)}'))
            # Try scraper as fallback
            return self._fetch_from_scraper(scraper, match)

    def _fetch_from_scraper(self, scraper, match):
        """Fetch result using web scraper"""
        try:
            result = scraper.get_match_result(
                match.home_team,
                match.away_team,
                match.match_date,
                match.league_name
            )

            if result:
                self.stdout.write(self.style.SUCCESS(f'    ✓ Found via {result.get("source", "scraper")}'))

            return result

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'    Scraper Error: {str(e)}'))
            return None

    def _evaluate_prediction(self, match):
        """Evaluate if the prediction was correct"""
        bet = match.suggested_bet.lower()
        home_score = match.home_score
        away_score = match.away_score
        total_goals = home_score + away_score

        # IMPORTANT: Check complex bets FIRST before simple bets
        # Complex bets (Win + BTTS, Win + O2.5, Win + U2.5, etc.)
        if ' and ' in bet or ' & ' in bet:
            # Split into parts and evaluate each
            parts = bet.replace(' and ', '&').split('&')
            all_correct = True
            failed_parts = []

            for part in parts:
                part = part.strip()
                # Create a temporary match object for recursive evaluation
                from copy import copy
                temp_match = copy(match)
                temp_match.suggested_bet = part
                result = self._evaluate_prediction(temp_match)

                if not result.get('correct'):
                    all_correct = False
                    failed_parts.append(part)

            return {'correct': all_correct, 'outcome': 'WIN' if all_correct else 'LOSS'}

        # Home Win
        elif 'home win' in bet or f'{match.home_team.lower()} win' in bet or bet.startswith(match.home_team.lower()):
            correct = home_score > away_score
            return {'correct': correct, 'outcome': 'WIN' if correct else 'LOSS'}

        # Away Win
        elif 'away win' in bet or f'{match.away_team.lower()} win' in bet:
            correct = away_score > home_score
            return {'correct': correct, 'outcome': 'WIN' if correct else 'LOSS'}

        # Draw
        elif 'draw' in bet and 'double chance' not in bet:
            correct = home_score == away_score
            return {'correct': correct, 'outcome': 'WIN' if correct else 'LOSS'}

        # Both Teams to Score (BTTS)
        elif 'both teams to score' in bet or 'btts' in bet or 'gg' in bet.replace('-', ''):
            correct = home_score > 0 and away_score > 0
            return {'correct': correct, 'outcome': 'WIN' if correct else 'LOSS'}

        # Over 2.5 Goals
        elif 'over 2.5' in bet or 'o2.5' in bet:
            correct = total_goals > 2.5
            return {'correct': correct, 'outcome': 'WIN' if correct else 'LOSS'}

        # Under 2.5 Goals
        elif 'under 2.5' in bet or 'u2.5' in bet:
            correct = total_goals < 2.5
            return {'correct': correct, 'outcome': 'WIN' if correct else 'LOSS'}

        # Double Chance
        elif 'double chance' in bet or 'or draw' in bet:
            if match.home_team.lower() in bet:
                correct = home_score >= away_score
            else:
                correct = away_score >= home_score
            return {'correct': correct, 'outcome': 'WIN' if correct else 'LOSS'}

        # Default: unable to determine
        return {'correct': None, 'outcome': 'UNKNOWN'}

    def _generate_post_mortem(self, gemini, match):
        """Generate AI post-mortem analysis"""
        try:
            prompt = f"""
You are analyzing a football match prediction that was made using AI.

MATCH DETAILS:
- Match: {match.home_team} vs {match.away_team}
- League: {match.league_name}
- Date: {match.match_date.strftime('%Y-%m-%d')}

ACTUAL RESULT:
- Final Score: {match.home_team} {match.home_score} - {match.away_score} {match.away_team}
- Status: {match.match_status}

AI PREDICTION:
- Suggested Bet: {match.suggested_bet}
- Confidence Score: {match.confidence_score}/10.0
- Original Analysis: {match.gemini_analysis[:500] if match.gemini_analysis else 'N/A'}

PREDICTION OUTCOME:
- Result: {'CORRECT ✅' if match.prediction_correct else 'INCORRECT ❌'}

TASK - Generate a concise post-mortem analysis (3-4 sentences):

1. **What Happened**: Briefly describe the actual match outcome and key events
2. **Prediction Analysis**: Explain why the prediction was correct or incorrect
3. **Learning Points**: What factors were missed or correctly identified
4. **Improvement Suggestions**: One specific recommendation to improve future predictions for similar matches

Keep the analysis data-driven, objective, and focused on improving the prediction model.
"""

            response = gemini.client.models.generate_content(
                model=gemini.model_name,
                contents=prompt,
                config={
                    'tools': [{'google_search': {}}]
                }
            )

            if response and response.text:
                return response.text.strip()

            return None

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'    Gemini Error: {str(e)}'))
            return None

    def _show_accuracy_stats(self):
        """Display accuracy statistics"""
        acca_matches = Match.objects.filter(
            is_in_daily_acca=True,
            result_fetched=True,
            match_status='FT',
            prediction_outcome__isnull=False
        )

        if acca_matches.exists():
            total = acca_matches.count()
            correct = acca_matches.filter(prediction_correct=True).count()
            incorrect = acca_matches.filter(prediction_correct=False).count()
            accuracy = (correct / total * 100) if total > 0 else 0

            self.stdout.write('\n' + '='*60)
            self.stdout.write(self.style.SUCCESS('\n📊 ACCUMULATOR ACCURACY STATISTICS'))
            self.stdout.write(f'\nTotal Predictions: {total}')
            self.stdout.write(self.style.SUCCESS(f'✅ Correct: {correct} ({accuracy:.1f}%)'))
            self.stdout.write(self.style.ERROR(f'❌ Incorrect: {incorrect} ({100-accuracy:.1f}%)'))

            # Show by confidence level
            high_conf = acca_matches.filter(confidence_score__gte=8.0)
            if high_conf.exists():
                high_correct = high_conf.filter(prediction_correct=True).count()
                high_total = high_conf.count()
                high_accuracy = (high_correct / high_total * 100) if high_total > 0 else 0
                self.stdout.write(f'\nHigh Confidence (8.0+): {high_correct}/{high_total} ({high_accuracy:.1f}%)')
