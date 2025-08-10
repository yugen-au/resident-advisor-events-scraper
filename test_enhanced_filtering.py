#!/usr/bin/env python3
"""
Test script for enhanced filtering functionality
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from enhanced_event_fetcher import FilterExpression, EnhancedEventFetcher
from datetime import datetime, timedelta

def test_filter_expressions():
    """Test different filter expressions"""
    
    print("Testing Filter Expression Parser")
    print("=" * 40)
    
    test_cases = [
        "genre:eq:techno",
        "genre:in:techno,house,minimal",
        "genre:ne:jazz",
        "eventType:eq:club",
        "genre:in:techno,house AND eventType:eq:club",
        "genre:ne:jazz AND eventType:ne:festival"
    ]
    
    for expression in test_cases:
        print(f"\nTesting: {expression}")
        
        try:
            filter_expr = FilterExpression(expression)
            
            graphql_filters = filter_expr.get_graphql_filters()
            client_filters = filter_expr.get_client_filters()
            
            print(f"  GraphQL filters: {graphql_filters}")
            print(f"  Client filters: {len(client_filters)} filters")
            
            for cf in client_filters:
                print(f"    - {cf['field']} {cf['operator']} {cf['values']}")
                
        except Exception as e:
            print(f"  ERROR: {e}")

def test_enhanced_fetcher():
    """Test the enhanced event fetcher with a simple query"""
    
    print("\n\nTesting Enhanced Event Fetcher")
    print("=" * 40)
    
    # Test dates (next week)
    today = datetime.now()
    next_week = today + timedelta(days=7)
    
    start_date = today.strftime("%Y-%m-%dT00:00:00.000Z")
    end_date = next_week.strftime("%Y-%m-%dT23:59:59.999Z")
    
    print(f"Date range: {start_date} to {end_date}")
    
    try:
        # Test with filter expression
        fetcher = EnhancedEventFetcher(
            areas=1,  # Sydney
            listing_date_gte=start_date,
            listing_date_lte=end_date,
            filter_expression="genre:in:techno,house"
        )
        
        print("Created fetcher with filter: genre:in:techno,house")
        
        # Test just getting one page
        result = fetcher.get_events(1)
        
        print(f"Results: {len(result.get('events', []))} events")
        print(f"Filter options available: {list(result.get('filter_options', {}).keys())}")
        
        if result.get('filter_options', {}).get('genre'):
            genres = result['filter_options']['genre'][:5]  # First 5
            print("Available genres:")
            for genre in genres:
                print(f"  - {genre.get('label')} ({genre.get('count')} events)")
        
    except Exception as e:
        print(f"ERROR: {e}")

if __name__ == "__main__":
    test_filter_expressions()
    test_enhanced_fetcher()
