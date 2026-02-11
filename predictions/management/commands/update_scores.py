from django.core.management.base import BaseCommand
from django.utils import timezone
from predictions.models import Match
from predictions.services.intelligence import GeminiAnalyzer
from datetime import datetime
import sys


class Command(BaseCommand):
    help = 'Enhanced manual score update tool with bulk operations and validation'

    def add_arguments(self, parser):
        parser.add_argument('--match-id', type=int, help='Update specific match by ID')
        parser.add_argument('--home-score', type=int, help='Home team score')
        parser.add_argument('--away-score', type=int, help='Away team score')
        parser.add_argument('--status', type=str, default='FT', help='Match status (default: FT)')
        
        # Bulk operations
        parser.add_argument('--league', type=str, help='Update all matches in league for date')
        parser.add_argument('--date', type=str, help='Date (YYYY-MM-DD) for bulk operations')
        parser.add_argument('--interactive', action='store_true', help='Interactive mode for multiple matches')
        
        # Validation options
        parser.add_argument('--force', action='store_true', help='Skip validation checks')
        parser.add_argument('--dry-run', action='store_true', help='Show what would be updated without saving')

    def handle(self, *args, **options):
        self.stdout.write('=== Enhanced Score Update Tool ===\n')

        if options['match_id']:
            self._update_single_match(options)
        elif options['league'] and options['date']:
            self._update_league_matches(options)
        elif options['interactive']:
            self._interactive_mode(options)
        else:
            self.stdout.write(self.style.ERROR('Please specify --match-id or use --interactive mode'))
            self._show_usage()

    def _update_single_match(self, options):
        """Update a single match by ID"""
        try:
            match = Match.objects.get(id=options['match_id'])
        except Match.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'Match with ID {options["match_id"]} not found'))
            return

        if not options['home_score'] or not options['away_score']:
            self.stdout.write(self.style.ERROR('Both --home-score and --away-score are required'))
            return

        self._update_match_scores(match, options['home_score'], options['away_score'], 
                                options['status'], options)

    def _update_league_matches(self, options):
        """Update all matches for a specific league and date"""
        try:
            target_date = datetime.strptime(options['date'], '%Y-%m-%d').date()
        except ValueError:
            self.stdout.write(self.style.ERROR('Invalid date format. Use YYYY-MM-DD'))
            return

        matches = Match.objects.filter(
            league_name__icontains=options['league'],
            match_date__date=target_date,
            result_fetched=False
        )

        if not matches.exists():
            self.stdout.write(self.style.WARNING(f'No pending matches found for {options["league"]} on {target_date}'))
            return

        self.stdout.write(f'Found {matches.count()} matches for {options["league"]} on {target_date}:\n')
        
        for i, match in enumerate(matches, 1):
            self.stdout.write(f'{i}. {match.home_team} vs {match.away_team} (ID: {match.id})')

        self.stdout.write(f'\nUse --match-id to update specific matches, or --interactive for guided updates\n')

    def _interactive_mode(self, options):
        """Interactive mode for updating multiple matches"""
        # Find matches that need updating
        cutoff_date = timezone.now().date()
        
        pending_matches = Match.objects.filter(
            match_date__date__lte=cutoff_date,
            result_fetched=False
        ).exclude(
            match_status__in=['NS', 'PST', 'CAN']
        ).order_by('-is_in_daily_acca', 'match_date')

        if not pending_matches.exists():
            self.stdout.write(self.style.SUCCESS('No matches need score updates!'))
            return

        self.stdout.write(f'Found {pending_matches.count()} matches needing updates:\n')

        for match in pending_matches:
            self.stdout.write(f'\n📍 {match.home_team} vs {match.away_team}')
            self.stdout.write(f'   League: {match.league_name}')
            self.stdout.write(f'   Date: {match.match_date.strftime("%Y-%m-%d %H:%M")}')
            self.stdout.write(f'   ID: {match.id}')
            if match.is_in_daily_acca:
                self.stdout.write('   🎯 ACCA MATCH')

            try:
                # Get user input
                response = input('\nEnter scores (format: "2-1" or "2-1:FT") or [s]kip or [q]uit: ').strip()
                
                if response.lower() == 'q':
                    break
                elif response.lower() == 's' or response == '':
                    continue

                # Parse input
                if ':' in response:
                    score_part, status = response.split(':')
                    status = status.upper()
                else:
                    score_part = response
                    status = 'FT'

                if '-' not in score_part:
                    self.stdout.write(self.style.ERROR('Invalid format. Use "2-1" or "2-1:FT"'))
                    continue

                try:
                    home_score, away_score = map(int, score_part.split('-'))
                except ValueError:
                    self.stdout.write(self.style.ERROR('Invalid scores. Use numbers only.'))
                    continue

                # Validate scores
                if not self._validate_scores(home_score, away_score, match, options):
                    continue

                # Update the match
                self._update_match_scores(match, home_score, away_score, status, options)

            except KeyboardInterrupt:
                self.stdout.write('\n\nUpdate cancelled by user.')
                break
            except EOFError:
                break

    def _update_match_scores(self, match, home_score, away_score, status, options):
        """Update match with scores and handle prediction evaluation"""
        
        # Validation
        if not self._validate_scores(home_score, away_score, match, options):
            return

        # Show what will be updated
        self.stdout.write(f'\n📝 Updating: {match.home_team} vs {match.away_team}')
        self.stdout.write(f'   Score: {home_score} - {away_score}')
        self.stdout.write(f'   Status: {status}')

        if options.get('dry_run'):
            self.stdout.write(self.style.WARNING('DRY RUN - No changes saved'))
            return

        # Store old values for rollback
        old_home_score = match.home_score
        old_away_score = match.away_score
        old_status = match.match_status
        old_fetched = match.result_fetched

        try:
            # Update match
            match.home_score = home_score
            match.away_score = away_score
            match.match_status = status
            match.result_fetched = True
            match.result_fetched_at = timezone.now()

            self.stdout.write(f'✅ Result: {match.home_team} {home_score} - {away_score} {match.away_team} ({status})')

            # Evaluate prediction
            if match.suggested_bet:
                from predictions.management.commands.fetch_results import Command as FetchCommand
                fetch_cmd = FetchCommand()
                
                prediction_result = fetch_cmd._evaluate_prediction(match)
                match.prediction_correct = prediction_result['correct']
                match.prediction_outcome = prediction_result['outcome']

                outcome_icon = '✅' if prediction_result['correct'] else '❌'
                self.stdout.write(f'🎯 Prediction: {outcome_icon} {prediction_result["outcome"]}')

                # Generate post-mortem for ACCA matches
                if match.is_in_daily_acca and prediction_result['correct'] is not None:
                    self._generate_post_mortem(match)

            match.save()
            self.stdout.write(self.style.SUCCESS('✅ Match updated successfully!'))

        except Exception as e:
            # Rollback on error
            match.home_score = old_home_score
            match.away_score = old_away_score
            match.match_status = old_status
            match.result_fetched = old_fetched
            
            self.stdout.write(self.style.ERROR(f'❌ Error updating match: {str(e)}'))

    def _validate_scores(self, home_score, away_score, match, options):
        """Validate score inputs"""
        if options.get('force'):
            return True

        # Basic validation
        if home_score < 0 or away_score < 0:
            self.stdout.write(self.style.ERROR('Scores cannot be negative'))
            return False

        if home_score > 20 or away_score > 20:
            response = input(f'⚠️  High score detected ({home_score}-{away_score}). Continue? [y/N]: ')
            if response.lower() != 'y':
                return False

        # Check if match has already been updated
        if match.result_fetched and not options.get('force'):
            self.stdout.write(f'⚠️  Match already has result: {match.home_score}-{match.away_score} ({match.match_status})')
            response = input('Overwrite existing result? [y/N]: ')
            if response.lower() != 'y':
                return False

        return True

    def _generate_post_mortem(self, match):
        """Generate post-mortem analysis for ACCA matches"""
        try:
            self.stdout.write('🤖 Generating AI post-mortem analysis...')
            gemini = GeminiAnalyzer()

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

