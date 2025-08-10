from flask import Flask, request, jsonify, send_file
import os
import tempfile
import json
import requests
import asyncio
import concurrent.futures
import time
from datetime import datetime
from event_fetcher import EnhancedEventFetcher

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
        "message": "RA Events & Artists API with Advanced Filtering",
        "endpoints": {
            "events": "/events?area=1&start_date=2025-08-10&end_date=2025-08-17",
            "events_with_filters": "/events?area=1&start_date=2025-08-10&end_date=2025-08-17&genre=techno&sort=score&include_bumps=true",
            "areas": "/areas",
            "filters": "/filters?area=1",
            "search": {
                "global": "/search?q=hard+techno",
                "by_type": "/search?q=minimal+techno&type=artist",
                "artists": "/artist/search?q=charlotte+de+witte",
                "labels": "/label/search?q=drumcode"
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
                "popular": "/reviews/popular?days=14"
            }
        },
        "features": {
            "genre_filtering": "Filter events by music genre (techno, house, etc.)",
            "event_type_filtering": "Filter by event type (club, festival, etc.)",
            "advanced_sorting": "Sort by date, score, or title",
            "bumped_events": "Include promoted/sponsored events",
            "enhanced_data": "Rich event details including interested count, tickets, promoters",
            "batch_processing": "Query multiple artists, labels, or areas in one request"
        },
        "examples": {
            "by_genre": "/events?area=1&start_date=2025-08-10&end_date=2025-08-17&genre=techno",
            "by_event_type": "/events?area=1&start_date=2025-08-10&end_date=2025-08-17&event_type=club",
            "sorted_by_score": "/events?area=1&start_date=2025-08-10&end_date=2025-08-17&sort=score",
            "no_bumped_events": "/events?area=1&start_date=2025-08-10&end_date=2025-08-17&include_bumps=false",
            "combined_filters": "/events?area=1&start_date=2025-08-10&end_date=2025-08-17&genre=house&event_type=club&sort=score"
        },
        "batch_examples": {
            "multi_artists": {
                "method": "POST",
                "endpoint": "/artists/batch",
                "body": {"queries": ["charlotte de witte", "amelie lens", "adam beyer"]}
            },
            "multi_labels": {
                "method": "POST", 
                "endpoint": "/labels/batch",
                "body": {"queries": ["drumcode", "hotflush", "minus"]}
            },
            "multi_areas": {
                "method": "POST",
                "endpoint": "/events/batch", 
                "body": {
                    "areas": [1, 2, 3],
                    "start_date": "2025-08-10",
                    "end_date": "2025-08-17",
                    "genre": "techno"
                }
            },
            "mixed_search": {
                "method": "POST",
                "endpoint": "/search/batch",
                "body": {
                    "artists": ["charlotte de witte"],
                    "labels": ["drumcode"],
                    "general": ["berlin techno"]
                }
            }
        }
    })

@app.route('/events', methods=['GET'])
def get_events():
    """Fetch events from Resident Advisor with advanced filtering support"""
    try:
        area = request.args.get('area')
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        output_format = request.args.get('format', 'json').lower()
        
        # New filtering parameters
        genre = request.args.get('genre')
        event_type = request.args.get('event_type')
        sort_by = request.args.get('sort', 'listingDate')
        include_bumps = request.args.get('include_bumps', 'true').lower() == 'true'
        
        if not all([area, start_date, end_date]):
            return jsonify({
                "error": "Missing required parameters",
                "required": ["area", "start_date", "end_date"],
                "optional": ["genre", "event_type", "sort", "include_bumps", "format"],
                "example": "/events?area=1&start_date=2025-08-10&end_date=2025-08-17&genre=techno&sort=score"
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
            
        # Validate sort parameter
        valid_sorts = ['listingDate', 'score', 'title']
        if sort_by not in valid_sorts:
            return jsonify({
                "error": f"Invalid sort parameter. Must be one of: {valid_sorts}"
            }), 400
            
        listing_date_gte = f"{start_date}T00:00:00.000Z"
        listing_date_lte = f"{end_date}T23:59:59.999Z"
        
        # Use enhanced event fetcher with new filtering options
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
        area_info = get_area_info(area)
        
        if output_format == 'csv':
            with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.csv', encoding='utf-8') as tmp_file:
                output_file = tmp_file.name
            
            try:
                event_fetcher.save_events_to_csv(events_data, output_file)
                filename = f'ra_events_{area}_{start_date}_{end_date}'
                if genre:
                    filename += f'_{genre}'
                if event_type:
                    filename += f'_{event_type}'
                filename += '.csv'
                
                return send_file(output_file, as_attachment=True, 
                               download_name=filename, mimetype='text/csv')
            finally:
                if os.path.exists(output_file):
                    os.unlink(output_file)
        else:
            # Format JSON response
            events_json = []
            bumps_json = []
            
            # Process regular events
            for event in events_data["events"]:
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
                    "interested_count": event_data.get("interestedCount", 0),
                    "is_ticketed": event_data.get("isTicketed", False),
                    "is_saved": event_data.get("isSaved", False),
                    "is_interested": event_data.get("isInterested", False),
                    "flyer_front": event_data.get("flyerFront"),
                    "promoters": [p.get("id") for p in event_data.get("promoters", [])],
                    "tickets": event_data.get("tickets", []),
                    "is_bumped": False
                })
            
            # Process bumped events
            for bump in events_data["bumps"]:
                event_data = bump["event"]
                bumps_json.append({
                    "bump_id": bump.get("id"),
                    "bump_date": bump.get("date"),
                    "click_url": bump.get("clickUrl"),
                    "impression_url": bump.get("impressionUrl"),
                    "event": {
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
                        "interested_count": event_data.get("interestedCount", 0),
                        "is_ticketed": event_data.get("isTicketed", False),
                        "flyer_front": event_data.get("flyerFront"),
                        "is_bumped": True
                    }
                })
            
            # Process filter options
            filter_info = {}
            if events_data.get("filter_options"):
                fo = events_data["filter_options"]
                if "genre" in fo:
                    filter_info["available_genres"] = [
                        {"label": g.get("label"), "value": g.get("value"), "count": g.get("count")}
                        for g in fo["genre"]
                    ]
                if "eventType" in fo:
                    filter_info["available_event_types"] = [
                        {"value": et.get("value"), "count": et.get("count")}
                        for et in fo["eventType"]
                    ]
            
            response_data = {
                "area": area_info if area_info else {"id": area, "name": "Unknown"},
                "start_date": start_date,
                "end_date": end_date,
                "filters": {
                    "genre": genre,
                    "event_type": event_type,
                    "sort_by": sort_by,
                    "include_bumps": include_bumps
                },
                "counts": {
                    "total_results": events_data.get("total_results", 0),
                    "regular_events": len(events_json),
                    "bumped_events": len(bumps_json)
                },
                "events": events_json,
                "bumped_events": bumps_json if include_bumps else [],
                "filter_options": filter_info
            }
            
            return jsonify(response_data)
                
    except Exception as e:
        return jsonify({"error": "Internal server error", "message": str(e)}), 500

