"""
Uncertainty and Variance Analysis for Football Predictions
Handles confidence calibration and anti-overfitting measures
"""
import logging
from datetime import timedelta
from django.utils import timezone
from django.db.models import Avg, Count, Case, When, FloatField
from ..models import Match

logger = logging.getLogger(__name__)


class ConfidenceCalibrator:
    """
    Calibrates confidence scores based on historical performance to avoid overconfidence.
    Embraces football's inherent randomness rather than fighting it.
    """
    
    def __init__(self, min_sample_size=10):
        self.min_sample_size = min_sample_size
        self.confidence_bands = {
            'very_high': (8.5, 10.0),
            'high': (7.0, 8.5),
            'medium': (5.5, 7.0),
            'low': (3.0, 5.5),
            'very_low': (0.0, 3.0)
        }
    
    def get_historical_accuracy_by_confidence(self, days_back=30):
        """
        Calculate actual accuracy rates for different confidence bands.
        Returns realistic probability ranges rather than inflated confidence.
        """
        cutoff_date = timezone.now() - timedelta(days=days_back)
        
        completed_matches = Match.objects.filter(
            result_fetched=True,
            match_status='FT',
            updated_at__gte=cutoff_date,
            confidence_score__gt=0
        )
        
        if completed_matches.count() < self.min_sample_size:
            logger.warning(f"Only {completed_matches.count()} samples for calibration. Using conservative defaults.")
            return self._get_default_calibration()
        
        calibration_data = {}
        
        for band_name, (min_conf, max_conf) in self.confidence_bands.items():
            band_matches = completed_matches.filter(
                confidence_score__gte=min_conf,
                confidence_score__lt=max_conf
            )
            
            if band_matches.exists():
                total = band_matches.count()
                correct = band_matches.filter(prediction_correct=True).count()
                accuracy = correct / total if total > 0 else 0
                
                # Calculate confidence interval for small samples
                confidence_interval = self._calculate_confidence_interval(correct, total)
                
                calibration_data[band_name] = {
                    'raw_accuracy': accuracy,
                    'sample_size': total,
                    'confidence_interval': confidence_interval,
                    'calibrated_probability': self._apply_uncertainty_penalty(accuracy, total),
                    'range': (min_conf, max_conf)
                }
        
        return calibration_data
    
    def _calculate_confidence_interval(self, successes, trials, confidence_level=0.95):
        """
        Calculate Wilson score interval for binomial proportion.
        More robust for small sample sizes than normal approximation.
        """
        if trials == 0:
            return (0, 0)
        
        from math import sqrt
        
        # Z-score for 95% confidence
        z = 1.96
        p = successes / trials
        
        denominator = 1 + (z**2) / trials
        center = p + (z**2) / (2 * trials)
        half_width = z * sqrt((p * (1 - p) + (z**2) / (4 * trials)) / trials)
        
        lower = max(0, (center - half_width) / denominator)
        upper = min(1, (center + half_width) / denominator)
        
        return (lower, upper)
    
    def _apply_uncertainty_penalty(self, raw_accuracy, sample_size):
        """
        Apply penalty for small sample sizes and football's inherent variance.
        Prevents overconfidence from lucky streaks.
        """
        # Base uncertainty penalty for football's randomness
        football_variance_penalty = 0.05  # Even perfect data has 5% uncertainty
        
        # Sample size penalty (more penalty for fewer samples)
        if sample_size < 5:
            sample_penalty = 0.15
        elif sample_size < 10:
            sample_penalty = 0.10
        elif sample_size < 20:
            sample_penalty = 0.05
        else:
            sample_penalty = 0.02
        
        # Apply penalties
        calibrated = raw_accuracy - football_variance_penalty - sample_penalty
        
        # Cap maximum confidence at 80% (even with perfect historical data)
        return min(0.80, max(0.10, calibrated))
    
    def _get_default_calibration(self):
        """
        Conservative default calibration when insufficient historical data.
        Based on realistic football prediction expectations.
        """
        return {
            'very_high': {
                'calibrated_probability': 0.65,
                'confidence_interval': (0.55, 0.75),
                'sample_size': 0,
                'range': (8.5, 10.0)
            },
            'high': {
                'calibrated_probability': 0.60,
                'confidence_interval': (0.50, 0.70),
                'sample_size': 0,
                'range': (7.0, 8.5)
            },
            'medium': {
                'calibrated_probability': 0.55,
                'confidence_interval': (0.45, 0.65),
                'sample_size': 0,
                'range': (5.5, 7.0)
            },
            'low': {
                'calibrated_probability': 0.45,
                'confidence_interval': (0.35, 0.55),
                'sample_size': 0,
                'range': (3.0, 5.5)
            },
            'very_low': {
                'calibrated_probability': 0.35,
                'confidence_interval': (0.25, 0.45),
                'sample_size': 0,
                'range': (0.0, 3.0)
            }
        }
    
    def calibrate_confidence(self, raw_confidence):
        """
        Convert raw confidence score to calibrated probability.
        Returns realistic probability rather than inflated confidence.
        """
        calibration_data = self.get_historical_accuracy_by_confidence()
        
        for band_name, (min_conf, max_conf) in self.confidence_bands.items():
            if min_conf <= raw_confidence < max_conf:
                band_data = calibration_data.get(band_name)
                if band_data:
                    return {
                        'calibrated_probability': band_data['calibrated_probability'],
                        'confidence_interval': band_data['confidence_interval'],
                        'band': band_name,
                        'raw_confidence': raw_confidence,
                        'sample_size': band_data['sample_size']
                    }
        
        # Fallback for edge cases
        return {
            'calibrated_probability': 0.50,
            'confidence_interval': (0.40, 0.60),
            'band': 'unknown',
            'raw_confidence': raw_confidence,
            'sample_size': 0
        }


