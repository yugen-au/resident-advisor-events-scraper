# Resident Advisor API & Event Scraper

A comprehensive Flask API for interacting with Resident Advisor (RA.co) to fetch events, search artists, and discover electronic music content. This project provides a full REST API with advanced filtering capabilities and batch processing across three API versions.

## Features

- **Event searching** with sophisticated filtering (genre, artist, venue, date ranges)
- **Area name support** - use "sydney" instead of area codes
- **Individual lookups** for artists, labels, and events
- **Batch operations** for production scalability
- **Advanced filtering** with 15+ operators (contains_all, contains_none, gt, lt, between, etc.)
- **GraphQL integration** with hybrid client-side processing
- **SQLite caching** for area mappings

## API Versions

| Version | Endpoints | Key Features |
|---------|-----------|--------------|
| **V1** | 8 endpoints | Simple parameter interface, individual lookups |
| **V2** | 3 endpoints | Native GraphQL, multi-genre support |
| **V3** | 7 endpoints | Advanced filtering, logical operators, batch processing |

## Quick Start

### Prerequisites
- Python 3.11 or higher
- Flask, requests packages

### Installation
```bash
# Clone and install dependencies
git clone <repository-url>
cd resident-advisor-events-scraper
pip install flask requests

# Start the API server
python app.py
```

The API will be available at `http://localhost:8080`

## API Endpoints

### V1 - Basic API
```bash
# Events with filtering
GET /events?area=sydney&start_date=2025-08-10&end_date=2025-08-17&genre=techno

# List all areas
GET /areas

# Individual lookups
GET /artist/charlottedewitte  # By slug
GET /label/67890           # By ID
GET /venue/168             # By ID
GET /event/1447038         # By ID

# Search
GET /search?q=charlotte&type=artist
```

### V2 - GraphQL Multi-Genre API
```bash
# Multi-genre events
GET /v2/events?area=melbourne&start_date=2025-08-10&end_date=2025-08-17&genre=techno,house

# Enhanced search with type filtering
GET /v2/search?q=charlotte&filter=type:any:artist,event

# Artist lookup (supports both slug and ID)
GET /v2/artist/charlottedewitte
```

### V3 - Advanced Filtering API
```bash
# Complex filtering with logical operators
GET /v3/events?area=sydney&start_date=2025-08-10&end_date=2025-08-17&filter=genre:contains_any:techno,house AND artists:has:charlotte

# Advanced search
GET /v3/search?q=charlotte&filter=type:eq:artist AND country:has:belgium

# Batch operations
POST /v3/artists/batch
POST /v3/labels/batch
POST /v3/venues/batch
POST /v3/events/batch
POST /v3/search/batch
```

## V3 Filter Operators

| Operator | Description | Example |
|----------|-------------|---------|
| `eq` | Exact match | `genre:eq:techno` |
| `contains_any` | Match any value (OR) | `genre:contains_any:techno,house` |
| `contains_all` | Match all values (AND) | `genre:contains_all:techno,industrial` |
| `has` | Substring match | `artists:has:charlotte` |
| `gt`, `lt` | Numeric comparison | `interested:gt:100` |
| `between` | Range | `price:between:10,30` |

### Logical Operators
Combine expressions with `AND`, `OR`, `NOT`:
```bash
genre:contains_any:techno,house AND artists:has:charlotte
```

## Batch Operations

### Limits
- **Artists**: 50 per batch
- **Labels**: 50 per batch
- **Venues**: 50 per batch
- **Events**: 20 queries per batch
- **Search**: 30 queries per batch

### Example Batch Request
```bash
curl -X POST "http://localhost:8080/v3/artists/batch" \
  -H "Content-Type: application/json" \
  -d '{
    "artist_slugs": ["charlottedewitte", "amelielens", "benklock"],
    "include": ["stats", "booking", "labels"]
  }'

# Venue batch example
curl -X POST "http://localhost:8080/v3/venues/batch" \
  -H "Content-Type: application/json" \
  -d '{
    "venue_ids": ["168", "420", "123"]
  }'
```

## Area Support

All endpoints support area names instead of numeric codes:

```bash
# Use area names
/events?area=sydney&start_date=2025-08-10&end_date=2025-08-17

# Available areas include
GET /areas
```

**Confirmed areas**: Sydney (1), Melbourne (2), Perth (3), Canberra (4), Adelaide (5), Hobart (6)

## Testing

```bash
# Test basic functionality
curl "http://localhost:8080/areas"
curl "http://localhost:8080/events?area=sydney&start_date=2025-08-10&end_date=2025-08-17&genre=techno"

# Test V2 multi-genre
curl "http://localhost:8080/v2/events?area=melbourne&start_date=2025-08-10&end_date=2025-08-17&genre=techno,house"

# Test V3 advanced filtering
curl "http://localhost:8080/v3/events?area=sydney&start_date=2025-08-10&end_date=2025-08-17&filter=genre:contains_any:techno,house"
```

## File Structure

### Core Files
- `app.py` - Main Flask API with all endpoints
- `event_fetcher.py` - V1 basic event fetching
- `enhanced_event_fetcher_v2.py` - V2 GraphQL support
- `advanced_event_fetcher.py` - V3 ultimate filtering
- `area_cache.py` - Area name caching system
- `requirements.txt` - Python dependencies
- `Dockerfile` - Container configuration

## Legal Considerations

This tool is for educational and personal use only. Please respect Resident Advisor's terms of service and be mindful of rate limiting when making requests to their API.

## License

This project is provided as-is for educational purposes. Please ensure compliance with Resident Advisor's terms of service when using this tool.