@app.route('/filters', methods=['GET'])
def get_available_filters():
    """Get available genres and event types for filtering"""
    try:
        area = request.args.get('area', 1)  # Default to area 1 (Sydney)
        
        try:
            area = int(area)
        except ValueError:
            return jsonify({"error": "Area must be a number"}), 400
        
        # Use a short date range to get filter options quickly
        from datetime import datetime, timedelta
        today = datetime.now()
        tomorrow = today + timedelta(days=1)
        
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
        
        response = {
            "area": area,
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
        
        response["usage"] = {
            "genre_filter": "/events?area=1&start_date=2025-08-10&end_date=2025-08-17&genre=techno",
            "event_type_filter": "/events?area=1&start_date=2025-08-10&end_date=2025-08-17&event_type=club",
            "combined": "/events?area=1&start_date=2025-08-10&end_date=2025-08-17&genre=house&event_type=club&sort=score"
        }
        
        return jsonify(response)
        
    except Exception as e:
        return jsonify({"error": "Internal server error", "message": str(e)}), 500

# ============ BATCH ENDPOINTS ============

@app.route('/artists/batch', methods=['POST'])
def batch_artist_search():
    """Search for multiple artists at once"""
    try:
        data = request.get_json()
        if not data or 'queries' not in data:
            return jsonify({
                "error": "Missing 'queries' in request body",
                "example": {"queries": ["charlotte de witte", "amelie lens", "adam beyer"]},
                "max_queries": 10
            }), 400
        
        queries = data['queries']
        if not isinstance(queries, list) or len(queries) == 0:
            return jsonify({"error": "Queries must be a non-empty list"}), 400
            
        if len(queries) > 10:  # Rate limiting
            return jsonify({"error": "Maximum 10 queries per batch request"}), 400
        
        results = []
        
        # Process queries with rate limiting
        for i, query in enumerate(queries):
            if i > 0:  # Add delay between requests (except first)
                time.sleep(0.5)  # 500ms delay
            
            try:
                # Use existing search logic
                payload = {
                    "operationName": "GET_GLOBAL_SEARCH_RESULTS",
                    "variables": {"searchTerm": query, "indices": ["ARTIST"]},
                    "query": """query GET_GLOBAL_SEARCH_RESULTS($searchTerm: String!, $indices: [IndexType!]) {
                        search(searchTerm: $searchTerm limit: 16 indices: $indices includeNonLive: false) {
                            searchType id value contentUrl imageUrl countryName score
                        }
                    }"""
                }
                
                response = requests.post('https://ra.co/graphql', headers={
                    'Content-Type': 'application/json',
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:106.0) Gecko/20100101 Firefox/106.0'
                }, json=payload, timeout=10)
                
                if response.status_code == 200:
                    data = response.json()
                    search_results = data.get('data', {}).get('search', [])
                    
                    artists = []
                    for r in search_results:
                        if r['searchType'] == 'ARTIST':
                            artists.append({
                                "id": r['id'],
                                "name": r['value'],
                                "slug": r['contentUrl'].split('/')[-1] if r['contentUrl'] else None,
                                "url": r['contentUrl'],
                                "country": r.get('countryName'),
                                "image": r.get('imageUrl'),
                                "score": r.get('score')
                            })
                    
                    results.append({
                        "query": query,
                        "success": True,
                        "artists": artists,
                        "count": len(artists)
                    })
                else:
                    results.append({
                        "query": query,
                        "success": False,
                        "error": f"HTTP {response.status_code}",
                        "artists": [],
                        "count": 0
                    })
                    
            except Exception as e:
                results.append({
                    "query": query,
                    "success": False,
                    "error": str(e),
                    "artists": [],
                    "count": 0
                })
        
        # Summary statistics
        successful_queries = sum(1 for r in results if r['success'])
        total_artists = sum(r['count'] for r in results)
        
        return jsonify({
            "batch_summary": {
                "total_queries": len(queries),
                "successful_queries": successful_queries,
                "failed_queries": len(queries) - successful_queries,
                "total_artists_found": total_artists
            },
            "results": results
        })
        
    except Exception as e:
        return jsonify({"error": "Internal server error", "message": str(e)}), 500

