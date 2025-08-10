# Enhanced Event Fetcher with Hybrid Filtering
import requests
import json
import time
import csv
import sys
import argparse
import re
from datetime import datetime, timedelta
from typing import Dict, List, Any, Union, Optional

URL = 'https://ra.co/graphql'
HEADERS = {
    'Content-Type': 'application/json',
    'Referer': 'https://ra.co/events/uk/london',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:106.0) Gecko/20100101 Firefox/106.0'
}
DELAY = 1  # Rate limiting delay

class FilterExpression:
    """Parse and apply complex filter expressions"""
    
    def __init__(self, expression: str = None):
        self.expression = expression
        self.graphql_filters = {}
        self.client_filters = []
        
        if expression:
            self._parse_expression(expression)
    
    def _parse_expression(self, expression: str):
        """Parse filter expression into GraphQL and client-side components"""
        # Simple parser for expressions like:
        # "genre:in:techno,house" 
        # "area:eq:1 AND genre:ne:jazz"
        # "area:eq:1 AND NOT genre:in:jazz,ambient"
        
        # Split by logical operators
        parts = re.split(r'\s+(AND|OR|NOT)\s+', expression)
        
        current_operator = 'AND'
        
        for i, part in enumerate(parts):
            part = part.strip()
            
            if part in ['AND', 'OR', 'NOT']:
                current_operator = part
                continue
                
            if ':' in part:
                field, operator, values = part.split(':', 2)
                
                # Check if we can handle this in GraphQL
                if self._can_handle_in_graphql(field, operator, values):
                    self._add_graphql_filter(field, operator, values)
                else:
                    self._add_client_filter(field, operator, values, current_operator)
    
    def _can_handle_in_graphql(self, field: str, operator: str, values: str) -> bool:
        """Check if this filter can be handled by GraphQL"""
        # Based on our testing, RA GraphQL supports:
        # - eq, ne for single values
        # - gte, lte for dates
        # - NOT operator not supported natively
        # - IN operator not supported natively
        
        if operator in ['eq', 'ne', 'gte', 'lte']:
            return True
        if operator == 'in':
            return False  # Not supported by RA
        return False
    
    def _add_graphql_filter(self, field: str, operator: str, values: str):
        """Add filter that can be handled by GraphQL"""
        if operator == 'eq':
            self.graphql_filters[field] = {"eq": values}
        elif operator == 'ne':
            self.graphql_filters[field] = {"ne": values}
        elif operator == 'gte':
            if field not in self.graphql_filters:
                self.graphql_filters[field] = {}
            self.graphql_filters[field]["gte"] = values
        elif operator == 'lte':
            if field not in self.graphql_filters:
                self.graphql_filters[field] = {}
            self.graphql_filters[field]["lte"] = values
    
    def _add_client_filter(self, field: str, operator: str, values: str, logical_op: str):
        """Add filter that needs client-side processing"""
        self.client_filters.append({
            'field': field,
            'operator': operator, 
            'values': values.split(',') if ',' in values else [values],
            'logical_op': logical_op
        })
    
    def get_graphql_filters(self) -> Dict[str, Any]:
        """Get filters that can be applied at GraphQL level"""
        return self.graphql_filters
    
    def get_client_filters(self) -> List[Dict[str, Any]]:
        """Get filters that need client-side processing"""
        return self.client_filters
    
    def apply_client_filters(self, events: List[Dict]) -> List[Dict]:
        """Apply client-side filters to event list"""
        if not self.client_filters:
            return events
        
        filtered_events = []
        
        for event in events:
            if self._event_matches_client_filters(event):
                filtered_events.append(event)
        
        return filtered_events
    
    def _event_matches_client_filters(self, event: Dict) -> bool:
        """Check if event matches all client-side filters"""
        for filter_def in self.client_filters:
            field = filter_def['field']
            operator = filter_def['operator']
            values = filter_def['values']
            logical_op = filter_def.get('logical_op', 'AND')
            
            # Get field value from event
            event_value = self._get_event_field_value(event, field)
            
            # Apply filter
            if operator == 'in':
                matches = event_value in values
            elif operator == 'nin' or (logical_op == 'NOT' and operator == 'in'):
                matches = event_value not in values
            elif operator == 'eq':
                matches = event_value == values[0]
            elif operator == 'ne':
                matches = event_value != values[0]
            else:
                matches = True  # Unknown operator, don't filter
            
            # For now, use AND logic (all filters must match)
            if not matches:
                return False
        
        return True
    
    def _get_event_field_value(self, event: Dict, field: str) -> Any:
        """Extract field value from event object"""
        # Map filter field names to event object structure
        if field == 'genre':
            # Genre might be in event.pick.genre or similar
            return event.get('event', {}).get('genre', '')
        elif field == 'area':
            # Area would be in the venue or location
            return event.get('event', {}).get('venue', {}).get('area', '')
        elif field == 'eventType':
            return event.get('event', {}).get('eventType', '')
        
        # Default: try direct access
        return event.get('event', {}).get(field, '')


