from flask import Flask, request, jsonify, send_file
import os
import tempfile
import json
import requests
from datetime import datetime
from event_fetcher import EventFetcher

app = Flask(__name__)

def get_area_id_from_name(area_name):
    """
    Find area ID by searching through common area codes
    This is a simple approach - we test known area codes to find a match
    """
    try:
        # Clean the area name for comparison
        clean_name = area_name.lower().strip().replace('-', '').replace('_', '').replace(' ', '')
        
        # Test area codes 1-20 first (most common cities)
        for area_id in range(1, 21):
            area_info = get_area_info(area_id)
            if area_info and area_info.get('name'):
                # Compare cleaned names
                api_name = area_info['name'].lower().replace('-', '').replace('_', '').replace(' ', '')
                url_name = area_info.get('url_name', '').lower().replace('-', '').replace('_', '').replace(' ', '')
                
                if clean_name in api_name or clean_name in url_name or api_name in clean_name:
                    return area_id
        
        # Test some known higher numbers
        for area_id in [433, 674]:  # NSW, Byron Bay
            area_info = get_area_info(area_id)
            if area_info and area_info.get('name'):
                api_name = area_info['name'].lower().replace('-', '').replace('_', '').replace(' ', '')
                url_name = area_info.get('url_name', '').lower().replace('-', '').replace('_', '').replace(' ', '')
                
                if clean_name in api_name or clean_name in url_name or api_name in clean_name:
                    return area_id
                    
        return None
        
    except Exception as e:
        print(f"Error finding area ID for {area_name}: {e}")
        return None

def get_area_info(area_id):
    """
    Get area name and country info using RA's GraphQL API
    """
    try:
        url = 'https://ra.co/graphql'
        headers = {
            'Content-Type': 'application/json',
            'Referer': 'https://ra.co/events',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:106.0) Gecko/20100101 Firefox/106.0'
        }
        
        payload = {
            "operationName": "GET_AREA_INFO",
            "variables": {
                "areaId": str(area_id)
            },
            "query": """query GET_AREA_INFO($areaId: ID!) {
                area(id: $areaId) {
                    id
                    name
                    urlName
                    country {
                        name
                        urlCode
                    }
                }
            }"""
        }
        
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if 'data' in data and data['data']['area']:
                area_data = data['data']['area']
                return {
                    "id": area_data.get("id"),
                    "name": area_data.get("name"),
                    "url_name": area_data.get("urlName"),
                    "country": {
                        "name": area_data.get("country", {}).get("name"),
                        "code": area_data.get("country", {}).get("urlCode")
                    }
                }
        
        return None
        
    except Exception as e:
        print(f"Error getting area info for {area_id}: {e}")
        return None

def search_global(search_term, indices=None):
    """
    Search RA using the global search functionality
    """
    try:
        if indices is None:
            indices = ["AREA","ARTIST","CLUB","LABEL","PROMOTER","EVENT"]
            
        payload = {
            "operationName": "GET_GLOBAL_SEARCH_RESULTS",
            "variables": {
                "searchTerm": search_term,
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
            'Referer': 'https://ra.co/',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:106.0) Gecko/20100101 Firefox/106.0'
        }, json=payload, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            return data.get('data', {}).get('search', [])
        return []
        
    except Exception as e:
        print(f"Error in global search: {e}")
        return []

