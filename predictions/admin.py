from django.contrib import admin
from .models import Match


@admin.register(Match)
class MatchAdmin(admin.ModelAdmin):
    list_display = [
        'home_team',
        'away_team',
        'match_date',
        'league_name',
        'confidence_score',
        'is_in_daily_acca',
        'created_at'
    ]

    list_filter = [
        'is_in_daily_acca',
        'league_name',
        'match_date',
        'created_at'
    ]

    search_fields = [
        'home_team',
        'away_team',
        'league_name'
    ]

    readonly_fields = [
        'created_at',
        'updated_at',
        'api_football_id'
    ]

    fieldsets = (
        ('Match Information', {
            'fields': (
                'home_team',
                'away_team',
                'match_date',
                'league_name',
                'api_football_id'
            )
        }),
        ('Tipster Predictions', {
            'fields': (
                'tipster_1_pick',
                'tipster_2_pick',
                'tipster_3_pick'
            )
        }),
        ('AI Analysis', {
            'fields': (
                'gemini_analysis',
                'confidence_score',
                'suggested_bet',
                'is_in_daily_acca'
            )
        }),
        ('Metadata', {
            'fields': (
                'created_at',
                'updated_at'
            ),
            'classes': ('collapse',)
        })
    )

    ordering = ['-match_date', '-confidence_score']

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related()

    actions = ['mark_as_acca', 'remove_from_acca']

    @admin.action(description='Mark selected matches for daily acca')
    def mark_as_acca(self, request, queryset):
        updated = queryset.update(is_in_daily_acca=True)
        self.message_user(request, f'{updated} matches marked for daily accumulator.')

    @admin.action(description='Remove selected matches from daily acca')
    def remove_from_acca(self, request, queryset):
        updated = queryset.update(is_in_daily_acca=False)
        self.message_user(request, f'{updated} matches removed from daily accumulator.')