class EnhancedEventFetcher:
    """Enhanced class with hybrid filtering support"""

    def __init__(self, areas, listing_date_gte, listing_date_lte=None, genre=None, 
                 event_type=None, sort_by="listingDate", include_bumps=True, 
                 filter_expression=None):
        self.areas = areas
        self.listing_date_gte = listing_date_gte
        self.listing_date_lte = listing_date_lte
        self.genre = genre
        self.event_type = event_type
        self.sort_by = sort_by
        self.include_bumps = include_bumps
        
        # New: Advanced filtering
        self.filter_expr = FilterExpression(filter_expression) if filter_expression else None
        
        self.payload = self.generate_payload()

    def generate_payload(self):
        """Generate GraphQL payload with hybrid filtering"""
        operation_name = "GET_EVENT_LISTINGS_WITH_BUMPS" if self.include_bumps else "GET_EVENT_LISTINGS"
        
        # Start with base filters
        filters = {
            "areas": {"eq": self.areas},
            "listingDate": {"gte": self.listing_date_gte}
        }
        
        if self.listing_date_lte:
            filters["listingDate"]["lte"] = self.listing_date_lte
        
        # Add legacy filters
        if self.genre:
            filters["genre"] = {"eq": self.genre}
        if self.event_type:
            filters["eventType"] = {"eq": self.event_type}
        
        # Add advanced GraphQL filters
        if self.filter_expr:
            graphql_filters = self.filter_expr.get_graphql_filters()
            # Merge carefully to avoid conflicts
            for field, filter_def in graphql_filters.items():
                if field in filters and isinstance(filters[field], dict):
                    filters[field].update(filter_def)
                else:
                    filters[field] = filter_def
        
        # Configure sorting
        sort_config = self._get_sort_config()
        
        filter_options = {
            "genre": True,
            "eventType": True
        }

        if self.include_bumps:
            payload = {
                "operationName": "GET_EVENT_LISTINGS_WITH_BUMPS",
                "variables": {
                    "filters": filters,
                    "filterOptions": filter_options,
                    "pageSize": 20,
                    "page": 1,
                    "sort": sort_config,
                    "areaId": self.areas
                },
                "query": self._get_enhanced_query()
            }
        else:
            payload = {
                "operationName": "GET_EVENT_LISTINGS",
                "variables": {
                    "filters": filters,
                    "filterOptions": filter_options,
                    "pageSize": 20,
                    "page": 1
                },
                "query": self._get_basic_query()
            }

        return payload

    def fetch_all_events(self):
        """Fetch all events with hybrid filtering applied"""
        print(f"Fetching events with hybrid filtering...")
        if self.filter_expr and self.filter_expr.client_filters:
            print(f"Client-side filters will be applied: {len(self.filter_expr.client_filters)} filters")
        
        all_events = []
        all_bumps = []
        page = 1
        
        while True:
            print(f"Fetching page {page}...")
            result = self.get_events(page)
            
            events = result.get("events", [])
            bumps = result.get("bumps", [])
            
            if not events and not bumps:
                print("No more events found.")
                break
            
            all_events.extend(events)
            all_bumps.extend(bumps)
            
            page += 1
            time.sleep(DELAY)  # Rate limiting
            
            # Safety limit
            if page > 50:
                print("Reached page limit (50). Stopping.")
                break
        
        # Apply client-side filters
        if self.filter_expr:
            print(f"Applying client-side filters to {len(all_events)} events...")
            all_events = self.filter_expr.apply_client_filters(all_events)
            all_bumps = self.filter_expr.apply_client_filters(all_bumps)
            print(f"After client-side filtering: {len(all_events)} events")
        
        return {
            "events": all_events,
            "bumps": all_bumps,
            "total_events": len(all_events),
            "total_bumps": len(all_bumps),
            "filter_info": {
                "graphql_filters_applied": self.filter_expr.get_graphql_filters() if self.filter_expr else {},
                "client_filters_applied": len(self.filter_expr.client_filters) if self.filter_expr else 0
            }
        }

    def _get_sort_config(self):
        """Get sorting configuration based on sort_by parameter."""
        sort_configs = {
            "listingDate": {
                "listingDate": {"order": "ASCENDING"},
                "score": {"order": "DESCENDING"},
                "titleKeyword": {"order": "ASCENDING"}
            },
            "score": {
                "score": {"order": "DESCENDING"},
                "listingDate": {"order": "ASCENDING"},
                "titleKeyword": {"order": "ASCENDING"}
            },
            "title": {
                "titleKeyword": {"order": "ASCENDING"},
                "listingDate": {"order": "ASCENDING"},
                "score": {"order": "DESCENDING"}
            }
        }
        return sort_configs.get(self.sort_by, sort_configs["listingDate"])

    def get_events(self, page_number):
        """Fetch events for the given page number."""
        self.payload["variables"]["page"] = page_number
        response = requests.post(URL, headers=HEADERS, json=self.payload)

        try:
            response.raise_for_status()
            data = response.json()
        except (requests.exceptions.RequestException, ValueError) as e:
            print(f"Error fetching events: {e}")
            return {"events": [], "bumps": [], "filter_options": {}}

        if 'errors' in data:
            print(f"GraphQL errors: {data['errors']}")
            return {"events": [], "bumps": [], "filter_options": {}}

        if self.include_bumps:
            event_data = data.get("data", {}).get("eventListingsWithBumps", {})
        else:
            event_data = data.get("data", {}).get("eventListings", {})

        events = event_data.get("eventListings", {}).get("data", [])
        bumps_raw = event_data.get("bumps", [])
        
        # Process bumps to extract events (with safety checks)
        bumps = []
        if isinstance(bumps_raw, list):
            for bump in bumps_raw:
                if isinstance(bump, dict):
                    bump_decision = bump.get("bumpDecision", {})
                    if isinstance(bump_decision, dict) and bump_decision.get("event"):
                        bumps.append(bump_decision)
        
        filter_options = event_data.get("eventListings", {}).get("filterOptions", {})

        return {
            "events": events,
            "bumps": bumps,
            "filter_options": filter_options
        }

    def save_events_to_csv(self, events_data, output_file):
        """Save events to CSV with enhanced data"""
        events = events_data.get("events", [])
        
        with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = [
                'event_id', 'title', 'date', 'start_time', 'end_time',
                'venue_name', 'venue_id', 'artists', 'interested_count',
                'is_ticketed', 'content_url', 'flyer_front', 'promoters'
            ]
            
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            
            for event_item in events:
                event = event_item.get('event', {})
                
                # Extract artist names
                artists = ', '.join([artist.get('name', '') for artist in event.get('artists', [])])
                
                # Extract promoter info
                promoters = ', '.join([f"ID:{p.get('id', '')}" for p in event.get('promoters', [])])
                
                row = {
                    'event_id': event.get('id', ''),
                    'title': event.get('title', ''),
                    'date': event.get('date', ''),
                    'start_time': event.get('startTime', ''),
                    'end_time': event.get('endTime', ''),
                    'venue_name': event.get('venue', {}).get('name', ''),
                    'venue_id': event.get('venue', {}).get('id', ''),
                    'artists': artists,
                    'interested_count': event.get('interestedCount', 0),
                    'is_ticketed': event.get('isTicketed', False),
                    'content_url': event.get('contentUrl', ''),
                    'flyer_front': event.get('flyerFront', ''),
                    'promoters': promoters
                }
                
                writer.writerow(row)

    def _get_enhanced_query(self):
        """Get the enhanced GraphQL query with bumps support."""
        return """query GET_EVENT_LISTINGS_WITH_BUMPS($filters: FilterInputDtoInput, $filterOptions: FilterOptionsInputDtoInput, $page: Int, $pageSize: Int, $sort: SortInputDtoInput, $areaId: ID) {
  eventListingsWithBumps(
    filters: $filters
    filterOptions: $filterOptions
    pageSize: $pageSize
    page: $page
    sort: $sort
    areaId: $areaId
  ) {
    eventListings {
      data {
        id
        listingDate
        event {
          ...eventListingsFields
          __typename
        }
        __typename
      }
      filterOptions {
        genre {
          label
          value
          count
          __typename
        }
        eventType {
          value
          count
          __typename
        }
        __typename
      }
      totalResults
      __typename
    }
    bumps {
      bumpDecision {
        id
        date
        eventId
        clickUrl
        impressionUrl
        event {
          ...eventListingsFields
          artists {
            id
            name
            __typename
          }
          __typename
        }
        __typename
      }
      __typename
    }
    __typename
  }
}

fragment eventListingsFields on Event {
  id
  date
  startTime
  endTime
  title
  contentUrl
  flyerFront
  isTicketed
  interestedCount
  isSaved
  isInterested
  queueItEnabled
  newEventForm
  images {
    id
    filename
    alt
    type
    crop
    __typename
  }
  pick {
    id
    blurb
    __typename
  }
  venue {
    id
    name
    contentUrl
    live
    __typename
  }
  promoters {
    id
    __typename
  }
  artists {
    id
    name
    __typename
  }
  tickets(queryType: AVAILABLE) {
    validType
    onSaleFrom
    onSaleUntil
    __typename
  }
  __typename
}"""

    def _get_basic_query(self):
        """Get the basic GraphQL query without bumps."""
        return """query GET_EVENT_LISTINGS($filters: FilterInputDtoInput, $filterOptions: FilterOptionsInputDtoInput, $page: Int, $pageSize: Int) {
  eventListings(filters: $filters, filterOptions: $filterOptions, pageSize: $pageSize, page: $page) {
    data {
      id
      listingDate
      event {
        ...eventListingsFields
        artists {
          id
          name
          __typename
        }
        __typename
      }
      __typename
    }
    filterOptions {
      genre {
        label
        value
        count
        __typename
      }
      eventType {
        value
        count
        __typename
      }
      __typename
    }
    totalResults
    __typename
  }
}

fragment eventListingsFields on Event {
  id
  date
  startTime
  endTime
  title
  contentUrl
  flyerFront
  isTicketed
  interestedCount
  isSaved
  isInterested
  queueItEnabled
  newEventForm
  images {
    id
    filename
    alt
    type
    crop
    __typename
  }
  pick {
    id
    blurb
    __typename
  }
  venue {
    id
    name
    contentUrl
    live
    __typename
  }
  promoters {
    id
    __typename
  }
  artists {
    id
    name
    __typename
  }
  tickets(queryType: AVAILABLE) {
    validType
    onSaleFrom
    onSaleUntil
    __typename
  }
  __typename
}"""