def get_artist_by_slug(slug):
    """
    Get comprehensive artist information by slug
    """
    try:
        payload = {
            "operationName": "GET_ARTIST_BY_SLUG",
            "variables": {"slug": slug},
            "query": """query GET_ARTIST_BY_SLUG($slug: String!) {
                artist(slug: $slug) {
                    id
                    name
                    followerCount
                    firstName
                    lastName
                    aliases
                    isFollowing
                    coverImage
                    contentUrl
                    facebook
                    soundcloud
                    instagram
                    twitter
                    bandcamp
                    discogs
                    website
                    urlSafeName
                    pronouns
                    country {
                        id
                        name
                        urlCode
                        __typename
                    }
                    residentCountry {
                        id
                        name
                        urlCode
                        __typename
                    }
                    news(limit: 1) {
                        id
                        __typename
                    }
                    reviews(limit: 1, type: ALLMUSIC) {
                        id
                        __typename
                    }
                    ...biographyFields
                    __typename
                }
            }
            
            fragment biographyFields on Artist {
                id
                name
                contentUrl
                image
                biography {
                    id
                    blurb
                    content
                    discography
                    __typename
                }
                __typename
            }"""
        }
        
        response = requests.post('https://ra.co/graphql', headers={
            'Content-Type': 'application/json',
            'Referer': 'https://ra.co/',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:106.0) Gecko/20100101 Firefox/106.0'
        }, json=payload, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            return data.get('data', {}).get('artist')
        return None
        
    except Exception as e:
        print(f"Error getting artist {slug}: {e}")
        return None

@app.route('/', methods=['GET'])
def health_check():
    return jsonify({
        "status": "healthy", 
        "message": "RA Events & Artists API",
        "endpoints": {
            "events": {
                "description": "Get events by area and date range",
                "examples": [
                    "/events?area=1&start_date=2025-08-10&end_date=2025-08-17",
                    "/events?area_name=sydney&start_date=2025-08-10&end_date=2025-08-17&format=csv"
                ]
            },
            "areas": "/areas",
            "search": {
                "global": "/search?q={term}&type={artist|label|club|event}",
                "artists": "/artist/search?q={name}",
                "labels": "/label/search?q={name}"
            },
            "artists": {
                "profile": "/artist/{slug}",
                "stats": "/artist/{slug}/stats",
                "related": "/artist/{slug}/related", 
                "labels": "/artist/{slug}/labels"
            },
            "labels": {
                "profile": "/label/{id}",
                "artists": "/label/{id}/artists",
                "reviews": "/label/{id}/reviews"
            },
            "reviews": {
                "popular": "/reviews/popular?days={number}"
            }
        }
    })

