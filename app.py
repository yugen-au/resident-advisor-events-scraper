from flask import Flask, request, jsonify, send_file
import os
import tempfile
import json
import requests
import asyncio
import concurrent.futures
import time
import logging
import sys
from datetime import datetime
from event_fetcher import EnhancedEventFetcher
from enhanced_event_fetcher_v2 import EnhancedEventFetcherV2, V2FilterExpression
from advanced_search import AdvancedSearch
from advanced_event_fetcher import EnhancedEventFetcher as AdvancedEventFetcher, AdvancedFilterExpression
from area_cache import initialize_area_cache, get_area_id, get_area_info

# Set up logging
logging.basicConfig(level=logging.DEBUG, 
                  format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                  handlers=[logging.StreamHandler(sys.stdout)])

app = Flask(__name__)
app.logger.setLevel(logging.DEBUG)

# Add request logging middleware
@app.before_request
def log_request_info():
    app.logger.debug('Request: %s %s', request.method, request.path)
    app.logger.debug('Headers: %s', request.headers)
    app.logger.debug('Args: %s', request.args)
    app.logger.debug('Data: %s', request.get_data())

@app.after_request
def log_response_info(response):
    app.logger.debug('Response: %s', response.status)
    return response

# This function is now imported from area_cache.py
# def get_area_info(area_id):
#    """Get area name and country info using RA's GraphQL API"""
#    ...

# Note: We're now using the area_cache.get_area_info() function instead
# which includes caching and better error handling

def get_all_areas():
    """Get list of all available areas using RA's GraphQL API"""
    try:
        payload = {
            "operationName": "GET_AREAS",
            "variables": {},
            "query": """query GET_AREAS {
                areas {
                    id name urlName
                    country { name urlCode }
                }
            }"""
        }
        
        response = requests.post('https://ra.co/graphql', headers={
            'Content-Type': 'application/json',
            'Referer': 'https://ra.co/events',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:106.0) Gecko/20100101 Firefox/106.0'
        }, json=payload, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if 'data' in data and data['data']['areas']:
                return data['data']['areas']
        return []
    except Exception as e:
        print(f"Error getting areas: {e}")
        return []

def get_artist_by_slug(artist_slug):
    """Get single artist by slug using RA's GraphQL API (more reliable than ID)"""
    try:
        payload = {
            "operationName": "GET_ARTIST_BY_SLUG",
            "variables": {"slug": str(artist_slug)},
            "query": """query GET_ARTIST_BY_SLUG($slug: String!) {
                artist(slug: $slug) {
                    id name followerCount firstName lastName aliases isFollowing
                    coverImage contentUrl facebook soundcloud instagram twitter
                    bandcamp discogs website urlSafeName pronouns
                    country { id name urlCode __typename }
                    residentCountry { id name urlCode __typename }
                    news(limit: 1) { id __typename }
                    reviews(limit: 1, type: ALLMUSIC) { id __typename }
                    image
                    biography {
                        id blurb content discography __typename
                    }
                    __typename
                }
            }"""
        }
        
        response = requests.post('https://ra.co/graphql', headers={
            'Content-Type': 'application/json',
            'Referer': 'https://ra.co/artists',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:106.0) Gecko/20100101 Firefox/106.0'
        }, json=payload, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if 'data' in data and data['data']['artist']:
                return data['data']['artist']
        return None
    except Exception as e:
        print(f"Error getting artist by slug {artist_slug}: {e}")
        return None

def get_artist_events(artist_id):
    """Get artist events using the events query"""
    try:
        payload = {
            "operationName": "GET_ARTIST_EVENTS_ARCHIVE",
            "variables": {"id": str(artist_id)},
            "query": """query GET_ARTIST_EVENTS_ARCHIVE($id: ID!) {
                artist(id: $id) {
                    id
                    events(limit: 10, type: PREVIOUS) {
                        id title interestedCount isSaved isInterested date
                        contentUrl queueItEnabled flyerFront newEventForm
                        images { id filename alt type __typename }
                        pick { id blurb __typename }
                        artists { id name __typename }
                        venue {
                            id name contentUrl live
                            area {
                                id name urlName
                                country { id name urlCode __typename }
                                __typename
                            }
                            __typename
                        }
                        __typename
                    }
                    __typename
                }
            }"""
        }
        
        response = requests.post('https://ra.co/graphql', headers={
            'Content-Type': 'application/json',
            'Referer': 'https://ra.co/artists',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:106.0) Gecko/20100101 Firefox/106.0'
        }, json=payload, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if 'data' in data and data['data']['artist']:
                return data['data']['artist'].get('events', [])
        return []
    except Exception as e:
        print(f"Error getting artist events {artist_id}: {e}")
        return []

def get_artist_stats(artist_id):
    """Get artist statistics using GET_ARTIST_STATS GraphQL query"""
    try:
        payload = {
            "operationName": "GET_ARTIST_STATS",
            "variables": {"id": str(artist_id)},
            "query": """query GET_ARTIST_STATS($id: ID!) {
                artist(id: $id) {
                    id
                    firstEvent {
                        id
                        date
                        __typename
                    }
                    venuesMostPlayed {
                        id
                        name
                        contentUrl
                        __typename
                    }
                    regionsMostPlayed {
                        id
                        name
                        urlName
                        country {
                            id
                            name
                            urlCode
                            __typename
                        }
                        __typename
                    }
                    __typename
                }
            }"""
        }
        
        response = requests.post('https://ra.co/graphql', headers={
            'Content-Type': 'application/json',
            'Referer': 'https://ra.co/artists',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:106.0) Gecko/20100101 Firefox/106.0'
        }, json=payload, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if 'data' in data and data['data']['artist']:
                return data['data']['artist']
        return None
    except Exception as e:
        print(f"Error getting artist stats {artist_id}: {e}")
        return None

def get_artist_about(artist_id):
    """Get artist booking details using GET_ARTIST_ABOUT GraphQL query"""
    try:
        payload = {
            "operationName": "GET_ARTIST_ABOUT",
            "variables": {"id": str(artist_id)},
            "query": """query GET_ARTIST_ABOUT($id: ID!) {
                artist(id: $id) {
                    id
                    bookingDetails
                    contentUrl
                    biography {
                        id
                        blurb
                        __typename
                    }
                    __typename
                }
            }"""
        }
        
        response = requests.post('https://ra.co/graphql', headers={
            'Content-Type': 'application/json',
            'Referer': 'https://ra.co/artists',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:106.0) Gecko/20100101 Firefox/106.0'
        }, json=payload, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if 'data' in data and data['data']['artist']:
                return data['data']['artist']
        return None
    except Exception as e:
        print(f"Error getting artist about {artist_id}: {e}")
        return None

def get_related_artists(artist_id):
    """Get related artists using GET_RELATED_ARTISTS GraphQL query"""
    try:
        payload = {
            "operationName": "GET_RELATED_ARTISTS",
            "variables": {"id": str(artist_id)},
            "query": """query GET_RELATED_ARTISTS($id: ID!) {
                artist(id: $id) {
                    id
                    relatedArtists {
                        id
                        name
                        contentUrl
                        isFollowing
                        image
                        followerCount
                        __typename
                    }
                    __typename
                }
            }"""
        }
        
        response = requests.post('https://ra.co/graphql', headers={
            'Content-Type': 'application/json',
            'Referer': 'https://ra.co/artists',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:106.0) Gecko/20100101 Firefox/106.0'
        }, json=payload, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if 'data' in data and data['data']['artist']:
                return data['data']['artist'].get('relatedArtists', [])
        return []
    except Exception as e:
        print(f"Error getting related artists {artist_id}: {e}")
        return []

def get_artist_labels(artist_id):
    """Get artist labels using GET_ARTIST_LABELS GraphQL query"""
    try:
        payload = {
            "operationName": "GET_ARTIST_LABELS",
            "variables": {"id": str(artist_id)},
            "query": """query GET_ARTIST_LABELS($id: ID!) {
                artist(id: $id) {
                    id
                    labels {
                        id
                        name
                        contentUrl
                        imageUrl
                        isFollowing
                        followerCount
                        __typename
                    }
                    __typename
                }
            }"""
        }
        
        response = requests.post('https://ra.co/graphql', headers={
            'Content-Type': 'application/json',
            'Referer': 'https://ra.co/artists',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:106.0) Gecko/20100101 Firefox/106.0'
        }, json=payload, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if 'data' in data and data['data']['artist']:
                return data['data']['artist'].get('labels', [])
        return []
    except Exception as e:
        print(f"Error getting artist labels {artist_id}: {e}")
        return []

def get_label_by_id(label_id):
    """Get single label by ID using RA's GraphQL API"""
    try:
        payload = {
            "operationName": "GET_LABEL",
            "variables": {"id": str(label_id)},
            "query": """query GET_LABEL($id: ID!) {
                label(id: $id) {
                    id name imageUrl contentUrl imageLarge blurb facebook
                    discogs soundcloud link twitter dateEstablished
                    followerCount isFollowing
                    area {
                        id name
                        country { id name urlCode __typename }
                        __typename
                    }
                    reviews(limit: 200, excludeIds: []) {
                        id date title blurb contentUrl imageUrl recommended __typename
                    }
                    artists(limit: 100) {
                        id name contentUrl image isFollowing followerCount __typename
                    }
                    __typename
                }
            }"""
        }
        
        response = requests.post('https://ra.co/graphql', headers={
            'Content-Type': 'application/json',
            'Referer': 'https://ra.co/labels',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:106.0) Gecko/20100101 Firefox/106.0'
        }, json=payload, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if 'data' in data and data['data']['label']:
                return data['data']['label']
        return None
    except Exception as e:
        print(f"Error getting label {label_id}: {e}")
        return None

def get_venue_by_id(venue_id):
    """Get single venue by ID using RA's GraphQL API"""
    try:
        payload = {
            "operationName": "GET_VENUE",
            "variables": {"id": str(venue_id)},
            "query": """query GET_VENUE($id: ID!) {
                venue(id: $id) {
                    id
                    name
                    logoUrl
                    photo
                    blurb
                    address
                    isFollowing
                    contentUrl
                    phone
                    website
                    followerCount
                    capacity
                    raSays
                    isClosed
                    topArtists {
                        name
                        contentUrl
                        __typename
                    }
                    eventCountThisYear
                    area {
                        id
                        name
                        urlName
                        country {
                            id
                            name
                            urlCode
                            isoCode
                            __typename
                        }
                        __typename
                    }
                    __typename
                }
            }"""
        }
        
        response = requests.post('https://ra.co/graphql', headers={
            'Content-Type': 'application/json',
            'Referer': 'https://ra.co/clubs',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:106.0) Gecko/20100101 Firefox/106.0'
        }, json=payload, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if 'data' in data and data['data']['venue']:
                return data['data']['venue']
        return None
    except Exception as e:
        print(f"Error getting venue {venue_id}: {e}")
        return None

def get_event_by_id(event_id):
    """Get single event by ID using RA's GraphQL API"""
    try:
        payload = {
            "operationName": "GET_EVENT_DETAIL",
            "variables": {
                "id": str(event_id),
                "isAuthenticated": False,
                "canAccessPresale": False,
                "enableNewBrunchTicketing": False
            },
            "query": """query GET_EVENT_DETAIL($id: ID!, $isAuthenticated: Boolean!, $canAccessPresale: Boolean!, $enableNewBrunchTicketing: Boolean! = false) {
                event(id: $id) {
                    id
                    title
                    flyerFront
                    flyerBack
                    content
                    minimumAge
                    cost
                    contentUrl
                    embargoDate
                    date
                    time
                    startTime
                    endTime
                    interestedCount
                    lineup
                    isInterested
                    isSaved
                    isTicketed
                    isFestival
                    dateUpdated
                    resaleActive
                    newEventForm
                    datePosted
                    hasSecretVenue
                    live
                    canSubscribeToTicketNotifications
                    images {
                        id
                        filename
                        alt
                        type
                        crop
                        __typename
                    }
                    venue {
                        id
                        name
                        address
                        contentUrl
                        live
                        area {
                            id
                            name
                            urlName
                            country {
                                id
                                name
                                urlCode
                                isoCode
                                __typename
                            }
                            __typename
                        }
                        location {
                            latitude
                            longitude
                            __typename
                        }
                        __typename
                    }
                    promoters {
                        id
                        name
                        contentUrl
                        live
                        hasTicketAccess
                        tracking(types: [PAGEVIEW]) {
                            id
                            code
                            event
                            __typename
                        }
                        __typename
                    }
                    artists {
                        id
                        name
                        contentUrl
                        urlSafeName
                        __typename
                    }
                    pick {
                        id
                        blurb
                        author {
                            id
                            name
                            imageUrl
                            username
                            contributor
                            __typename
                        }
                        __typename
                    }
                    promotionalLinks {
                        title
                        url
                        __typename
                    }
                    tracking(types: [PAGEVIEW]) {
                        id
                        code
                        event
                        __typename
                    }
                    admin {
                        id
                        username
                        __typename
                    }
                    tickets(queryType: AVAILABLE) {
                        id
                        title
                        validType
                        onSaleFrom
                        priceRetail
                        isAddOn
                        currency {
                            id
                            code
                            __typename
                        }
                        __typename
                    }
                    standardTickets: tickets(queryType: AVAILABLE, ticketTierType: TICKETS) {
                        id
                        validType
                        __typename
                    }
                    userOrders @include(if: $isAuthenticated) {
                        id
                        rAOrderNumber
                        __typename
                    }
                    playerLinks {
                        id
                        sourceId
                        audioService {
                            id
                            name
                            __typename
                        }
                        __typename
                    }
                    childEvents {
                        id
                        date
                        isTicketed
                        ...brunchChildEventFragment @include(if: $enableNewBrunchTicketing)
                        __typename
                    }
                    genres {
                        id
                        name
                        slug
                        __typename
                    }
                    setTimes {
                        id
                        lineup
                        status
                        __typename
                    }
                    area {
                        ianaTimeZone
                        __typename
                    }
                    presaleStatus
                    isSignedUpToPresale @include(if: $canAccessPresale)
                    ticketingSystem
                    __typename
                }
            }

            fragment brunchChildEventFragment on Event {
                canSubscribeToTicketNotifications
                promoters {
                    id
                    __typename
                }
                standardTickets: tickets(queryType: AVAILABLE, ticketTierType: TICKETS) {
                    id
                    validType
                    __typename
                }
                __typename
            }"""
        }
        
        response = requests.post('https://ra.co/graphql', headers={
            'Content-Type': 'application/json',
            'Referer': 'https://ra.co/events',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:106.0) Gecko/20100101 Firefox/106.0'
        }, json=payload, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if 'data' in data and data['data']['event']:
                return data['data']['event']
        return None
    except Exception as e:
        print(f"Error getting event {event_id}: {e}")
        return None

def search_ra(query, search_type="all"):
    """Enhanced search using RA's global search GraphQL API"""
    try:
        # Map search_type to indices for global search
        indices = []
        if search_type == "all":
            indices = ["AREA", "ARTIST", "CLUB", "LABEL", "PROMOTER", "EVENT"]
        elif search_type == "artist":
            indices = ["ARTIST"]
        elif search_type == "label":
            indices = ["LABEL"]
        elif search_type == "event":
            indices = ["EVENT"]
        else:
            # Default to all if invalid type
            indices = ["AREA", "ARTIST", "CLUB", "LABEL", "PROMOTER", "EVENT"]
        
        # Use the global search GraphQL query
        payload = {
            "operationName": "GET_GLOBAL_SEARCH_RESULTS",
            "variables": {
                "searchTerm": query,
                "indices": indices
            },
            "query": """query GET_GLOBAL_SEARCH_RESULTS($searchTerm: String!, $indices: [IndexType!]) {
                search(
                    searchTerm: $searchTerm
                    limit: 16
                    indices: $indices
                    includeNonLive: false
                ) {
                    searchType
                    id
                    value
                    areaName
                    countryId
                    countryName
                    countryCode
                    contentUrl
                    imageUrl
                    score
                    clubName
                    clubContentUrl
                    date
                    __typename
                }
            }"""
        }
        
        response = requests.post('https://ra.co/graphql', headers={
            'Content-Type': 'application/json',
            'Referer': 'https://ra.co/search',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:106.0) Gecko/20100101 Firefox/106.0'
        }, json=payload, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if 'data' in data and 'search' in data['data']:
                # Format the results to match the expected V1 format
                formatted_results = {
                    "artists": [],
                    "labels": [],
                    "events": []
                }
                
                for item in data['data']['search']:
                    search_type = item.get('searchType', '').lower()
                    
                    if search_type == 'artist':
                        formatted_results['artists'].append({
                            "id": item.get('id'),
                            "name": item.get('value'),
                            "content_url": item.get('contentUrl'),
                            "images": [{
                                "id": None,
                                "filename": item.get('imageUrl'),
                                "alt": item.get('value'),
                                "type": "profile",
                                "crop": None
                            }] if item.get('imageUrl') else []
                        })
                    elif search_type == 'label':
                        formatted_results['labels'].append({
                            "id": item.get('id'),
                            "name": item.get('value'),
                            "content_url": item.get('contentUrl'),
                            "images": [{
                                "id": None,
                                "filename": item.get('imageUrl'),
                                "alt": item.get('value'),
                                "type": "profile",
                                "crop": None
                            }] if item.get('imageUrl') else []
                        })
                    elif search_type == 'upcomingevent':
                        formatted_results['events'].append({
                            "id": item.get('id'),
                            "title": item.get('value'),
                            "date": item.get('date'),
                            "content_url": item.get('contentUrl'),
                            "venue": {
                                "id": None,
                                "name": item.get('clubName')
                            },
                            "artists": []  # Global search doesn't provide artists for events
                        })
                
                return formatted_results
            
        return {
            "artists": [],
            "labels": [],
            "events": []
        }
    except Exception as e:
        print(f"Error searching for '{query}': {e}")
        return {
            "artists": [],
            "labels": [],
            "events": []
        }

