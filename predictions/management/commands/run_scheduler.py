import schedule
import time
import logging
from datetime import datetime
from django.core.management.base import BaseCommand
from django.core.management import call_command
from django.utils import timezone
from predictions.models import Match

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Runs the scheduling daemon for SmartAcca'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Starting SmartAcca Scheduler...'))
        
        # Schedule the daily morning task
        schedule.every().day.at("07:00").do(self.job_fetch_matches)
        
        # If the script restarts during the day, we might need to kickstart the result fetching
        # if there are unfinished matches for today.
        if self.should_run_result_fetching():
            self.start_result_fetching()

        while True:
            schedule.run_pending()
            time.sleep(60)

    def job_fetch_matches(self):
        """
        Runs every morning at 7:00 AM.
        1. Generates the daily accumulator.
        2. Starts the hourly result fetching job.
        """
        self.stdout.write(self.style.SUCCESS(f"[{datetime.now()}] 🌅 Starting daily match generation task"))
        try:
            call_command('generate_daily_acca', reset=True)
            self.stdout.write(self.style.SUCCESS(f"[{datetime.now()}] ✅ Daily matches generated successfully"))
            
            # Start the hourly result fetching cycle
            self.start_result_fetching()
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"[{datetime.now()}] ❌ Error generating matches: {str(e)}"))

    def start_result_fetching(self):
        """
        Starts the hourly job to fetch results.
        Clears any existing result jobs to avoid duplicates.
        """
        # Clear existing jobs with this tag to prevent duplicates
        schedule.clear('results')
        
        # Schedule the job to run every hour
        schedule.every().hour.do(self.job_fetch_results).tag('results')
        self.stdout.write(self.style.SUCCESS(f"[{datetime.now()}] 🕒 Result fetching scheduled (Every hour)"))

    def job_fetch_results(self):
        """
        Runs every hour.
        1. Fetches latest results.
        2. Checks if all matches for the day are finished.
        3. If all finished, stops this scheduled job.
        """
        self.stdout.write(f"[{datetime.now()}] 🔍 Fetching latest results...")
        try:
            call_command('fetch_results')
            
            # Check if we should continue running
            if not self.should_run_result_fetching():
                self.stdout.write(self.style.SUCCESS(f"[{datetime.now()}] 🏁 All matches for today have finished. Stopping result fetcher."))
                return schedule.CancelJob
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"[{datetime.now()}] ❌ Error fetching results: {str(e)}"))

    def should_run_result_fetching(self):
        """
        Checks if there are any matches today that are not yet finished.
        Returns True if we should be fetching results.
        """
        today = timezone.now().date()
        
        # Get today's acca matches
        todays_matches = Match.objects.filter(
            match_date__date=today,
            is_in_daily_acca=True
        )
        
        if not todays_matches.exists():
            return False
            
        # Check if any match is NOT finished (i.e., not FT, AET, PEN, PST, CANC, ABD)
        # We look for matches that are not 'result_fetched' OR where status is still live/upcoming
        finished_statuses = ['FT', 'AET', 'PEN', 'PST', 'CANC', 'ABD', 'WO']
        
        unfinished_matches = todays_matches.exclude(match_status__in=finished_statuses)
        
        count = unfinished_matches.count()
        if count > 0:
            self.stdout.write(f"[{datetime.now()}] ℹ️ {count} matches still active/upcoming today.")
            return True
            
        return False