@app.route('/events', methods=['GET'])
def get_events():
    """
    Fetch events from Resident Advisor
    Query parameters:
    - area: Area code (required) OR area_name: Area name like 'sydney', 'melbourne'
    - start_date: Start date YYYY-MM-DD (required) 
    - end_date: End date YYYY-MM-DD (required)
    - format: 'csv' or 'json' (optional, default: json)
    """
    try:
        # Get query parameters
        area = request.args.get('area')
        area_name = request.args.get('area_name')
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        output_format = request.args.get('format', 'json').lower()
        
        # Must have either area or area_name
        if not (area or area_name) or not all([start_date, end_date]):
            return jsonify({
                "error": "Missing required parameters",
                "required": ["area OR area_name", "start_date", "end_date"],
                "examples": [
                    "/events?area=1&start_date=2025-08-10&end_date=2025-08-17",
                    "/events?area_name=sydney&start_date=2025-08-10&end_date=2025-08-17"
                ]
            }), 400
        
        # If area_name provided, get the area ID
        if area_name and not area:
            area = get_area_id_from_name(area_name)
            if area is None:
                return jsonify({
                    "error": f"Could not find area ID for '{area_name}'",
                    "suggestion": "Try area names like 'sydney', 'melbourne', 'adelaide', 'perth'"
                }), 404
            
        # Validate area is numeric
        try:
            area = int(area)
        except ValueError:
            return jsonify({"error": "Area must be a number"}), 400
            
        # Validate date format
        try:
            datetime.strptime(start_date, '%Y-%m-%d')
            datetime.strptime(end_date, '%Y-%m-%d')
        except ValueError:
            return jsonify({
                "error": "Invalid date format. Use YYYY-MM-DD"
            }), 400
            
        # Convert dates to GraphQL format
        listing_date_gte = f"{start_date}T00:00:00.000Z"
        listing_date_lte = f"{end_date}T23:59:59.999Z"
        
        # Create event fetcher and get events
        event_fetcher = EventFetcher(area, listing_date_gte, listing_date_lte)
        events = event_fetcher.fetch_all_events()
        
        # Get area information from GraphQL
        area_info = get_area_info(area)
        
        if output_format == 'csv':
            # Create temporary CSV file
            with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.csv', encoding='utf-8') as tmp_file:
                output_file = tmp_file.name
            
            try:
                event_fetcher.save_events_to_csv(events, output_file)
                return send_file(
                    output_file, 
                    as_attachment=True, 
                    download_name=f'ra_events_{area}_{start_date}_{end_date}.csv',
                    mimetype='text/csv'
                )
            finally:
                # Clean up temp file after sending
                if os.path.exists(output_file):
                    os.unlink(output_file)
        else:
            # Return JSON response
            events_json = []
            for event in events:
                event_data = event["event"]
                events_json.append({
                    "id": event_data.get("id"),
                    "title": event_data.get("title"),
                    "date": event_data.get("date"),
                    "start_time": event_data.get("startTime"),
                    "end_time": event_data.get("endTime"),
                    "artists": [artist.get("name") for artist in event_data.get("artists", [])],
                    "venue": {
                        "name": event_data.get("venue", {}).get("name"),
                        "url": event_data.get("venue", {}).get("contentUrl")
                    },
                    "event_url": event_data.get("contentUrl"),
                    "attending": event_data.get("attending"),
                    "is_ticketed": event_data.get("isTicketed"),
                    "flyer_front": event_data.get("flyerFront")
                })
            
            return jsonify({
                "area": area_info if area_info else {"id": area, "name": "Unknown"},
                "start_date": start_date,
                "end_date": end_date,
                "count": len(events_json),
                "events": events_json
            })
                
    except Exception as e:
        return jsonify({
            "error": "Internal server error", 
            "message": str(e)
        }), 500

@app.route('/areas', methods=['GET'])
def list_areas():
    """
    Return discovered RA area codes with names from GraphQL API
    """
    discovered_areas = {}
    
    # Test known area codes and get their names dynamically
    known_codes = [1, 2, 3, 4, 5, 6, 8, 433, 674]
    
    for area_id in known_codes:
        area_info = get_area_info(area_id)
        if area_info:
            discovered_areas[str(area_id)] = f"{area_info['name']}, {area_info['country']['code']}"
    
    return jsonify({
        "message": "Resident Advisor area codes",
        "areas": discovered_areas,
        "usage": {
            "by_code": "/events?area=1&start_date=2025-08-10&end_date=2025-08-17",
            "by_name": "/events?area_name=sydney&start_date=2025-08-10&end_date=2025-08-17"
        }
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=False)


def get_artist_stats(artist_id):
    """
    Get artist performance statistics
    """
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
            'Referer': 'https://ra.co/',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:106.0) Gecko/20100101 Firefox/106.0'
        }, json=payload, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            return data.get('data', {}).get('artist')
        return None
        
    except Exception as e:
        print(f"Error getting artist stats: {e}")
        return None

def get_related_artists(artist_id):
    """
    Get related artists for discovery
    """
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
            'Referer': 'https://ra.co/',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:106.0) Gecko/20100101 Firefox/106.0'
        }, json=payload, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            return data.get('data', {}).get('artist', {}).get('relatedArtists', [])
        return []
        
    except Exception as e:
        print(f"Error getting related artists: {e}")
        return []

def get_artist_labels(artist_id):
    """
    Get labels associated with an artist
    """
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
            'Referer': 'https://ra.co/',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:106.0) Gecko/20100101 Firefox/106.0'
        }, json=payload, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            return data.get('data', {}).get('artist', {}).get('labels', [])
        return []
        
    except Exception as e:
        print(f"Error getting artist labels: {e}")
        return []