@app.route('/test', methods=['GET'])
def test_route():
    """Test route to verify logging"""
    app.logger.debug("This is a DEBUG log message")
    app.logger.info("This is an INFO log message")
    app.logger.warning("This is a WARNING log message")
    app.logger.error("This is an ERROR log message")
    
    return jsonify({
        "status": "success",
        "message": "Test route with logging"
    })

@app.route('/', methods=['GET'])
def health_check():
    return jsonify({
        "status": "healthy",
        "message": "Resident Advisor API - Events, Artists & Search with Advanced Filtering",
        "api_versions": {
            "v1": {
                "description": "Simple parameter interface with individual lookups",
                "endpoints": {
                    "/events": "Event fetching with basic filtering",
                    "/areas": "List all available areas",
                    "/filters": "Get available filters for an area",
                    "/artist/{slug}": "Get artist by slug",
                    "/label/{id}": "Get label by ID",
                    "/venue/{id}": "Get venue by ID",
                    "/event/{id}": "Get event by ID",
                    "/search": "Search artists, labels, and events"
                },
                "examples": {
                    "events": "/events?area=sydney&start_date=2025-08-15&end_date=2025-08-20&genre=techno",
                    "search": "/search?q=dax&type=artist",
                    "lookup": "/artist/daxj"
                }
            },
            "v2": {
                "description": "Native GraphQL with multi-genre support",
                "endpoints": {
                    "/v2/events": "Multi-genre event fetching with GraphQL",
                    "/v2/search": "Enhanced search with type filtering",
                    "/v2/filters": "Available filters with V2 capabilities",
                    "/v2/artist/{identifier}": "Artist lookup (supports slug or ID)"
                },
                "examples": {
                    "events": "/v2/events?area=melbourne&start_date=2025-08-15&end_date=2025-08-20&genre=techno,house",
                    "search": "/v2/search?q=amelie&filter=type:any:artist,event",
                    "artist": "/v2/artist/amelielens?include=stats,labels"
                },
                "supported_operators": ["eq", "any"]
            },
            "v3": {
                "description": "Advanced filtering with logical operators and batch processing",
                "endpoints": {
                    "/v3/events": "Advanced event filtering with logical operators",
                    "/v3/search": "Advanced search with complex filtering",
                    "/v3/filters": "Available filters with V3 capabilities",
                    "/v3/artist/{slug}": "Artist lookup by slug",
                    "/v3/artists/batch": "Batch artist lookups (up to 50)",
                    "/v3/labels/batch": "Batch label lookups (up to 50)",
                    "/v3/venues/batch": "Batch venue lookups (up to 50)",
                    "/v3/events/batch": "Batch event queries (up to 20)",
                    "/v3/search/batch": "Batch search queries (up to 30)"
                },
                "examples": {
                    "events": "/v3/events?area=sydney&start_date=2025-08-15&end_date=2025-08-20&filter=genre:contains_any:techno,house AND artists:has:ben",
                    "search": "/v3/search?q=ben&filter=type:eq:artist AND country:has:germany",
                    "batch": "POST /v3/artists/batch with JSON body"
                },
                "key_operators": ["eq", "contains_any", "contains_all", "has", "gt", "lt", "between"],
                "logical_operators": ["AND", "OR", "NOT"]
            }
        },
        "key_features": {
            "area_names": {
                "description": "Use area names instead of numeric codes",
                "examples": ["sydney", "melbourne", "perth", "canberra", "adelaide", "hobart"],
                "usage": "?area=sydney instead of ?area=1"
            },
            "batch_processing": {
                "description": "Process multiple requests efficiently",
                "limits": {
                    "artists": 50,
                    "labels": 50,
                    "venues": 50,
                    "events": 20,
                    "search": 30
                }
            },
            "caching_system": {
                "description": "Optimized area name to ID mapping",
                "endpoints": {
                    "/cache/areas": "View cache status",
                    "/cache/areas/lookup": "Look up area by name",
                    "/cache/areas/refresh": "Refresh cache"
                }
            }
        },
        "quick_start": {
            "basic_events": "/events?area=sydney&start_date=2025-08-15&end_date=2025-08-20",
            "multi_genre": "/v2/events?area=melbourne&genre=techno,house&start_date=2025-08-15&end_date=2025-08-20",
            "advanced_filter": "/v3/events?area=sydney&filter=genre:contains_any:techno,house&start_date=2025-08-15&end_date=2025-08-20"
        }
    })

@app.route('/events', methods=['GET'])
def get_events():
    """Fetch events from Resident Advisor with basic filtering support (v1)"""
    try:
        area = request.args.get('area')
        country = request.args.get('country', 'au')  # Default to Australia
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        genre = request.args.get('genre')
        event_type = request.args.get('event_type')
        sort_by = request.args.get('sort', 'listingDate')
        include_bumps = request.args.get('include_bumps', 'true').lower() == 'true'
        
        if not all([area, start_date, end_date]):
            return jsonify({
                "error": "Missing required parameters",
                "endpoint": "/events (V1 - Basic Event Fetching)",
                "required": ["area", "start_date", "end_date"],
                "optional": {
                    "genre": "Single genre (e.g., techno, house, minimal)",
                    "event_type": "Type of event (club, festival, etc.)",
                    "sort": "Sort order (listingDate, score, title)",
                    "include_bumps": "Include promoted events (true/false)",
                    "country": "Country code for area lookup (e.g., au, us, uk)"
                },
                "examples": {
                    "basic": "/events?area=sydney&start_date=2025-08-15&end_date=2025-08-20",
                    "with_genre": "/events?area=melbourne&start_date=2025-08-15&end_date=2025-08-20&genre=techno",
                    "numeric_area": "/events?area=1&start_date=2025-08-15&end_date=2025-08-20&genre=house",
                    "with_country": "/events?area=sydney&country=au&start_date=2025-08-15&end_date=2025-08-20"
                },
                "area_support": {
                    "description": "Use area names or numeric IDs",
                    "available_areas": ["sydney", "melbourne", "perth", "canberra", "adelaide", "hobart"],
                    "usage": "?area=sydney (recommended) or ?area=1"
                },
                "date_format": "YYYY-MM-DD",
                "upgrade_suggestions": {
                    "multi_genre": "Use /v2/events for multiple genres: ?genre=techno,house",
                    "advanced_filtering": "Use /v3/events for complex filters: ?filter=genre:contains_any:techno,house"
                }
            }), 400
            
        # Handle string-based area names
        area_cache_info = None
        if area and not area.isdigit():
            area_lookup = get_area_id(area, country)
            if not area_lookup:
                return jsonify({
                    "error": f"Area '{area}' not found in country '{country}'",
                    "suggestions": ["Try using a different spelling", "Use the /areas endpoint to see available areas"]
                }), 404
            
            # Store cache info for the response
            area_cache_info = {
                "cache_status": area_lookup["cache_status"],
                "cache_message": area_lookup["cache_message"],
                "lookup_key": f"{area.lower()}_{country.lower()}"
            }
            
            # Extract just the area ID for the API call
            area = area_lookup["area_id"]
            
        try:
            area = int(area)
        except (ValueError, TypeError):
            return jsonify({"error": "Invalid area parameter"}), 400
            
        listing_date_gte = f"{start_date}T00:00:00.000Z"
        listing_date_lte = f"{end_date}T23:59:59.999Z"
        
        # Use basic event fetcher with V1 simple filtering
        event_fetcher = EnhancedEventFetcher(
            areas=area,
            listing_date_gte=listing_date_gte,
            listing_date_lte=listing_date_lte,
            genre=genre,
            event_type=event_type,
            sort_by=sort_by,
            include_bumps=include_bumps
        )
        
        events_data = event_fetcher.fetch_all_events()
        area_info = get_area_info(area_id=area)
        
        # Format area_info to match the existing API format
        formatted_area_info = None
        if area_info:
            formatted_area_info = {
                "id": area_info.get("id"),
                "name": area_info.get("name"),
                "url_name": area_info.get("urlName"),
                "country": {
                    "name": area_info.get("country", {}).get("name"),
                    "code": area_info.get("country", {}).get("urlCode")
                }
            }
        
        response = {
            "status": "success",
            "version": "v1",
            "area": formatted_area_info,
            "date_range": {
                "start": start_date,
                "end": end_date
            },
            "filtering": {
                "genre": genre,
                "event_type": event_type,
                "sort": sort_by,
                "include_bumps": include_bumps
            },
            "events": events_data.get("events", []),
            "bumps": events_data.get("bumps", []),
            "total_events": len(events_data.get("events", [])),
            "total_bumps": len(events_data.get("bumps", []))
        }
        
        # Add cache info if available
        if area_cache_info:
            response["area_lookup"] = area_cache_info
        
        return jsonify(response)
        
    except Exception as e:
        return jsonify({"error": "Internal server error", "message": str(e)}), 500

@app.route('/areas', methods=['GET'])
def get_areas_endpoint():
    """List all available areas (v1)"""
    try:
        areas = get_all_areas()
        
        return jsonify({
            "status": "success",
            "version": "v1",
            "areas": areas,
            "total": len(areas)
        })
        
    except Exception as e:
        return jsonify({"error": "Internal server error", "message": str(e)}), 500

@app.route('/filters', methods=['GET'])
def get_filters():
    """Get available filters for an area (v1)"""
    try:
        area = request.args.get('area')
        
        if not area:
            return jsonify({
                "error": "Missing required parameter: area",
                "example": "/filters?area=1"
            }), 400
            
        try:
            area = int(area)
        except ValueError:
            return jsonify({"error": "Area must be a number"}), 400
        
        # Use a short date range to get filter options quickly
        from datetime import timedelta
        today = datetime.now()
        tomorrow = today + timedelta(days=7)
        
        listing_date_gte = today.strftime("%Y-%m-%dT00:00:00.000Z")
        listing_date_lte = tomorrow.strftime("%Y-%m-%dT23:59:59.999Z")
        
        # Create a fetcher to get filter options
        event_fetcher = EnhancedEventFetcher(
            areas=area,
            listing_date_gte=listing_date_gte,
            listing_date_lte=listing_date_lte,
            include_bumps=True
        )
        
        # Fetch just one page to get filter options
        result = event_fetcher.get_events(1)
        filter_options = result.get("filter_options", {})
        area_info = get_area_info(area)
        
        response = {
            "status": "success",
            "version": "v1",
            "area": area_info,
            "capabilities": {
                "description": "Basic filtering with single values only",
                "genre_support": "Single genre only (no multi-genre)",
                "operators": ["eq", "ne"]
            },
            "available_filters": {}
        }
        
        if "genre" in filter_options:
            response["available_filters"]["genres"] = [
                {
                    "label": g.get("label"),
                    "value": g.get("value"),
                    "count": g.get("count")
                }
                for g in filter_options["genre"]
            ]
        
        if "eventType" in filter_options:
            response["available_filters"]["event_types"] = [
                {
                    "value": et.get("value"),
                    "count": et.get("count")
                }
                for et in filter_options["eventType"]
            ]
        
        response["usage_examples"] = {
            "basic_filtering": f"/events?area={area}&start_date=2025-08-10&end_date=2025-08-17&genre=techno",
            "event_type": f"/events?area={area}&start_date=2025-08-10&end_date=2025-08-17&event_type=club",
            "sorting": f"/events?area={area}&start_date=2025-08-10&end_date=2025-08-17&sort=score"
        }
        
        return jsonify(response)
        
    except Exception as e:
        return jsonify({"error": "Internal server error", "message": str(e)}), 500

@app.route('/artist', methods=['GET'])
def artist_help():
    """Artist lookup help endpoint - shows how to use artist endpoints across API versions"""
    return jsonify({
        "message": "Artist Lookup Endpoints - How to find artist information",
        "api_versions": {
            "v1": {
                "endpoint": "/artist/{slug}",
                "description": "Basic artist lookup by slug only",
                "example": "/artist/daxj",
                "supported_identifiers": ["slug"],
                "returns": "Basic artist info + recent events"
            },
            "v2": {
                "endpoint": "/v2/artist/{identifier}",
                "description": "Enhanced artist lookup with additional data options",
                "examples": {
                    "by_slug": "/v2/artist/amelielens",
                    "by_id": "/v2/artist/61166",
                    "with_includes": "/v2/artist/benklock?include=stats,labels,booking"
                },
                "supported_identifiers": ["slug", "id"],
                "additional_features": "Optional include parameter for stats, labels, booking, etc.",
                "returns": "Comprehensive artist data with optional sections"
            },
            "v3": {
                "endpoint": "/v3/artist/{slug}",
                "description": "Advanced artist lookup by slug with full data",
                "example": "/v3/artist/benklock",
                "supported_identifiers": ["slug"],
                "returns": "Complete artist profile with all available data"
            }
        },
        "batch_operations": {
            "v3_batch": {
                "endpoint": "POST /v3/artists/batch",
                "description": "Batch artist lookups (up to 50 artists)",
                "example_request": {
                    "artist_slugs": ["daxj", "amelielens", "benklock"],
                    "include": ["stats", "labels", "booking"],
                    "rate_limit_delay": 0.5
                },
                "max_artists": 50,
                "features": "V2-style include system + configurable rate limiting"
            }
        },
        "popular_artists": {
            "examples": {
                "dax_j": {
                    "slug": "daxj",
                    "id": "11733",
                    "name": "Dax J"
                },
                "amelie_lens": {
                    "slug": "amelielens", 
                    "id": "61166",
                    "name": "Amelie Lens"
                },
                "ben_klock": {
                    "slug": "benklock",
                    "id": "966", 
                    "name": "Ben Klock"
                }
            },
            "note": "Use these for testing - they're popular artists with rich data"
        },
        "finding_artist_slugs": {
            "search_endpoints": {
                "v1": "/search?q=dax&type=artist",
                "v2": "/v2/search?q=amelie&filter=type:eq:artist", 
                "v3": "/v3/search?q=ben&filter=type:eq:artist"
            },
            "tips": [
                "Search first to find the exact artist slug",
                "Artist slugs are usually lowercase with no spaces",
                "Use the search endpoints to discover new artists"
            ]
        },
        "identifier_guide": {
            "slug": {
                "description": "URL-safe artist name (e.g., 'amelielens', 'benklock')",
                "usage": "Recommended for all lookups - more readable and stable",
                "supported_versions": ["v1", "v2", "v3"]
            },
            "id": {
                "description": "Numeric artist ID (e.g., '11733', '61166')",
                "usage": "Only supported in V2 - use slug when possible",
                "supported_versions": ["v2"]
            }
        },
        "version_comparison": {
            "choose_v1": "Simple artist info + recent events",
            "choose_v2": "Need specific data sections (stats, labels) or have artist ID",
            "choose_v3": "Want complete artist profile or need batch processing"
        }
    })

