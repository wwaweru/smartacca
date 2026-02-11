#!/bin/bash

# Simple cron job script for SmartAcca result fetching
# Add to crontab with: */30 * * * * /home/ubuntu/smartacca/run_scheduler.sh

cd /home/ubuntu/smartacca

# Activate virtual environment
source venv/bin/activate

echo "[$(date)] Starting result fetch..." >> logs/scheduler.log

# Run result fetching with prioritization
python manage.py fetch_results --days-back=1 >> logs/scheduler.log 2>&1

echo "[$(date)] Result fetch completed" >> logs/scheduler.log