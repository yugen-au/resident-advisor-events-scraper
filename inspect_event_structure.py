#!/usr/bin/env python3
"""
Test script to examine event data structure for multi-genre support
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from enhanced_event_fetcher import EnhancedEventFetcher
from datetime import datetime, timedelta
import json

def inspect_event_structure():
    """Inspect actual event data structure"""
    
    print("Inspecting Event Data Structure")
    print("=" * 40)
    
    # Test dates (next week)
    today = datetime.now()
    next_week = today + timedelta(days=7)
    
    start_date = today.strftime("%Y-%m-%dT00:00:00.000Z")
    end_date = next_week.strftime("%Y-%m-%dT23:59:59.999Z")
    
    try:
        fetcher = EnhancedEventFetcher(
            areas=1,  # Sydney
            listing_date_gte=start_date,
            listing_date_lte=end_date
        )
        
        # Get one page of events
        result = fetcher.get_events(1)
        
        events = result.get('events', [])
        if events:
            print(f"Found {len(events)} events. Examining first event structure...")
            
            # Look at first event in detail
            first_event = events[0]
            print("\nFirst Event Structure:")
            print(json.dumps(first_event, indent=2)[:2000] + "..." if len(str(first_event)) > 2000 else json.dumps(first_event, indent=2))
            
            # Check if genre info is available
            event_data = first_event.get('event', {})
            print(f"\nEvent data keys: {list(event_data.keys())}")
            
            # Look for genre information
            if 'pick' in event_data:
                pick_data = event_data.get('pick', {})
                print(f"Pick data: {pick_data}")
            
            # Check artists (might have genre info)
            artists = event_data.get('artists', [])
            if artists:
                print(f"\nFirst artist: {artists[0]}")
        
        # Check filter options for genre structure
        filter_options = result.get('filter_options', {})
        if 'genre' in filter_options:
            genres = filter_options['genre'][:5]
            print(f"\nAvailable genre options (first 5):")
            for genre in genres:
                print(f"  {genre}")
        
    except Exception as e:
        print(f"ERROR: {e}")

if __name__ == "__main__":
    inspect_event_structure()
