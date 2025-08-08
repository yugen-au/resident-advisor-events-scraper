# Resident Advisor API & Event Scraper

A comprehensive Flask API and Python tool for interacting with Resident Advisor (RA.co) to fetch events, search artists, explore labels, and discover electronic music content. This project provides both a command-line interface and a full REST API for accessing RA's data, including **advanced filtering** and **batch processing** capabilities.

## Features

### 🎉 Event Scraping & Advanced Filtering
- Fetch events by area/city and date range
- **Genre filtering** (techno, house, drum & bass, etc.)
- **Event type filtering** (club events, festivals, etc.)
- **Advanced sorting** (by date, popularity score, or title)
- **Bumped events support** (promoted/sponsored events)
- Export to CSV or JSON format
- **Enhanced event data** (interested count, ticket info, promoters)

### 🚀 Batch Processing (NEW!)
- **Multi-artist search** - Query multiple artists simultaneously
- **Multi-label search** - Search several record labels at once
- **Multi-area events** - Get events from multiple cities/areas
- **Mixed batch search** - Combine artists, labels, and general queries
- **Rate limiting protection** - Built-in delays to respect API limits

### 🎧 Artist Discovery
- Search artists by name
- Get detailed artist profiles and biographies
- Find related artists for music discovery
- View artist performance statistics and career history
- Explore artist's associated record labels

### 🏷️ Label Exploration
- Search record labels
- Get comprehensive label information
- Discover artists signed to specific labels
- Browse music reviews for label releases

### 🔍 Advanced Search
- Global search across artists, labels, clubs, and events
- Type-filtered searches (artist-only, label-only, etc.)
- Smart search with relevance scoring

### 📝 Music Reviews
- Browse popular music reviews
- Filter reviews by time period
- Get reviews for specific labels

### 🌍 Geographic Data
- Area/city discovery with country information
- Support for major electronic music cities worldwide

## API Endpoints

### Core Endpoints
- `GET /` - API health check and endpoint documentation
- `GET /events` - Fetch events with advanced filtering support
- `GET /areas` - List available RA area codes
- `GET /filters` - Get available genres and event types for filtering
- `GET /search` - Global search with optional type filtering

### Batch Endpoints (NEW!)
- `POST /artists/batch` - Search multiple artists simultaneously
- `POST /labels/batch` - Search multiple labels simultaneously  
- `POST /events/batch` - Get events from multiple areas at once
- `POST /search/batch` - Mixed batch search (artists + labels + general)

### Artist Endpoints
- `GET /artist/search` - Search for artists
- `GET /artist/{slug}` - Get artist profile and biography
- `GET /artist/{slug}/stats` - Get artist performance statistics
- `GET /artist/{slug}/related` - Find related artists
- `GET /artist/{slug}/labels` - Get artist's associated labels

### Label Endpoints
- `GET /label/search` - Search for record labels
- `GET /label/{id}` - Get label profile and information
- `GET /label/{id}/artists` - Get all artists on a label
- `GET /label/{id}/reviews` - Get music reviews for a label

### Review Endpoints
- `GET /reviews/popular` - Get popular music reviews

## Installation

### Prerequisites
- Python 3.11 or higher
- pip package manager

### Setup
1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd resident-advisor-events-scraper
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Usage

### Command-Line Interface
Use the command-line tool for advanced event scraping:

```bash
python event_fetcher.py <area_id> <start_date> <end_date> [options]
```

**Available Options:**
- `-o, --output` - Output file path (default: events.csv)
- `-g, --genre` - Filter by genre (e.g., 'techno', 'house')
- `-t, --event-type` - Filter by event type (e.g., 'club', 'festival')
- `-s, --sort` - Sort by: listingDate, score, or title (default: listingDate)
- `--no-bumps` - Exclude bumped/promoted events

**Examples:**
```bash
# Basic usage
python event_fetcher.py 1 2025-08-10 2025-08-17 -o sydney_events.csv

# Filter by genre
python event_fetcher.py 1 2025-08-10 2025-08-17 --genre techno -o techno_events.csv

# Sort by popularity and exclude bumped events
python event_fetcher.py 1 2025-08-10 2025-08-17 --sort score --no-bumps -o popular_events.csv

# Combined filtering
python event_fetcher.py 1 2025-08-10 2025-08-17 -g house -t club -s score -o house_club_events.csv
```

