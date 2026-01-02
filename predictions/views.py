from django.shortcuts import render
from django.utils import timezone
from django.db.models import Q, Count, Case, When, IntegerField
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from datetime import timedelta
from .models import Match


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
    }

    return render(request, 'predictions/dashboard.html', context)


def post_mortem(request):
    """
    Post-mortem analysis view showing prediction accuracy and AI insights.
    """
    # Filter parameters
    days_back = int(request.GET.get('days', 7))
    outcome_filter = request.GET.get('outcome', 'all')  # all, correct, incorrect
    page = request.GET.get('page', 1)

    # Calculate date range
    cutoff_date = timezone.now() - timedelta(days=days_back)

    # Base query: completed matches with results
    base_query = Match.objects.filter(
        match_date__gte=cutoff_date,
        result_fetched=True,
        match_status='FT',
        is_in_daily_acca=True
    )

    # Apply outcome filter
    if outcome_filter == 'correct':
        matches_query = base_query.filter(prediction_correct=True)
    elif outcome_filter == 'incorrect':
        matches_query = base_query.filter(prediction_correct=False)
    else:
        matches_query = base_query

    matches_query = matches_query.order_by('-match_date')

    # Pagination
    paginator = Paginator(matches_query, 10)  # 10 matches per page
    try:
        matches = paginator.page(page)
    except PageNotAnInteger:
        matches = paginator.page(1)
    except EmptyPage:
        matches = paginator.page(paginator.num_pages)

    # Calculate statistics
    total_predictions = base_query.count()
    correct_predictions = base_query.filter(prediction_correct=True).count()
    incorrect_predictions = base_query.filter(prediction_correct=False).count()
    accuracy = (correct_predictions / total_predictions * 100) if total_predictions > 0 else 0

    # Accuracy by confidence level
    high_conf_matches = base_query.filter(confidence_score__gte=8.0)
    high_conf_correct = high_conf_matches.filter(prediction_correct=True).count()
    high_conf_total = high_conf_matches.count()
    high_conf_accuracy = (high_conf_correct / high_conf_total * 100) if high_conf_total > 0 else 0

    medium_conf_matches = base_query.filter(confidence_score__gte=6.0, confidence_score__lt=8.0)
    medium_conf_correct = medium_conf_matches.filter(prediction_correct=True).count()
    medium_conf_total = medium_conf_matches.count()
    medium_conf_accuracy = (medium_conf_correct / medium_conf_total * 100) if medium_conf_total > 0 else 0

    # Group matches by date for daily view (only for the current page)
    matches_by_date = {}
    for match in matches:
        date_key = match.match_date.date()
        if date_key not in matches_by_date:
            matches_by_date[date_key] = []
        matches_by_date[date_key].append(match)

    context = {
        'matches': matches,
        'matches_by_date': matches_by_date,
        'total_predictions': total_predictions,
        'correct_predictions': correct_predictions,
        'incorrect_predictions': incorrect_predictions,
        'accuracy': accuracy,
        'high_conf_accuracy': high_conf_accuracy,
        'high_conf_total': high_conf_total,
        'medium_conf_accuracy': medium_conf_accuracy,
        'medium_conf_total': medium_conf_total,
        'days_back': days_back,
        'outcome_filter': outcome_filter,
    }

    return render(request, 'predictions/post_mortem.html', context)