@app.route('/labels/batch', methods=['POST'])
def batch_label_search():
    """Search for multiple labels at once"""
    try:
        data = request.get_json()
        if not data or 'queries' not in data:
            return jsonify({
                "error": "Missing 'queries' in request body",
                "example": {"queries": ["drumcode", "hotflush", "minus"]},
                "max_queries": 10
            }), 400
        
        queries = data['queries']
        if not isinstance(queries, list) or len(queries) == 0:
            return jsonify({"error": "Queries must be a non-empty list"}), 400
            
        if len(queries) > 10:  # Rate limiting
            return jsonify({"error": "Maximum 10 queries per batch request"}), 400
        
        results = []
        
        # Process queries with rate limiting
        for i, query in enumerate(queries):
            if i > 0:  # Add delay between requests
                time.sleep(0.5)  # 500ms delay
            
            try:
                payload = {
                    "operationName": "GET_GLOBAL_SEARCH_RESULTS",
                    "variables": {"searchTerm": query, "indices": ["LABEL"]},
                    "query": """query GET_GLOBAL_SEARCH_RESULTS($searchTerm: String!, $indices: [IndexType!]) {
                        search(searchTerm: $searchTerm limit: 16 indices: $indices includeNonLive: false) {
                            searchType id value contentUrl imageUrl countryName score
                        }
                    }"""
                }
                
                response = requests.post('https://ra.co/graphql', headers={
                    'Content-Type': 'application/json',
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:106.0) Gecko/20100101 Firefox/106.0'
                }, json=payload, timeout=10)
                
                if response.status_code == 200:
                    data = response.json()
                    search_results = data.get('data', {}).get('search', [])
                    
                    labels = []
                    for r in search_results:
                        if r['searchType'] == 'LABEL':
                            labels.append({
                                "id": r['id'],
                                "name": r['value'],
                                "url": r['contentUrl'],
                                "country": r.get('countryName'),
                                "image": r.get('imageUrl'),
                                "score": r.get('score')
                            })
                    
                    results.append({
                        "query": query,
                        "success": True,
                        "labels": labels,
                        "count": len(labels)
                    })
                else:
                    results.append({
                        "query": query,
                        "success": False,
                        "error": f"HTTP {response.status_code}",
                        "labels": [],
                        "count": 0
                    })
                    
            except Exception as e:
                results.append({
                    "query": query,
                    "success": False,
                    "error": str(e),
                    "labels": [],
                    "count": 0
                })
        
        # Summary statistics
        successful_queries = sum(1 for r in results if r['success'])
        total_labels = sum(r['count'] for r in results)
        
        return jsonify({
            "batch_summary": {
                "total_queries": len(queries),
                "successful_queries": successful_queries,
                "failed_queries": len(queries) - successful_queries,
                "total_labels_found": total_labels
            },
            "results": results
        })
        
    except Exception as e:
        return jsonify({"error": "Internal server error", "message": str(e)}), 500

@app.route('/events/batch', methods=['POST'])
def batch_events_search():
    """Get events for multiple areas at once"""
    try:
        data = request.get_json()
        if not data or 'areas' not in data:
            return jsonify({
                "error": "Missing 'areas' in request body",
                "example": {
                    "areas": [1, 2, 3],
                    "start_date": "2025-08-10",
                    "end_date": "2025-08-17",
                    "genre": "techno"
                },
                "max_areas": 5
            }), 400
        
        areas = data['areas']
        start_date = data.get('start_date')
        end_date = data.get('end_date')
        
        if not isinstance(areas, list) or len(areas) == 0:
            return jsonify({"error": "Areas must be a non-empty list"}), 400
            
        if len(areas) > 5:  # Rate limiting for batch events
            return jsonify({"error": "Maximum 5 areas per batch request"}), 400
            
        if not start_date or not end_date:
            return jsonify({"error": "start_date and end_date are required"}), 400
        
        # Validate dates
        try:
            datetime.strptime(start_date, '%Y-%m-%d')
            datetime.strptime(end_date, '%Y-%m-%d')
        except ValueError:
            return jsonify({"error": "Invalid date format. Use YYYY-MM-DD"}), 400
        
        # Optional filtering parameters
        genre = data.get('genre')
        event_type = data.get('event_type')
        sort_by = data.get('sort', 'listingDate')
        include_bumps = data.get('include_bumps', True)
        
        listing_date_gte = f"{start_date}T00:00:00.000Z"
        listing_date_lte = f"{end_date}T23:59:59.999Z"
        
        results = []
        
        # Process areas with rate limiting
        for i, area in enumerate(areas):
            if i > 0:  # Add delay between requests
                time.sleep(1.0)  # 1 second delay for event queries
            
            try:
                area = int(area)
                
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
                area_info = get_area_info(area)
                
                # Format events
                events_json = []
                for event in events_data["events"]:
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
                        "interested_count": event_data.get("interestedCount", 0),
                        "is_ticketed": event_data.get("isTicketed", False)
                    })
                
                results.append({
                    "area": area_info if area_info else {"id": area, "name": "Unknown"},
                    "success": True,
                    "events": events_json,
                    "bumped_events": len(events_data["bumps"]),
                    "total_results": events_data.get("total_results", 0),
                    "count": len(events_json)
                })
                
            except Exception as e:
                results.append({
                    "area": {"id": area, "name": "Unknown"},
                    "success": False,
                    "error": str(e),
                    "events": [],
                    "bumped_events": 0,
                    "total_results": 0,
                    "count": 0
                })
        
        # Summary statistics
        successful_queries = sum(1 for r in results if r['success'])
        total_events = sum(r['count'] for r in results)
        total_bumped = sum(r['bumped_events'] for r in results)
        
        return jsonify({
            "batch_summary": {
                "total_areas": len(areas),
                "successful_areas": successful_queries,
                "failed_areas": len(areas) - successful_queries,
                "total_events_found": total_events,
                "total_bumped_events": total_bumped
            },
            "filters": {
                "start_date": start_date,
                "end_date": end_date,
                "genre": genre,
                "event_type": event_type,
                "sort_by": sort_by,
                "include_bumps": include_bumps
            },
            "results": results
        })
        
    except Exception as e:
        return jsonify({"error": "Internal server error", "message": str(e)}), 500