### Flask API Server
Start the API server:

```bash
python app.py
```

The server will start on `http://localhost:8080` (or the PORT environment variable).

### API Usage Examples

#### Get Events with Advanced Filtering
```bash
# Basic event query
curl "http://localhost:8080/events?area=1&start_date=2025-08-10&end_date=2025-08-17"

# Filter by genre
curl "http://localhost:8080/events?area=1&start_date=2025-08-10&end_date=2025-08-17&genre=techno"

# Filter by event type
curl "http://localhost:8080/events?area=1&start_date=2025-08-10&end_date=2025-08-17&event_type=club"

# Sort by popularity score
curl "http://localhost:8080/events?area=1&start_date=2025-08-10&end_date=2025-08-17&sort=score"

# Combined filtering
curl "http://localhost:8080/events?area=1&start_date=2025-08-10&end_date=2025-08-17&genre=house&event_type=club&sort=score"

# Exclude bumped/promoted events
curl "http://localhost:8080/events?area=1&start_date=2025-08-10&end_date=2025-08-17&include_bumps=false"

# Download as CSV with filters
curl "http://localhost:8080/events?area=1&start_date=2025-08-10&end_date=2025-08-17&genre=techno&format=csv" -o events.csv
```

#### Discover Available Filters
```bash
# Get available genres and event types for an area
curl "http://localhost:8080/filters?area=1"
```

#### Search Artists
```bash
# Search for an artist
curl "http://localhost:8080/artist/search?q=charlotte+de+witte"

# Get artist profile
curl "http://localhost:8080/artist/charlotte-de-witte"

# Get related artists
curl "http://localhost:8080/artist/charlotte-de-witte/related"
```

#### Explore Labels
```bash
# Search for labels
curl "http://localhost:8080/label/search?q=drumcode"

# Get label information
curl "http://localhost:8080/label/1234"

# Get label's artists
curl "http://localhost:8080/label/1234/artists"
```

#### Batch Processing Examples
```bash
# Multi-artist search
curl -X POST "http://localhost:8080/artists/batch" \
  -H "Content-Type: application/json" \
  -d '{"queries": ["charlotte de witte", "amelie lens", "adam beyer"]}'

# Multi-label search
curl -X POST "http://localhost:8080/labels/batch" \
  -H "Content-Type: application/json" \
  -d '{"queries": ["drumcode", "hotflush", "minus"]}'

# Multi-area events with filtering
curl -X POST "http://localhost:8080/events/batch" \
  -H "Content-Type: application/json" \
  -d '{
    "areas": [1, 2, 3],
    "start_date": "2025-08-10",
    "end_date": "2025-08-17",
    "genre": "techno",
    "sort": "score"
  }'

# Mixed batch search
curl -X POST "http://localhost:8080/search/batch" \
  -H "Content-Type: application/json" \
  -d '{
    "artists": ["charlotte de witte", "amelie lens"],
    "labels": ["drumcode", "hotflush"],
    "general": ["berlin techno", "minimal house"]
  }'
```

### Batch Processing Benefits

**🚀 Efficiency**: Query multiple targets in one API call instead of making separate requests

**⏱️ Rate Limiting**: Built-in delays (500ms-1s) between requests to respect RA's API limits

**📊 Comprehensive Results**: Get detailed statistics and summaries for all batch operations

**🛡️ Error Handling**: Individual query failures don't stop the entire batch operation

**💾 Reduced Overhead**: Lower network overhead and faster overall processing

**🎯 Batch Limits**: 
- Artists/Labels: Max 10 queries per batch
- Events: Max 5 areas per batch  
- Mixed search: Max 15 total queries per batch

### Cloud Deployment (Google Cloud Run)

This project is optimized for deployment on Google Cloud Run with proper environment variable handling.

