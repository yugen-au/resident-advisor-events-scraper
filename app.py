from flask import Flask, request, jsonify, send_file
import os
import tempfile
import json
import re
import requests
from datetime import datetime
from event_fetcher import EventFetcher

app = Flask(__name__)

def get_area_id_from_name(area_name):
    """
    Get area ID by scraping RA's events page for the given area name
    """
    try:
        # Clean the area name (lowercase, replace spaces with hyphens)
        clean_name = area_name.lower().replace(' ', '-').replace('_', '-')
        
        # Visit RA's events page for this area
        url = f"https://ra.co/events/{clean_name}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:106.0) Gecko/20100101 Firefox/106.0'
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            # Look for GraphQL requests or area ID in the page
            # This is a simplified approach - we might need to make it more robust
            content = response.text
            
            # Try to find area ID in script tags or data attributes
            # Pattern might vary - this is a starting point
            area_id_match = re.search(r'"areaId["\s]*:\s*(\d+)', content)
            if area_id_match:
                return int(area_id_match.group(1))
                
            # Alternative patterns to look for
            area_match = re.search(r'"area["\s]*:\s*(\d+)', content)
            if area_match:
                return int(area_match.group(1))
                
        return None
        
    except Exception as e:
        print(f"Error getting area ID for {area_name}: {e}")
        return None

@app.route('/', methods=['GET'])
def health_check():
    return jsonify({
        "status": "healthy", 
        "message": "RA Events Scraper API",
        "endpoints": {
            "events": "/events?area={area}&start_date={YYYY-MM-DD}&end_date={YYYY-MM-DD}&format={json|csv}",
            "areas": "/areas"
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
                    "suggestion": "Try area names like 'sydney', 'melbourne', 'berlin', 'new-york'"
                }), 404
            
        # Validate area is numeric
        try:
            area = int(area)
        except (ValueError, TypeError):
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
                "area": area,
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
    Return known RA area codes for reference
    """
    known_areas = {
        "1": "Sydney (+ Brisbane)",
        "2": "Melbourne",
        "3": "Perth", 
        "4": "Canberra",
        "5": "Adelaide",
        "6": "Hobart",
        "8": "New York, US",
        "433": "New South Wales",
        "674": "Byron Bay"
    }
    return jsonify({
        "message": "Known Resident Advisor area codes",
        "areas": known_areas,
        "note": "Use 'area' parameter with numeric codes, or 'area_name' parameter with city names like 'sydney', 'melbourne'",
        "examples": [
            "/events?area=1&start_date=2025-08-10&end_date=2025-08-17",
            "/events?area_name=berlin&start_date=2025-08-10&end_date=2025-08-17"
        ]
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=False)
