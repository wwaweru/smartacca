"""
Management command to generate the daily AI-verified accumulator
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import datetime
from predictions.models import Match
from predictions.services.intelligence import get_fixtures, analyze_match
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Generate the daily AI-verified 5-match accumulator'

    def add_arguments(self, parser):
        parser.add_argument(
            '--reset',
            action='store_true',
            help='Reset all previous acca selections before generating new ones',
        )
        parser.add_argument(
            '--date',
            type=str,
            help='Date to fetch fixtures for (YYYY-MM-DD format). Defaults to today.',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('=== SmartAcca Daily Accumulator Generator ==='))

        # Get date parameter
        target_date = options.get('date')
        if target_date:
            self.stdout.write(f'Fetching fixtures for: {target_date}')
        else:
            target_date = datetime.now().strftime('%Y-%m-%d')
            self.stdout.write(f'Fetching fixtures for today: {target_date}')

        # Step 1: Reset previous acca selections if requested
        if options['reset']:
            self.stdout.write('\nResetting previous accumulator selections...')
            Match.objects.filter(is_in_daily_acca=True).update(is_in_daily_acca=False)
            self.stdout.write(self.style.SUCCESS('Previous selections cleared.'))

        # Step 2: Fetch fixtures from API-Football
        self.stdout.write('\nStep 1: Fetching fixtures from API-Football...')
        try:
            fixtures = get_fixtures(target_date)
            self.stdout.write(self.style.SUCCESS(f'Found {len(fixtures)} fixtures from top European leagues.'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error fetching fixtures: {str(e)}'))
            return

        if not fixtures:
            self.stdout.write(self.style.WARNING('No fixtures found for this date. Exiting.'))
            return

        # Display found fixtures
        self.stdout.write('\nFixtures found:')
        for idx, fixture in enumerate(fixtures, 1):
            self.stdout.write(f'  {idx}. {fixture["home_team"]} vs {fixture["away_team"]} ({fixture["league_name"]})')

        # Step 3: Analyze each match with Gemini AI (with request pacing and quota management)
        self.stdout.write('\nStep 2: Analyzing matches with Gemini AI...')
        self.stdout.write('Note: Using Gemini 2.5 Flash with higher rate limits. Analyzing all available matches.')
        analyzed_matches = []
        
        # Gemini 2.5 Flash quota management (higher limits than flash-lite)
        MAX_DAILY_ANALYSIS = 50  # Much higher limit for full Gemini 2.5 Flash
        request_delay = 1  # Reduced delay due to higher rate limits
        
        # Prioritize matches from top leagues first
        top_leagues = ['Premier League', 'La Liga', 'Serie A', 'Bundesliga', 'Ligue 1', 'Champions League', 'Europa League']
        
        # Sort fixtures by league importance
        def get_league_priority(fixture):
            league_name = fixture.get('league_name', '')
            if league_name in top_leagues:
                return top_leagues.index(league_name)
            return 999  # Low priority for other leagues
        
        prioritized_fixtures = sorted(fixtures, key=get_league_priority)
        
        # Limit analysis to quota-safe number
        fixtures_to_analyze = prioritized_fixtures[:MAX_DAILY_ANALYSIS]
        
        if len(fixtures) > MAX_DAILY_ANALYSIS:
            self.stdout.write(self.style.WARNING(
                f'Limiting analysis to {MAX_DAILY_ANALYSIS} matches due to free tier quota limits. '
                f'Prioritizing top leagues. ({len(fixtures) - MAX_DAILY_ANALYSIS} matches skipped)'
            ))

        for idx, match_data in enumerate(fixtures_to_analyze, 1):
            self.stdout.write(f'\nAnalyzing match {idx}/{len(fixtures_to_analyze)}: '
                            f'{match_data["home_team"]} vs {match_data["away_team"]} ({match_data["league_name"]})')

            try:
                # Add delay before request (except for first request)
                if idx > 1:
                    self.stdout.write(f'  - Waiting {request_delay}s to respect rate limits...')
                    import time
                    time.sleep(request_delay)
                
                # Perform AI analysis
                analysis = analyze_match(match_data)

                analyzed_matches.append(analysis)

                self.stdout.write(f'  - Confidence Score: {analysis["confidence_score"]:.1f}/10.0')
                self.stdout.write(f'  - Risk Level: {analysis["risk_level"]}')
                self.stdout.write(f'  - Suggested Bet: {analysis.get("suggested_bet", "N/A")}')

            except Exception as e:
                self.stdout.write(self.style.ERROR(f'  - Error analyzing match: {str(e)}'))
                continue

        if not analyzed_matches:
            self.stdout.write(self.style.WARNING('No matches successfully analyzed. Exiting.'))
            return

        # Step 4: Sort all matches by confidence score and save all analyzed matches
        self.stdout.write('\nStep 3: Saving all analyzed matches sorted by confidence score...')

        # Sort all analyzed matches by confidence score (highest first)
        sorted_matches = sorted(analyzed_matches, key=lambda x: x['confidence_score'], reverse=True)
        
        # Get top matches for accumulator (low and medium risk only)
        low_risk_matches = [m for m in sorted_matches if m['risk_level'] == 'Low Risk']
        medium_risk_matches = [m for m in sorted_matches if m['risk_level'] == 'Medium Risk']
        acca_candidates = low_risk_matches + medium_risk_matches
        
        # Select top 5 for daily accumulator
        top_5_matches = acca_candidates[:5] if len(acca_candidates) >= 5 else acca_candidates
        
        self.stdout.write(f'Total matches analyzed: {len(sorted_matches)}')
        self.stdout.write(f'Accumulator candidates (Low/Medium risk): {len(acca_candidates)}')
        self.stdout.write(f'Selected for daily accumulator: {len(top_5_matches)}')

        # Step 5: Save ALL matches to database, mark accumulator matches
        self.stdout.write('\nStep 4: Saving all matches to database...')

        # First, reset all previous acca selections for today
        today_date = datetime.strptime(target_date, '%Y-%m-%d').date()
        today_matches = Match.objects.filter(match_date__date=today_date)
        today_matches.update(is_in_daily_acca=False)
        
        saved_count = 0
        acca_count = 0
        
        # Save all fixtures (analyzed and unanalyzed)
        all_fixtures_to_save = []
        
        # Add analyzed matches first
        for match_data in sorted_matches:
            all_fixtures_to_save.append({
                'data': match_data,
                'analyzed': True,
                'is_in_acca': match_data in top_5_matches
            })
        
        # Add unanalyzed fixtures (those skipped due to quota limits)
        skipped_fixtures = [f for f in fixtures if f not in fixtures_to_analyze]
        for match_data in skipped_fixtures:
            # Create a minimal entry for unanalyzed matches
            match_entry = {
                'home_team': match_data['home_team'],
                'away_team': match_data['away_team'],
                'match_date': match_data['match_date'],
                'league_name': match_data.get('league_name', 'Unknown'),
                'fixture_id': match_data.get('fixture_id', hash(f"{match_data['home_team']}{match_data['away_team']}") % 1000000),
                'gemini_analysis': 'Not analyzed - quota limit reached',
                'confidence_score': 0.0,
                'risk_level': 'Not Analyzed',
                'suggested_bet': 'N/A'
            }
            all_fixtures_to_save.append({
                'data': match_entry,
                'analyzed': False,
                'is_in_acca': False
            })
        
        # Now save all fixtures
        for fixture_info in all_fixtures_to_save:
            match_data = fixture_info['data']
            is_in_acca = fixture_info['is_in_acca']
            try:
                # Parse match_date if it's a string
                match_date = match_data['match_date']
                if isinstance(match_date, str):
                    from dateutil import parser
                    match_date = parser.parse(match_date)

                # Create or update match
                match, created = Match.objects.update_or_create(
                    api_football_id=match_data.get('fixture_id', hash(f"{match_data['home_team']}{match_data['away_team']}") % 1000000),
                    defaults={
                        'home_team': match_data['home_team'],
                        'away_team': match_data['away_team'],
                        'match_date': match_date,
                        'league_name': match_data.get('league_name', 'Unknown'),
                        'tipster_1_pick': match_data.get('tipster_1_pick'),
                        'tipster_2_pick': match_data.get('tipster_2_pick'),
                        'tipster_3_pick': match_data.get('tipster_3_pick'),
                        'gemini_analysis': match_data['gemini_analysis'],
                        'confidence_score': match_data['confidence_score'],
                        'suggested_bet': match_data.get('suggested_bet', 'N/A'),
                        'is_in_daily_acca': is_in_acca
                    }
                )

                status = 'Created' if created else 'Updated'
                acca_status = ' [ACCUMULATOR]' if is_in_acca else ''
                analyzed_status = ' [ANALYZED]' if fixture_info['analyzed'] else ' [QUOTA LIMIT]'
                
                if fixture_info['analyzed']:
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'{status}: {match.home_team} vs {match.away_team} '
                            f'(Score: {match.confidence_score:.1f}, Risk: {match_data["risk_level"]}, Bet: {match.suggested_bet}){acca_status}'
                        )
                    )
                else:
                    self.stdout.write(
                        self.style.WARNING(
                            f'{status}: {match.home_team} vs {match.away_team} '
                            f'(Not analyzed - quota limit){analyzed_status}'
                        )
                    )
                
                saved_count += 1
                if is_in_acca:
                    acca_count += 1

            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(
                        f'Error saving {match_data["home_team"]} vs {match_data["away_team"]}: {str(e)}'
                    )
                )
                continue

        # Step 6: Summary
        self.stdout.write('\n' + '='*60)
        self.stdout.write(self.style.SUCCESS(f'Daily matches analysis completed successfully!'))
        self.stdout.write(f'Total matches saved: {saved_count}')
        self.stdout.write(f'Matches in daily accumulator: {acca_count}')

        # Display all matches and the accumulator
        all_matches = Match.objects.filter(
            match_date__date=today_date
        ).exclude(
            confidence_score=0.0
        ).order_by('-confidence_score')
        
        acca_matches = all_matches.filter(is_in_daily_acca=True)

        self.stdout.write('\n=== ALL TODAY\'S ANALYZED MATCHES (Sorted by Confidence) ===')
        for idx, match in enumerate(all_matches, 1):
            acca_indicator = ' [IN ACCUMULATOR]' if match.is_in_daily_acca else ''
            self.stdout.write(f'{idx}. {match.home_team} vs {match.away_team} ({match.league_name}){acca_indicator}')
            self.stdout.write(f'   Confidence: {match.confidence_score:.1f}/10.0')
            self.stdout.write(f'   Suggested Bet: {match.suggested_bet or "N/A"}')
            
        self.stdout.write('\n=== TODAY\'S AI-VERIFIED ACCUMULATOR ===')
        for idx, match in enumerate(acca_matches, 1):
            self.stdout.write(f'\n{idx}. {match.home_team} vs {match.away_team} ({match.league_name})')
            self.stdout.write(f'   Confidence: {match.confidence_score:.1f}/10.0')
            self.stdout.write(f'   Suggested Bet: {match.suggested_bet or "N/A"}')
            self.stdout.write(f'   AI Rationale: {match.gemini_analysis[:100]}...')

        self.stdout.write('\n' + '='*60)
        self.stdout.write(self.style.SUCCESS('Done!'))
        self.stdout.write('\nView your accumulator at: http://127.0.0.1:8000/')
