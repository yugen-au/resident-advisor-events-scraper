# Enhanced API endpoints with advanced filtering
# Add this to your existing app.py

from enhanced_event_fetcher import EnhancedEventFetcher as EnhancedEventFetcherV2, FilterExpression

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
            "complex": "/v2/events?area=1&start_date=2025-08-10&end_date=2025-08-17&filter=genre:in:techno,house AND eventType:eq:club AND sort=score"
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


# Add enhanced batch processing with filtering
@app.route('/v2/events/batch', methods=['POST'])
def batch_events_v2():
    """Enhanced batch event fetching with advanced filtering"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                "error": "Missing request body",
                "example": {
                    "areas": [1, 2],
                    "start_date": "2025-08-10",
                    "end_date": "2025-08-17",
                    "filter": "genre:in:techno,house"
                }
            }), 400
        
        areas = data.get('areas', [])
        start_date = data.get('start_date')
        end_date = data.get('end_date')
        filter_expression = data.get('filter')
        
        # Legacy filters
        genre = data.get('genre')
        event_type = data.get('event_type')
        sort_by = data.get('sort', 'listingDate')
        include_bumps = data.get('include_bumps', True)
        
        if not areas or not start_date or not end_date:
            return jsonify({
                "error": "Missing required fields",
                "required": ["areas", "start_date", "end_date"],
                "optional": ["genre", "event_type", "sort", "include_bumps", "filter"]
            }), 400
        
        if len(areas) > 5:
            return jsonify({"error": "Maximum 5 areas per batch request"}), 400
        
        # Convert dates
        listing_date_gte = f"{start_date}T00:00:00.000Z"
        listing_date_lte = f"{end_date}T23:59:59.999Z"
        
        batch_results = {}
        total_events = 0
        total_bumps = 0
        
        for area in areas:
            print(f"Processing area {area} with enhanced filtering...")
            
            try:
                # Create enhanced fetcher for each area
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
                
                # Fetch events for this area
                events_data = event_fetcher.fetch_all_events()
                
                batch_results[str(area)] = {
                    "area_info": get_area_info(area),
                    "events_count": events_data.get('total_events', 0),
                    "bumps_count": events_data.get('total_bumps', 0),
                    "events": events_data.get('events', []),
                    "bumps": events_data.get('bumps', []),
                    "filter_info": events_data.get('filter_info', {})
                }
                
                total_events += events_data.get('total_events', 0)
                total_bumps += events_data.get('total_bumps', 0)
                
                # Rate limiting between areas
                time.sleep(1)
                
            except Exception as e:
                batch_results[str(area)] = {
                    "error": f"Failed to fetch events for area {area}: {str(e)}",
                    "events_count": 0,
                    "bumps_count": 0,
                    "events": [],
                    "bumps": []
                }
        
        return jsonify({
            "status": "success",
            "batch_info": {
                "areas_processed": len(areas),
                "date_range": {"start": start_date, "end": end_date},
                "filter_applied": filter_expression,
                "total_events": total_events,
                "total_bumps": total_bumps
            },
            "results": batch_results
        })
        
    except Exception as e:
        return jsonify({"error": "Internal server error", "message": str(e)}), 500
