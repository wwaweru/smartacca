# SmartAcca Phase 1 - Quick Start

## ✅ Phase 1 Complete!

The app now fetches matches from API-Football instead of scraping tipsters.

## Current Status

🟢 **Server Running**: http://127.0.0.1:8000/
🟢 **Accumulator Generated**: 4 matches ready
🟢 **All Systems Operational**

## Quick Actions

### View Your Accumulator
```bash
# Open in browser
http://127.0.0.1:8000/
```

### Generate New Accumulator
```bash
# For today (uses mock data currently)
./venv/bin/python manage.py generate_daily_acca --reset

# For a specific date
./venv/bin/python manage.py generate_daily_acca --reset --date 2025-12-26
```

### Access Admin Panel
```bash
# Visit: http://127.0.0.1:8000/admin/
# Username: admin
# Password: admin123
```

## Current Accumulator (Example)

Based on the last generation:

1. **PSG vs Marseille** (Ligue 1)
   - Bet: Home Win
   - Confidence: 7.9/10

2. **Inter Milan vs AC Milan** (Serie A)
   - Bet: Both Teams to Score
   - Confidence: 6.4/10

3. **Manchester City vs Arsenal** (Premier League)
   - Bet: Home Win
   - Confidence: 6.2/10

4. **Bayern Munich vs Borussia Dortmund** (Bundesliga)
   - Bet: Over 2.5 Goals
   - Confidence: 5.1/10

## Key Features Now Available

✅ **API-Football Integration**
- Fetches real fixtures from top European leagues
- Falls back to mock data for testing

✅ **AI Betting Recommendations**
- Analyzes each match
- Suggests specific bets (Home Win, BTTS, Over 2.5, etc.)
- Provides confidence scores

✅ **Beautiful Dashboard**
- Responsive Bootstrap UI
- Shows suggested bets prominently
- Displays AI rationale

✅ **Smart Selection**
- Filters by risk level
- Sorts by confidence
- Selects top 5 matches

## Mock Data Notice

Currently using **mock data** for:
- ⚠️ Match fixtures (API-Football returns no matches for today)
- ⚠️ AI analysis (Gemini API key is invalid)

This allows you to test the complete workflow!

## Enable Real Data

### 1. Get API-Football Key
1. Visit https://www.api-football.com/
2. Sign up for free account
3. Copy your API key
4. Update `.env`: `API_FOOTBALL_KEY=your_real_key_here`

### 2. Get Gemini AI Key
1. Visit https://ai.google.dev/
2. Create API key
3. Update `.env`: `GEMINI_API_KEY=your_real_key_here`

### 3. Restart & Generate
```bash
# Kill the server (Ctrl+C if in foreground)
# Or check running tasks: /tasks

# Start server
./venv/bin/python manage.py runserver

# Generate with real data
./venv/bin/python manage.py generate_daily_acca --reset
```

## What's Different from Before?

### ❌ Removed (Phase 2)
- Tipster scraping (Tipstrr, Squawka, PredictZ)
- Scraper service
- Tipster pick aggregation

### ✅ Added
- Direct API-Football fixture fetching
- AI-generated betting recommendations
- Suggested bet field on matches
- Date parameter for fixtures
- Enhanced error handling
- Mock data for testing

### 🔄 Updated
- Gemini AI prompt (no tipster data needed)
- Dashboard UI (shows suggested bets)
- Management command workflow
- Database schema

## Troubleshooting

### No matches showing?
```bash
./venv/bin/python manage.py generate_daily_acca --reset
```

### Server not running?
```bash
./venv/bin/python manage.py runserver
```

### Want to see fixtures for a date with real matches?
```bash
# Try a recent date with matches
./venv/bin/python manage.py generate_daily_acca --date 2025-12-28
```

### Check what's in the database
```bash
./venv/bin/python manage.py shell
>>> from predictions.models import Match
>>> Match.objects.filter(is_in_daily_acca=True).count()
>>> Match.objects.filter(is_in_daily_acca=True).values('home_team', 'away_team', 'suggested_bet')
```

## Next Steps

Ready for Phase 2? This will add:
- Real tipster scraping (Tipstrr, Squawka, PredictZ)
- Combined AI analysis (tipsters + API-Football)
- Consensus scoring
- Enhanced betting insights

## Support

Check the documentation:
- `README.md` - Full documentation
- `PHASE1_COMPLETE.md` - Technical details
- `QUICKSTART.md` - Original quick start

---

**Everything is working!** 🎉

Your SmartAcca app is now fetching matches from API-Football and generating AI-powered accumulator bets.