#### Deploy to Cloud Run
```bash
# Build and deploy in one command
gcloud run deploy ra-events-api \
  --source . \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --memory 1Gi \
  --cpu 1 \
  --timeout 300

# Or build with Docker first
docker build -t gcr.io/YOUR-PROJECT-ID/ra-events-api .
docker push gcr.io/YOUR-PROJECT-ID/ra-events-api
gcloud run deploy ra-events-api \
  --image gcr.io/YOUR-PROJECT-ID/ra-events-api \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated
```

#### Test Your Cloud Run Deployment
```bash
# Use the Cloud Run test script
python test_cloud_run_api.py

# Or test manually with your Cloud Run URL
curl "https://your-service-url.a.run.app/"
```

## Docker Deployment

### Build and Run
```bash
# Build the Docker image
docker build -t ra-events-api .

# Run the container
docker run -p 8080:8080 ra-events-api
```

### Cloud Deployment
This project is configured for deployment on platforms like Google Cloud Run, with proper PORT environment variable handling.

## Testing

### Local Testing
```bash
# Start your Flask API locally
python app.py

# Run the local test script
python test_enhanced_api.py
```

### Cloud Run Testing
```bash
# Test your deployed Cloud Run service
python test_cloud_run_api.py

# The script will prompt for your Cloud Run URL
# Format: https://your-service-name-hash-region.a.run.app
```

### Manual Testing Examples
```bash
# Replace YOUR_CLOUD_RUN_URL with your actual deployment URL

# Test basic functionality
curl "https://YOUR_CLOUD_RUN_URL/"

# Test events with filtering
curl "https://YOUR_CLOUD_RUN_URL/events?area=1&start_date=2025-08-10&end_date=2025-08-17&genre=techno"

# Test batch artist search
curl -X POST "https://YOUR_CLOUD_RUN_URL/artists/batch" \
  -H "Content-Type: application/json" \
  -d '{"queries": ["charlotte de witte", "amelie lens"]}'
```

## Area Codes

The API supports electronic music cities worldwide. Use the `/areas` endpoint to discover available area codes. Currently confirmed area codes include:

**Australia:**
- Sydney (1)
- Melbourne (2) 
- Perth (3)
- Canberra (4)
- Adelaide (5)
- Hobart (6)

Additional area codes can be discovered using the included PowerShell discovery script.

## Data Output

### Event Data Fields (Enhanced)
- Event ID and title
- Date and time information
- Artist lineup
- Venue details
- Event URL
- **Interested count** (replaces attendance)
- **Ticket information** and availability
- **Promoter details**
- **Bumped/promoted event status**
- Ticketing information
- Event flyer images
- **Save/interest status**

### Artist Data Fields
- Artist profile and biography
- Social media links
- Career statistics
- Performance history
- Associated labels
- Related artists

### Label Data Fields
- Label information and history
- Artist roster
- Music reviews
- Social media presence
- Geographic location

## Rate Limiting & Best Practices

- The API includes built-in delays between requests
- Respects RA.co's servers with appropriate headers
- Implements error handling and retry logic
- Uses proper User-Agent strings

## Technical Architecture

### Core Components
- `app.py` - Flask API server with all endpoints, advanced filtering, and batch processing
- `event_fetcher.py` - Event scraping with advanced filtering support
- `test_cloud_run_api.py` - Comprehensive test script for Cloud Run deployments
- `ra_area_discovery_api.ps1` - PowerShell script for discovering area codes
- `requirements.txt` - Python dependencies
- `Dockerfile` - Container configuration for Cloud Run

### Technologies Used
- **Flask** - Web framework for API
- **Requests** - HTTP client for RA.co API calls
- **JSON** - Data serialization
- **CSV** - Event data export
- **Docker** - Containerization for Cloud Run
- **Concurrent Processing** - Batch request handling with rate limiting
- **Google Cloud Run** - Serverless deployment platform

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## Legal Considerations

This tool is for educational and personal use only. Please respect Resident Advisor's terms of service and be mindful of rate limiting when making requests to their API.

## License

This project is provided as-is for educational purposes. Please ensure compliance with Resident Advisor's terms of service when using this tool.