@app.route('/artist/<artist_slug>', methods=['GET'])
def get_artist_endpoint(artist_slug):
    """Get single artist by slug (v1) - NOTE: Artists must be looked up by slug, not ID"""
    try:
        artist_data = get_artist_by_slug(artist_slug)
        
        if not artist_data:
            return jsonify({
                "error": "Artist not found",
                "artist_slug": artist_slug,
                "note": "Artists must be searched by slug (e.g., 'jazminenikitta'), not ID"
            }), 404
        
        # Get additional event data
        artist_id = artist_data.get('id')
        events_data = []
        if artist_id:
            events_data = get_artist_events(artist_id)
        
        return jsonify({
            "status": "success",
            "version": "v1",
            "artist": {
                "id": artist_data.get('id'),
                "name": artist_data.get('name'),
                "content_url": artist_data.get('contentUrl'),
                "follower_count": artist_data.get('followerCount', 0),
                "image": artist_data.get('image'),
                "url_safe_name": artist_data.get('urlSafeName'),
                "country": artist_data.get('country'),
                "resident_country": artist_data.get('residentCountry'),
                "social_links": {
                    "soundcloud": artist_data.get('soundcloud'),
                    "facebook": artist_data.get('facebook'),
                    "instagram": artist_data.get('instagram'),
                    "twitter": artist_data.get('twitter'),
                    "bandcamp": artist_data.get('bandcamp'),
                    "website": artist_data.get('website'),
                    "discogs": artist_data.get('discogs')
                },
                "biography": artist_data.get('biography'),
                "events": events_data,
                "total_events": len(events_data)
            }
        })
        
    except Exception as e:
        return jsonify({"error": "Internal server error", "message": str(e)}), 500
@app.route('/label', methods=['GET'])
def label_help():
    """Label lookup help endpoint - shows how to use label endpoints"""
    return jsonify({
        "message": "Label Lookup Endpoints - How to find record label information",
        "available_endpoints": {
            "v1": {
                "endpoint": "/label/{id}",
                "description": "Basic label lookup by numeric ID",
                "example": "/label/3068",
                "supported_identifiers": ["numeric_id"],
                "returns": "Basic label info + upcoming events"
            },
            "v3_batch": {
                "endpoint": "POST /v3/labels/batch",
                "description": "Batch label lookups (up to 50 labels)",
                "note": "See /v3/labels/batch endpoint for detailed batch information"
            }
        },
        "identifier_format": {
            "description": "Labels use numeric IDs only",
            "format": "Numeric string (e.g., '3068', '67890')",
            "note": "Unlike artists, labels do not have slug-based identifiers"
        },
        "example_labels": {
            "note": "Example using real label IDs for testing",
            "examples": [
                {
                    "id": "3068",
                    "name": "Hate",
                    "usage": "/label/3068"
                },
                {
                    "id": "67890", 
                    "usage": "/label/67890"
                },
                {
                    "id": "54321",
                    "usage": "/label/54321"
                }
            ]
        },
        "finding_label_ids": {
            "search_methods": {
                "v1_search": "/search?q=label_name&type=label",
                "v2_search": "/v2/search?q=label_name&filter=type:eq:label",
                "v3_search": "/v3/search?q=label_name&filter=type:eq:label"
            },
            "artist_associations": {
                "description": "Find labels through artist profiles",
                "v2_example": "/v2/artist/amelielens?include=labels"
            },
            "tips": [
                "Search for label names to find their numeric IDs",
                "Check artist profiles for associated labels",
                "Label IDs are required for all label lookups"
            ]
        },
        "api_coverage": {
            "v1_individual": "Individual label lookups with basic info and events",
            "v2_integration": "Labels included in artist data (use /v2/artist/{id}?include=labels)",
            "v3_batch": "Batch processing available - see POST /v3/labels/batch"
        },
        "response_data": {
            "v1_fields": [
                "id", "name", "contentUrl", "image", "followerCount",
                "upcomingEvents", "country", "description"
            ],
            "upcoming_events": "Recent and upcoming releases/events from the label"
        },
        "limitations": {
            "no_slug_support": "Labels only support numeric IDs, not URL-safe names",
            "no_v2_endpoint": "V2 API doesn't have dedicated label endpoints",
            "search_required": "Must search or check artist profiles to find label IDs"
        },
        "workflow_suggestions": {
            "discovery": "1. Search for label name → 2. Get label ID → 3. Lookup label details",
            "artist_exploration": "1. Get artist profile with labels → 2. Lookup individual labels",
            "batch_processing": "For multiple labels, see POST /v3/labels/batch endpoint"
        }
    })

@app.route('/label/<label_id>', methods=['GET'])
def get_label_endpoint(label_id):
    """Get single label by ID (v1)"""
    try:
        label_data = get_label_by_id(label_id)
        
        if not label_data:
            return jsonify({
                "error": "Label not found",
                "label_id": label_id
            }), 404
        
        # Format upcoming events
        upcoming_events = []
        if label_data.get('upcomingEvents', {}).get('edges'):
            for edge in label_data['upcomingEvents']['edges']:
                event = edge['node']
                upcoming_events.append({
                    "id": event.get('id'),
                    "title": event.get('title'),
                    "date": event.get('date'),
                    "venue": {
                        "id": event.get('venue', {}).get('id'),
                        "name": event.get('venue', {}).get('name')
                    },
                    "content_url": event.get('contentUrl')
                })
        
        return jsonify({
            "status": "success",
            "version": "v1",
            "label": {
                "id": label_data.get('id'),
                "name": label_data.get('name'),
                "description": label_data.get('description'),
                "content_url": label_data.get('contentUrl'),
                "images": label_data.get('images', []),
                "upcoming_events": upcoming_events
            }
        })
        
    except Exception as e:
        return jsonify({"error": "Internal server error", "message": str(e)}), 500

@app.route('/venue', methods=['GET'])
def venue_help():
    """Venue lookup help endpoint - shows how to use venue endpoints"""
    return jsonify({
        "message": "Venue Lookup Endpoints - How to find venue information",
        "available_endpoints": {
            "v1": {
                "endpoint": "/venue/{id}",
                "description": "Basic venue lookup by numeric ID",
                "example": "/venue/168",
                "supported_identifiers": ["numeric_id"],
                "returns": "Complete venue info including top artists, capacity, location"
            }
        },
        "identifier_format": {
            "description": "Venues use numeric IDs only",
            "format": "Numeric string (e.g., '168', '420')",
            "note": "Unlike artists, venues do not have slug-based identifiers"
        },
        "example_venues": {
            "note": "Example using real venue IDs for testing",
            "examples": [
                {
                    "id": "168",
                    "name": "Chinese Laundry",
                    "location": "Sydney",
                    "usage": "/venue/168"
                },
                {
                    "id": "420",
                    "usage": "/venue/420"
                }
            ]
        },
        "finding_venue_ids": {
            "search_methods": {
                "v1_search": "/search?q=venue_name&type=venue",
                "event_results": "Extract venue IDs from event search results"
            },
            "event_associations": {
                "description": "Find venues through event searches",
                "example": "/events?area=sydney&start_date=2025-08-15&end_date=2025-08-20"
            },
            "tips": [
                "Search for venue names to find their numeric IDs",
                "Check event results for venue information",
                "Venue IDs are required for all venue lookups"
            ]
        },
        "response_data": {
            "v1_fields": [
                "id", "name", "logoUrl", "photo", "blurb", "address", 
                "phone", "website", "followerCount", "capacity", "topArtists",
                "eventCountThisYear", "area", "isClosed"
            ],
            "top_artists": "Most frequently performing artists at this venue",
            "location_info": "Complete address and area information"
        },
        "workflow_suggestions": {
            "discovery": "1. Search for venue name → 2. Get venue ID → 3. Lookup venue details",
            "event_exploration": "1. Search events by area → 2. Extract venue IDs → 3. Lookup individual venues"
        }
    })

@app.route('/venue/<venue_id>', methods=['GET'])
def get_venue_endpoint(venue_id):
    """Get single venue by ID (v1)"""
    try:
        venue_data = get_venue_by_id(venue_id)
        
        if not venue_data:
            return jsonify({
                "error": "Venue not found",
                "venue_id": venue_id
            }), 404
        
        return jsonify({
            "status": "success",
            "version": "v1",
            "venue": {
                "id": venue_data.get('id'),
                "name": venue_data.get('name'),
                "logoUrl": venue_data.get('logoUrl'),
                "photo": venue_data.get('photo'),
                "blurb": venue_data.get('blurb'),
                "address": venue_data.get('address'),
                "phone": venue_data.get('phone'),
                "website": venue_data.get('website'),
                "followerCount": venue_data.get('followerCount'),
                "capacity": venue_data.get('capacity'),
                "isClosed": venue_data.get('isClosed'),
                "raSays": venue_data.get('raSays'),
                "isFollowing": venue_data.get('isFollowing'),
                "eventCountThisYear": venue_data.get('eventCountThisYear'),
                "contentUrl": venue_data.get('contentUrl'),
                "topArtists": venue_data.get('topArtists', []),
                "area": venue_data.get('area')
            }
        })
        
    except Exception as e:
        return jsonify({"error": "Internal server error", "message": str(e)}), 500

@app.route('/event', methods=['GET'])
def event_help():
    """Event lookup help endpoint - shows individual event lookup functionality"""
    return jsonify({
        "message": "Individual Event Lookup - How to get detailed event information",
        "endpoint": {
            "v1": {
                "endpoint": "/event/{id}",
                "description": "Individual event lookup by numeric ID",
                "example": "/event/1447038",
                "returns": "Complete event details including venue, artists, tickets, timing"
            }
        },
        "finding_event_ids": {
            "search_methods": {
                "recommended": "Use event search endpoints to find events, then extract IDs from results",
                "workflow": "1. Search events by criteria → 2. Get event ID from results → 3. Lookup individual event"
            },
            "search_endpoints": {
                "v1": "/events?area=sydney&start_date=2025-08-15&end_date=2025-08-20&genre=techno",
                "v2": "/v2/events?area=melbourne&start_date=2025-08-15&end_date=2025-08-20&genre=techno,house",
                "v3": "/v3/events?area=sydney&start_date=2025-08-15&end_date=2025-08-20&filter=genre:contains_any:techno,house"
            },
            "example_workflow": {
                "step1": "Search: /events?area=sydney&start_date=2025-08-15&end_date=2025-08-20",
                "step2": "Extract event ID from search results",
                "step3": "Lookup: /event/{extracted_id}"
            }
        },
        "identifier_format": {
            "description": "Events use numeric IDs only",
            "format": "Numeric string (e.g., '1447038', '1523456')",
            "example_event": {
                "id": "1447038",
                "usage": "/event/1447038"
            }
        },
        "response_data": {
            "comprehensive_fields": [
                "id", "title", "date", "time", "venue", "artists", "lineup",
                "cost", "minimumAge", "interestedCount", "isTicketed", "genres",
                "flyer", "tickets", "promoters", "description", "location"
            ],
            "venue_details": "Complete venue information including name, address, area",
            "artist_lineup": "Full artist lineup with IDs and names",
            "ticket_info": "Pricing and ticketing platform details",
            "timing": "Date, start time, end time information"
        },
        "common_use_cases": {
            "event_details": "Get complete information about a specific event",
            "venue_info": "Find venue details and location for an event",
            "lineup_check": "See full artist lineup and set times",
            "ticket_research": "Check pricing and ticketing information"
        },
        "limitations": {
            "id_required": "Must have numeric event ID - no search by name",
            "search_first": "Use event search endpoints to discover event IDs",
            "single_event": "Returns one event only - use search endpoints for multiple events"
        },
        "related_endpoints": {
            "event_search": "Use /events, /v2/events, or /v3/events to find events by criteria",
            "artist_lookup": "Use /artist/{slug} to get more artist information",
            "venue_search": "Use V3 events with venue filters to find events by venue"
        }
    })

@app.route('/event/<event_id>', methods=['GET'])
def get_event_endpoint(event_id):
    """Get single event by ID (v1)"""
    try:
        event_data = get_event_by_id(event_id)
        
        if not event_data:
            return jsonify({
                "error": "Event not found",
                "event_id": event_id
            }), 404
        
        return jsonify({
            "status": "success",
            "version": "v1",
            "event": {
                "id": event_data.get('id'),
                "title": event_data.get('title'),
                "content_url": event_data.get('contentUrl'),
                "date": event_data.get('date'),
                "time": event_data.get('time'),
                "start_time": event_data.get('startTime'),
                "end_time": event_data.get('endTime'),
                "cost": event_data.get('cost'),
                "minimum_age": event_data.get('minimumAge'),
                "interested_count": event_data.get('interestedCount', 0),
                "is_ticketed": event_data.get('isTicketed', False),
                "is_festival": event_data.get('isFestival', False),
                "lineup": event_data.get('lineup'),
                "content": event_data.get('content'),
                "flyer_front": event_data.get('flyerFront'),
                "flyer_back": event_data.get('flyerBack'),
                "venue": {
                    "id": event_data.get('venue', {}).get('id'),
                    "name": event_data.get('venue', {}).get('name'),
                    "address": event_data.get('venue', {}).get('address'),
                    "content_url": event_data.get('venue', {}).get('contentUrl'),
                    "area": {
                        "id": event_data.get('venue', {}).get('area', {}).get('id'),
                        "name": event_data.get('venue', {}).get('area', {}).get('name'),
                        "url_name": event_data.get('venue', {}).get('area', {}).get('urlName'),
                        "country": event_data.get('venue', {}).get('area', {}).get('country')
                    },
                    "location": event_data.get('venue', {}).get('location')
                } if event_data.get('venue') else None,
                "artists": [
                    {
                        "id": artist.get('id'),
                        "name": artist.get('name'),
                        "content_url": artist.get('contentUrl'),
                        "url_safe_name": artist.get('urlSafeName')
                    }
                    for artist in event_data.get('artists', [])
                ],
                "promoters": [
                    {
                        "id": promoter.get('id'),
                        "name": promoter.get('name'),
                        "content_url": promoter.get('contentUrl')
                    }
                    for promoter in event_data.get('promoters', [])
                ],
                "genres": [
                    {
                        "id": genre.get('id'),
                        "name": genre.get('name'),
                        "slug": genre.get('slug')
                    }
                    for genre in event_data.get('genres', [])
                ],
                "images": event_data.get('images', []),
                "tickets": event_data.get('tickets', []),
                "promotional_links": event_data.get('promotionalLinks', []),
                "pick": event_data.get('pick'),
                "admin": event_data.get('admin'),
                "set_times": event_data.get('setTimes'),
                "date_posted": event_data.get('datePosted'),
                "date_updated": event_data.get('dateUpdated'),
                "live": event_data.get('live', False),
                "ticketing_system": event_data.get('ticketingSystem')
            }
        })
        
    except Exception as e:
        return jsonify({"error": "Internal server error", "message": str(e)}), 500

@app.route('/search', methods=['GET'])
def search_endpoint():
    """Basic search (artist, label, event) (v1)"""
    try:
        query = request.args.get('q')
        search_type = request.args.get('type', 'all')
        
        if not query:
            return jsonify({
                "error": "Missing required parameter: q (query)",
                "optional": "type (artist, label, event, all)",
                "examples": {
                    "search_all": "/search?q=techno",
                    "search_artists": "/search?q=charlotte&type=artist",
                    "search_labels": "/search?q=fabric&type=label",
                    "search_events": "/search?q=warehouse&type=event"
                }
            }), 400
        
        valid_types = ['all', 'artist', 'label', 'event']
        if search_type not in valid_types:
            return jsonify({
                "error": f"Invalid search type. Must be one of: {valid_types}"
            }), 400
        
        # Get search results using the enhanced search_ra function
        search_results = search_ra(query, search_type)
        
        # Build response
        response = {
            "status": "success",
            "version": "v1",
            "query": query,
            "type": search_type,
            "results": search_results
        }
        
        # Add total counts
        totals = {
            "artists": len(search_results.get('artists', [])),
            "labels": len(search_results.get('labels', [])),
            "events": len(search_results.get('events', []))
        }
        
        response["total_results"] = totals
        
        return jsonify(response)
        
    except Exception as e:
        return jsonify({"error": "Internal server error", "message": str(e)}), 500

def get_all_areas():
    """Get list of all available areas using RA's GraphQL API"""
    try:
        payload = {
            "operationName": "GET_AREAS",
            "variables": {},
            "query": """query GET_AREAS {
                areas {
                    id name urlName
                    country { name urlCode }
                }
            }"""
        }
        
        response = requests.post('https://ra.co/graphql', headers={
            'Content-Type': 'application/json',
            'Referer': 'https://ra.co/events',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:106.0) Gecko/20100101 Firefox/106.0'
        }, json=payload, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if 'data' in data and data['data']['areas']:
                return data['data']['areas']
        return []
    except Exception as e:
        print(f"Error getting areas: {e}")
        return []