class UncertaintyAnalyzer:
    """
    Categorizes matches by their predictability level.
    Helps identify when AI should be humble about its predictions.
    """
    
    def __init__(self):
        self.uncertainty_categories = {
            'predictable': {
                'description': 'Clear patterns, multiple confirming factors',
                'probability_range': (0.65, 0.80),
                'recommendation': 'Standard stake'
            },
            'uncertain': {
                'description': 'Mixed signals, moderate confidence',
                'probability_range': (0.50, 0.65),
                'recommendation': 'Reduced stake or avoid'
            },
            'coin_flip': {
                'description': 'Evenly matched, essentially random',
                'probability_range': (0.45, 0.55),
                'recommendation': 'Skip - no edge detected'
            },
            'upset_prone': {
                'description': 'Favorite vulnerable to specific factors',
                'probability_range': (0.55, 0.70),
                'recommendation': 'Consider underdog value'
            }
        }
    
    def analyze_uncertainty(self, match_data, api_stats, gemini_analysis):
        """
        Analyze match uncertainty based on data quality and signal strength.
        Returns uncertainty category and reasoning.
        """
        uncertainty_factors = []
        confidence_signals = []
        
        # Analyze data quality
        data_quality = self._assess_data_quality(api_stats)
        if data_quality['score'] < 0.6:
            uncertainty_factors.append(f"Limited data quality ({data_quality['score']:.1f}/1.0)")
        else:
            confidence_signals.append(f"Good data quality ({data_quality['score']:.1f}/1.0)")
        
        # Analyze signal consistency
        signal_consistency = self._assess_signal_consistency(match_data, api_stats)
        if signal_consistency['conflicting_signals'] > 2:
            uncertainty_factors.append(f"Conflicting signals ({signal_consistency['conflicting_signals']})")
        else:
            confidence_signals.append("Consistent signals across indicators")
        
        # Analyze team form variance
        form_variance = self._assess_form_variance(api_stats)
        if form_variance > 0.7:
            uncertainty_factors.append("High team form variance")
        
        # Determine uncertainty category
        uncertainty_score = len(uncertainty_factors) / (len(uncertainty_factors) + len(confidence_signals))
        
        if uncertainty_score >= 0.7:
            category = 'coin_flip'
        elif uncertainty_score >= 0.5:
            category = 'uncertain'
        elif uncertainty_score >= 0.3:
            category = 'upset_prone'
        else:
            category = 'predictable'
        
        return {
            'category': category,
            'uncertainty_score': uncertainty_score,
            'uncertainty_factors': uncertainty_factors,
            'confidence_signals': confidence_signals,
            'recommendation': self.uncertainty_categories[category]['recommendation'],
            'data_quality': data_quality
        }
    
    def _assess_data_quality(self, api_stats):
        """
        Assess quality and completeness of available data.
        Poor data quality increases uncertainty.
        """
        quality_score = 0.0
        max_score = 4.0
        missing_data = []
        
        # Check injury data quality
        home_injuries = api_stats.get('home_team', {}).get('injuries', [])
        away_injuries = api_stats.get('away_team', {}).get('injuries', [])
        
        if home_injuries and away_injuries:
            if not any('unavailable' in str(inj).lower() for inj in home_injuries + away_injuries):
                quality_score += 1.0
            else:
                missing_data.append('injury_data')
        else:
            missing_data.append('injury_data')
        
        # Check form data
        if (api_stats.get('home_team', {}).get('recent_results') and 
            api_stats.get('away_team', {}).get('recent_results')):
            quality_score += 1.0
        else:
            missing_data.append('recent_form')
        
        # Check standings data
        if (api_stats.get('home_team', {}).get('league_position') and 
            api_stats.get('away_team', {}).get('league_position')):
            quality_score += 1.0
        else:
            missing_data.append('league_standings')
        
        # Bonus for complete dataset
        if len(missing_data) == 0:
            quality_score += 1.0
        
        return {
            'score': quality_score / max_score,
            'missing_data': missing_data,
            'completeness': (max_score - len(missing_data)) / max_score
        }
    
    def _assess_signal_consistency(self, match_data, api_stats):
        """
        Check if different indicators point in the same direction.
        Conflicting signals increase uncertainty.
        """
        signals = []
        
        # Form signals
        home_form = api_stats.get('home_team', {}).get('recent_results', [])
        away_form = api_stats.get('away_team', {}).get('recent_results', [])
        
        if home_form and away_form:
            home_wins = home_form.count('W')
            away_wins = away_form.count('W')
            
            if home_wins > away_wins + 1:
                signals.append('form_favors_home')
            elif away_wins > home_wins + 1:
                signals.append('form_favors_away')
            else:
                signals.append('form_neutral')
        
        # League position signals
        home_pos = api_stats.get('home_team', {}).get('league_position', {})
        away_pos = api_stats.get('away_team', {}).get('league_position', {})
        
        if home_pos and away_pos:
            home_position = home_pos.get('position', 999)
            away_position = away_pos.get('position', 999)
            
            if home_position < away_position - 3:
                signals.append('standings_favor_home')
            elif away_position < home_position - 3:
                signals.append('standings_favor_away')
            else:
                signals.append('standings_neutral')
        
        # Count conflicting signals
        home_signals = [s for s in signals if 'home' in s]
        away_signals = [s for s in signals if 'away' in s]
        conflicting_signals = min(len(home_signals), len(away_signals))
        
        return {
            'signals': signals,
            'conflicting_signals': conflicting_signals,
            'consistency': 1 - (conflicting_signals / max(1, len(signals)))
        }
    
    def _assess_form_variance(self, api_stats):
        """
        Assess variance in team form (high variance = less predictable).
        """
        variance_factors = 0
        
        # Check for inconsistent recent results
        for team in ['home_team', 'away_team']:
            recent_results = api_stats.get(team, {}).get('recent_results', [])
            if recent_results and len(recent_results) >= 3:
                # Check for mixed results (not all W/D/L)
                unique_results = set(recent_results)
                if len(unique_results) >= 3:  # Has W, D, and L
                    variance_factors += 1
        
        return variance_factors / 2  # Normalize to 0-1


