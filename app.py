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
from enhanced_event_fetcher import EnhancedEventFetcher as EnhancedEventFetcherV2, FilterExpression
from advanced_event_fetcher import EnhancedEventFetcher as AdvancedEventFetcher, AdvancedFilterExpression

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
        "message": "RA Events & Artists API with Ultimate Multi-Level Filtering",
        "api_versions": {
            "v1": {
                "endpoint": "/events",
                "description": "Basic filtering (single genre, single event type)",
                "example": "/events?area=1&start_date=2025-08-10&end_date=2025-08-17&genre=techno"
            },
            "v2": {
                "endpoint": "/v2/events", 
                "description": "Enhanced filtering (multi-genre OR, basic expressions)",
                "example": "/v2/events?area=1&start_date=2025-08-10&end_date=2025-08-17&genre=techno,house,minimal"
            },
            "v3": {
                "endpoint": "/v3/events",
                "description": "Ultimate filtering (multi-genre AND/OR, all 8 operators, maximum flexibility)",
                "example": "/v3/events?area=1&start_date=2025-08-10&end_date=2025-08-17&filter=genre:contains_all:techno,industrial"
            }
        }
    })

@app.route('/events', methods=['GET'])
def get_events():
    """Fetch events from Resident Advisor with basic filtering support (v1)"""
    try:
        area = request.args.get('area')
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
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
            
        listing_date_gte = f"{start_date}T00:00:00.000Z"
        listing_date_lte = f"{end_date}T23:59:59.999Z"
        
        # Use basic event fetcher
        event_fetcher = EnhancedEventFetcher(
            areas=area,
            listing_date_gte=listing_date_gte,
            listing_date_lte=listing_date_lte
        )
        
        events_data = event_fetcher.fetch_all_events()
        
        return jsonify({
            "status": "success",
            "version": "v1",
            "area": area,
            "events": events_data.get("events", []),
            "total": len(events_data.get("events", []))
        })
        
    except Exception as e:
        return jsonify({"error": "Internal server error", "message": str(e)}), 500

@app.route('/v2/events', methods=['GET'])
def get_events_v2():
    """Enhanced events endpoint with advanced filtering support (v2)"""
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
                "version": "v2",
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

@app.route('/v2/filters', methods=['GET'])
def get_available_filters_v2():
    """Get available filters with enhanced information (v2)"""
    try:
        area = request.args.get('area', 1)
        
        try:
            area = int(area)
        except ValueError:
            return jsonify({"error": "Area must be a number"}), 400
        
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

