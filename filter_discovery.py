#!/usr/bin/env python3
"""
Quick test to discover RA GraphQL filtering capabilities
"""

import requests
import json
from datetime import datetime, timedelta

URL = 'https://ra.co/graphql'
HEADERS = {
    'Content-Type': 'application/json',
    'Referer': 'https://ra.co/events',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:106.0) Gecko/20100101 Firefox/106.0'
}

def test_operators():
    """Test key operators we need"""
    today = datetime.now()
    tomorrow = today + timedelta(days=3)
    
    # Test IN operator for genres
    test_filters = {
        "areas": {"eq": 1},
        "listingDate": {
            "gte": today.strftime("%Y-%m-%dT00:00:00.000Z"),
            "lte": tomorrow.strftime("%Y-%m-%dT23:59:59.999Z")
        },
        "genre": {"in": ["techno", "house"]}  # Test multiple genres
    }
    
    payload = {
        "operationName": "GET_EVENT_LISTINGS_WITH_BUMPS",
        "variables": {
            "filters": test_filters,
            "filterOptions": {"genre": True, "eventType": True},
            "pageSize": 5,
            "page": 1,
            "areaId": 1
        },
        "query": """query GET_EVENT_LISTINGS_WITH_BUMPS($filters: FilterInputDtoInput, $filterOptions: FilterOptionsInputDtoInput, $page: Int, $pageSize: Int, $areaId: ID) {
            eventListingsWithBumps(filters: $filters, filterOptions: $filterOptions, pageSize: $pageSize, page: $page, areaId: $areaId) {
                eventListings {
                    data { id event { title } }
                    totalResults
                }
            }
        }"""
    }
    
    try:
        response = requests.post(URL, headers=HEADERS, json=payload, timeout=10)
        result = response.json()
        
        if 'errors' in result:
            print("IN operator not supported:", result['errors'][0]['message'])
            return False
        elif 'data' in result:
            count = result['data']['eventListingsWithBumps']['eventListings']['totalResults']
            print(f"IN operator supported - found {count} results")
            return True
    except Exception as e:
        print(f"Error testing: {e}")
        return False

if __name__ == "__main__":
    print("Testing GraphQL IN operator support...")
    test_operators()