def get_label_info(label_id):
    """
    Get comprehensive label information
    """
    try:
        payload = {
            "operationName": "GET_LABEL",
            "variables": {"id": str(label_id)},
            "query": """query GET_LABEL($id: ID!) {
                label(id: $id) {
                    id
                    name
                    imageUrl
                    contentUrl
                    imageLarge
                    blurb
                    facebook
                    discogs
                    soundcloud
                    link
                    twitter
                    dateEstablished
                    followerCount
                    isFollowing
                    area {
                        id
                        name
                        country {
                            id
                            name
                            urlCode
                            __typename
                        }
                        __typename
                    }
                    reviews(limit: 200, excludeIds: []) {
                        id
                        date
                        title
                        blurb
                        contentUrl
                        imageUrl
                        recommended
                        __typename
                    }
                    artists(limit: 100) {
                        id
                        name
                        contentUrl
                        image
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
            'Referer': 'https://ra.co/',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:106.0) Gecko/20100101 Firefox/106.0'
        }, json=payload, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            return data.get('data', {}).get('label')
        return None
        
    except Exception as e:
        print(f"Error getting label {label_id}: {e}")
        return None

def get_popular_reviews(date_from=None, date_to=None):
    """
    Get popular music reviews
    """
    try:
        from datetime import datetime, timedelta
        
        if not date_from:
            date_from = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%S.000Z")
        if not date_to:
            date_to = datetime.now().strftime("%Y-%m-%d")
            
        payload = {
            "operationName": "GET_POPULAR_REVIEWS",
            "variables": {
                "dateFrom": date_from,
                "dateTo": date_to
            },
            "query": """query GET_POPULAR_REVIEWS($dateFrom: DateTime, $dateTo: DateTime) {
                reviews(
                    limit: 10
                    type: ALL
                    orderBy: POPULAR
                    dateFrom: $dateFrom
                    dateTo: $dateTo
                ) {
                    id
                    title
                    imageUrl
                    contentUrl
                    blurb
                    date
                    recommended
                    labels {
                        id
                        name
                        contentUrl
                        live
                        __typename
                    }
                    __typename
                }
            }"""
        }
        
        response = requests.post('https://ra.co/graphql', headers={
            'Content-Type': 'application/json',
            'Referer': 'https://ra.co/',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:106.0) Gecko/20100101 Firefox/106.0'
        }, json=payload, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            return data.get('data', {}).get('reviews', [])
        return []
        
    except Exception as e:
        print(f"Error getting popular reviews: {e}")
        return []


# ============ SEARCH ENDPOINTS ============

@app.route('/search', methods=['GET'])
def global_search():
    """
    Global search across RA database
    Query parameters:
    - q: Search term (required)
    - type: Filter by type (optional) - artist, label, club, event, area, promoter
    """
    try:
        search_term = request.args.get('q')
        search_type = request.args.get('type', '').upper()
        
        if not search_term:
            return jsonify({
                "error": "Missing search term",
                "usage": "/search?q=charlotte+de+witte&type=artist"
            }), 400
            
        # Map type filter to indices
        type_mapping = {
            'ARTIST': ['ARTIST'],
            'LABEL': ['LABEL'], 
            'CLUB': ['CLUB'],
            'EVENT': ['EVENT'],
            'AREA': ['AREA'],
            'PROMOTER': ['PROMOTER']
        }
        
        indices = type_mapping.get(search_type, ["AREA","ARTIST","CLUB","LABEL","PROMOTER","EVENT"])
        results = search_global(search_term, indices)
        
        # Group results by type
        grouped_results = {}
        for result in results:
            result_type = result['searchType'].lower()
            if result_type not in grouped_results:
                grouped_results[result_type] = []
            grouped_results[result_type].append({
                "id": result['id'],
                "name": result['value'],
                "url": result['contentUrl'],
                "image": result.get('imageUrl'),
                "country": result.get('countryName'),
                "score": result['score']
            })
            
        return jsonify({
            "search_term": search_term,
            "results": grouped_results,
            "total_results": len(results)
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ============ ARTIST ENDPOINTS ============

@app.route('/artist/search', methods=['GET'])
def search_artists():
    """
    Search for artists specifically
    Query parameters:
    - q: Artist name or style term (required)
    """
    try:
        search_term = request.args.get('q')
        if not search_term:
            return jsonify({
                "error": "Missing search term",
                "usage": "/artist/search?q=charlotte+de+witte"
            }), 400
            
        results = search_global(search_term, ["ARTIST"])
        artists = []
        
        for result in results:
            if result['searchType'] == 'ARTIST':
                # Extract slug from contentUrl
                slug = result['contentUrl'].split('/')[-1] if result['contentUrl'] else None
                artists.append({
                    "id": result['id'],
                    "name": result['value'],
                    "slug": slug,
                    "url": result['contentUrl'],
                    "image": result.get('imageUrl'),
                    "country": result.get('countryName'),
                    "score": result['score']
                })
                
        return jsonify({
            "search_term": search_term,
            "artists": artists,
            "count": len(artists)
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/artist/<slug>', methods=['GET'])
def get_artist_profile(slug):
    """
    Get comprehensive artist profile by slug
    """
    try:
        artist = get_artist_by_slug(slug)
        if not artist:
            return jsonify({"error": f"Artist '{slug}' not found"}), 404
            
        # Clean and structure the response
        profile = {
            "id": artist.get('id'),
            "name": artist.get('name'),
            "aliases": artist.get('aliases'),
            "pronouns": artist.get('pronouns'),
            "follower_count": artist.get('followerCount'),
            "image": artist.get('coverImage'),
            "bio": {
                "blurb": artist.get('biography', {}).get('blurb'),
                "content": artist.get('biography', {}).get('content'),
                "discography": artist.get('biography', {}).get('discography')
            },
            "social": {
                "facebook": artist.get('facebook'),
                "soundcloud": artist.get('soundcloud'),
                "instagram": artist.get('instagram'),
                "twitter": artist.get('twitter'),
                "bandcamp": artist.get('bandcamp'),
                "discogs": artist.get('discogs'),
                "website": artist.get('website')
            },
            "location": {
                "country": artist.get('country', {}).get('name') if artist.get('country') else None,
                "country_code": artist.get('country', {}).get('urlCode') if artist.get('country') else None,
                "resident_country": artist.get('residentCountry', {}).get('name') if artist.get('residentCountry') else None
            },
            "ra_url": f"https://ra.co{artist.get('contentUrl', '')}"
        }
        
        return jsonify(profile)
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/artist/<slug>/stats', methods=['GET'])
def get_artist_statistics(slug):
    """
    Get artist performance statistics
    """
    try:
        # First get the artist to get their ID
        artist = get_artist_by_slug(slug)
        if not artist:
            return jsonify({"error": f"Artist '{slug}' not found"}), 404
            
        stats = get_artist_stats(artist['id'])
        if not stats:
            return jsonify({"error": "Stats not available"}), 404
            
        return jsonify({
            "artist_id": stats.get('id'),
            "career_start": stats.get('firstEvent', {}).get('date') if stats.get('firstEvent') else None,
            "top_venues": [
                {
                    "id": venue['id'],
                    "name": venue['name'], 
                    "url": venue['contentUrl']
                } for venue in stats.get('venuesMostPlayed', [])
            ],
            "top_regions": [
                {
                    "id": region['id'],
                    "name": region['name'],
                    "country": region.get('country', {}).get('name'),
                    "url_name": region['urlName']
                } for region in stats.get('regionsMostPlayed', [])
            ]
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/artist/<slug>/related', methods=['GET'])
def get_artist_related(slug):
    """
    Get related artists for music discovery
    """
    try:
        # First get the artist to get their ID
        artist = get_artist_by_slug(slug)
        if not artist:
            return jsonify({"error": f"Artist '{slug}' not found"}), 404
            
        related = get_related_artists(artist['id'])
        
        related_artists = []
        for artist_data in related:
            # Extract slug from contentUrl
            artist_slug = artist_data['contentUrl'].split('/')[-1] if artist_data['contentUrl'] else None
            related_artists.append({
                "id": artist_data['id'],
                "name": artist_data['name'],
                "slug": artist_slug,
                "url": artist_data['contentUrl'],
                "image": artist_data.get('image'),
                "follower_count": artist_data.get('followerCount')
            })
            
        return jsonify({
            "artist": {"name": artist['name'], "slug": slug},
            "related_artists": related_artists,
            "count": len(related_artists)
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/artist/<slug>/labels', methods=['GET'])
def get_artist_label_info(slug):
    """
    Get labels associated with an artist
    """
    try:
        # First get the artist to get their ID
        artist = get_artist_by_slug(slug)
        if not artist:
            return jsonify({"error": f"Artist '{slug}' not found"}), 404
            
        labels = get_artist_labels(artist['id'])
        
        label_list = []
        for label in labels:
            label_list.append({
                "id": label['id'],
                "name": label['name'],
                "url": label['contentUrl'],
                "image": label.get('imageUrl'),
                "follower_count": label.get('followerCount')
            })
            
        return jsonify({
            "artist": {"name": artist['name'], "slug": slug},
            "labels": label_list,
            "count": len(label_list)
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ============ LABEL ENDPOINTS ============

@app.route('/label/search', methods=['GET'])
def search_labels():
    """
    Search for record labels
    Query parameters:
    - q: Label name or style term (required)
    """
    try:
        search_term = request.args.get('q')
        if not search_term:
            return jsonify({
                "error": "Missing search term",
                "usage": "/label/search?q=drumcode"
            }), 400
            
        results = search_global(search_term, ["LABEL"])
        labels = []
        
        for result in results:
            if result['searchType'] == 'LABEL':
                labels.append({
                    "id": result['id'],
                    "name": result['value'],
                    "url": result['contentUrl'],
                    "image": result.get('imageUrl'),
                    "country": result.get('countryName'),
                    "score": result['score']
                })
                
        return jsonify({
            "search_term": search_term,
            "labels": labels,
            "count": len(labels)
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/label/<label_id>', methods=['GET'])
def get_label_profile(label_id):
    """
    Get comprehensive label information
    """
    try:
        label = get_label_info(label_id)
        if not label:
            return jsonify({"error": f"Label '{label_id}' not found"}), 404
            
        profile = {
            "id": label.get('id'),
            "name": label.get('name'),
            "description": label.get('blurb'),
            "established": label.get('dateEstablished'),
            "follower_count": label.get('followerCount'),
            "image": label.get('imageUrl'),
            "image_large": label.get('imageLarge'),
            "location": {
                "area": label.get('area', {}).get('name') if label.get('area') else None,
                "country": label.get('area', {}).get('country', {}).get('name') if label.get('area', {}).get('country') else None
            },
            "social": {
                "facebook": label.get('facebook'),
                "soundcloud": label.get('soundcloud'),
                "discogs": label.get('discogs'),
                "twitter": label.get('twitter'),
                "website": label.get('link')
            },
            "artists_count": len(label.get('artists', [])),
            "reviews_count": len(label.get('reviews', [])),
            "ra_url": f"https://ra.co{label.get('contentUrl', '')}"
        }
        
        return jsonify(profile)
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/label/<label_id>/artists', methods=['GET'])
def get_label_artists(label_id):
    """
    Get all artists signed to a label
    """
    try:
        label = get_label_info(label_id)
        if not label:
            return jsonify({"error": f"Label '{label_id}' not found"}), 404
            
        artists = []
        for artist_data in label.get('artists', []):
            # Extract slug from contentUrl
            slug = artist_data['contentUrl'].split('/')[-1] if artist_data['contentUrl'] else None
            artists.append({
                "id": artist_data['id'],
                "name": artist_data['name'],
                "slug": slug,
                "url": artist_data['contentUrl'],
                "image": artist_data.get('image'),
                "follower_count": artist_data.get('followerCount')
            })
            
        return jsonify({
            "label": {"id": label['id'], "name": label['name']},
            "artists": artists,
            "count": len(artists)
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/label/<label_id>/reviews', methods=['GET'])
def get_label_reviews(label_id):
    """
    Get music reviews for a label's releases
    """
    try:
        label = get_label_info(label_id)
        if not label:
            return jsonify({"error": f"Label '{label_id}' not found"}), 404
            
        reviews = []
        for review in label.get('reviews', []):
            reviews.append({
                "id": review['id'],
                "title": review['title'],
                "description": review.get('blurb'),
                "date": review['date'],
                "url": review['contentUrl'],
                "image": review.get('imageUrl'),
                "recommended": review.get('recommended')
            })
            
        return jsonify({
            "label": {"id": label['id'], "name": label['name']},
            "reviews": reviews,
            "count": len(reviews)
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/reviews/popular', methods=['GET'])
def get_trending_reviews():
    """
    Get popular music reviews
    Query parameters:
    - days: Number of days back to search (default: 7)
    """
    try:
        days = int(request.args.get('days', 7))
        
        from datetime import datetime, timedelta
        date_from = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%S.000Z")
        date_to = datetime.now().strftime("%Y-%m-%d")
        
        reviews = get_popular_reviews(date_from, date_to)
        
        review_list = []
        for review in reviews:
            review_list.append({
                "id": review['id'],
                "title": review['title'],
                "description": review.get('blurb'),
                "date": review['date'],
                "url": review['contentUrl'],
                "image": review.get('imageUrl'),
                "recommended": review.get('recommended'),
                "labels": [
                    {
                        "id": label['id'],
                        "name": label['name'],
                        "url": label['contentUrl']
                    } for label in review.get('labels', [])
                ]
            })
            
        return jsonify({
            "period": f"Last {days} days",
            "reviews": review_list,
            "count": len(review_list)
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/search', methods=['GET'])
def simple_search():
    q = request.args.get('q')
    if not q: return jsonify({"error": "Missing q parameter"}), 400
    
    try:
        payload = {
            "operationName": "GET_GLOBAL_SEARCH_RESULTS",
            "variables": {"searchTerm": q, "indices": ["ARTIST", "LABEL"]},
            "query": """query GET_GLOBAL_SEARCH_RESULTS($searchTerm: String!, $indices: [IndexType!]) {
                search(searchTerm: $searchTerm limit: 10 indices: $indices includeNonLive: false) {
                    searchType id value contentUrl
                }
            }"""
        }
        
        response = requests.post('https://ra.co/graphql', headers={
            'Content-Type': 'application/json',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:106.0) Gecko/20100101 Firefox/106.0'
        }, json=payload, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            results = data.get('data', {}).get('search', [])
            return jsonify({"results": [{"type": r['searchType'], "name": r['value'], "url": r['contentUrl']} for r in results]})
        return jsonify({"error": "Search failed"}), 500
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/artist/<slug>', methods=['GET'])
def simple_artist(slug):
    try:
        payload = {
            "operationName": "GET_ARTIST_BY_SLUG",
            "variables": {"slug": slug},
            "query": """query GET_ARTIST_BY_SLUG($slug: String!) {
                artist(slug: $slug) {
                    name biography { blurb content } country { name }
                }
            }"""
        }
        
        response = requests.post('https://ra.co/graphql', headers={
            'Content-Type': 'application/json',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:106.0) Gecko/20100101 Firefox/106.0'
        }, json=payload, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            artist = data.get('data', {}).get('artist')
            if artist:
                return jsonify({
                    "name": artist.get('name'),
                    "bio": artist.get('biography', {}).get('blurb'),
                    "country": artist.get('country', {}).get('name')
                })
        return jsonify({"error": "Artist not found"}), 404
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=False)