Generate a concise post-mortem analysis (3-4 sentences):
1. What happened in the match
2. Why the prediction was right/wrong
3. Key learning points
4. Improvement suggestions

Keep it objective and data-driven.
"""

            response = gemini.client.models.generate_content(
                model=gemini.model_name,
                contents=prompt,
                config={'tools': [{'google_search': {}}]}
            )

            if response and response.text:
                match.post_mortem_analysis = response.text.strip()
                match.post_mortem_generated = True
                match.post_mortem_generated_at = timezone.now()
                self.stdout.write(self.style.SUCCESS('✅ Post-mortem generated'))

        except Exception as e:
            self.stdout.write(self.style.WARNING(f'⚠️  Could not generate post-mortem: {str(e)}'))

    def _show_usage(self):
        """Show usage examples"""
        self.stdout.write('\nUsage Examples:')
        self.stdout.write('  Single match:    python manage.py update_scores --match-id 123 --home-score 2 --away-score 1')
        self.stdout.write('  Interactive:     python manage.py update_scores --interactive')
        self.stdout.write('  League overview: python manage.py update_scores --league "Championship" --date 2024-01-15')
        self.stdout.write('  Dry run:         python manage.py update_scores --match-id 123 --home-score 2 --away-score 1 --dry-run')
        
        # Show pending matches
        pending = Match.objects.filter(
            match_date__date__lte=timezone.now().date(),
            result_fetched=False
        ).exclude(
            match_status__in=['NS', 'PST', 'CAN']
        ).count()
        
        if pending > 0:
            self.stdout.write(f'\n📊 {pending} matches currently need score updates.')
            self.stdout.write('   Use --interactive mode for guided updates.')