@app.route('/search/batch', methods=['POST'])
def batch_mixed_search():
    """Mixed batch search for artists, labels, and general queries"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                "error": "Missing request body",
                "example": {
                    "artists": ["charlotte de witte", "amelie lens"],
                    "labels": ["drumcode", "hotflush"],
                    "general": ["berlin techno", "minimal house"]
                },
                "max_total_queries": 15
            }), 400
        
        artists = data.get('artists', [])
        labels = data.get('labels', [])
        general = data.get('general', [])
        
        total_queries = len(artists) + len(labels) + len(general)
        
        if total_queries == 0:
            return jsonify({"error": "At least one query type must be provided"}), 400
            
        if total_queries > 15:  # Rate limiting
            return jsonify({"error": "Maximum 15 total queries per batch request"}), 400
        
        results = {
            "artists": [],
            "labels": [],
            "general": []
        }
        
        query_count = 0
        
        # Process artist queries
        for query in artists:
            if query_count > 0:
                time.sleep(0.5)  # Rate limiting delay
            query_count += 1
            
            try:
                payload = {
                    "operationName": "GET_GLOBAL_SEARCH_RESULTS",
                    "variables": {"searchTerm": query, "indices": ["ARTIST"]},
                    "query": """query GET_GLOBAL_SEARCH_RESULTS($searchTerm: String!, $indices: [IndexType!]) {
                        search(searchTerm: $searchTerm limit: 16 indices: $indices includeNonLive: false) {
                            searchType id value contentUrl imageUrl countryName score
                        }
                    }"""
                }
                
                response = requests.post('https://ra.co/graphql', headers={
                    'Content-Type': 'application/json',
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:106.0) Gecko/20100101 Firefox/106.0'
                }, json=payload, timeout=10)
                
                if response.status_code == 200:
                    data = response.json()
                    search_results = data.get('data', {}).get('search', [])
                    
                    artist_results = []
                    for r in search_results:
                        if r['searchType'] == 'ARTIST':
                            artist_results.append({
                                "id": r['id'],
                                "name": r['value'],
                                "slug": r['contentUrl'].split('/')[-1] if r['contentUrl'] else None,
                                "url": r['contentUrl'],
                                "country": r.get('countryName'),
                                "image": r.get('imageUrl'),
                                "score": r.get('score')
                            })
                    
                    results["artists"].append({
                        "query": query,
                        "success": True,
                        "results": artist_results,
                        "count": len(artist_results)
                    })
                else:
                    results["artists"].append({
                        "query": query,
                        "success": False,
                        "error": f"HTTP {response.status_code}",
                        "results": [],
                        "count": 0
                    })
                    
            except Exception as e:
                results["artists"].append({
                    "query": query,
                    "success": False,
                    "error": str(e),
                    "results": [],
                    "count": 0
                })
        
        # Process label queries (similar pattern)
        for query in labels:
            if query_count > 0:
                time.sleep(0.5)
            query_count += 1
            
            try:
                payload = {
                    "operationName": "GET_GLOBAL_SEARCH_RESULTS",
                    "variables": {"searchTerm": query, "indices": ["LABEL"]},
                    "query": """query GET_GLOBAL_SEARCH_RESULTS($searchTerm: String!, $indices: [IndexType!]) {
                        search(searchTerm: $searchTerm limit: 16 indices: $indices includeNonLive: false) {
                            searchType id value contentUrl imageUrl countryName score
                        }
                    }"""
                }
                
                response = requests.post('https://ra.co/graphql', headers={
                    'Content-Type': 'application/json',
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:106.0) Gecko/20100101 Firefox/106.0'
                }, json=payload, timeout=10)
                
                if response.status_code == 200:
                    data = response.json()
                    search_results = data.get('data', {}).get('search', [])
                    
                    label_results = []
                    for r in search_results:
                        if r['searchType'] == 'LABEL':
                            label_results.append({
                                "id": r['id'],
                                "name": r['value'],
                                "url": r['contentUrl'],
                                "country": r.get('countryName'),
                                "image": r.get('imageUrl'),
                                "score": r.get('score')
                            })
                    
                    results["labels"].append({
                        "query": query,
                        "success": True,
                        "results": label_results,
                        "count": len(label_results)
                    })
                else:
                    results["labels"].append({
                        "query": query,
                        "success": False,
                        "error": f"HTTP {response.status_code}",
                        "results": [],
                        "count": 0
                    })
                    
            except Exception as e:
                results["labels"].append({
                    "query": query,
                    "success": False,
                    "error": str(e),
                    "results": [],
                    "count": 0
                })
        
        # Process general queries (all types)
        for query in general:
            if query_count > 0:
                time.sleep(0.5)
            query_count += 1
            
            try:
                payload = {
                    "operationName": "GET_GLOBAL_SEARCH_RESULTS",
                    "variables": {"searchTerm": query, "indices": ["ARTIST", "LABEL", "CLUB", "EVENT"]},
                    "query": """query GET_GLOBAL_SEARCH_RESULTS($searchTerm: String!, $indices: [IndexType!]) {
                        search(searchTerm: $searchTerm limit: 16 indices: $indices includeNonLive: false) {
                            searchType id value contentUrl imageUrl countryName score
                        }
                    }"""
                }
                
                response = requests.post('https://ra.co/graphql', headers={
                    'Content-Type': 'application/json',
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:106.0) Gecko/20100101 Firefox/106.0'
                }, json=payload, timeout=10)
                
                if response.status_code == 200:
                    data = response.json()
                    search_results = data.get('data', {}).get('search', [])
                    
                    general_results = []
                    for r in search_results:
                        general_results.append({
                            "type": r['searchType'].lower(),
                            "id": r['id'],
                            "name": r['value'],
                            "url": r['contentUrl'],
                            "country": r.get('countryName'),
                            "image": r.get('imageUrl'),
                            "score": r.get('score')
                        })
                    
                    results["general"].append({
                        "query": query,
                        "success": True,
                        "results": general_results,
                        "count": len(general_results)
                    })
                else:
                    results["general"].append({
                        "query": query,
                        "success": False,
                        "error": f"HTTP {response.status_code}",
                        "results": [],
                        "count": 0
                    })
                    
            except Exception as e:
                results["general"].append({
                    "query": query,
                    "success": False,
                    "error": str(e),
                    "results": [],
                    "count": 0
                })
        
        # Calculate summary
        total_successful = 0
        total_results = 0
        
        for category in results.values():
            for result in category:
                if result['success']:
                    total_successful += 1
                    total_results += result['count']
        
        return jsonify({
            "batch_summary": {
                "total_queries": total_queries,
                "successful_queries": total_successful,
                "failed_queries": total_queries - total_successful,
                "total_results_found": total_results,
                "query_breakdown": {
                    "artists": len(artists),
                    "labels": len(labels),
                    "general": len(general)
                }
            },
            "results": results
        })
        
    except Exception as e:
        return jsonify({"error": "Internal server error", "message": str(e)}), 500

# ============ END BATCH ENDPOINTS ============

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
    """Enhanced search RA database with type filtering"""
    q = request.args.get('q')
    search_type = request.args.get('type', '').upper()
    
    if not q: 
        return jsonify({
            "error": "Missing q parameter", 
            "usage": {
                "global": "/search?q=hard+techno",
                "filtered": "/search?q=minimal+techno&type=artist"
            }
        }), 400
    
    # Map type parameter to indices
    if search_type == 'ARTIST':
        indices = ["ARTIST"]
    elif search_type == 'LABEL':
        indices = ["LABEL"]
    elif search_type == 'CLUB':
        indices = ["CLUB"]
    elif search_type == 'EVENT':
        indices = ["EVENT"]
    else:
        indices = ["ARTIST", "LABEL", "CLUB", "EVENT"]
    
    try:
        payload = {
            "operationName": "GET_GLOBAL_SEARCH_RESULTS",
            "variables": {"searchTerm": q, "indices": indices},
            "query": """query GET_GLOBAL_SEARCH_RESULTS($searchTerm: String!, $indices: [IndexType!]) {
                search(searchTerm: $searchTerm limit: 16 indices: $indices includeNonLive: false) {
                    searchType id value contentUrl imageUrl countryName score
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
            
            # Group results by type
            grouped_results = {"artists": [], "labels": [], "clubs": [], "events": []}
            
            for r in results:
                item = {
                    "id": r['id'],
                    "name": r['value'], 
                    "url": r['contentUrl'],
                    "country": r.get('countryName'),
                    "image": r.get('imageUrl'),
                    "score": r.get('score')
                }
                
                if r['searchType'] == 'ARTIST':
                    item['slug'] = r['contentUrl'].split('/')[-1] if r['contentUrl'] else None
                    grouped_results["artists"].append(item)
                elif r['searchType'] == 'LABEL':
                    grouped_results["labels"].append(item)
                elif r['searchType'] == 'CLUB':
                    grouped_results["clubs"].append(item)
                elif r['searchType'] in ['EVENT', 'UPCOMINGEVENT']:
                    grouped_results["events"].append(item)
            
            return jsonify({
                "search_term": q,
                "filter_type": search_type.lower() if search_type else "all",
                "results": grouped_results,
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

# ============ ADDITIONAL ARTIST ENDPOINTS ============

@app.route('/artist/search', methods=['GET'])
def search_artists():
    """Search specifically for artists"""
    q = request.args.get('q')
    if not q: 
        return jsonify({"error": "Missing q parameter", "usage": "/artist/search?q=charlotte+de+witte"}), 400
    
    try:
        # Use existing search but filter only artists
        payload = {
            "operationName": "GET_GLOBAL_SEARCH_RESULTS",
            "variables": {"searchTerm": q, "indices": ["ARTIST"]},
            "query": """query GET_GLOBAL_SEARCH_RESULTS($searchTerm: String!, $indices: [IndexType!]) {
                search(searchTerm: $searchTerm limit: 16 indices: $indices includeNonLive: false) {
                    searchType id value contentUrl imageUrl countryName score
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
            for r in results:
                if r['searchType'] == 'ARTIST':
                    artists.append({
                        "id": r['id'],
                        "name": r['value'],
                        "slug": r['contentUrl'].split('/')[-1] if r['contentUrl'] else None,
                        "url": r['contentUrl'],
                        "country": r.get('countryName'),
                        "image": r.get('imageUrl'),
                        "score": r.get('score')
                    })
            
            return jsonify({
                "search_term": q,
                "artists": artists,
                "count": len(artists)
            })
        
        return jsonify({"error": "Search failed"}), 500
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/artist/<slug>/stats', methods=['GET'])
def get_artist_stats(slug):
    """Get artist performance statistics"""
    try:
        # First get the artist to get their ID
        artist_response = requests.post('https://ra.co/graphql', headers={
            'Content-Type': 'application/json',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:106.0) Gecko/20100101 Firefox/106.0'
        }, json={
            "operationName": "GET_ARTIST_BY_SLUG",
            "variables": {"slug": slug},
            "query": "query GET_ARTIST_BY_SLUG($slug: String!) { artist(slug: $slug) { id } }"
        }, timeout=10)
        
        if artist_response.status_code != 200:
            return jsonify({"error": "Artist not found"}), 404
            
        artist_data = artist_response.json().get('data', {}).get('artist')
        if not artist_data:
            return jsonify({"error": "Artist not found"}), 404
            
        # Now get stats
        payload = {
            "operationName": "GET_ARTIST_STATS",
            "variables": {"id": str(artist_data['id'])},
            "query": """query GET_ARTIST_STATS($id: ID!) {
                artist(id: $id) {
                    id
                    firstEvent { id date }
                    venuesMostPlayed { id name contentUrl }
                    regionsMostPlayed { id name urlName country { name urlCode } }
                }
            }"""
        }
        
        response = requests.post('https://ra.co/graphql', headers={
            'Content-Type': 'application/json',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:106.0) Gecko/20100101 Firefox/106.0'
        }, json=payload, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            stats = data.get('data', {}).get('artist')
            if stats:
                return jsonify({
                    "artist_slug": slug,
                    "career_start": stats.get('firstEvent', {}).get('date') if stats.get('firstEvent') else None,
                    "top_venues": [
                        {"name": venue['name'], "url": venue['contentUrl']} 
                        for venue in stats.get('venuesMostPlayed', [])
                    ],
                    "top_regions": [
                        {
                            "name": region['name'],
                            "country": region.get('country', {}).get('name'),
                            "url_name": region['urlName']
                        } for region in stats.get('regionsMostPlayed', [])
                    ]
                })
        
        return jsonify({"error": "Stats not available"}), 404
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/artist/<slug>/related', methods=['GET'])
def get_related_artists(slug):
    """Get related artists for discovery"""
    try:
        # First get the artist ID
        artist_response = requests.post('https://ra.co/graphql', headers={
            'Content-Type': 'application/json',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:106.0) Gecko/20100101 Firefox/106.0'
        }, json={
            "operationName": "GET_ARTIST_BY_SLUG", 
            "variables": {"slug": slug},
            "query": "query GET_ARTIST_BY_SLUG($slug: String!) { artist(slug: $slug) { id name } }"
        }, timeout=10)
        
        if artist_response.status_code != 200:
            return jsonify({"error": "Artist not found"}), 404
            
        artist_data = artist_response.json().get('data', {}).get('artist')
        if not artist_data:
            return jsonify({"error": "Artist not found"}), 404
            
        # Get related artists
        payload = {
            "operationName": "GET_RELATED_ARTISTS",
            "variables": {"id": str(artist_data['id'])},
            "query": """query GET_RELATED_ARTISTS($id: ID!) {
                artist(id: $id) {
                    relatedArtists {
                        id name contentUrl image followerCount
                    }
                }
            }"""
        }
        
        response = requests.post('https://ra.co/graphql', headers={
            'Content-Type': 'application/json',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:106.0) Gecko/20100101 Firefox/106.0'
        }, json=payload, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            related = data.get('data', {}).get('artist', {}).get('relatedArtists', [])
            
            related_artists = []
            for artist in related:
                related_artists.append({
                    "id": artist['id'],
                    "name": artist['name'],
                    "slug": artist['contentUrl'].split('/')[-1] if artist['contentUrl'] else None,
                    "url": artist['contentUrl'],
                    "image": artist.get('image'),
                    "follower_count": artist.get('followerCount')
                })
            
            return jsonify({
                "artist": {"name": artist_data['name'], "slug": slug},
                "related_artists": related_artists,
                "count": len(related_artists)
            })
        
        return jsonify({"error": "Related artists not available"}), 404
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/artist/<slug>/labels', methods=['GET'])
def get_artist_labels(slug):
    """Get labels associated with an artist"""
    try:
        # First get the artist ID
        artist_response = requests.post('https://ra.co/graphql', headers={
            'Content-Type': 'application/json',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:106.0) Gecko/20100101 Firefox/106.0'
        }, json={
            "operationName": "GET_ARTIST_BY_SLUG",
            "variables": {"slug": slug},
            "query": "query GET_ARTIST_BY_SLUG($slug: String!) { artist(slug: $slug) { id name } }"
        }, timeout=10)
        
        if artist_response.status_code != 200:
            return jsonify({"error": "Artist not found"}), 404
            
        artist_data = artist_response.json().get('data', {}).get('artist')
        if not artist_data:
            return jsonify({"error": "Artist not found"}), 404
            
        # Get artist labels
        payload = {
            "operationName": "GET_ARTIST_LABELS",
            "variables": {"id": str(artist_data['id'])},
            "query": """query GET_ARTIST_LABELS($id: ID!) {
                artist(id: $id) {
                    labels {
                        id name contentUrl imageUrl followerCount
                    }
                }
            }"""
        }
        
        response = requests.post('https://ra.co/graphql', headers={
            'Content-Type': 'application/json',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:106.0) Gecko/20100101 Firefox/106.0'
        }, json=payload, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            labels = data.get('data', {}).get('artist', {}).get('labels', [])
            
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
                "artist": {"name": artist_data['name'], "slug": slug},
                "labels": label_list,
                "count": len(label_list)
            })
        
        return jsonify({"error": "Labels not available"}), 404
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ============ LABEL ENDPOINTS ============

@app.route('/label/search', methods=['GET'])
def search_labels():
    """Search for record labels"""
    q = request.args.get('q')
    if not q: 
        return jsonify({"error": "Missing q parameter", "usage": "/label/search?q=drumcode"}), 400
    
    try:
        payload = {
            "operationName": "GET_GLOBAL_SEARCH_RESULTS",
            "variables": {"searchTerm": q, "indices": ["LABEL"]},
            "query": """query GET_GLOBAL_SEARCH_RESULTS($searchTerm: String!, $indices: [IndexType!]) {
                search(searchTerm: $searchTerm limit: 16 indices: $indices includeNonLive: false) {
                    searchType id value contentUrl imageUrl countryName score
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
            
            labels = []
            for r in results:
                if r['searchType'] == 'LABEL':
                    labels.append({
                        "id": r['id'],
                        "name": r['value'],
                        "url": r['contentUrl'],
                        "country": r.get('countryName'),
                        "image": r.get('imageUrl'),
                        "score": r.get('score')
                    })
            
            return jsonify({
                "search_term": q,
                "labels": labels,
                "count": len(labels)
            })
        
        return jsonify({"error": "Search failed"}), 500
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/label/<label_id>', methods=['GET'])
def get_label_profile(label_id):
    """Get comprehensive label information"""
    try:
        payload = {
            "operationName": "GET_LABEL",
            "variables": {"id": str(label_id)},
            "query": """query GET_LABEL($id: ID!) {
                label(id: $id) {
                    id name imageUrl contentUrl blurb dateEstablished followerCount
                    area { name country { name urlCode } }
                    facebook discogs soundcloud twitter link
                }
            }"""
        }
        
        response = requests.post('https://ra.co/graphql', headers={
            'Content-Type': 'application/json',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:106.0) Gecko/20100101 Firefox/106.0'
        }, json=payload, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            label = data.get('data', {}).get('label')
            if label:
                return jsonify({
                    "id": label.get('id'),
                    "name": label.get('name'),
                    "description": label.get('blurb'),
                    "established": label.get('dateEstablished'),
                    "follower_count": label.get('followerCount'),
                    "image": label.get('imageUrl'),
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
                    "ra_url": f"https://ra.co{label.get('contentUrl', '')}"
                })
        
        return jsonify({"error": f"Label '{label_id}' not found"}), 404
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/label/<label_id>/artists', methods=['GET'])
def get_label_artists(label_id):
    """Get all artists signed to a label"""
    try:
        payload = {
            "operationName": "GET_LABEL",
            "variables": {"id": str(label_id)},
            "query": """query GET_LABEL($id: ID!) {
                label(id: $id) {
                    id name
                    artists(limit: 100) {
                        id name contentUrl image followerCount
                    }
                }
            }"""
        }
        
        response = requests.post('https://ra.co/graphql', headers={
            'Content-Type': 'application/json',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:106.0) Gecko/20100101 Firefox/106.0'
        }, json=payload, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            label = data.get('data', {}).get('label')
            if label:
                artists = []
                for artist_data in label.get('artists', []):
                    artists.append({
                        "id": artist_data['id'],
                        "name": artist_data['name'],
                        "slug": artist_data['contentUrl'].split('/')[-1] if artist_data['contentUrl'] else None,
                        "url": artist_data['contentUrl'],
                        "image": artist_data.get('image'),
                        "follower_count": artist_data.get('followerCount')
                    })
                
                return jsonify({
                    "label": {"id": label['id'], "name": label['name']},
                    "artists": artists,
                    "count": len(artists)
                })
        
        return jsonify({"error": f"Label '{label_id}' not found"}), 404
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/label/<label_id>/reviews', methods=['GET'])
def get_label_reviews(label_id):
    """Get music reviews for a label's releases"""
    try:
        payload = {
            "operationName": "GET_LABEL",
            "variables": {"id": str(label_id)},
            "query": """query GET_LABEL($id: ID!) {
                label(id: $id) {
                    id name
                    reviews(limit: 50) {
                        id title blurb date contentUrl imageUrl recommended
                    }
                }
            }"""
        }
        
        response = requests.post('https://ra.co/graphql', headers={
            'Content-Type': 'application/json',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:106.0) Gecko/20100101 Firefox/106.0'
        }, json=payload, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            label = data.get('data', {}).get('label')
            if label:
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
        
        return jsonify({"error": f"Label '{label_id}' not found"}), 404
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ============ ENHANCED SEARCH & REVIEWS ============

@app.route('/reviews/popular', methods=['GET'])
def get_popular_reviews():
    """Get popular music reviews"""
    try:
        days = int(request.args.get('days', 7))
        
        from datetime import timedelta
        date_from = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%S.000Z")
        date_to = datetime.now().strftime("%Y-%m-%d")
        
        payload = {
            "operationName": "GET_POPULAR_REVIEWS",
            "variables": {"dateFrom": date_from, "dateTo": date_to},
            "query": """query GET_POPULAR_REVIEWS($dateFrom: DateTime, $dateTo: DateTime) {
                reviews(limit: 20 type: ALL orderBy: POPULAR dateFrom: $dateFrom dateTo: $dateTo) {
                    id title imageUrl contentUrl blurb date recommended
                    labels { id name contentUrl }
                }
            }"""
        }
        
        response = requests.post('https://ra.co/graphql', headers={
            'Content-Type': 'application/json',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:106.0) Gecko/20100101 Firefox/106.0'
        }, json=payload, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            reviews = data.get('data', {}).get('reviews', [])
            
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
                        {"id": label['id'], "name": label['name'], "url": label['contentUrl']} 
                        for label in review.get('labels', [])
                    ]
                })
            
            return jsonify({
                "period": f"Last {days} days",
                "reviews": review_list,
                "count": len(review_list)
            })
        
        return jsonify({"error": "Reviews not available"}), 404
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500



if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=False)


# ============ ENHANCED V2 ENDPOINTS ============
# Enhanced API endpoints with advanced filtering support

@app.route('/v2/events')
def get_events_v2():
    """
    Enhanced events endpoint with advanced filtering support
    
    Parameters:
    - Legacy: area, start_date, end_date, genre, event_type, sort, include_bumps
    - Enhanced: filter (advanced filter expression)
    - Enhanced: genre (now supports comma-separated values for multiple genres)
    
    Examples:
    - Legacy: /v2/events?area=1&start_date=2025-08-10&end_date=2025-08-17&genre=techno
    - Multi-genre: /v2/events?area=1&start_date=2025-08-10&end_date=2025-08-17&genre=techno,house,minimal
    - Advanced: /v2/events?area=1&start_date=2025-08-10&end_date=2025-08-17&filter=genre:in:techno,house
    - Complex: /v2/events?area=1&start_date=2025-08-10&end_date=2025-08-17&filter=genre:in:techno,house AND eventType:eq:club
    """
    
    try:
        # Get parameters
        area = request.args.get('area')
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
                "required": ["area", "start_date", "end_date"],
                "optional": {
                    "genre": "Single genre or comma-separated multiple genres",
                    "event_type": "club, festival, etc.",
                    "sort": "listingDate, score, title",
                    "include_bumps": "true/false",
                    "format": "json/csv",
                    "filter": "Advanced filter expression"
                },
                "examples": {
                    "multi_genre": "/v2/events?area=1&start_date=2025-08-10&end_date=2025-08-17&genre=techno,house,minimal",
                    "advanced_filter": "/v2/events?area=1&start_date=2025-08-10&end_date=2025-08-17&filter=genre:in:techno,house AND eventType:eq:club",
                    "exclusion": "/v2/events?area=1&start_date=2025-08-10&end_date=2025-08-17&filter=genre:ne:jazz"
                },
                "filter_syntax": {
                    "operators": ["eq", "ne", "in", "nin", "gte", "lte"],
                    "logical": ["AND", "OR", "NOT"],
                    "examples": [
                        "genre:eq:techno",
                        "genre:in:techno,house,minimal", 
                        "genre:ne:jazz",
                        "genre:in:techno,house AND eventType:eq:club"
                    ]
                }
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
            
        # Validate sort parameter
        valid_sorts = ['listingDate', 'score', 'title']
        if sort_by not in valid_sorts:
            return jsonify({
                "error": f"Invalid sort parameter. Must be one of: {valid_sorts}"
            }), 400
            
        # Convert dates
        listing_date_gte = f"{start_date}T00:00:00.000Z"
        listing_date_lte = f"{end_date}T23:59:59.999Z"
        
        # Handle multiple genres in legacy parameter
        if genre and ',' in genre and not filter_expression:
            # Convert comma-separated genres to filter expression
            genres = [g.strip() for g in genre.split(',')]
            filter_expression = f"genre:in:{','.join(genres)}"
            genre = None  # Clear to avoid conflict
        
        # Create enhanced event fetcher
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
        area_info = get_area_info(area)
        
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
                "version": "v2_enhanced",
                "area": area_info,
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
            
            return jsonify(response)
        
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": "Internal server error", "message": str(e)}), 500


@app.route('/v2/filters')
def get_available_filters_v2():
    """Get available filters with enhanced information"""
    try:
        area = request.args.get('area', 1)
        
        try:
            area = int(area)
        except ValueError:
            return jsonify({"error": "Area must be a number"}), 400
        
        # Use a short date range to get filter options quickly
        from datetime import datetime, timedelta
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
        
        response = {
            "version": "v2",
            "area": area,
            "enhanced_features": {
                "multi_genre_support": "Use comma-separated values: genre=techno,house,minimal",
                "advanced_expressions": "Use filter parameter: filter=genre:in:techno,house AND eventType:eq:club",
                "client_side_filtering": "Complex logic handled automatically"
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
            "multi_genre": "/v2/events?area=1&start_date=2025-08-10&end_date=2025-08-17&genre=techno,house,minimal",
            "advanced_filter": "/v2/events?area=1&start_date=2025-08-10&end_date=2025-08-17&filter=genre:in:techno,house AND eventType:eq:club",
            "exclusion": "/v2/events?area=1&start_date=2025-08-10&end_date=2025-08-17&filter=genre:ne:jazz",
            "complex": "/v2/events?area=1&start_date=2025-08-10&end_date=2025-08-17&filter=genre:in:techno,house AND eventType:eq:club"
        }
        
        response["supported_operators"] = {
            "eq": "equals (exact match)",
            "ne": "not equals",
            "in": "in array (client-side for unsupported GraphQL)",
            "nin": "not in array (client-side)",
            "gte": "greater than or equal",
            "lte": "less than or equal"
        }
        
        response["logical_operators"] = ["AND", "OR", "NOT"]
        
        return jsonify(response)
        
    except Exception as e:
        return jsonify({"error": "Internal server error", "message": str(e)}), 500