@app.route('/v2/events', methods=['GET'])
def get_events_v2():
    """Enhanced events endpoint with advanced filtering support (v2)"""
    try:
        # Get parameters
        area = request.args.get('area')
        country = request.args.get('country', 'au')  # Default to Australia
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        output_format = request.args.get('format', 'json').lower()
        
        # Enhanced parameters
        genre = request.args.get('genre')
        event_type = request.args.get('event_type')
        sort_by = request.args.get('sort', 'listingDate')
        include_bumps = request.args.get('include_bumps', 'true').lower() == 'true'
        filter_expression = request.args.get('filter')
        
        if not all([area, start_date, end_date]):
            return jsonify({
                "error": "Missing required parameters",
                "endpoint": "/v2/events (V2 - Native GraphQL Multi-Genre)",
                "required": ["area", "start_date", "end_date"],
                "optional": {
                    "genre": "Single genre or comma-separated multiple genres (e.g., techno,house,minimal)",
                    "event_type": "Type of event (club, festival, etc.)",
                    "sort": "Sort order (listingDate, score, title)",
                    "include_bumps": "Include promoted events (true/false)",
                    "format": "Response format (json/csv)",
                    "filter": "Native GraphQL filter expression",
                    "country": "Country code for area lookup (e.g., au, us, uk)"
                },
                "key_features": {
                    "multi_genre": "Native support for multiple genres in single request",
                    "graphql_native": "Uses RA's native GraphQL operators for optimal performance",
                    "filter_expressions": "Supports native filter syntax alongside simple parameters"
                },
                "examples": {
                    "basic_multi_genre": "/v2/events?area=sydney&start_date=2025-08-15&end_date=2025-08-20&genre=techno,house",
                    "single_genre": "/v2/events?area=melbourne&start_date=2025-08-15&end_date=2025-08-20&genre=techno",
                    "with_filter": "/v2/events?area=perth&start_date=2025-08-15&end_date=2025-08-20&filter=genre:any:techno,house",
                    "event_type": "/v2/events?area=adelaide&start_date=2025-08-15&end_date=2025-08-20&filter=eventType:eq:club"
                },
                "filter_syntax": {
                    "description": "Native GraphQL operators for optimal performance",
                    "operators": ["eq", "any"],
                    "examples": {
                        "exact_match": "genre:eq:techno",
                        "multiple_genres": "genre:any:techno,house,minimal",
                        "event_type": "eventType:eq:club"
                    }
                },
                "area_support": {
                    "description": "Use area names or numeric IDs",
                    "available_areas": ["sydney", "melbourne", "perth", "canberra", "adelaide", "hobart"],
                    "usage": "?area=sydney (recommended) or ?area=1"
                },
                "date_format": "YYYY-MM-DD",
                "upgrade_suggestion": "Use /v3/events for advanced filtering with logical operators (AND, OR, NOT) and client-side processing"
            }), 400
            
        # Handle string-based area names
        area_cache_info = None
        if area and not area.isdigit():
            area_lookup = get_area_id(area, country)
            if not area_lookup:
                return jsonify({
                    "error": f"Area '{area}' not found in country '{country}'",
                    "suggestions": ["Try using a different spelling", "Use the /areas endpoint to see available areas"]
                }), 404
            
            # Store cache info for the response
            area_cache_info = {
                "cache_status": area_lookup["cache_status"],
                "cache_message": area_lookup["cache_message"],
                "lookup_key": f"{area.lower()}_{country.lower()}"
            }
            
            # Extract just the area ID for the API call
            area = area_lookup["area_id"]
            
        try:
            area = int(area)
        except (ValueError, TypeError):
            return jsonify({"error": "Invalid area parameter"}), 400
            
        try:
            datetime.strptime(start_date, '%Y-%m-%d')
            datetime.strptime(end_date, '%Y-%m-%d')
        except ValueError:
            return jsonify({"error": "Invalid date format. Use YYYY-MM-DD"}), 400
            
        # Validate sort parameter
        valid_sorts = ['listingDate', 'score', 'title']
        if sort_by not in valid_sorts:
            return jsonify({
                "error": f"Invalid sort parameter. Must be one of: {valid_sorts}"
            }), 400
            
        # Convert dates
        listing_date_gte = f"{start_date}T00:00:00.000Z"
        listing_date_lte = f"{end_date}T23:59:59.999Z"
        
        # V2: No need to convert comma-separated genres to filter expressions
        # The V2 fetcher handles this natively now
        
        # Create enhanced event fetcher V2 with native GraphQL support
        event_fetcher = EnhancedEventFetcherV2(
            areas=area,
            listing_date_gte=listing_date_gte,
            listing_date_lte=listing_date_lte,
            genre=genre,
            event_type=event_type,
            sort_by=sort_by,
            include_bumps=include_bumps,
            filter_expression=filter_expression
        )
        
        # Fetch events
        events_data = event_fetcher.fetch_all_events()
        area_info = get_area_info(area_id=area)
        
        # Format area_info to match the existing API format
        formatted_area_info = None
        if area_info:
            formatted_area_info = {
                "id": area_info.get("id"),
                "name": area_info.get("name"),
                "url_name": area_info.get("urlName"),
                "country": {
                    "name": area_info.get("country", {}).get("name"),
                    "code": area_info.get("country", {}).get("urlCode")
                }
            }
        
        if output_format == 'csv':
            # CSV output
            with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.csv', encoding='utf-8') as tmp_file:
                output_file = tmp_file.name
            
            try:
                event_fetcher.save_events_to_csv(events_data, output_file)
                filename = f'ra_events_v2_{area}_{start_date}_{end_date}'
                if filter_expression:
                    # Sanitize filter expression for filename
                    filter_safe = filter_expression.replace(':', '_').replace(',', '_').replace(' ', '_')[:50]
                    filename += f'_filter_{filter_safe}'
                filename += '.csv'
                
                return send_file(output_file, as_attachment=True, 
                               download_name=filename, mimetype='text/csv')
            finally:
                if os.path.exists(output_file):
                    os.unlink(output_file)
        else:
            # JSON response
            events_json = []
            bumps_json = []
            
            # Process events
            for event_item in events_data.get("events", []):
                event = event_item.get('event', {})
                
                artists = [{"id": artist.get('id'), "name": artist.get('name')} 
                          for artist in event.get('artists', [])]
                
                events_json.append({
                    "id": event.get('id'),
                    "title": event.get('title'),
                    "date": event.get('date'),
                    "start_time": event.get('startTime'),
                    "end_time": event.get('endTime'),
                    "venue": {
                        "id": event.get('venue', {}).get('id'),
                        "name": event.get('venue', {}).get('name'),
                        "contentUrl": event.get('venue', {}).get('contentUrl')
                    },
                    "artists": artists,
                    "interested_count": event.get('interestedCount', 0),
                    "is_ticketed": event.get('isTicketed', False),
                    "content_url": event.get('contentUrl'),
                    "flyer_front": event.get('flyerFront'),
                    "is_saved": event.get('isSaved', False),
                    "is_interested": event.get('isInterested', False)
                })
            
            # Process bumps
            for bump_item in events_data.get("bumps", []):
                event = bump_item.get('event', {})
                
                artists = [{"id": artist.get('id'), "name": artist.get('name')} 
                          for artist in event.get('artists', [])]
                
                bumps_json.append({
                    "id": event.get('id'),
                    "title": event.get('title'),
                    "date": event.get('date'),
                    "start_time": event.get('startTime'),
                    "end_time": event.get('endTime'),
                    "venue": {
                        "id": event.get('venue', {}).get('id'),
                        "name": event.get('venue', {}).get('name'),
                        "contentUrl": event.get('venue', {}).get('contentUrl')
                    },
                    "artists": artists,
                    "interested_count": event.get('interestedCount', 0),
                    "is_ticketed": event.get('isTicketed', False),
                    "content_url": event.get('contentUrl'),
                    "flyer_front": event.get('flyerFront'),
                    "is_saved": event.get('isSaved', False),
                    "is_interested": event.get('isInterested', False),
                    "is_bumped": True
                })
            
            # Build response
            response = {
                "status": "success",
                "version": "v2",
                "area": formatted_area_info,
                "date_range": {
                    "start": start_date,
                    "end": end_date
                },
                "filtering": {
                    "legacy_filters": {
                        "genre": genre,
                        "event_type": event_type,
                        "sort": sort_by,
                        "include_bumps": include_bumps
                    },
                    "advanced_filter": filter_expression,
                    "applied_filters": events_data.get('filter_info', {})
                },
                "results": {
                    "total_events": events_data.get('total_events', 0),
                    "total_bumps": events_data.get('total_bumps', 0),
                    "events": events_json,
                    "bumped_events": bumps_json
                }
            }
            
            # Add cache info if available
            if area_cache_info:
                response["area_lookup"] = area_cache_info
            
            return jsonify(response)
        
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": "Internal server error", "message": str(e)}), 500

@app.route('/v2/filters', methods=['GET'])
def get_available_filters_v2():
    """Get available filters with enhanced information (v2)"""
    try:
        area = request.args.get('area')
        country = request.args.get('country', 'au')  # Default to Australia
        
        # Handle string-based area names
        area_cache_info = None
        if area and not area.isdigit():
            area_lookup = get_area_id(area, country)
            if not area_lookup:
                return jsonify({
                    "error": f"Area '{area}' not found in country '{country}'",
                    "suggestions": ["Try using a different spelling", "Use the /areas endpoint to see available areas"]
                }), 404
            
            # Store cache info for the response
            area_cache_info = {
                "cache_status": area_lookup["cache_status"],
                "cache_message": area_lookup["cache_message"],
                "lookup_key": f"{area.lower()}_{country.lower()}"
            }
            
            # Extract just the area ID for the API call
            area = area_lookup["area_id"]
                
        try:
            area = int(area or 1)  # Default to area 1 (Sydney) if not provided
        except (ValueError, TypeError):
            return jsonify({"error": "Invalid area parameter"}), 400
        
        # Use a short date range to get filter options quickly
        from datetime import timedelta
        today = datetime.now()
        tomorrow = today + timedelta(days=7)  # Extended range for more options
        
        listing_date_gte = today.strftime("%Y-%m-%dT00:00:00.000Z")
        listing_date_lte = tomorrow.strftime("%Y-%m-%dT23:59:59.999Z")
        
        # Create a fetcher to get filter options
        event_fetcher = EnhancedEventFetcherV2(
            areas=area,
            listing_date_gte=listing_date_gte,
            listing_date_lte=listing_date_lte,
            include_bumps=True
        )
        
        # Fetch just one page to get filter options
        result = event_fetcher.get_events(1)
        filter_options = result.get("filter_options", {})
        
        area_info = get_area_info(area_id=area)
        
        # Format area_info to match the existing API format
        formatted_area_info = None
        if area_info:
            formatted_area_info = {
                "id": area_info.get("id"),
                "name": area_info.get("name"),
                "url_name": area_info.get("urlName"),
                "country": {
                    "name": area_info.get("country", {}).get("name"),
                    "code": area_info.get("country", {}).get("urlCode")
                }
            }
        
        response = {
            "version": "v2",
            "area": formatted_area_info,
            "enhanced_features": {
                "multi_genre_support": "Use comma-separated values: genre=techno,house,minimal",
                "advanced_expressions": "Use filter parameter: filter=genre:in:techno,house AND eventType:eq:club",
                "client_side_filtering": "Complex logic handled automatically"
            },
            "available_filters": {}
        }
        
        # Add cache info if available
        if area_cache_info:
            response["area_lookup"] = area_cache_info
        
        if "genre" in filter_options:
            response["available_filters"]["genres"] = [
                {
                    "label": g.get("label"),
                    "value": g.get("value"),
                    "count": g.get("count")
                }
                for g in filter_options["genre"]
            ]
        
        if "eventType" in filter_options:
            response["available_filters"]["event_types"] = [
                {
                    "value": et.get("value"),
                    "count": et.get("count")
                }
                for et in filter_options["eventType"]
            ]
        
        response["usage_examples"] = {
            "multi_genre": "/v2/events?area=1&start_date=2025-08-10&end_date=2025-08-17&genre=techno,house,minimal",
            "native_filter": "/v2/events?area=1&start_date=2025-08-10&end_date=2025-08-17&filter=genre:any:techno,house",
            "single_genre": "/v2/events?area=1&start_date=2025-08-10&end_date=2025-08-17&filter=genre:eq:techno",
            "event_type": "/v2/events?area=1&start_date=2025-08-10&end_date=2025-08-17&filter=eventType:eq:club"
        }
        
        response["supported_operators"] = {
            "eq": "equals (exact match) - native GraphQL",
            "any": "multi-genre OR - native GraphQL"
        }
        
        response["logical_operators"] = ["Support coming in future V2 updates"]
        
        return jsonify(response)
        
    except Exception as e:
        return jsonify({"error": "Internal server error", "message": str(e)}), 500

@app.route('/v2/search', methods=['GET'])
def search_v2():
    """Enhanced search endpoint with V2 filter syntax for indices"""
    try:
        query = request.args.get('q')
        search_type = request.args.get('type', 'all')
        filter_expression = request.args.get('filter')
        
        if not query:
            return jsonify({
                "error": "Missing required parameter: q (query)",
                "required": ["q"],
                "optional": {
                    "type": "artist, label, event, or all (default: all)",
                    "filter": "V2 filter expression for content types (indices)"
                },
                "examples": {
                    "basic_search": "/v2/search?q=charlotte&type=artist",
                    "multi_type": "/v2/search?q=techno&type=all",
                    "with_filter": "/v2/search?q=festival&filter=type:any:event,artist"
                },
                "supported_types": ["artist", "label", "event", "all"],
                "v2_features": {
                    "consistent_syntax": "Uses the same filter syntax as other V2 endpoints",
                    "supported_operators": ["eq", "any"],
                    "type_filtering": "Filter by content types using type:any:event,artist,label"
                }
            }), 400
        
        # Validate search type if provided directly
        valid_types = ['artist', 'label', 'event', 'all']
        if search_type not in valid_types:
            return jsonify({
                "error": f"Invalid search type. Must be one of: {valid_types}"
            }), 400
        
        # Initialize indices
        indices = []
        
        # Parse V2 filter expression if provided
        if filter_expression:
            try:
                # For search, we have a special case for filtering indices
                if filter_expression.startswith('type:'):
                    # Parse for consistency with other v2 endpoints
                    parts = filter_expression.split(':')
                    if len(parts) == 3 and parts[0] == 'type':
                        operator = parts[1]
                        values = parts[2].split(',')
                        
                        if operator == 'eq' and len(values) == 1:
                            # Single type - convert to appropriate search type
                            type_value = values[0].upper()
                            if type_value == 'ARTIST' or type_value == 'LABEL' or type_value == 'EVENT':
                                search_type = type_value.lower()
                            else:
                                return jsonify({
                                    "error": f"Invalid type value in filter. Must be one of: artist, label, event"
                                }), 400
                        
                        elif operator == 'any' and len(values) >= 1:
                            # Convert to indices for GraphQL
                            search_type = 'custom'  # Custom multi-type search
                            for v in values:
                                if v.upper() in ['ARTIST', 'LABEL', 'EVENT', 'AREA', 'CLUB', 'PROMOTER']:
                                    indices.append(v.upper())
                                else:
                                    return jsonify({
                                        "error": f"Invalid type value in filter: {v}. Must be one of: artist, label, event, area, club, promoter"
                                    }), 400
                        else:
                            return jsonify({
                                "error": f"Invalid operator for type filter. Must be 'eq' or 'any'"
                            }), 400
                    else:
                        return jsonify({
                            "error": "Invalid filter syntax. Expected format: type:eq:artist or type:any:artist,event"
                        }), 400
                else:
                    return jsonify({
                        "error": "Invalid filter for search. Only 'type' filtering is supported in V2 search"
                    }), 400
            except Exception as e:
                return jsonify({
                    "error": f"Invalid filter expression: {str(e)}"
                }), 400
        
        # Perform search using the global search GraphQL operation
        # This is different from V1 search which uses separate GraphQL operations
        
        # Map standard search types to indices
        if search_type == 'all':
            indices = ["AREA", "ARTIST", "CLUB", "LABEL", "PROMOTER", "EVENT"]
        elif search_type == 'artist':
            indices = ["ARTIST"]
        elif search_type == 'label':
            indices = ["LABEL"]
        elif search_type == 'event':
            indices = ["EVENT"]
        # else: custom indices from filter already set
        
        # Use global search GraphQL operation
        try:
            payload = {
                "operationName": "GET_GLOBAL_SEARCH_RESULTS",
                "variables": {
                    "searchTerm": query,
                    "indices": indices
                },
                "query": """query GET_GLOBAL_SEARCH_RESULTS($searchTerm: String!, $indices: [IndexType!]) {
                    search(
                        searchTerm: $searchTerm
                        limit: 16
                        indices: $indices
                        includeNonLive: false
                    ) {
                        searchType
                        id
                        value
                        areaName
                        countryId
                        countryName
                        countryCode
                        contentUrl
                        imageUrl
                        score
                        clubName
                        clubContentUrl
                        date
                        __typename
                    }
                }"""
            }
            
            response = requests.post('https://ra.co/graphql', headers={
                'Content-Type': 'application/json',
                'Referer': 'https://ra.co/search',
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:106.0) Gecko/20100101 Firefox/106.0'
            }, json=payload, timeout=10)
            
            if response.status_code != 200:
                return jsonify({
                    "error": "Search failed",
                    "message": f"Search request failed with status {response.status_code}"
                }), 500
                
            data = response.json()
            
            if 'errors' in data:
                return jsonify({
                    "error": "GraphQL search error",
                    "message": str(data['errors'])
                }), 500
            
            search_results = data.get('data', {}).get('search', [])
            
            # Group results by searchType
            grouped_results = {}
            for result in search_results:
                result_type = result.get('searchType', '').lower()
                if result_type not in grouped_results:
                    grouped_results[result_type] = []
                grouped_results[result_type].append(result)
            
            return jsonify({
                "status": "success",
                "version": "v2", 
                "query": query,
                "filter": {
                    "expression": filter_expression,
                    "indices": indices,
                    "search_type": search_type
                },
                "results": grouped_results,
                "result_counts": {k: len(v) for k, v in grouped_results.items()},
                "total_results": len(search_results)
            })
            
        except Exception as e:
            return jsonify({
                "error": "Search execution failed",
                "message": str(e)
            }), 500
        
    except Exception as e:
        return jsonify({"error": "Internal server error", "message": str(e)}), 500

