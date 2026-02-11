from django.shortcuts import render
from django.utils import timezone
from django.db.models import Q, Count, Case, When, IntegerField
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from datetime import timedelta
from .models import Match
from .filters import MatchFilter

# Import MatchFilter to access UNCERTAINTY_CHOICES
from .filters import MatchFilter


def dashboard(request):
    """
    Main dashboard view displaying predictions with filters.
    """
    # Filter parameters
    date_filter = request.GET.get('date', 'today')  # today, yesterday, all
    status_filter = request.GET.get('status', 'all')  # all, upcoming, completed, won, lost
    page = request.GET.get('page', 1)

    # Base query - show all analyzed matches (excluding unanalyzed ones with 0 confidence)
    base_query = Match.objects.exclude(confidence_score=0.0)

    # Apply date filter
    today = timezone.now().date()
    if date_filter == 'today':
        matches_query = base_query.filter(match_date__date=today)
    elif date_filter == 'yesterday':
        yesterday = today - timedelta(days=1)
        matches_query = base_query.filter(match_date__date=yesterday)
    elif date_filter == 'week':
        week_ago = timezone.now() - timedelta(days=7)
        matches_query = base_query.filter(match_date__gte=week_ago)
    else:  # all
        matches_query = base_query

    # Apply status filter
    if status_filter == 'upcoming':
        matches_query = matches_query.filter(result_fetched=False)
    elif status_filter == 'completed':
        matches_query = matches_query.filter(result_fetched=True, match_status='FT')
    elif status_filter == 'won':
        matches_query = matches_query.filter(prediction_correct=True)
    elif status_filter == 'lost':
        matches_query = matches_query.filter(prediction_correct=False)

    # Apply django-filter for confidence and uncertainty
    match_filter = MatchFilter(request.GET, queryset=matches_query)
    matches_query = match_filter.qs

    matches_query = matches_query.order_by('-match_date', '-confidence_score')

    # Pagination
    paginator = Paginator(matches_query, 10)  # 10 matches per page
    try:
        matches = paginator.page(page)
    except PageNotAnInteger:
        matches = paginator.page(1)
    except EmptyPage:
        matches = paginator.page(paginator.num_pages)

    # Calculate statistics (on the filtered query, not just the page)
    total_matches = matches_query.count()
    completed_matches = matches_query.filter(result_fetched=True, match_status='FT')
    total_completed = completed_matches.count()

    if total_completed > 0:
        correct_predictions = completed_matches.filter(prediction_correct=True).count()
        incorrect_predictions = completed_matches.filter(prediction_correct=False).count()
        accuracy = (correct_predictions / total_completed * 100)
    else:
        correct_predictions = 0
        incorrect_predictions = 0
        accuracy = 0

    upcoming_matches = matches_query.filter(result_fetched=False).count()

    # Get latest update time
    latest_update = None
    if matches_query.exists():
        latest_update = matches_query.latest('updated_at').updated_at

    # Removed: Dynamic fetching of uncertainty categories, now using fixed choices from filters.py
    # uncertainty_categories = Match.objects.exclude(uncertainty_category__isnull=True).exclude(uncertainty_category__exact='').values_list('uncertainty_category', flat=True).distinct()

    context = {
        'acca_matches': matches,
        'total_matches': total_matches,
        'upcoming_matches': upcoming_matches,
        'completed_matches': total_completed,
        'correct_predictions': correct_predictions,
        'incorrect_predictions': incorrect_predictions,
        'accuracy': accuracy,
        'latest_update': latest_update,
        'current_date': timezone.now(),
        'date_filter': date_filter,
        'status_filter': status_filter,
        'filter': match_filter,
        'uncertainty_categories': [choice[0] for choice in MatchFilter.UNCERTAINTY_CHOICES],
    }

    return render(request, 'predictions/dashboard.html', context)


