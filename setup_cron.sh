#!/bin/bash

echo "Setting up SmartAcca automated scheduling..."

# Create proper cron jobs with full paths
(crontab -l 2>/dev/null || true; echo "# SmartAcca automated result fetching every 30 minutes"; echo "*/30 * * * * /home/ubuntu/smartacca/run_scheduler.sh") | crontab -

# Add daily ACCA generation (8:00 AM EAT)
(crontab -l 2>/dev/null; echo "# SmartAcca daily ACCA generation at 8:00 AM EAT"; echo "0 8 * * * cd /home/ubuntu/smartacca && source venv/bin/activate && python manage.py generate_daily_acca >> logs/daily_acca.log 2>&1") | crontab -

echo "✅ Cron jobs installed:"
crontab -l

echo ""
echo "📋 Manual commands for testing:"
echo "  • Generate daily ACCA: python manage.py generate_daily_acca"
echo "  • Fetch results: python manage.py fetch_results"
echo "  • View logs: tail -f logs/scheduler.log"