@app.route('/v2/artist', methods=['GET'])
def v2_artist_help():
    """V2 Artist lookup help endpoint - shows enhanced artist lookup capabilities"""
    return jsonify({
        "endpoint": "/v2/artist/{identifier} (V2 - Enhanced Artist Lookup)",
        "description": "Enhanced artist lookup with optional additional data sections",
        "supported_identifiers": {
            "slug": {
                "description": "URL-safe artist name (recommended)",
                "examples": ["daxj", "amelielens", "benklock"],
                "note": "Provides complete basic artist data"
            },
            "id": {
                "description": "Numeric artist ID",
                "examples": ["11733", "61166", "966"],
                "note": "Limited basic data - slug recommended"
            }
        },
        "include_options": {
            "description": "Optional data sections to include in response",
            "valid_options": ["stats", "booking", "labels", "related", "all"],
            "details": {
                "stats": "Artist statistics and follower data",
                "booking": "Booking and contact information",
                "labels": "Associated record labels",
                "related": "Related artists and recommendations",
                "all": "Include all available data sections"
            }
        },
        "examples": {
            "basic_slug": "/v2/artist/daxj",
            "basic_id": "/v2/artist/11733",
            "with_stats": "/v2/artist/amelielens?include=stats",
            "multiple_sections": "/v2/artist/benklock?include=stats,booking,labels",
            "all_data": "/v2/artist/amelielens?include=all"
        },
        "popular_artists": {
            "dax_j": {
                "slug": "daxj",
                "id": "11733",
                "example": "/v2/artist/daxj?include=stats,labels"
            },
            "amelie_lens": {
                "slug": "amelielens",
                "id": "61166", 
                "example": "/v2/artist/amelielens?include=booking,related"
            },
            "ben_klock": {
                "slug": "benklock",
                "id": "966",
                "example": "/v2/artist/benklock?include=all"
            }
        },
        "usage_tips": {
            "finding_artists": "Use /v2/search?q=artist_name&filter=type:eq:artist to find artist slugs",
            "identifier_preference": "Use slug when possible - provides better basic data than ID",
            "include_combinations": "Combine multiple sections: ?include=stats,booking,labels",
            "all_option": "Use ?include=all to get complete artist profile"
        },
        "response_structure": {
            "basic_fields": ["id", "name", "contentUrl", "followerCount", "image", "country"],
            "conditional_sections": {
                "stats": "Detailed statistics when include=stats",
                "booking": "Contact information when include=booking", 
                "labels": "Associated labels when include=labels",
                "related": "Related artists when include=related"
            }
        },
        "version_comparison": {
            "vs_v1": "V2 provides optional include sections and supports both slug/ID",
            "vs_v3": "V3 gives complete profile by default, V2 allows selective data retrieval"
        }
    })

@app.route('/v2/artist/<artist_identifier>', methods=['GET'])
def get_artist_v2(artist_identifier):
    """Enhanced artist endpoint with optional additional data (v2)"""
    try:
        include_param = request.args.get('include', '')
        
        # Parse include parameter
        include_options = []
        if include_param:
            include_options = [opt.strip().lower() for opt in include_param.split(',')]
        
        # Validate include options
        valid_includes = ['stats', 'booking', 'related', 'labels', 'all']
        invalid_includes = [opt for opt in include_options if opt not in valid_includes]
        
        if invalid_includes:
            return jsonify({
                "error": f"Invalid include options: {invalid_includes}",
                "valid_options": valid_includes,
                "examples": {
                    "basic": "/v2/artist/asss",
                    "with_stats": "/v2/artist/asss?include=stats",
                    "multiple": "/v2/artist/asss?include=stats,booking,related",
                    "all_data": "/v2/artist/asss?include=all"
                }
            }), 400
        
        # Handle 'all' option
        if 'all' in include_options:
            include_options = ['stats', 'booking', 'related', 'labels']
        
        # Get basic artist data - handle both slug and ID
        artist_data = None
        artist_id = None
        
        # Try as slug first, then as ID if that fails
        if not artist_identifier.isdigit():
            # It's a slug
            artist_data = get_artist_by_slug(artist_identifier)
        else:
            # It's potentially an ID - we need to get basic info first
            # RA's GraphQL doesn't have a direct "get by ID" for basic info
            # So we'll try to construct a minimal response and get the ID
            artist_id = artist_identifier
        
        # If we got data from slug, extract the ID
        if artist_data:
            artist_id = artist_data.get('id')
        elif artist_id:
            # For ID-only requests, we still need basic artist data
            # We can try the stats query which will give us the ID validation
            stats_test = get_artist_stats(artist_id)
            if not stats_test:
                return jsonify({
                    "error": "Artist not found",
                    "artist_identifier": artist_identifier,
                    "note": "Use artist slug (e.g., 'asss') for best results, or ensure ID is valid"
                }), 404
            
            # For ID-only, we have limited basic data
            artist_data = {"id": artist_id, "name": "Unknown", "note": "Limited data when using ID directly"}
        
        if not artist_id:
            return jsonify({
                "error": "Artist not found",
                "artist_identifier": artist_identifier,
                "suggestion": "Try using the artist's slug (e.g., 'asss') instead of ID"
            }), 404
        
        # Build base response with V2 structure
        response = {
            "status": "success",
            "version": "v2",
            "artist": {
                "id": artist_data.get('id'),
                "name": artist_data.get('name'),
                "content_url": artist_data.get('contentUrl'),
                "follower_count": artist_data.get('followerCount', 0),
                "image": artist_data.get('image'),
                "url_safe_name": artist_data.get('urlSafeName'),
                "country": artist_data.get('country'),
                "resident_country": artist_data.get('residentCountry'),
                "social_links": {
                    "soundcloud": artist_data.get('soundcloud'),
                    "facebook": artist_data.get('facebook'),
                    "instagram": artist_data.get('instagram'),
                    "twitter": artist_data.get('twitter'),
                    "bandcamp": artist_data.get('bandcamp'),
                    "website": artist_data.get('website'),
                    "discogs": artist_data.get('discogs')
                },
                "biography": artist_data.get('biography'),
                "events": get_artist_events(artist_id),  # Always include events
            },
            "include_info": {
                "requested": include_options,
                "available": valid_includes
            }
        }
        
        # Add optional data based on include parameters
        if 'stats' in include_options:
            stats_data = get_artist_stats(artist_id)
            if stats_data:
                response["artist"]["stats"] = {
                    "first_event": stats_data.get('firstEvent'),
                    "venues_most_played": stats_data.get('venuesMostPlayed', []),
                    "regions_most_played": stats_data.get('regionsMostPlayed', [])
                }
            else:
                response["artist"]["stats"] = {"error": "Stats data unavailable"}
        
        if 'booking' in include_options:
            about_data = get_artist_about(artist_id)
            if about_data:
                response["artist"]["booking"] = {
                    "booking_details": about_data.get('bookingDetails'),
                    "content_url": about_data.get('contentUrl')
                }
            else:
                response["artist"]["booking"] = {"error": "Booking data unavailable"}
        
        if 'related' in include_options:
            related_data = get_related_artists(artist_id)
            response["artist"]["related_artists"] = related_data
            response["artist"]["related_artists_count"] = len(related_data)
        
        if 'labels' in include_options:
            labels_data = get_artist_labels(artist_id)
            response["artist"]["labels"] = labels_data
            response["artist"]["labels_count"] = len(labels_data)
        
        # Add event count
        response["artist"]["total_events"] = len(response["artist"]["events"])
        
        return jsonify(response)
        
    except Exception as e:
        return jsonify({"error": "Internal server error", "message": str(e)}), 500

# Routes below will be removed or rewritten
# V2 artist and label endpoints have been removed since they don't provide
# actual V2 functionality beyond what's available in the V1 endpoints

@app.route('/v3/search', methods=['GET'])
def search_v3():
    """Ultimate search endpoint with advanced filtering (v3)"""
    try:
        query = request.args.get('q')
        filter_expression = request.args.get('filter')
        limit = request.args.get('limit', 50)
        
        app.logger.debug(f"V3 Search request - query: '{query}', filter: '{filter_expression}', limit: {limit}")
        
        if not query:
            return jsonify({
                "error": "Missing required parameter: q (query)",
                "required": ["q"],
                "optional": {
                    "filter": "V3 advanced filter expression (e.g., type:any:artist,event AND area:has:berlin)",
                    "limit": "Maximum number of results to return (default: 50)"
                },
                "examples": {
                    "basic_search": "/v3/search?q=charlotte",
                    "type_filtering": "/v3/search?q=techno&filter=type:any:artist,event",
                    "advanced_filtering": "/v3/search?q=party&filter=type:any:event,club AND area:has:berlin",
                    "artist_search": "/v3/search?q=charlotte&filter=type:eq:artist"
                },
                "v3_advanced_operators": {
                    "type": "Content type filtering - type:eq:artist, type:any:artist,event",
                    "area": "Area filtering - area:has:berlin, area:eq:london", 
                    "logical": "Combine with AND, OR, NOT - filter1 AND filter2"
                }
            }), 400
        
        try:
            limit = int(limit)
            if limit < 1 or limit > 100:
                return jsonify({
                    "error": "Invalid limit parameter. Must be between 1 and 100."
                }), 400
        except ValueError:
            return jsonify({
                "error": "Invalid limit parameter. Must be a number."
            }), 400
        
        # Use the AdvancedSearch class for V3 functionality
        app.logger.debug("Creating AdvancedSearch instance for V3 search")
        
        try:
            advanced_search = AdvancedSearch(
                query=query,
                filter_expression=filter_expression,
                limit=min(limit, 16)  # Use same limit as working V2
            )
            
            # Perform the advanced search
            search_results = advanced_search.search()
            
            app.logger.debug(f"AdvancedSearch returned {search_results.get('total_results', 0)} results")
            
            # Format results in V3 style response
            formatted_results = {
                "artists": [],
                "labels": [],
                "events": [],
                "clubs": [],
                "promoters": [],
                "areas": []
            }
            
            # Group results by searchType
            for result in search_results.get("results", []):
                search_type = result.get('searchType', '').lower()
                
                if search_type == 'artist':
                    formatted_results['artists'].append({
                        "id": result.get('id'),
                        "name": result.get('value'),
                        "area": result.get('areaName'),
                        "country": result.get('countryName'),
                        "content_url": result.get('contentUrl'),
                        "image_url": result.get('imageUrl'),
                        "score": result.get('score')
                    })
                elif search_type == 'label':
                    formatted_results['labels'].append({
                        "id": result.get('id'),
                        "name": result.get('value'),
                        "area": result.get('areaName'),
                        "country": result.get('countryName'),
                        "content_url": result.get('contentUrl'),
                        "image_url": result.get('imageUrl'),
                        "score": result.get('score')
                    })
                elif search_type == 'upcomingevent':
                    formatted_results['events'].append({
                        "id": result.get('id'),
                        "title": result.get('value'),
                        "date": result.get('date'),
                        "venue": {
                            "name": result.get('clubName'),
                            "content_url": result.get('clubContentUrl')
                        },
                        "area": result.get('areaName'),
                        "country": result.get('countryName'),
                        "content_url": result.get('contentUrl'),
                        "image_url": result.get('imageUrl'),
                        "score": result.get('score')
                    })
                elif search_type == 'club':
                    formatted_results['clubs'].append({
                        "id": result.get('id'),
                        "name": result.get('value'),
                        "area": result.get('areaName'),
                        "country": result.get('countryName'),
                        "content_url": result.get('contentUrl'),
                        "image_url": result.get('imageUrl'),
                        "score": result.get('score')
                    })
                elif search_type == 'promoter':
                    formatted_results['promoters'].append({
                        "id": result.get('id'),
                        "name": result.get('value'),
                        "area": result.get('areaName'),
                        "country": result.get('countryName'),
                        "content_url": result.get('contentUrl'),
                        "image_url": result.get('imageUrl'),
                        "score": result.get('score')
                    })
                elif search_type == 'area':
                    formatted_results['areas'].append({
                        "id": result.get('id'),
                        "name": result.get('value'),
                        "country": result.get('countryName'),
                        "country_code": result.get('countryCode'),
                        "content_url": result.get('contentUrl'),
                        "image_url": result.get('imageUrl'),
                        "score": result.get('score')
                    })
            
            # Build V3 response
            response = {
                "status": "success",
                "version": "v3_ultimate",
                "query": query,
                "filtering": {
                    "filter_expression": filter_expression,
                    "applied_filters": search_results.get("filter_info", {})
                },
                "results": {
                    "total": search_results.get("total_results", 0),
                    "by_type": {
                        "artists": len(formatted_results.get("artists", [])),
                        "labels": len(formatted_results.get("labels", [])),
                        "events": len(formatted_results.get("events", [])),
                        "clubs": len(formatted_results.get("clubs", [])),
                        "promoters": len(formatted_results.get("promoters", [])),
                        "areas": len(formatted_results.get("areas", []))
                    },
                    "artists": formatted_results.get("artists", []),
                    "labels": formatted_results.get("labels", []),
                    "events": formatted_results.get("events", []),
                    "clubs": formatted_results.get("clubs", []),
                    "promoters": formatted_results.get("promoters", []),
                    "areas": formatted_results.get("areas", [])
                }
            }
            
            return jsonify(response)
            
        except Exception as e:
            app.logger.exception(f"Error in AdvancedSearch: {str(e)}")
            return jsonify({"error": "Advanced search failed", "message": str(e)}), 500
        
    except Exception as e:
        app.logger.exception(f"Exception in search_v3: {str(e)}")
        return jsonify({"error": "Internal server error", "message": str(e)}), 500

