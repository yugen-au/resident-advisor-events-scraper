from flask import Flask, request, jsonify, send_file
import os
import tempfile
import json
from datetime import datetime
from event_fetcher import EventFetcher

app = Flask(__name__)

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
    - area: Area code (required)
    - start_date: Start date YYYY-MM-DD (required) 
    - end_date: End date YYYY-MM-DD (required)
    - format: 'csv' or 'json' (optional, default: json)
    """
    try:
        # Get query parameters
        area = request.args.get('area')
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        output_format = request.args.get('format', 'json').lower()
        
        # Validate required parameters
        if not all([area, start_date, end_date]):
            return jsonify({
                "error": "Missing required parameters",
                "required": ["area", "start_date", "end_date"],
                "example": "/events?area=34&start_date=2025-08-10&end_date=2025-08-17"
            }), 400
            
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
    Return common RA area codes for reference
    """
    common_areas = {
        "1": "London, UK",
        "3": "New York, US", 
        "5": "Berlin, DE",
        "13": "Amsterdam, NL",
        "17": "Barcelona, ES",
        "34": "Sydney, AU",
        "44": "Melbourne, AU",
        "18": "Paris, FR",
        "40": "Los Angeles, US",
        "47": "Tokyo, JP",
        "15": "Ibiza, ES",
        "19": "Chicago, US",
        "39": "Miami, US",
        "22": "Detroit, US"
    }
    return jsonify({
        "message": "Common Resident Advisor area codes",
        "areas": common_areas,
        "note": "Use the numeric keys as the 'area' parameter"
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=False)