@app.route('/v3/events', methods=['GET'])
def get_events_v3():
    """Ultimate events endpoint with maximum multi-value filtering flexibility (v3)"""
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
                    "filter": "Ultimate filter expression with all 8 operators"
                },
                "ultimate_examples": {
                    "multi_genre_AND": "/v3/events?area=1&start_date=2025-08-10&end_date=2025-08-17&filter=genre:contains_all:techno,industrial",
                    "multi_genre_OR": "/v3/events?area=1&start_date=2025-08-10&end_date=2025-08-17&filter=genre:contains_any:techno,house,minimal",
                    "artist_filtering": "/v3/events?area=1&start_date=2025-08-10&end_date=2025-08-17&filter=artists:has:charlotte",
                    "complex_logic": "/v3/events?area=1&start_date=2025-08-10&end_date=2025-08-17&filter=genre:contains_all:techno,industrial AND eventType:eq:club",
                    "exclusion": "/v3/events?area=1&start_date=2025-08-10&end_date=2025-08-17&filter=genre:contains_none:jazz,ambient"
                },
                "all_operators": {
                    "eq": "equals - genre:eq:techno",
                    "ne": "not equals - genre:ne:jazz", 
                    "in": "in array (OR) - genre:in:techno,house",
                    "nin": "not in array - genre:nin:jazz,ambient",
                    "has": "has specific value - artists:has:charlotte",
                    "contains_all": "has ALL values (AND) - genre:contains_all:techno,industrial",
                    "contains_any": "has ANY values (OR) - genre:contains_any:techno,house,minimal",
                    "contains_none": "has NONE of values - genre:contains_none:jazz,ambient"
                },
                "logical_operators": ["AND", "OR", "NOT"],
                "supported_fields": ["genre", "artists", "venue", "eventType", "area"]
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
        area_info = get_area_info(area)
        
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
                    "ultimate_filter": filter_expression,
                    "applied_filters": events_data.get('filter_info', {}),
                    "capabilities": {
                        "multi_value_fields": ["genre", "artists", "venue"],
                        "all_operators": ["eq", "ne", "in", "nin", "has", "contains_all", "contains_any", "contains_none"],
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
            
            return jsonify(response)
        
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": "Internal server error", "message": str(e)}), 500

@app.route('/v3/filters', methods=['GET'])
def get_available_filters_v3():
    """Get available filters with ultimate multi-value capabilities (v3)"""
    try:
        area = request.args.get('area', 1)
        
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
        
        # Create an advanced fetcher to get filter options
        event_fetcher = AdvancedEventFetcher(
            areas=area,
            listing_date_gte=listing_date_gte,
            listing_date_lte=listing_date_lte,
            include_bumps=True
        )
        
        # Fetch just one page to get filter options
        result = event_fetcher.get_events(1)
        filter_options = result.get("filter_options", {})
        
        response = {
            "version": "v3_ultimate",
            "area": area,
            "ultimate_features": {
                "multi_value_fields": "Support for arrays of genres, artists, venues",
                "all_operators": "Complete set of 8 operators for maximum flexibility",
                "advanced_logic": "Complex AND/OR/NOT expressions with multi-value support",
                "artist_filtering": "Filter events by specific artists: artists:has:charlotte",
                "venue_filtering": "Filter events by venue: venue:has:fabric",
                "genre_arrays": "Events can have multiple genres, filter with contains_all/contains_any"
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
        
        response["ultimate_examples"] = {
            "multi_genre_AND": "/v3/events?area=1&start_date=2025-08-10&end_date=2025-08-17&filter=genre:contains_all:techno,industrial",
            "multi_genre_OR": "/v3/events?area=1&start_date=2025-08-10&end_date=2025-08-17&filter=genre:contains_any:techno,house,minimal",
            "artist_search": "/v3/events?area=1&start_date=2025-08-10&end_date=2025-08-17&filter=artists:has:charlotte",
            "venue_search": "/v3/events?area=1&start_date=2025-08-10&end_date=2025-08-17&filter=venue:has:fabric",
            "complex_AND": "/v3/events?area=1&start_date=2025-08-10&end_date=2025-08-17&filter=genre:contains_all:techno,industrial AND eventType:eq:club",
            "exclusion": "/v3/events?area=1&start_date=2025-08-10&end_date=2025-08-17&filter=genre:contains_none:jazz,ambient",
            "artist_genre_combo": "/v3/events?area=1&start_date=2025-08-10&end_date=2025-08-17&filter=artists:has:charlotte AND genre:contains_any:techno,minimal"
        }
        
        response["all_operators"] = {
            "eq": "equals (exact match) - genre:eq:techno",
            "ne": "not equals - genre:ne:jazz",
            "in": "in array (OR logic) - genre:in:techno,house",
            "nin": "not in array - genre:nin:jazz,ambient",
            "has": "has specific value (for multi-value fields) - artists:has:charlotte",
            "contains_all": "has ALL specified values (AND logic) - genre:contains_all:techno,industrial",
            "contains_any": "has ANY specified values (OR logic) - genre:contains_any:techno,house,minimal",
            "contains_none": "has NONE of specified values - genre:contains_none:jazz,ambient"
        }
        
        response["logical_operators"] = ["AND", "OR", "NOT"]
        
        response["supported_fields"] = {
            "genre": "Music genre (multi-value)",
            "artists": "Artist names (multi-value)",
            "venue": "Venue names (multi-value)",
            "eventType": "Event type (single value)",
            "area": "Geographic area (single value)"
        }
        
        return jsonify(response)
        
    except Exception as e:
        return jsonify({"error": "Internal server error", "message": str(e)}), 500

if __name__ == '__main__':
    # Debug: Print all registered routes
    print("Registered routes:")
    for rule in app.url_map.iter_rules():
        print(f"  {rule.rule} -> {rule.endpoint}")
    
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=True)