@app.route('/v3/events', methods=['GET'])
def get_events_v3():
    """Ultimate events endpoint with maximum multi-value filtering flexibility (v3)"""
    try:
        # Get parameters
        area = request.args.get('area')
        country = request.args.get('country', 'au')  # Default to Australia
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        output_format = request.args.get('format', 'json').lower()
        
        # Enhanced parameters
        genre = request.args.get('genre')
        event_type = request.args.get('event_type')
        sort_by = request.args.get('sort', 'listingDate')
        include_bumps = request.args.get('include_bumps', 'true').lower() == 'true'
        filter_expression = request.args.get('filter')
        
        if not all([area, start_date, end_date]):
            return jsonify({
                "error": "Missing required parameters",
                "endpoint": "/v3/events (V3 - Advanced Filtering with Logical Operators)",
                "required": ["area", "start_date", "end_date"],
                "optional": {
                    "filter": "Advanced filter expression with logical operators (AND, OR, NOT)",
                    "genre": "Single genre (will be converted to filter expression)",
                    "event_type": "Type of event (will be converted to filter expression)",
                    "sort": "Sort order (listingDate, score, title)",
                    "include_bumps": "Include promoted events (true/false)",
                    "format": "Response format (json/csv)",
                    "country": "Country code for area lookup (e.g., au, us, uk)"
                },
                "key_features": {
                    "hybrid_processing": "Combines GraphQL native operations with client-side filtering",
                    "logical_operators": "Full support for AND, OR, NOT combinations",
                    "advanced_filtering": "15+ operators including substring matching and numeric comparisons",
                    "multi_field_filtering": "Filter on genre, artists, venue, event type, and more"
                },
                "examples": {
                    "basic_filter": "/v3/events?area=sydney&start_date=2025-08-15&end_date=2025-08-20&filter=genre:eq:techno",
                    "multi_genre_or": "/v3/events?area=melbourne&start_date=2025-08-15&end_date=2025-08-20&filter=genre:contains_any:techno,house",
                    "multi_genre_and": "/v3/events?area=perth&start_date=2025-08-15&end_date=2025-08-20&filter=genre:contains_all:techno,industrial",
                    "artist_filtering": "/v3/events?area=adelaide&start_date=2025-08-15&end_date=2025-08-20&filter=artists:has:ben",
                    "venue_filtering": "/v3/events?area=canberra&start_date=2025-08-15&end_date=2025-08-20&filter=venue:has:fabric",
                    "complex_logic": "/v3/events?area=sydney&start_date=2025-08-15&end_date=2025-08-20&filter=genre:contains_any:techno,house AND artists:has:amelie",
                    "exclusion": "/v3/events?area=melbourne&start_date=2025-08-15&end_date=2025-08-20&filter=genre:contains_none:jazz,ambient",
                    "numeric_filter": "/v3/events?area=sydney&start_date=2025-08-15&end_date=2025-08-20&filter=interested:gt:100"
                },
                "filter_operators": {
                    "basic": {
                        "eq": "Exact match - genre:eq:techno",
                        "contains_any": "Match any value (OR) - genre:contains_any:techno,house",
                        "contains_all": "Match all values (AND) - genre:contains_all:techno,industrial",
                        "contains_none": "Match none (exclusion) - genre:contains_none:jazz,ambient"
                    },
                    "text_matching": {
                        "has": "Substring match - artists:has:amelie",
                        "starts": "Starts with - title:starts:opening",
                        "ends": "Ends with - venue:ends:club"
                    },
                    "numeric": {
                        "gt": "Greater than - interested:gt:100",
                        "lt": "Less than - price:lt:50",
                        "gte": "Greater or equal - interested:gte:100",
                        "lte": "Less or equal - price:lte:50",
                        "between": "Range - price:between:20,80"
                    },
                    "array": {
                        "in": "In array (OR) - genre:in:techno,house",
                        "nin": "Not in array - genre:nin:jazz,ambient",
                        "all": "Has all (AND) - genre:all:techno,industrial"
                    }
                },
                "logical_operators": {
                    "AND": "Both conditions must be true",
                    "OR": "Either condition can be true", 
                    "NOT": "Condition must be false",
                    "example": "genre:contains_any:techno,house AND artists:has:ben NOT venue:has:jazz"
                },
                "filterable_fields": {
                    "event_content": ["genre", "artists", "venue", "eventType", "title"],
                    "timing": ["date", "startTime", "endTime"],
                    "metrics": ["interested", "price"],
                    "boolean": ["isTicketed"]
                },
                "area_support": {
                    "description": "Use area names or numeric IDs",
                    "available_areas": ["sydney", "melbourne", "perth", "canberra", "adelaide", "hobart"],
                    "usage": "?area=sydney (recommended) or ?area=1"
                },
                "date_format": "YYYY-MM-DD",
                "performance_note": "V3 uses hybrid processing - simple filters use GraphQL, complex filters use client-side processing"
            }), 400
            
        # Handle string-based area names
        area_cache_info = None
        if area and not area.isdigit():
            area_lookup = get_area_id(area, country)
            if not area_lookup:
                return jsonify({
                    "error": f"Area '{area}' not found in country '{country}'",
                    "suggestions": ["Try using a different spelling", "Use the /areas endpoint to see available areas"]
                }), 404
            
            # Store cache info for the response
            area_cache_info = {
                "cache_status": area_lookup["cache_status"],
                "cache_message": area_lookup["cache_message"],
                "lookup_key": f"{area.lower()}_{country.lower()}"
            }
            
            # Extract just the area ID for the API call
            area = area_lookup["area_id"]
            
        try:
            area = int(area)
        except (ValueError, TypeError):
            return jsonify({"error": "Invalid area parameter"}), 400
            
        try:
            datetime.strptime(start_date, '%Y-%m-%d')
            datetime.strptime(end_date, '%Y-%m-%d')
        except ValueError:
            return jsonify({"error": "Invalid date format. Use YYYY-MM-DD"}), 400
            
        # Validate sort parameter
        valid_sorts = ['listingDate', 'score', 'title']
        if sort_by not in valid_sorts:
            return jsonify({
                "error": f"Invalid sort parameter. Must be one of: {valid_sorts}"
            }), 400
        
        # Convert dates
        listing_date_gte = f"{start_date}T00:00:00.000Z"
        listing_date_lte = f"{end_date}T23:59:59.999Z"
        
        # Create ultimate advanced event fetcher
        event_fetcher = AdvancedEventFetcher(
            areas=area,
            listing_date_gte=listing_date_gte,
            listing_date_lte=listing_date_lte,
            genre=genre,
            event_type=event_type,
            sort_by=sort_by,
            include_bumps=include_bumps,
            filter_expression=filter_expression
        )
        
        # Fetch events
        events_data = event_fetcher.fetch_all_events()
        area_info = get_area_info(area_id=area)
        
        # Format area_info to match the existing API format
        formatted_area_info = None
        if area_info:
            formatted_area_info = {
                "id": area_info.get("id"),
                "name": area_info.get("name"),
                "url_name": area_info.get("urlName"),
                "country": {
                    "name": area_info.get("country", {}).get("name"),
                    "code": area_info.get("country", {}).get("urlCode")
                }
            }
        
        if output_format == 'csv':
            # CSV output
            with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.csv', encoding='utf-8') as tmp_file:
                output_file = tmp_file.name
            
            try:
                event_fetcher.save_events_to_csv(events_data, output_file)
                filename = f'ra_events_v3_{area}_{start_date}_{end_date}'
                if filter_expression:
                    # Sanitize filter expression for filename
                    filter_safe = filter_expression.replace(':', '_').replace(',', '_').replace(' ', '_')[:50]
                    filename += f'_filter_{filter_safe}'
                filename += '.csv'
                
                return send_file(output_file, as_attachment=True, 
                               download_name=filename, mimetype='text/csv')
            finally:
                if os.path.exists(output_file):
                    os.unlink(output_file)
        else:
            # JSON response
            events_json = []
            bumps_json = []
            
            # Process events
            for event_item in events_data.get("events", []):
                event = event_item.get('event', {})
                
                artists = [{"id": artist.get('id'), "name": artist.get('name')} 
                          for artist in event.get('artists', [])]
                
                events_json.append({
                    "id": event.get('id'),
                    "title": event.get('title'),
                    "date": event.get('date'),
                    "start_time": event.get('startTime'),
                    "end_time": event.get('endTime'),
                    "venue": {
                        "id": event.get('venue', {}).get('id'),
                        "name": event.get('venue', {}).get('name'),
                        "contentUrl": event.get('venue', {}).get('contentUrl')
                    },
                    "artists": artists,
                    "interested_count": event.get('interestedCount', 0),
                    "is_ticketed": event.get('isTicketed', False),
                    "content_url": event.get('contentUrl'),
                    "flyer_front": event.get('flyerFront'),
                    "is_saved": event.get('isSaved', False),
                    "is_interested": event.get('isInterested', False)
                })
            
            # Process bumps
            for bump_item in events_data.get("bumps", []):
                event = bump_item.get('event', {})
                
                artists = [{"id": artist.get('id'), "name": artist.get('name')} 
                          for artist in event.get('artists', [])]
                
                bumps_json.append({
                    "id": event.get('id'),
                    "title": event.get('title'),
                    "date": event.get('date'),
                    "start_time": event.get('startTime'),
                    "end_time": event.get('endTime'),
                    "venue": {
                        "id": event.get('venue', {}).get('id'),
                        "name": event.get('venue', {}).get('name'),
                        "contentUrl": event.get('venue', {}).get('contentUrl')
                    },
                    "artists": artists,
                    "interested_count": event.get('interestedCount', 0),
                    "is_ticketed": event.get('isTicketed', False),
                    "content_url": event.get('contentUrl'),
                    "flyer_front": event.get('flyerFront'),
                    "is_saved": event.get('isSaved', False),
                    "is_interested": event.get('isInterested', False),
                    "is_bumped": True
                })
            
            # Build response
            response = {
                "status": "success",
                "version": "v3_ultimate",
                "area": formatted_area_info,
                "date_range": {
                    "start": start_date,
                    "end": end_date
                },
                "filtering": {
                    "legacy_filters": {
                        "genre": genre,
                        "event_type": event_type,
                        "sort": sort_by,
                        "include_bumps": include_bumps
                    },
                    "ultimate_filter": filter_expression,
                    "applied_filters": events_data.get('filter_info', {}),
                    "capabilities": {
                        "multi_value_fields": ["genre", "artists", "venue", "title", "date", "time", "startTime", "endTime", "interested", "isTicketed", "price"],
                        "all_operators": ["eq", "in", "nin", "has", "contains_all", "contains_any", "contains_none", "all", "gt", "lt", "gte", "lte", "between", "starts", "ends"],
                        "logical_operators": ["AND", "OR", "NOT"]
                    }
                },
                "results": {
                    "total_events": events_data.get('total_events', 0),
                    "total_bumps": events_data.get('total_bumps', 0),
                    "events": events_json,
                    "bumped_events": bumps_json
                }
            }
            
            # Add cache info if available
            if area_cache_info:
                response["area_lookup"] = area_cache_info
            
            return jsonify(response)
        
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": "Internal server error", "message": str(e)}), 500

@app.route('/cache/areas', methods=['GET'])
def get_area_cache_status():
    """Get status and contents of the area cache"""
    try:
        from area_cache import get_cache_stats, get_all_cached_areas
        
        # Get cache statistics
        stats = get_cache_stats()
        
        # Get all cached areas
        cached_areas = get_all_cached_areas()
        
        # Build response
        response = {
            "status": "success",
            "cache_stats": stats,
            "total_cached_areas": len(cached_areas),
            "cached_areas": cached_areas
        }
        
        return jsonify(response)
        
    except Exception as e:
        return jsonify({"error": "Failed to retrieve cache information", "message": str(e)}), 500

@app.route('/cache/areas/export', methods=['GET'])
def export_cache_to_json():
    """Export the area cache to a JSON file format"""
    try:
        from area_cache import get_all_cached_areas
        
        # Get all cached areas
        cached_areas = get_all_cached_areas()
        
        # Build the export format
        export_data = {
            "cached_areas": cached_areas,
            "last_updated": datetime.now().isoformat(),
            "total_areas": len(cached_areas)
        }
        
        # Get the output format
        output_format = request.args.get('format', 'json').lower()
        
        if output_format == 'file':
            # Generate a file for download
            from flask import send_file
            import tempfile
            
            # Create a temporary file
            with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as tmp_file:
                json.dump(export_data, tmp_file, indent=2)
                tmp_path = tmp_file.name
            
            try:
                return send_file(
                    tmp_path,
                    as_attachment=True,
                    download_name='cache.json',
                    mimetype='application/json'
                )
            finally:
                # Clean up the temporary file after sending
                os.unlink(tmp_path)
        else:
            # Return JSON response
            return jsonify(export_data)
        
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": f"Failed to export cache: {str(e)}"
        }), 500

@app.route('/cache/areas/refresh', methods=['POST'])
def refresh_area_cache():
    """Manually trigger a targeted refresh of the area cache"""
    try:
        from area_cache import refresh_cache
        
        # Trigger the refresh
        result = refresh_cache()
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": f"Failed to refresh cache: {str(e)}"
        }), 500

@app.route('/cache/areas/lookup', methods=['GET'])
def lookup_area():
    """Look up an area ID by name and country"""
    try:
        area_name = request.args.get('area')
        country_code = request.args.get('country', 'au')
        
        if not area_name:
            return jsonify({
                "error": "Missing required parameter: area",
                "example": "/cache/areas/lookup?area=sydney&country=au"
            }), 400
        
        from area_cache import get_area_id, get_area_info
        
        # Look up the area ID
        area_lookup = get_area_id(area_name, country_code)
        
        if not area_lookup:
            return jsonify({
                "status": "not_found",
                "message": f"Area '{area_name}' not found in country '{country_code}'",
                "lookup_key": f"{area_name}_{country_code}".lower()
            }), 404
        
        # Get full area info
        area_info = get_area_info(area_id=area_lookup["area_id"])
        
        # Build response
        response = {
            "status": "success",
            "lookup": {
                "area_name": area_name,
                "country_code": country_code,
                "lookup_key": f"{area_name}_{country_code}".lower()
            },
            "cache_info": {
                "cache_status": area_lookup["cache_status"],
                "cache_message": area_lookup["cache_message"],
            },
            "result": {
                "area_id": area_lookup["area_id"],
                "area_info": area_info
            }
        }
        
        return jsonify(response)
        
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": f"Failed to look up area: {str(e)}"
        }), 500
    try:
        from area_cache import refresh_cache
        
        # Trigger the refresh
        result = refresh_cache()
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": f"Failed to refresh cache: {str(e)}"
        }), 500
    try:
        from area_cache import get_cache_stats, get_all_cached_areas
        
        # Get cache statistics
        stats = get_cache_stats()
        
        # Get all cached areas
        cached_areas = get_all_cached_areas()
        
        # Build response
        response = {
            "status": "success",
            "cache_stats": stats,
            "total_cached_areas": len(cached_areas),
            "cached_areas": cached_areas
        }
        
        return jsonify(response)
        
    except Exception as e:
        return jsonify({"error": "Failed to retrieve cache information", "message": str(e)}), 500
