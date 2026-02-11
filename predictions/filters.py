import django_filters
from .models import Match

class MatchFilter(django_filters.FilterSet):
    UNCERTAINTY_CHOICES = [
        ('Predictable', 'Predictable'),
        ('Uncertain', 'Uncertain'),
        ('Certain', 'Certain'),
        ('Coin Flip', 'Coin Flip'),
        ('Upset Prone', 'Upset Prone'),
    ]

    confidence_score_min = django_filters.NumberFilter(field_name='confidence_score', lookup_expr='gte')
    confidence_score_max = django_filters.NumberFilter(field_name='confidence_score', lookup_expr='lte')
    uncertainty_category = django_filters.ChoiceFilter(field_name='uncertainty_category', choices=UNCERTAINTY_CHOICES)

    class Meta:
        model = Match
        fields = ['confidence_score_min', 'confidence_score_max', 'uncertainty_category']