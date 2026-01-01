# SmartAcca Quick Start Guide

## Getting Started in 3 Steps

### 1. Start the Development Server

```bash
./venv/bin/python manage.py runserver
```

### 2. Access the Application

- **Dashboard**: http://127.0.0.1:8000/
- **Admin Panel**: http://127.0.0.1:8000/admin/
  - Username: `admin`
  - Password: `admin123`

### 3. Generate Your First Accumulator

In a new terminal:

```bash
./venv/bin/python manage.py generate_daily_acca --reset
```

## What You'll See

The command will:
1. Scrape tipster predictions (currently using mock data)
2. Analyze each match with AI
3. Select the top 5 matches based on confidence scores
4. Display them on the dashboard

## Next Steps

### For Production Use

1. **Update API Keys** in `.env`:
   - Get a valid Google Gemini API key from https://ai.google.dev/
   - Get an API-Football key from https://www.api-football.com/

2. **Implement Real Scraping**:
   - Edit `predictions/services/scraper.py`
   - Add actual HTML parsing for tipster websites
   - Respect robots.txt and rate limits

3. **Enable Real API Calls**:
   - Update `predictions/services/intelligence.py`
   - Implement actual API-Football endpoint calls
   - Add proper error handling

### Project Structure

```
Key Files:
├── predictions/models.py              # Match data model
├── predictions/views.py               # Dashboard logic
├── predictions/services/
│   ├── scraper.py                     # Tipster scraping
│   └── intelligence.py                # AI analysis
├── predictions/management/commands/
│   └── generate_daily_acca.py         # Main command
└── predictions/templates/predictions/
    ├── base.html                      # Base template
    └── dashboard.html                 # Main dashboard

Configuration:
├── .env                               # API keys & settings
├── smart_acca_project/settings.py     # Django settings
└── requirements.txt                   # Python dependencies
```

### Common Commands

```bash
# Create admin user
./venv/bin/python manage.py createsuperuser

# Run migrations
./venv/bin/python manage.py migrate

# Generate accumulator (reset previous)
./venv/bin/python manage.py generate_daily_acca --reset

# Start server
./venv/bin/python manage.py runserver

# Access Django shell
./venv/bin/python manage.py shell
```

### Troubleshooting

**No matches showing on dashboard?**
- Run: `./venv/bin/python manage.py generate_daily_acca`

**Gemini API errors?**
- Verify your API key in `.env`
- Check quotas at https://ai.google.dev/

**Can't access admin?**
- Username: `admin`
- Password: `admin123`
- URL: http://127.0.0.1:8000/admin/

### Development vs Production

**Current State (Development)**:
- Uses mock data for tipster scraping
- SQLite database
- Debug mode enabled
- Placeholder API responses

**Production Ready Requires**:
- Real web scraping implementation
- Valid API keys (Gemini + API-Football)
- PostgreSQL database
- Debug mode disabled
- Proper security settings
- Rate limiting
- Error monitoring

### Features to Explore

1. **Admin Interface**:
   - View all matches
   - Manually select accumulator matches
   - Filter by date, league, confidence score

2. **Dashboard**:
   - Beautiful Bootstrap UI
   - AI rationale for each pick
   - Tipster consensus view
   - Confidence scoring

3. **Management Command**:
   - Automated daily generation
   - Risk assessment
   - Smart selection algorithm

## Support

Refer to `README.md` for detailed documentation.

---

**Happy Betting! Remember to gamble responsibly.**
