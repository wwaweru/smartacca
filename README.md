# SmartAcca - AI-Driven Football Accumulator App

An intelligent Django application that uses Google Gemini AI and API-Football to generate verified daily football accumulator bets by analyzing tipster predictions and team statistics.

## Features

- **Multi-Source Tipster Scraping**: Aggregates predictions from multiple tipster websites
- **AI-Powered Analysis**: Uses Google Gemini AI to analyze match data and assess risk levels
- **API-Football Integration**: Fetches real-time team statistics, form, and injury data
- **Automated Daily Accumulator**: Generates a curated 5-match accumulator based on confidence scores
- **Beautiful Dashboard**: Bootstrap-based responsive UI displaying AI-verified picks
- **Django Admin Integration**: Full admin interface for managing matches and predictions

## Technology Stack

- **Backend**: Django 6.0
- **AI**: Google Gemini Flash Lite
- **Data API**: API-Football
- **Scraping**: BeautifulSoup4 & Playwright
- **Frontend**: Bootstrap 5, Font Awesome
- **Database**: SQLite (default, easily switchable)

## Project Structure

```
acca/
├── smart_acca_project/          # Main Django project
│   ├── settings.py              # Project settings with env variables
│   └── urls.py                  # Main URL configuration
├── predictions/                 # Main application
│   ├── models.py                # Match model
│   ├── views.py                 # Dashboard views
│   ├── admin.py                 # Admin configuration
│   ├── services/                # Business logic
│   │   ├── scraper.py           # Tipster scraping service
│   │   └── intelligence.py      # AI & API-Football integration
│   ├── management/commands/     # Custom Django commands
│   │   └── generate_daily_acca.py
│   └── templates/predictions/   # HTML templates
├── .env                         # Environment variables (API keys)
├── manage.py                    # Django management script
└── README.md                    # This file
```

## Installation & Setup

### 1. Prerequisites

- Python 3.8+
- pip

### 2. Environment Setup

The virtual environment and dependencies are already installed. If you need to reinstall:

```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install django requests google-generativeai beautifulsoup4 playwright django-environ celery redis
```

### 3. Environment Variables

The `.env` file is already configured with:

```env
API_FOOTBALL_KEY=919e868555256d201e65bc52d6caca22
GEMINI_API_KEY=AIzaSyCpSBDRplsrORwf43RBOUfv90v-0NqYI0s
DEBUG=True
SECRET_KEY=django-insecure-smartacca-development-key-change-in-production
ALLOWED_HOSTS=localhost,127.0.0.1
```

### 4. Database Setup

Migrations have already been run. To reset the database:

```bash
./venv/bin/python manage.py migrate
```

### 5. Create Admin User

```bash
./venv/bin/python manage.py createsuperuser
```

Follow the prompts to create your admin account.

## Usage

### Running the Development Server

```bash
./venv/bin/python manage.py runserver
```

Visit:
- **Dashboard**: http://127.0.0.1:8000/
- **Admin Panel**: http://127.0.0.1:8000/admin/

### Generating Daily Accumulator

Run the management command to scrape tipster predictions, analyze with AI, and create the daily accumulator:

```bash
./venv/bin/python manage.py generate_daily_acca
```

Options:
- `--reset`: Clear previous accumulator selections before generating new ones

```bash
./venv/bin/python manage.py generate_daily_acca --reset
```

### How It Works

1. **Scraping Phase**: The scraper collects today's match predictions from multiple tipster sources
2. **Data Enrichment**: For each match, the system fetches team statistics from API-Football
3. **AI Analysis**: Google Gemini analyzes the combination of tipster picks and team stats
4. **Risk Assessment**: Each match receives a confidence score (0-10) and risk level (Low/Medium/High)
5. **Selection**: The top 5 low-risk matches with highest confidence scores are selected
6. **Display**: The accumulator is displayed on the dashboard with full AI rationale

## API Services

### Scraper Service (`predictions/services/scraper.py`)

- **Purpose**: Scrapes tipster predictions from multiple websites
- **Sources**: Tipstrr, Squawka, PredictZ (currently using mock data)
- **Output**: List of matches with tipster picks

**Note**: The scraper currently returns mock data. For production, implement actual HTML parsing logic for each tipster website.

### Intelligence Service (`predictions/services/intelligence.py`)

Two main components:

1. **APIFootballClient**:
   - Fetches team statistics, form, injuries
   - Currently using mock data structure
   - Replace with actual API calls in production

2. **GeminiAnalyzer**:
   - Uses Google Gemini AI to analyze matches
   - Processes tipster picks and team stats
   - Returns confidence score and risk assessment

## Admin Interface

Access the Django admin at `/admin/` to:

- View all matches in the database
- Filter by accumulator status, league, date
- Manually mark/unmark matches for the daily accumulator
- View AI analysis and confidence scores
- Search matches by team names

## Customization

### Adding New Tipster Sources

Edit `predictions/services/scraper.py`:

```python
self.sources = {
    'tipstrr': 'https://www.tipstrr.com/todays-tips',
    'your_source': 'https://www.yourtipster.com/predictions'
}
```

Then implement parsing logic in `_parse_html()`.

### Modifying AI Prompt

Edit `predictions/services/intelligence.py` in the `_build_analysis_prompt()` method to customize how Gemini analyzes matches.

### Changing Accumulator Size

Edit `predictions/management/commands/generate_daily_acca.py`:

```python
# Change from 5 to your desired number
top_5_matches = sorted_matches[:5]  # Change the number here
```

## Production Considerations

### Security
- Change `SECRET_KEY` in `.env`
- Set `DEBUG=False`
- Use environment-specific settings
- Implement rate limiting for scraping

### API Integration
- Replace mock data with actual API-Football calls
- Implement proper HTML parsing for tipster websites
- Add error handling and retry logic
- Consider caching API responses

### Scaling
- Use PostgreSQL instead of SQLite
- Implement Celery for background task processing
- Add Redis for caching
- Set up proper logging

### Legal & Compliance
- Ensure web scraping complies with website terms of service
- Add rate limiting to respect API quotas
- Include proper disclaimers about gambling
- Consider user authentication for personalized features

## Troubleshooting

### Gemini API Errors
- Verify your `GEMINI_API_KEY` is valid
- Check API quota limits
- Review prompt formatting in `intelligence.py`

### Scraping Issues
- Check internet connectivity
- Verify target websites are accessible
- Update HTML parsing logic if website structure changes

### Migration Issues
```bash
./venv/bin/python manage.py makemigrations
./venv/bin/python manage.py migrate
```

## License

This is a demonstration project. Ensure compliance with:
- API-Football terms of service
- Google Gemini AI terms of service
- Tipster website scraping policies
- Local gambling and betting regulations

## Disclaimer

SmartAcca is for educational and entertainment purposes only. Always gamble responsibly and never bet more than you can afford to lose. The AI predictions are not guaranteed to be accurate.

## Support

For issues and questions:
1. Check the Django logs
2. Verify API keys in `.env`
3. Review service implementation in `predictions/services/`

---

**Built with Django 6.0, Google Gemini AI, and API-Football**
# smartacca
