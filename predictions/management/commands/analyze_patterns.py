"""
Management command to analyze postmortem patterns and generate learning insights.
Focuses on detecting signal vs noise to avoid overfitting.
"""
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from datetime import timedelta
from predictions.services.uncertainty_analyzer import PostmortemPatternDetector
import json


class Command(BaseCommand):
    help = 'Analyze postmortem patterns to identify systematic biases and learning opportunities'

    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=30,
            help='Number of days to look back for pattern analysis (default: 30)'
        )
        parser.add_argument(
            '--min-occurrences',
            type=int,
            default=3,
            help='Minimum pattern occurrences to be considered significant (default: 3)'
        )
        parser.add_argument(
            '--output-format',
            choices=['text', 'json'],
            default='text',
            help='Output format for results'
        )
        parser.add_argument(
            '--save-insights',
            action='store_true',
            help='Save insights to a file for reference'
        )

    def handle(self, *args, **options):
        days_back = options['days']
        min_occurrences = options['min_occurrences']
        output_format = options['output_format']
        save_insights = options['save_insights']

        self.stdout.write(
            self.style.SUCCESS(f'🔍 Analyzing prediction patterns from last {days_back} days...')
        )
        
        try:
            # Initialize pattern detector
            pattern_detector = PostmortemPatternDetector(min_pattern_occurrences=min_occurrences)
            
            # Detect systematic biases
            bias_analysis = pattern_detector.detect_systematic_biases(days_back=days_back)
            
            # Generate learning insights
            learning_insights = pattern_detector.generate_learning_insights()
            
            # Output results
            if output_format == 'json':
                self._output_json(bias_analysis, learning_insights)
            else:
                self._output_text(bias_analysis, learning_insights, days_back, min_occurrences)
            
            # Save insights if requested
            if save_insights:
                self._save_insights_to_file(bias_analysis, learning_insights, days_back)
                
        except Exception as e:
            raise CommandError(f'Error analyzing patterns: {str(e)}')

    def _output_text(self, bias_analysis, learning_insights, days_back, min_occurrences):
        """Output results in human-readable text format."""
        self.stdout.write(self.style.SUCCESS('\n' + '='*60))
        self.stdout.write(self.style.SUCCESS('📊 PREDICTION PATTERN ANALYSIS REPORT'))
        self.stdout.write(self.style.SUCCESS('='*60))
        
        # Analysis parameters
        self.stdout.write(f'📅 Analysis Period: {days_back} days')
        self.stdout.write(f'🔢 Minimum Pattern Occurrences: {min_occurrences}')
        
        if bias_analysis['insufficient_data']:
            self.stdout.write(self.style.WARNING('\n⚠️  INSUFFICIENT DATA'))
            self.stdout.write('Not enough prediction failures to detect patterns.')
            self.stdout.write('Continue collecting results for meaningful pattern analysis.')
            return
        
        # Summary statistics
        self.stdout.write(f'\n📈 ANALYSIS SUMMARY:')
        self.stdout.write(f'  • Total Failed Predictions: {bias_analysis["total_failures"]}')
        self.stdout.write(f'  • Patterns Detected: {len(bias_analysis["patterns"])}')
        self.stdout.write(f'  • Analysis Quality: {learning_insights["analysis_quality"]}')
        
        # Detected patterns
        if bias_analysis['patterns']:
            self.stdout.write(f'\n🔍 SYSTEMATIC PATTERNS DETECTED:')
            
            for pattern_name, pattern_data in bias_analysis['patterns'].items():
                frequency = pattern_data['frequency']
                occurrences = pattern_data['occurrences']
                
                if frequency > 0.5:
                    style = self.style.ERROR  # High frequency = major issue
                elif frequency > 0.3:
                    style = self.style.WARNING  # Medium frequency = notable issue
                else:
                    style = self.style.NOTICE  # Lower frequency = minor issue
                
                self.stdout.write(
                    style(f'  🔸 {pattern_name.replace("_", " ").title()}:')
                )
                self.stdout.write(f'    - Frequency: {frequency:.1%} ({occurrences} occurrences)')
                
                # Show examples for high-frequency patterns
                if frequency > 0.3 and 'examples' in pattern_data:
                    self.stdout.write('    - Recent Examples:')
                    for example in pattern_data['examples'][:2]:
                        match = f"{example['home_team']} vs {example['away_team']}"
                        analysis_snippet = example['post_mortem_analysis'][:100] + '...'
                        self.stdout.write(f'      • {match}: {analysis_snippet}')
        
        # Learning insights
        if learning_insights['insights']:
            self.stdout.write(f'\n💡 LEARNING INSIGHTS:')
            for insight in learning_insights['insights']:
                self.stdout.write(f'  • {insight}')
        
        # Recommendations
        if learning_insights['recommendations']:
            self.stdout.write(f'\n🎯 ACTIONABLE RECOMMENDATIONS:')
            for i, recommendation in enumerate(learning_insights['recommendations'], 1):
                self.stdout.write(f'  {i}. {recommendation}')
        
        # Anti-overfitting warning
        self.stdout.write(f'\n⚠️  OVERFITTING PREVENTION:')
        self.stdout.write('• Only patterns with 3+ occurrences are shown (signal vs noise)')
        self.stdout.write('• Football\'s inherent randomness means some failures are normal')
        self.stdout.write('• Focus on systematic biases, not individual match outcomes')
        self.stdout.write('• Re-run this analysis after collecting more data')
        
        self.stdout.write(self.style.SUCCESS('\n' + '='*60))

    def _output_json(self, bias_analysis, learning_insights):
        """Output results in JSON format."""
        result = {
            'timestamp': timezone.now().isoformat(),
            'bias_analysis': bias_analysis,
            'learning_insights': learning_insights
        }
        
        self.stdout.write(json.dumps(result, indent=2, default=str))

    def _save_insights_to_file(self, bias_analysis, learning_insights, days_back):
        """Save insights to a timestamped file."""
        timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
        filename = f'prediction_insights_{days_back}days_{timestamp}.json'
        
        data = {
            'analysis_date': timezone.now().isoformat(),
            'analysis_period_days': days_back,
            'bias_analysis': bias_analysis,
            'learning_insights': learning_insights,
            'metadata': {
                'generated_by': 'analyze_patterns management command',
                'purpose': 'Identify systematic prediction biases for model improvement'
            }
        }
        
        try:
            with open(filename, 'w') as f:
                json.dump(data, f, indent=2, default=str)
            
            self.stdout.write(
                self.style.SUCCESS(f'💾 Insights saved to: {filename}')
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Failed to save insights: {str(e)}')
            )