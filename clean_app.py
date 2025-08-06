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

def search_global(search_term):
    """Search RA using the global search functionality"""
    try:
        payload = {
            "operationName": "GET_GLOBAL_SEARCH_RESULTS",
            "variables": {"searchTerm": search_term, "indices": ["ARTIST", "LABEL"]},
            "query": """query GET_GLOBAL_SEARCH_RESULTS($searchTerm: String!, $indices: [IndexType!]) {
                search(searchTerm: $searchTerm limit: 16 indices: $indices includeNonLive: false) {
                    searchType id value contentUrl imageUrl score countryName __typename
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
    """Get artist information by slug"""
    try:
        payload = {
            "operationName": "GET_ARTIST_BY_SLUG",
            "variables": {"slug": slug},
            "query": """query GET_ARTIST_BY_SLUG($slug: String!) {
                artist(slug: $slug) {
                    id name followerCount contentUrl
                    country { name urlCode }
                    biography { blurb content }
                    soundcloud instagram
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
        print(f"Error getting artist {slug}: {e}")
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

# YOUR EXISTING EVENTS ENDPOINTS (keeping these exactly as they were)