@app.route('/v3/filters', methods=['GET'])
def get_filters_v3():
    """Get available filters with V3 advanced information"""
    try:
        area = request.args.get('area')
        country = request.args.get('country', 'au')  # Default to Australia
        
        # Handle string-based area names
        area_cache_info = None
        if area and not area.isdigit():
            area_lookup = get_area_id(area, country)
            if not area_lookup:
                return jsonify({
                    "error": f"Area '{area}' not found in country '{country}'",
                    "suggestions": ["Try using a different spelling", "Use the /areas endpoint to see available areas"]
                }), 404
            
            # Store cache info for the response
            area_cache_info = {
                "cache_status": area_lookup["cache_status"],
                "cache_message": area_lookup["cache_message"],
                "lookup_key": f"{area.lower()}_{country.lower()}"
            }
            
            # Extract just the area ID for the API call
            area = area_lookup["area_id"]
                
        try:
            area = int(area or 1)  # Default to area 1 (Sydney) if not provided
        except (ValueError, TypeError):
            return jsonify({"error": "Invalid area parameter"}), 400
        
        # Use a short date range to get filter options quickly
        from datetime import timedelta
        today = datetime.now()
        tomorrow = today + timedelta(days=7)
        
        listing_date_gte = today.strftime("%Y-%m-%dT00:00:00.000Z")
        listing_date_lte = tomorrow.strftime("%Y-%m-%dT23:59:59.999Z")
        
        # Create an advanced fetcher to get filter options
        from advanced_event_fetcher import EnhancedEventFetcher as AdvancedEventFetcher
        
        event_fetcher = AdvancedEventFetcher(
            areas=area,
            listing_date_gte=listing_date_gte,
            listing_date_lte=listing_date_lte,
            include_bumps=True
        )
        
        # Fetch just one page to get filter options
        result = event_fetcher.get_events(1)
        filter_options = result.get("filter_options", {})
        area_info = get_area_info(area_id=area)
        
        # Format area_info to match the existing API format
        formatted_area_info = None
        if area_info:
            formatted_area_info = {
                "id": area_info.get("id"),
                "name": area_info.get("name"),
                "url_name": area_info.get("urlName"),
                "country": {
                    "name": area_info.get("country", {}).get("name"),
                    "code": area_info.get("country", {}).get("urlCode")
                }
            }
        
        response = {
            "version": "v3_ultimate",
            "area": formatted_area_info,
            "ultimate_features": {
                "multi_value_fields": "Support for arrays of genres, artists, venues",
                "all_operators": "Complete set of operators for maximum flexibility",
                "advanced_logic": "Complex AND/OR/NOT expressions with multi-value support",
                "artist_filtering": "Filter events by specific artists: artists:has:charlotte",
                "venue_filtering": "Filter events by venue: venue:has:fabric",
                "genre_arrays": "Events can have multiple genres, filter with contains_all/contains_any"
            },
            "available_filters": {}
        }
        
        # Add cache info if available
        if area_cache_info:
            response["area_lookup"] = area_cache_info
        
        if "genre" in filter_options:
            response["available_filters"]["genres"] = [
                {
                    "label": g.get("label"),
                    "value": g.get("value"),
                    "count": g.get("count")
                }
                for g in filter_options["genre"]
            ]
        
        if "eventType" in filter_options:
            response["available_filters"]["event_types"] = [
                {
                    "value": et.get("value"),
                    "count": et.get("count")
                }
                for et in filter_options["eventType"]
            ]
        
        response["ultimate_examples"] = {
            "multi_genre_AND": "/v3/events?area=1&start_date=2025-08-10&end_date=2025-08-17&filter=genre:contains_all:techno,industrial",
            "multi_genre_OR": "/v3/events?area=1&start_date=2025-08-10&end_date=2025-08-17&filter=genre:contains_any:techno,house,minimal",
            "artist_search": "/v3/events?area=1&start_date=2025-08-10&end_date=2025-08-17&filter=artists:has:charlotte",
            "venue_search": "/v3/events?area=1&start_date=2025-08-10&end_date=2025-08-17&filter=venue:has:fabric",
            "complex_AND": "/v3/events?area=1&start_date=2025-08-10&end_date=2025-08-17&filter=genre:contains_all:techno,industrial AND eventType:eq:club",
            "exclusion": "/v3/events?area=1&start_date=2025-08-10&end_date=2025-08-17&filter=genre:contains_none:jazz,ambient",
            "artist_genre_combo": "/v3/events?area=1&start_date=2025-08-10&end_date=2025-08-17&filter=artists:has:charlotte AND genre:contains_any:techno,minimal"
        }
        
        response["search_examples"] = {
            "basic_search": "/v3/search?q=charlotte",
            "filtered_search": "/v3/search?q=techno&filter=type:any:artist,event",
            "complex_filter": "/v3/search?q=party&filter=type:any:event,club AND area:has:berlin",
            "artist_search": "/v3/search?q=charlotte&filter=type:eq:artist"
        }
        
        response["all_operators"] = {
            "eq": "equals (exact match) - genre:eq:techno",
            "in": "in array (OR logic) - genre:in:techno,house",
            "nin": "not in array - genre:nin:jazz,ambient",
            "has": "has specific value (for multi-value fields) - artists:has:charlotte",
            "contains_all": "has ALL specified values (AND logic) - genre:contains_all:techno,industrial",
            "contains_any": "has ANY specified values (OR logic) - genre:contains_any:techno,house,minimal",
            "contains_none": "has NONE of specified values - genre:contains_none:jazz,ambient",
            "all": "has ALL values (AND) - genre:all:techno,industrial",
            "gt": "greater than - interested:gt:100",
            "lt": "less than - price:lt:20",
            "gte": "greater than or equal - interested:gte:100",
            "lte": "less than or equal - price:lte:20",
            "between": "range (inclusive) - price:between:10,30",
            "starts": "starts with - title:starts:opening",
            "ends": "ends with - venue:ends:club"
        }
        
        response["logical_operators"] = ["AND", "OR", "NOT"]
        
        response["supported_fields"] = {
            "genre": "Music genre (multi-value)",
            "artists": "Artist names (multi-value)",
            "venue": "Venue names (multi-value)",
            "eventType": "Event type (single value)",
            "area": "Geographic area (single value)",
            "title": "Event title (single value)",
            "date": "Event date (single value)",
            "time": "Event start time (single value)",
            "startTime": "Event start time (single value)",
            "endTime": "Event end time (single value)",
            "interested": "Interested count (numeric)",
            "isTicketed": "Whether event is ticketed (boolean)",
            "price": "Event price/cost (numeric)"
        }
        
        return jsonify(response)
        
    except Exception as e:
        return jsonify({"error": "Internal server error", "message": str(e)}), 500

# =============================================================================
# V3 BATCH ENDPOINTS
# =============================================================================

@app.route('/v3/artists/batch', methods=['POST'])
def batch_artists_v3():
    """Enhanced batch artist lookup endpoint (v3) with V2 include features"""
    try:
        if not request.is_json:
            return jsonify({
                "error": "Content-Type must be application/json",
                "example_request": {
                    "artist_slugs": ["asss", "dixon", "ben-klock"],
                    "include": ["stats", "labels"],
                    "include_all": False
                },
                "v2_features": "Now supports V2 include system for rich artist data",
                "note": "Artists can ONLY be looked up by slug, not ID. Use /v3/search/batch to find artist slugs."
            }), 400
        
        data = request.get_json()
        artist_slugs = data.get('artist_slugs', [])
        include_param = data.get('include', [])
        include_all = data.get('include_all', False)
        rate_limit_delay = data.get('rate_limit_delay', 0.5)
        
        if not artist_slugs:
            return jsonify({
                "error": "Missing 'artist_slugs' parameter",
                "required": ["artist_slugs"],
                "optional": {
                    "include": "Array of include options: ['stats', 'booking', 'related', 'labels']",
                    "include_all": "Boolean - get all available data (overrides include)",
                    "rate_limit_delay": "Delay between requests in seconds (default: 0.5)"
                },
                "example_requests": {
                    "basic": {
                        "artist_slugs": ["asss", "dixon"]
                    },
                    "with_includes": {
                        "artist_slugs": ["asss", "dixon"],
                        "include": ["stats", "labels", "booking"]
                    },
                    "full_data": {
                        "artist_slugs": ["asss", "dixon"],
                        "include_all": True
                    }
                },
                "v2_include_options": ["stats", "booking", "related", "labels", "all"],
                "constraints": {
                    "max_slugs": 50,
                    "format": "Array of artist slug strings"
                },
                "help": {
                    "finding_slugs": "Use /v3/search?q=artist_name&filter=type:eq:artist to find artist slugs",
                    "slug_format": "Artist slugs are usually lowercase names without spaces (e.g., 'charlotte-de-witte')"
                }
            }), 400
        
        if not isinstance(artist_slugs, list):
            return jsonify({
                "error": "Invalid 'artist_slugs' parameter - must be an array",
                "provided_type": type(artist_slugs).__name__
            }), 400
        
        if len(artist_slugs) > 50:
            return jsonify({
                "error": "Too many artist slugs. Maximum 50 allowed per batch request.",
                "provided": len(artist_slugs),
                "maximum": 50
            }), 400
        
        # Process include parameters (V2 style)
        include_options = []
        if include_all:
            include_options = ['stats', 'booking', 'related', 'labels']
        elif include_param:
            if isinstance(include_param, list):
                include_options = [opt.strip().lower() for opt in include_param]
            else:
                return jsonify({
                    "error": "Invalid 'include' parameter - must be an array",
                    "provided_type": type(include_param).__name__,
                    "valid_options": ["stats", "booking", "related", "labels"]
                }), 400
        
        # Validate include options
        valid_includes = ['stats', 'booking', 'related', 'labels']
        invalid_includes = [opt for opt in include_options if opt not in valid_includes]
        
        if invalid_includes:
            return jsonify({
                "error": f"Invalid include options: {invalid_includes}",
                "valid_options": valid_includes,
                "provided": include_options
            }), 400
        
        # Process each artist slug with V2 functionality
        results = []
        errors = []
        
        app.logger.info(f"V3 Batch processing {len(artist_slugs)} artists with includes: {include_options}")
        
        for i, artist_slug in enumerate(artist_slugs):
            try:
                app.logger.debug(f"Processing artist {i+1}/{len(artist_slugs)} (slug): {artist_slug}")
                
                # Get basic artist data using V2 approach
                artist_data = get_artist_by_slug(artist_slug)
                
                if not artist_data:
                    errors.append({
                        "artist_slug": artist_slug,
                        "batch_index": i,
                        "error": f"Artist not found",
                        "status": "not_found",
                        "suggestion": f"Try searching: /v3/search?q={artist_slug}&filter=type:eq:artist"
                    })
                    continue
                
                # Extract artist ID for additional queries
                artist_id = artist_data.get('id')
                
                # Build V2-style response structure
                result = {
                    "id": artist_data.get('id'),
                    "name": artist_data.get('name'),
                    "content_url": artist_data.get('contentUrl'),
                    "follower_count": artist_data.get('followerCount', 0),
                    "image": artist_data.get('image'),
                    "url_safe_name": artist_data.get('urlSafeName'),
                    "country": artist_data.get('country'),
                    "resident_country": artist_data.get('residentCountry'),
                    "social_links": {
                        "soundcloud": artist_data.get('soundcloud'),
                        "facebook": artist_data.get('facebook'),
                        "instagram": artist_data.get('instagram'),
                        "twitter": artist_data.get('twitter'),
                        "bandcamp": artist_data.get('bandcamp'),
                        "website": artist_data.get('website'),
                        "discogs": artist_data.get('discogs')
                    },
                    "biography": artist_data.get('biography'),
                    "events": get_artist_events(artist_id),  # Always include events
                    "batch_index": i,
                    "lookup_slug": artist_slug,
                    "status": "success"
                }
                
                # Add V2 include data based on parameters
                include_errors = []
                
                if 'stats' in include_options:
                    stats_data = get_artist_stats(artist_id)
                    if stats_data:
                        result["stats"] = {
                            "first_event": stats_data.get('firstEvent'),
                            "venues_most_played": stats_data.get('venuesMostPlayed', []),
                            "regions_most_played": stats_data.get('regionsMostPlayed', [])
                        }
                    else:
                        include_errors.append("stats")
                
                if 'booking' in include_options:
                    about_data = get_artist_about(artist_id)
                    if about_data:
                        result["booking"] = {
                            "booking_details": about_data.get('bookingDetails'),
                            "content_url": about_data.get('contentUrl')
                        }
                    else:
                        include_errors.append("booking")
                
                if 'related' in include_options:
                    related_data = get_related_artists(artist_id)
                    result["related_artists"] = related_data
                    result["related_artists_count"] = len(related_data)
                
                if 'labels' in include_options:
                    labels_data = get_artist_labels(artist_id)
                    result["labels"] = labels_data
                    result["labels_count"] = len(labels_data)
                
                # Add metadata
                result["total_events"] = len(result["events"])
                result["v2_includes_requested"] = include_options
                if include_errors:
                    result["include_errors"] = include_errors
                
                results.append(result)
                    
                # Rate limiting - configurable delay between requests
                if i < len(artist_slugs) - 1:  # Don't delay after the last request
                    time.sleep(rate_limit_delay)
                    
            except Exception as e:
                app.logger.error(f"Error processing artist {artist_slug}: {str(e)}")
                errors.append({
                    "artist_slug": artist_slug,
                    "batch_index": i,
                    "error": str(e),
                    "status": "error"
                })
        
        # Calculate processing stats
        base_queries_per_artist = 2  # get_artist_by_slug + get_artist_events
        additional_queries_per_artist = len(include_options)
        total_queries_per_artist = base_queries_per_artist + additional_queries_per_artist
        estimated_time = len(artist_slugs) * rate_limit_delay
        
        response = {
            "status": "success",
            "version": "v3_batch_enhanced",
            "batch_info": {
                "lookup_method": "slug_only_with_v2_includes",
                "requested": len(artist_slugs),
                "successful": len(results),
                "failed": len(errors),
                "v2_features": {
                    "include_options_used": include_options,
                    "include_all_mode": include_all,
                    "graphql_queries_per_artist": total_queries_per_artist,
                    "total_graphql_queries": len(results) * total_queries_per_artist
                },
                "performance": {
                    "rate_limit_delay": rate_limit_delay,
                    "estimated_processing_time": f"~{estimated_time:.1f}s",
                    "actual_delay_applied": f"{(len(artist_slugs) - 1) * rate_limit_delay:.1f}s"
                }
            },
            "artists": results,
            "errors": errors if errors else None,
            "note": "Enhanced with V2 include system. Artists can only be looked up by slug."
        }
        
        return jsonify(response)
        
    except Exception as e:
        return jsonify({"error": "Internal server error", "message": str(e)}), 500

@app.route('/v3/labels/batch', methods=['POST'])
def batch_labels_v3():
    """Batch label lookup endpoint (v3)"""
    try:
        if not request.is_json:
            return jsonify({
                "error": "Content-Type must be application/json",
                "example_request": {
                    "label_ids": ["12345", "67890", "11111"]
                }
            }), 400
        
        data = request.get_json()
        label_ids = data.get('label_ids', [])
        
        if not label_ids or not isinstance(label_ids, list):
            return jsonify({
                "error": "Missing or invalid 'label_ids' parameter",
                "required": ["label_ids"],
                "example_request": {
                    "label_ids": ["12345", "67890", "11111"]
                },
                "constraints": {
                    "max_ids": 50,
                    "format": "Array of label ID strings"
                }
            }), 400
        
        if len(label_ids) > 50:
            return jsonify({
                "error": "Too many label IDs. Maximum 50 allowed per batch request.",
                "provided": len(label_ids),
                "maximum": 50
            }), 400
        
        # Process each label ID
        results = []
        errors = []
        
        for i, label_id in enumerate(label_ids):
            try:
                app.logger.debug(f"Processing label {i+1}/{len(label_ids)}: {label_id}")
                
                label_data = get_label_by_id(label_id)
                
                if label_data:
                    # Format upcoming events
                    upcoming_events = []
                    if label_data.get('upcomingEvents', {}).get('edges'):
                        for edge in label_data['upcomingEvents']['edges']:
                            event = edge['node']
                            upcoming_events.append({
                                "id": event.get('id'),
                                "title": event.get('title'),
                                "date": event.get('date'),
                                "venue": {
                                    "id": event.get('venue', {}).get('id'),
                                    "name": event.get('venue', {}).get('name')
                                },
                                "content_url": event.get('contentUrl')
                            })
                    
                    results.append({
                        "id": label_data.get('id'),
                        "name": label_data.get('name'),
                        "description": label_data.get('description'),
                        "content_url": label_data.get('contentUrl'),
                        "images": label_data.get('images', []),
                        "upcoming_events": upcoming_events,
                        "batch_index": i,
                        "status": "success"
                    })
                else:
                    errors.append({
                        "label_id": label_id,
                        "batch_index": i,
                        "error": "Label not found",
                        "status": "not_found"
                    })
                    
                # Rate limiting - small delay between requests
                if i < len(label_ids) - 1:  # Don't delay after the last request
                    time.sleep(0.5)
                    
            except Exception as e:
                app.logger.error(f"Error processing label {label_id}: {str(e)}")
                errors.append({
                    "label_id": label_id,
                    "batch_index": i,
                    "error": str(e),
                    "status": "error"
                })
        
        response = {
            "status": "success",
            "version": "v3_batch",
            "batch_info": {
                "requested": len(label_ids),
                "successful": len(results),
                "failed": len(errors),
                "processing_time": f"~{len(label_ids) * 0.5:.1f}s estimated"
            },
            "labels": results,
            "errors": errors if errors else None
        }
        
        return jsonify(response)
        
    except Exception as e:
        return jsonify({"error": "Internal server error", "message": str(e)}), 500

