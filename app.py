from flask import Flask, request, jsonify, send_file
import os
import tempfile
import json
import requests
from datetime import datetime
from event_fetcher import EventFetcher

app = Flask(__name__)

def get_area_info(area_id):
    """Get area name and country info using RA's GraphQL API"""
    try:
        payload = {
            "operationName": "GET_AREA_INFO",
            "variables": {"areaId": str(area_id)},
            "query": """query GET_AREA_INFO($areaId: ID!) {
                area(id: $areaId) {
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

@app.route('/', methods=['GET'])
def health_check():
    return jsonify({
        "status": "healthy", 
        "message": "RA Events & Artists API",
        "endpoints": {
            "events": "/events?area=1&start_date=2025-08-10&end_date=2025-08-17",
            "areas": "/areas",
            "search": "/search?q=charlotte+de+witte", 
            "artist": "/artist/charlotte-de-witte"
        }
    })

@app.route('/events', methods=['GET'])
def get_events():
    """Fetch events from Resident Advisor"""
    try:
        area = request.args.get('area')
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        output_format = request.args.get('format', 'json').lower()
        
        if not all([area, start_date, end_date]):
            return jsonify({
                "error": "Missing required parameters",
                "required": ["area", "start_date", "end_date"],
                "example": "/events?area=1&start_date=2025-08-10&end_date=2025-08-17"
            }), 400
            
        try:
            area = int(area)
        except ValueError:
            return jsonify({"error": "Area must be a number"}), 400
            
        try:
            datetime.strptime(start_date, '%Y-%m-%d')
            datetime.strptime(end_date, '%Y-%m-%d')
        except ValueError:
            return jsonify({"error": "Invalid date format. Use YYYY-MM-DD"}), 400
            
        listing_date_gte = f"{start_date}T00:00:00.000Z"
        listing_date_lte = f"{end_date}T23:59:59.999Z"
        
        event_fetcher = EventFetcher(area, listing_date_gte, listing_date_lte)
        events = event_fetcher.fetch_all_events()
        
        area_info = get_area_info(area)
        
        if output_format == 'csv':
            with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.csv', encoding='utf-8') as tmp_file:
                output_file = tmp_file.name
            
            try:
                event_fetcher.save_events_to_csv(events, output_file)
                return send_file(output_file, as_attachment=True, 
                               download_name=f'ra_events_{area}_{start_date}_{end_date}.csv',
                               mimetype='text/csv')
            finally:
                if os.path.exists(output_file):
                    os.unlink(output_file)
        else:
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
        return jsonify({"error": "Internal server error", "message": str(e)}), 500

@app.route('/areas', methods=['GET'])
def list_areas():
    """Return discovered RA area codes with names from GraphQL API"""
    discovered_areas = {}
    known_codes = [1, 2, 3, 4, 5, 6, 8, 433, 674]
    
    for area_id in known_codes:
        area_info = get_area_info(area_id)
        if area_info:
            discovered_areas[str(area_id)] = f"{area_info['name']}, {area_info['country']['code']}"
    
    return jsonify({
        "message": "Resident Advisor area codes",
        "areas": discovered_areas,
        "usage": {
            "by_code": "/events?area=1&start_date=2025-08-10&end_date=2025-08-17"
        }
    })

@app.route('/search', methods=['GET'])
def search_ra():
    """Search RA database"""
    q = request.args.get('q')
    if not q: 
        return jsonify({"error": "Missing q parameter", "usage": "/search?q=charlotte+de+witte"}), 400
    
    try:
        payload = {
            "operationName": "GET_GLOBAL_SEARCH_RESULTS",
            "variables": {"searchTerm": q, "indices": ["ARTIST", "LABEL"]},
            "query": """query GET_GLOBAL_SEARCH_RESULTS($searchTerm: String!, $indices: [IndexType!]) {
                search(searchTerm: $searchTerm limit: 10 indices: $indices includeNonLive: false) {
                    searchType id value contentUrl imageUrl countryName
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
            
            artists = []
            labels = []
            for r in results:
                item = {
                    "id": r['id'],
                    "name": r['value'], 
                    "url": r['contentUrl'],
                    "country": r.get('countryName'),
                    "image": r.get('imageUrl')
                }
                if r['searchType'] == 'ARTIST':
                    item['slug'] = r['contentUrl'].split('/')[-1] if r['contentUrl'] else None
                    artists.append(item)
                elif r['searchType'] == 'LABEL':
                    labels.append(item)
            
            return jsonify({
                "search_term": q,
                "artists": artists,
                "labels": labels,
                "total": len(results)
            })
        
        return jsonify({"error": "Search failed"}), 500
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/artist/<slug>', methods=['GET'])
def get_artist(slug):
    """Get artist profile and bio"""
    try:
        payload = {
            "operationName": "GET_ARTIST_BY_SLUG",
            "variables": {"slug": slug},
            "query": """query GET_ARTIST_BY_SLUG($slug: String!) {
                artist(slug: $slug) {
                    id name followerCount contentUrl
                    country { name urlCode }
                    biography { blurb content discography }
                    soundcloud instagram twitter facebook website
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
                    "id": artist.get('id'),
                    "name": artist.get('name'),
                    "slug": slug,
                    "follower_count": artist.get('followerCount'),
                    "country": artist.get('country', {}).get('name'),
                    "bio": {
                        "blurb": artist.get('biography', {}).get('blurb'),
                        "content": artist.get('biography', {}).get('content'),
                        "discography": artist.get('biography', {}).get('discography')
                    },
                    "social": {
                        "soundcloud": artist.get('soundcloud'),
                        "instagram": artist.get('instagram'),
                        "twitter": artist.get('twitter'),
                        "facebook": artist.get('facebook'),
                        "website": artist.get('website')
                    },
                    "ra_url": f"https://ra.co{artist.get('contentUrl', '')}"
                })
        
        return jsonify({"error": f"Artist '{slug}' not found"}), 404
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=False)
