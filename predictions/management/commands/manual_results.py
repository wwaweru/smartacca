from django.core.management.base import BaseCommand
from django.utils import timezone
from predictions.models import Match
from predictions.services.intelligence import GeminiAnalyzer


class Command(BaseCommand):
    help = 'Manually enter match results when API quota is exhausted'

    def add_arguments(self, parser):
        parser.add_argument('--match-id', type=int, required=True, help='Match database ID')
        parser.add_argument('--home-score', type=int, required=True, help='Home team score')
        parser.add_argument('--away-score', type=int, required=True, help='Away team score')
        parser.add_argument('--status', type=str, default='FT', help='Match status (default: FT)')

    def handle(self, *args, **options):
        try:
            match = Match.objects.get(id=options['match_id'])
        except Match.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'Match with ID {options["match_id"]} not found'))
            return

        self.stdout.write(f'\nUpdating: {match.home_team} vs {match.away_team}')

        # Update scores
        match.home_score = options['home_score']
        match.away_score = options['away_score']
        match.match_status = options['status']
        match.result_fetched = True
        match.result_fetched_at = timezone.now()

        self.stdout.write(
            f"Result: {match.home_team} {match.home_score} - "
            f"{match.away_score} {match.away_team} ({match.match_status})"
        )

        # Evaluate prediction
        if match.suggested_bet and match.match_status == 'FT':
            from predictions.management.commands.fetch_results import Command as FetchCommand
            fetch_cmd = FetchCommand()
            prediction_result = fetch_cmd._evaluate_prediction(match)
            match.prediction_correct = prediction_result['correct']
            match.prediction_outcome = prediction_result['outcome']

            outcome_icon = '✅' if prediction_result['correct'] else '❌'
            self.stdout.write(
                f"Prediction: {outcome_icon} {prediction_result['outcome']}"
            )

            # Generate post-mortem if in acca
            if match.is_in_daily_acca:
                self.stdout.write('Generating AI post-mortem analysis...')
                try:
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
                        config={'tools': [{'google_search': {}}]}
                    )

                    if response and response.text:
                        match.post_mortem_analysis = response.text.strip()
                        match.post_mortem_generated = True
                        match.post_mortem_generated_at = timezone.now()
                        self.stdout.write(self.style.SUCCESS('✓ Post-mortem generated'))

                except Exception as e:
                    self.stdout.write(self.style.WARNING(f'Could not generate post-mortem: {str(e)}'))

        match.save()
        self.stdout.write(self.style.SUCCESS('\n✓ Match result saved successfully!'))