class PostmortemPatternDetector:
    """
    Detects systematic patterns in prediction failures.
    Focuses on signal vs noise to avoid overfitting.
    """
    
    def __init__(self, min_pattern_occurrences=3):
        self.min_pattern_occurrences = min_pattern_occurrences
    
    def detect_systematic_biases(self, days_back=60):
        """
        Identify systematic biases that occur frequently enough to be signal, not noise.
        """
        cutoff_date = timezone.now() - timedelta(days=days_back)
        
        failed_predictions = Match.objects.filter(
            result_fetched=True,
            match_status='FT',
            prediction_correct=False,
            updated_at__gte=cutoff_date,
            post_mortem_analysis__isnull=False
        )
        
        if failed_predictions.count() < self.min_pattern_occurrences:
            return {'patterns': [], 'insufficient_data': True}
        
        patterns = {}
        
        # Analyze postmortem text for common themes
        common_phrases = [
            'overestimated',
            'underestimated',
            'missed',
            'failed to account',
            'inaccurate assessment',
            'defensive stalemate',
            'upset potential',
            'expected goals'
        ]
        
        for phrase in common_phrases:
            count = sum(1 for match in failed_predictions 
                       if phrase.lower() in match.post_mortem_analysis.lower())
            
            if count >= self.min_pattern_occurrences:
                patterns[phrase] = {
                    'occurrences': count,
                    'frequency': count / failed_predictions.count(),
                    'examples': list(failed_predictions.filter(
                        post_mortem_analysis__icontains=phrase
                    )[:3].values('home_team', 'away_team', 'post_mortem_analysis'))
                }
        
        # Detect confidence level biases
        high_conf_failures = failed_predictions.filter(confidence_score__gte=8.0)
        if high_conf_failures.count() >= self.min_pattern_occurrences:
            patterns['overconfidence_bias'] = {
                'occurrences': high_conf_failures.count(),
                'frequency': high_conf_failures.count() / failed_predictions.count(),
                'description': 'High confidence predictions failing systematically'
            }
        
        return {
            'patterns': patterns,
            'total_failures': failed_predictions.count(),
            'analysis_period_days': days_back,
            'insufficient_data': False
        }
    
    def generate_learning_insights(self):
        """
        Generate actionable insights for improving predictions.
        Only includes patterns with statistical significance.
        """
        bias_analysis = self.detect_systematic_biases()
        
        if bias_analysis['insufficient_data']:
            return {
                'insights': ['Insufficient data for pattern detection'],
                'recommendations': ['Collect more prediction outcomes before learning']
            }
        
        insights = []
        recommendations = []
        
        patterns = bias_analysis['patterns']
        
        # High-frequency pattern insights
        for pattern_name, pattern_data in patterns.items():
            if pattern_data['frequency'] > 0.3:  # Appears in >30% of failures
                insights.append(f"Frequent issue: {pattern_name} (in {pattern_data['frequency']:.1%} of failures)")
                
                if pattern_name == 'overestimated':
                    recommendations.append("Add more conservative goal-scoring projections")
                elif pattern_name == 'defensive stalemate':
                    recommendations.append("Weight defensive strength metrics more heavily")
                elif pattern_name == 'upset potential':
                    recommendations.append("Add dynamic 'upset probability' factors")
        
        return {
            'insights': insights,
            'recommendations': recommendations,
            'patterns_detected': len(patterns),
            'analysis_quality': 'high' if bias_analysis['total_failures'] > 10 else 'moderate'
        }