@app.route('/v3/venues/batch', methods=['POST'])
def batch_venues_v3():
    """Batch venue lookup endpoint (v3)"""
    try:
        if not request.is_json:
            return jsonify({
                "error": "Content-Type must be application/json",
                "example_request": {
                    "venue_ids": ["168", "420", "123"]
                }
            }), 400
        
        data = request.get_json()
        venue_ids = data.get('venue_ids', [])
        
        if not venue_ids or not isinstance(venue_ids, list):
            return jsonify({
                "error": "Missing or invalid 'venue_ids' parameter",
                "required": ["venue_ids"],
                "example_request": {
                    "venue_ids": ["168", "420", "123"]
                },
                "constraints": {
                    "max_ids": 50,
                    "format": "Array of venue ID strings"
                }
            }), 400
        
        if len(venue_ids) > 50:
            return jsonify({
                "error": "Too many venue IDs. Maximum 50 allowed per batch request.",
                "provided": len(venue_ids),
                "maximum": 50
            }), 400
        
        # Process each venue ID
        results = []
        errors = []
        
        for i, venue_id in enumerate(venue_ids):
            try:
                app.logger.debug(f"Processing venue {i+1}/{len(venue_ids)}: {venue_id}")
                
                venue_data = get_venue_by_id(venue_id)
                
                if venue_data:
                    results.append({
                        "id": venue_data.get('id'),
                        "name": venue_data.get('name'),
                        "logoUrl": venue_data.get('logoUrl'),
                        "photo": venue_data.get('photo'),
                        "blurb": venue_data.get('blurb'),
                        "address": venue_data.get('address'),
                        "phone": venue_data.get('phone'),
                        "website": venue_data.get('website'),
                        "followerCount": venue_data.get('followerCount'),
                        "capacity": venue_data.get('capacity'),
                        "isClosed": venue_data.get('isClosed'),
                        "raSays": venue_data.get('raSays'),
                        "isFollowing": venue_data.get('isFollowing'),
                        "eventCountThisYear": venue_data.get('eventCountThisYear'),
                        "contentUrl": venue_data.get('contentUrl'),
                        "topArtists": venue_data.get('topArtists', []),
                        "area": venue_data.get('area'),
                        "batch_index": i,
                        "status": "success"
                    })
                else:
                    errors.append({
                        "venue_id": venue_id,
                        "batch_index": i,
                        "error": "Venue not found",
                        "status": "not_found"
                    })
                    
                # Rate limiting - small delay between requests
                if i < len(venue_ids) - 1:  # Don't delay after the last request
                    time.sleep(0.5)
                    
            except Exception as e:
                app.logger.error(f"Error processing venue {venue_id}: {str(e)}")
                errors.append({
                    "venue_id": venue_id,
                    "batch_index": i,
                    "error": str(e),
                    "status": "error"
                })
        
        response = {
            "status": "success",
            "version": "v3_batch",
            "batch_info": {
                "requested": len(venue_ids),
                "successful": len(results),
                "failed": len(errors),
                "processing_time": f"~{len(venue_ids) * 0.5:.1f}s estimated"
            },
            "venues": results,
            "errors": errors if errors else None
        }
        
        return jsonify(response)
        
    except Exception as e:
        return jsonify({"error": "Internal server error", "message": str(e)}), 500

@app.route('/v3/events/batch', methods=['POST'])
def batch_events_v3():
    """Batch events lookup across multiple areas endpoint (v3)"""
    try:
        if not request.is_json:
            return jsonify({
                "error": "Content-Type must be application/json",
                "example_request": {
                    "queries": [
                        {
                            "area": "sydney",
                            "start_date": "2025-08-12",
                            "end_date": "2025-08-16",
                            "filter": "genre:contains_any:techno,house"
                        },
                        {
                            "area": "melbourne",
                            "start_date": "2025-08-12", 
                            "end_date": "2025-08-16",
                            "filter": "artists:has:charlotte"
                        }
                    ]
                }
            }), 400
        
        data = request.get_json()
        queries = data.get('queries', [])
        
        if not queries or not isinstance(queries, list):
            return jsonify({
                "error": "Missing or invalid 'queries' parameter",
                "required": ["queries"],
                "example_request": {
                    "queries": [
                        {
                            "area": "sydney",
                            "start_date": "2025-08-12",
                            "end_date": "2025-08-16",
                            "filter": "genre:contains_any:techno,house"
                        }
                    ]
                },
                "constraints": {
                    "max_queries": 20,
                    "required_fields": ["area", "start_date", "end_date"],
                    "optional_fields": ["filter", "genre", "event_type", "sort_by", "include_bumps"]
                }
            }), 400
        
        if len(queries) > 20:
            return jsonify({
                "error": "Too many queries. Maximum 20 allowed per batch request.",
                "provided": len(queries),
                "maximum": 20
            }), 400
        
        # Process each query
        results = []
        errors = []
        
        for i, query in enumerate(queries):
            try:
                app.logger.debug(f"Processing events query {i+1}/{len(queries)}")
                
                # Validate required fields
                required_fields = ['area', 'start_date', 'end_date']
                missing_fields = [field for field in required_fields if field not in query]
                
                if missing_fields:
                    errors.append({
                        "query_index": i,
                        "error": f"Missing required fields: {missing_fields}",
                        "status": "validation_error"
                    })
                    continue
                
                # Extract parameters
                area = query.get('area')
                start_date = query.get('start_date')
                end_date = query.get('end_date')
                filter_expression = query.get('filter')
                genre = query.get('genre')
                event_type = query.get('event_type')
                sort_by = query.get('sort_by', 'listingDate')
                include_bumps = query.get('include_bumps', False)
                country = query.get('country', 'au')
                
                # Handle area name lookup
                area_cache_info = None
                if area and not area.isdigit():
                    area_lookup = get_area_id(area, country)
                    if not area_lookup:
                        errors.append({
                            "query_index": i,
                            "error": f"Area '{area}' not found in country '{country}'",
                            "status": "area_not_found"
                        })
                        continue
                    
                    area_cache_info = area_lookup
                    area = area_lookup["area_id"]
                
                try:
                    area = int(area)
                except (ValueError, TypeError):
                    errors.append({
                        "query_index": i,
                        "error": "Invalid area parameter",
                        "status": "validation_error"
                    })
                    continue
                
                # Validate dates
                try:
                    datetime.strptime(start_date, '%Y-%m-%d')
                    datetime.strptime(end_date, '%Y-%m-%d')
                except ValueError:
                    errors.append({
                        "query_index": i,
                        "error": "Invalid date format. Use YYYY-MM-DD",
                        "status": "validation_error"
                    })
                    continue
                
                # Convert dates
                listing_date_gte = f"{start_date}T00:00:00.000Z"
                listing_date_lte = f"{end_date}T23:59:59.999Z"
                
                # Create advanced event fetcher
                event_fetcher = AdvancedEventFetcher(
                    areas=area,
                    listing_date_gte=listing_date_gte,
                    listing_date_lte=listing_date_lte,
                    genre=genre,
                    event_type=event_type,
                    sort_by=sort_by,
                    include_bumps=include_bumps,
                    filter_expression=filter_expression
                )
                
                # Fetch events
                events_data = event_fetcher.fetch_all_events()
                area_info = get_area_info(area_id=area)
                
                # Format area_info
                formatted_area_info = None
                if area_info:
                    formatted_area_info = {
                        "id": area_info.get("id"),
                        "name": area_info.get("name"),
                        "url_name": area_info.get("urlName"),
                        "country": {
                            "name": area_info.get("country", {}).get("name"),
                            "code": area_info.get("country", {}).get("urlCode")
                        }
                    }
                
                results.append({
                    "query_index": i,
                    "query_params": {
                        "area": area,
                        "start_date": start_date,
                        "end_date": end_date,
                        "filter": filter_expression,
                        "genre": genre,
                        "event_type": event_type,
                        "sort_by": sort_by
                    },
                    "area_info": formatted_area_info,
                    "area_cache_info": area_cache_info,
                    "events": events_data.get("events", []),
                    "total_events": len(events_data.get("events", [])),
                    "filter_info": events_data.get("filter_info", {}),
                    "status": "success"
                })
                
                # Rate limiting - delay between queries
                if i < len(queries) - 1:  # Don't delay after the last request
                    time.sleep(1.0)  # Longer delay for event queries as they're more complex
                    
            except Exception as e:
                app.logger.error(f"Error processing events query {i}: {str(e)}")
                errors.append({
                    "query_index": i,
                    "error": str(e),
                    "status": "error"
                })
        
        # Calculate total events across all queries
        total_events = sum(result.get("total_events", 0) for result in results)
        
        response = {
            "status": "success",
            "version": "v3_batch",
            "batch_info": {
                "requested_queries": len(queries),
                "successful_queries": len(results),
                "failed_queries": len(errors),
                "total_events_found": total_events,
                "processing_time": f"~{len(queries) * 1.0:.1f}s estimated"
            },
            "results": results,
            "errors": errors if errors else None
        }
        
        return jsonify(response)
        
    except Exception as e:
        return jsonify({"error": "Internal server error", "message": str(e)}), 500

@app.route('/v3/search/batch', methods=['POST'])
def batch_search_v3():
    """Batch search across multiple queries endpoint (v3)"""
    try:
        if not request.is_json:
            return jsonify({
                "error": "Content-Type must be application/json",
                "example_request": {
                    "queries": [
                        {
                            "q": "charlotte",
                            "filter": "type:eq:artist"
                        },
                        {
                            "q": "techno",
                            "filter": "type:any:artist,event"
                        },
                        {
                            "q": "berlin",
                            "filter": "type:eq:area"
                        }
                    ]
                }
            }), 400
        
        data = request.get_json()
        queries = data.get('queries', [])
        
        if not queries or not isinstance(queries, list):
            return jsonify({
                "error": "Missing or invalid 'queries' parameter",
                "required": ["queries"],
                "example_request": {
                    "queries": [
                        {
                            "q": "charlotte",
                            "filter": "type:eq:artist"
                        },
                        {
                            "q": "techno",
                            "filter": "type:any:artist,event"
                        }
                    ]
                },
                "constraints": {
                    "max_queries": 30,
                    "required_fields": ["q"],
                    "optional_fields": ["filter", "limit"]
                }
            }), 400
        
        if len(queries) > 30:
            return jsonify({
                "error": "Too many queries. Maximum 30 allowed per batch request.",
                "provided": len(queries),
                "maximum": 30
            }), 400
        
        # Process each search query
        results = []
        errors = []
        
        for i, query in enumerate(queries):
            try:
                app.logger.debug(f"Processing search query {i+1}/{len(queries)}")
                
                # Validate required fields
                if 'q' not in query:
                    errors.append({
                        "query_index": i,
                        "error": "Missing required field: q (query)",
                        "status": "validation_error"
                    })
                    continue
                
                # Extract parameters
                search_query = query.get('q')
                filter_expression = query.get('filter')
                limit = query.get('limit', 50)
                
                # Validate limit
                try:
                    limit = int(limit)
                    if limit < 1 or limit > 100:
                        errors.append({
                            "query_index": i,
                            "error": "Invalid limit parameter. Must be between 1 and 100.",
                            "status": "validation_error"
                        })
                        continue
                except ValueError:
                    errors.append({
                        "query_index": i,
                        "error": "Invalid limit parameter. Must be a number.",
                        "status": "validation_error"
                    })
                    continue
                
                # Use the AdvancedSearch class for V3 functionality
                advanced_search = AdvancedSearch(
                    query=search_query,
                    filter_expression=filter_expression,
                    limit=min(limit, 16)  # Use same limit as working V2
                )
                
                # Perform the advanced search
                search_results = advanced_search.search()
                
                # Format results in V3 style response
                formatted_results = {
                    "artists": [],
                    "labels": [],
                    "events": [],
                    "clubs": [],
                    "promoters": [],
                    "areas": []
                }
                
                # Group results by searchType
                for result in search_results.get("results", []):
                    search_type = result.get('searchType', '').lower()
                    
                    if search_type == 'artist':
                        formatted_results['artists'].append({
                            "id": result.get('id'),
                            "name": result.get('value'),
                            "area": result.get('areaName'),
                            "country": result.get('countryName'),
                            "content_url": result.get('contentUrl'),
                            "image_url": result.get('imageUrl'),
                            "score": result.get('score')
                        })
                    elif search_type == 'label':
                        formatted_results['labels'].append({
                            "id": result.get('id'),
                            "name": result.get('value'),
                            "area": result.get('areaName'),
                            "country": result.get('countryName'),
                            "content_url": result.get('contentUrl'),
                            "image_url": result.get('imageUrl'),
                            "score": result.get('score')
                        })
                    elif search_type == 'upcomingevent':
                        formatted_results['events'].append({
                            "id": result.get('id'),
                            "title": result.get('value'),
                            "date": result.get('date'),
                            "venue": {
                                "name": result.get('clubName'),
                                "content_url": result.get('clubContentUrl')
                            },
                            "area": result.get('areaName'),
                            "country": result.get('countryName'),
                            "content_url": result.get('contentUrl'),
                            "image_url": result.get('imageUrl'),
                            "score": result.get('score')
                        })
                    elif search_type == 'club':
                        formatted_results['clubs'].append({
                            "id": result.get('id'),
                            "name": result.get('value'),
                            "area": result.get('areaName'),
                            "country": result.get('countryName'),
                            "content_url": result.get('contentUrl'),
                            "image_url": result.get('imageUrl'),
                            "score": result.get('score')
                        })
                    elif search_type == 'promoter':
                        formatted_results['promoters'].append({
                            "id": result.get('id'),
                            "name": result.get('value'),
                            "area": result.get('areaName'),
                            "country": result.get('countryName'),
                            "content_url": result.get('contentUrl'),
                            "image_url": result.get('imageUrl'),
                            "score": result.get('score')
                        })
                    elif search_type == 'area':
                        formatted_results['areas'].append({
                            "id": result.get('id'),
                            "name": result.get('value'),
                            "country": result.get('countryName'),
                            "country_code": result.get('countryCode'),
                            "content_url": result.get('contentUrl'),
                            "image_url": result.get('imageUrl'),
                            "score": result.get('score')
                        })
                
                results.append({
                    "query_index": i,
                    "query_params": {
                        "q": search_query,
                        "filter": filter_expression,
                        "limit": limit
                    },
                    "filtering": {
                        "filter_expression": filter_expression,
                        "applied_filters": search_results.get("filter_info", {})
                    },
                    "results": {
                        "total": search_results.get("total_results", 0),
                        "by_type": {
                            "artists": len(formatted_results.get("artists", [])),
                            "labels": len(formatted_results.get("labels", [])),
                            "events": len(formatted_results.get("events", [])),
                            "clubs": len(formatted_results.get("clubs", [])),
                            "promoters": len(formatted_results.get("promoters", [])),
                            "areas": len(formatted_results.get("areas", []))
                        },
                        "data": formatted_results
                    },
                    "status": "success"
                })
                
                # Rate limiting - delay between queries
                if i < len(queries) - 1:  # Don't delay after the last request
                    time.sleep(0.7)  # Moderate delay for search queries
                    
            except Exception as e:
                app.logger.error(f"Error processing search query {i}: {str(e)}")
                errors.append({
                    "query_index": i,
                    "error": str(e),
                    "status": "error"
                })
        
        # Calculate aggregate statistics
        total_results = sum(result.get("results", {}).get("total", 0) for result in results)
        total_by_type = {
            "artists": sum(result.get("results", {}).get("by_type", {}).get("artists", 0) for result in results),
            "labels": sum(result.get("results", {}).get("by_type", {}).get("labels", 0) for result in results),
            "events": sum(result.get("results", {}).get("by_type", {}).get("events", 0) for result in results),
            "clubs": sum(result.get("results", {}).get("by_type", {}).get("clubs", 0) for result in results),
            "promoters": sum(result.get("results", {}).get("by_type", {}).get("promoters", 0) for result in results),
            "areas": sum(result.get("results", {}).get("by_type", {}).get("areas", 0) for result in results)
        }
        
        response = {
            "status": "success",
            "version": "v3_batch",
            "batch_info": {
                "requested_queries": len(queries),
                "successful_queries": len(results),
                "failed_queries": len(errors),
                "total_results_found": total_results,
                "aggregate_by_type": total_by_type,
                "processing_time": f"~{len(queries) * 0.7:.1f}s estimated"
            },
            "results": results,
            "errors": errors if errors else None
        }
        
        return jsonify(response)
        
    except Exception as e:
        return jsonify({"error": "Internal server error", "message": str(e)}), 500

if __name__ == '__main__':
    # Initialize the area cache system
    print("Initializing area cache system...")
    initialize_area_cache()
    
    # Debug: Print all registered routes
    print("Registered routes:")
    for rule in app.url_map.iter_rules():
        print(f"  {rule.rule} -> {rule.endpoint}")
    
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=True)
