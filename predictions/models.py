from django.db import models


class Match(models.Model):
    home_team = models.CharField(max_length=100)
    away_team = models.CharField(max_length=100)
    match_date = models.DateTimeField()
    league_name = models.CharField(max_length=100)
    api_football_id = models.IntegerField(unique=True)

    # Tipster predictions
    tipster_1_pick = models.CharField(max_length=200, blank=True, null=True)
    tipster_2_pick = models.CharField(max_length=200, blank=True, null=True)
    tipster_3_pick = models.CharField(max_length=200, blank=True, null=True)

    # AI Analysis
    gemini_analysis = models.TextField(blank=True, null=True)
    confidence_score = models.FloatField(default=0.0)
    suggested_bet = models.CharField(max_length=200, blank=True, null=True)

    # Accumulator flag
    is_in_daily_acca = models.BooleanField(default=False)

    # Match Results
    home_score = models.IntegerField(null=True, blank=True)
    away_score = models.IntegerField(null=True, blank=True)
    match_status = models.CharField(max_length=20, blank=True, null=True)  # FT, HT, LIVE, NS, etc.
    result_fetched = models.BooleanField(default=False)
    result_fetched_at = models.DateTimeField(null=True, blank=True)

    # Prediction Outcome
    prediction_correct = models.BooleanField(null=True, blank=True)
    prediction_outcome = models.CharField(max_length=20, blank=True, null=True)  # WIN, LOSS, PENDING

    # Post-Mortem Analysis
    post_mortem_analysis = models.TextField(blank=True, null=True)
    post_mortem_generated = models.BooleanField(default=False)
    post_mortem_generated_at = models.DateTimeField(null=True, blank=True)

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-match_date']
        verbose_name_plural = 'Matches'

    def __str__(self):
        return f"{self.home_team} vs {self.away_team} - {self.match_date.strftime('%Y-%m-%d')}"
