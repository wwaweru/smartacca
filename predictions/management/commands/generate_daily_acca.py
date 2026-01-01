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

        # Step 3: Analyze each match with Gemini AI
        self.stdout.write('\nStep 2: Analyzing matches with Gemini AI...')
        analyzed_matches = []

        for idx, match_data in enumerate(fixtures, 1):
            self.stdout.write(f'\nAnalyzing match {idx}/{len(fixtures)}: '
                            f'{match_data["home_team"]} vs {match_data["away_team"]}')

            try:
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

        # Step 4: Sort by confidence score and select top 5 low-risk matches
        self.stdout.write('\nStep 3: Selecting top 5 low-risk matches for accumulator...')

        # Filter for low risk matches and sort by confidence score
        low_risk_matches = [m for m in analyzed_matches if m['risk_level'] == 'Low Risk']

        if len(low_risk_matches) < 5:
            self.stdout.write(self.style.WARNING(
                f'Only {len(low_risk_matches)} low-risk matches found. '
                'Including medium-risk matches...'
            ))
            # Include medium risk if not enough low risk
            medium_risk_matches = [m for m in analyzed_matches if m['risk_level'] == 'Medium Risk']
            low_risk_matches.extend(medium_risk_matches)

        # Sort by confidence score descending
        sorted_matches = sorted(low_risk_matches, key=lambda x: x['confidence_score'], reverse=True)

        # Select top 5
        top_5_matches = sorted_matches[:5]

        # Step 5: Save to database
        self.stdout.write('\nStep 4: Saving accumulator to database...')

        saved_count = 0
        for match_data in top_5_matches:
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
                        'is_in_daily_acca': True
                    }
                )

                status = 'Created' if created else 'Updated'
                self.stdout.write(
                    self.style.SUCCESS(
                        f'{status}: {match.home_team} vs {match.away_team} '
                        f'(Score: {match.confidence_score:.1f}, Bet: {match.suggested_bet})'
                    )
                )
                saved_count += 1

            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(
                        f'Error saving {match_data["home_team"]} vs {match_data["away_team"]}: {str(e)}'
                    )
                )
                continue

        # Step 6: Summary
        self.stdout.write('\n' + '='*60)
        self.stdout.write(self.style.SUCCESS(f'Daily accumulator generated successfully!'))
        self.stdout.write(f'Total matches in accumulator: {saved_count}')

        # Display the accumulator
        acca_matches = Match.objects.filter(is_in_daily_acca=True).order_by('-confidence_score')

        self.stdout.write('\n=== TODAY\'S AI-VERIFIED ACCUMULATOR ===')
        for idx, match in enumerate(acca_matches, 1):
            self.stdout.write(f'\n{idx}. {match.home_team} vs {match.away_team} ({match.league_name})')
            self.stdout.write(f'   Confidence: {match.confidence_score:.1f}/10.0')
            self.stdout.write(f'   Suggested Bet: {match.suggested_bet or "N/A"}')
            self.stdout.write(f'   AI Rationale: {match.gemini_analysis[:100]}...')

        self.stdout.write('\n' + '='*60)
        self.stdout.write(self.style.SUCCESS('Done!'))
        self.stdout.write('\nView your accumulator at: http://127.0.0.1:8000/')