def main():
    """Enhanced command line interface with filter expressions"""
    parser = argparse.ArgumentParser(description="Fetch RA events with advanced filtering")
    parser.add_argument("area", type=int, help="Area ID")
    parser.add_argument("start_date", help="Start date (YYYY-MM-DD)")
    parser.add_argument("end_date", help="End date (YYYY-MM-DD)")
    parser.add_argument("-o", "--output", default="events.csv", help="Output file")
    
    # Legacy filters
    parser.add_argument("-g", "--genre", help="Filter by genre")
    parser.add_argument("-t", "--event-type", help="Filter by event type")
    parser.add_argument("-s", "--sort", default="listingDate", choices=["listingDate", "score", "title"])
    parser.add_argument("--no-bumps", action="store_true", help="Exclude bumped events")
    
    # New advanced filter
    parser.add_argument("-f", "--filter", help="Advanced filter expression (e.g., 'genre:in:techno,house AND area:ne:2')")
    
    args = parser.parse_args()
    
    # Convert dates
    listing_date_gte = f"{args.start_date}T00:00:00.000Z"
    listing_date_lte = f"{args.end_date}T23:59:59.999Z"
    
    print(f"Enhanced Event Fetcher - Area: {args.area}")
    print(f"Date range: {args.start_date} to {args.end_date}")
    if args.filter:
        print(f"Advanced filter: {args.filter}")
    
    # Create enhanced fetcher
    fetcher = EnhancedEventFetcher(
        areas=args.area,
        listing_date_gte=listing_date_gte,
        listing_date_lte=listing_date_lte,
        genre=args.genre,
        event_type=args.event_type,
        sort_by=args.sort,
        include_bumps=not args.no_bumps,
        filter_expression=args.filter
    )
    
    # Fetch events
    events_data = fetcher.fetch_all_events()
    
    # Save to file
    fetcher.save_events_to_csv(events_data, args.output)
    
    print(f"Saved {events_data['total_events']} events to {args.output}")
    if events_data.get('filter_info'):
        filter_info = events_data['filter_info']
        print(f"GraphQL filters applied: {filter_info['graphql_filters_applied']}")
        print(f"Client-side filters applied: {filter_info['client_filters_applied']}")


if __name__ == "__main__":
    main()
