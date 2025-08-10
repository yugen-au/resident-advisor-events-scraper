# Enhanced Event Fetcher with Multi-Value Field Support
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

class AdvancedFilterExpression:
    """Parse and apply complex filter expressions with multi-value field support"""
    
    def __init__(self, expression: str = None):
        self.expression = expression
        self.graphql_filters = {}
        self.client_filters = []
        
        if expression:
            self._parse_expression(expression)
    
    def _parse_expression(self, expression: str):
        """Parse filter expression into GraphQL and client-side components"""
        # Enhanced parser for expressions like:
        # "genre:has:techno" - event has techno genre
        # "genre:contains_all:techno,industrial" - event has ALL specified genres
        # "genre:contains_any:techno,house" - event has ANY of specified genres
        # "genre:in:techno,house" - genre is one of these (OR logic)
        # "genre:has:techno AND genre:has:industrial" - event has both genres (AND logic)
        
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
        # Multi-value operators need client-side processing
        
        if operator in ['eq', 'ne', 'gte', 'lte']:
            return True
        if operator in ['in', 'has', 'contains_all', 'contains_any', 'nin']:
            return False  # Require client-side processing
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
        """Apply client-side filters to event list with multi-value support"""
        if not self.client_filters:
            return events
        
        filtered_events = []
        
        for event in events:
            if self._event_matches_client_filters(event):
                filtered_events.append(event)
        
        return filtered_events
    
    def _event_matches_client_filters(self, event: Dict) -> bool:
        """Check if event matches all client-side filters with enhanced logic"""
        for filter_def in self.client_filters:
            field = filter_def['field']
            operator = filter_def['operator']
            values = filter_def['values']
            logical_op = filter_def.get('logical_op', 'AND')
            
            # Get field value from event (can be single value or array)
            event_values = self._get_event_field_values(event, field)
            
            # Apply filter with enhanced operators
            matches = self._apply_filter_operator(event_values, operator, values, logical_op)
            
            # For now, use AND logic (all filters must match)
            if not matches:
                return False
        
        return True
    
    def _apply_filter_operator(self, event_values: Union[str, List[str]], operator: str, 
                             filter_values: List[str], logical_op: str) -> bool:
        """Apply filter operator with support for multi-value fields"""
        
        # Ensure event_values is a list for consistent processing
        if isinstance(event_values, str):
            event_values = [event_values] if event_values else []
        elif not isinstance(event_values, list):
            event_values = []
        
        # Normalize for comparison (lowercase, strip)
        event_values = [str(v).lower().strip() for v in event_values if v]
        filter_values = [str(v).lower().strip() for v in filter_values if v]
        
        if operator == 'eq':
            # Exact match (any event value equals any filter value)
            return any(ev in filter_values for ev in event_values)
        
        elif operator == 'ne':
            # Not equal (no event value equals any filter value)
            return not any(ev in filter_values for ev in event_values)
        
        elif operator == 'in':
            # Same as eq for multi-value fields (OR logic)
            return any(ev in filter_values for ev in event_values)
        
        elif operator == 'nin':
            # Not in array (no event value is in filter values)
            return not any(ev in filter_values for ev in event_values)
        
        elif operator == 'has':
            # Event has this specific value (for single value checks)
            return filter_values[0] in event_values
        
        elif operator == 'contains_all':
            # Event has ALL of the specified values (AND logic)
            return all(fv in event_values for fv in filter_values)
        
        elif operator == 'contains_any':
            # Event has ANY of the specified values (OR logic)  
            return any(fv in event_values for fv in filter_values)
        
        elif operator == 'contains_none':
            # Event has NONE of the specified values
            return not any(fv in event_values for fv in filter_values)
        
        else:
            # Unknown operator, don't filter
            return True
    
    def _get_event_field_values(self, event: Dict, field: str) -> Union[str, List[str]]:
        """Extract field values from event object (can return single value or array)"""
        
        if field == 'genre':
            # Try multiple sources for genre information
            event_data = event.get('event', {})
            
            # Check pick field
            pick = event_data.get('pick', {})
            if pick and 'genre' in pick:
                genre = pick.get('genre')
                return genre if isinstance(genre, list) else [genre] if genre else []
            
            # Try to infer from artists (artists might have genre info)
            artists = event_data.get('artists', [])
            genres = []
            for artist in artists:
                if 'genre' in artist:
                    artist_genre = artist.get('genre')
                    if isinstance(artist_genre, list):
                        genres.extend(artist_genre)
                    elif artist_genre:
                        genres.append(artist_genre)
            
            if genres:
                return genres
            
            # Fallback: try direct genre field
            direct_genre = event_data.get('genre')
            if direct_genre:
                return direct_genre if isinstance(direct_genre, list) else [direct_genre]
            
            # If no genre found, return empty list
            return []
        
        elif field == 'artists':
            # Get artist names
            event_data = event.get('event', {})
            artists = event_data.get('artists', [])
            return [artist.get('name', '') for artist in artists if artist.get('name')]
        
        elif field == 'eventType':
            event_data = event.get('event', {})
            event_type = event_data.get('eventType', '')
            return [event_type] if event_type else []
        
        elif field == 'venue':
            event_data = event.get('event', {})
            venue = event_data.get('venue', {})
            venue_name = venue.get('name', '')
            return [venue_name] if venue_name else []
        
        elif field == 'area':
            # Area would be in the venue or location
            event_data = event.get('event', {})
            venue = event_data.get('venue', {})
            area = venue.get('area', '')
            return [area] if area else []
        
        # Default: try direct access
        event_data = event.get('event', {})
        value = event_data.get(field, '')
        return [value] if value else []


class EnhancedEventFetcher:
    """Enhanced class with multi-value field filtering support"""

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
        
        # New: Advanced filtering with multi-value support
        self.filter_expr = AdvancedFilterExpression(filter_expression) if filter_expression else None
        
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
        """Fetch all events with enhanced multi-value filtering applied"""
        print(f"Fetching events with enhanced multi-value filtering...")
        if self.filter_expr and self.filter_expr.client_filters:
            print(f"Client-side filters will be applied: {len(self.filter_expr.client_filters)} filters")
            for cf in self.filter_expr.client_filters:
                print(f"  - {cf['field']} {cf['operator']} {cf['values']}")
        
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
        
        # Apply client-side filters with enhanced operators
        if self.filter_expr:
            print(f"Applying enhanced client-side filters to {len(all_events)} events...")
            all_events = self.filter_expr.apply_client_filters(all_events)
            all_bumps = self.filter_expr.apply_client_filters(all_bumps)
            print(f"After enhanced filtering: {len(all_events)} events")
        
        return {
            "events": all_events,
            "bumps": all_bumps,
            "total_events": len(all_events),
            "total_bumps": len(all_bumps),
            "filter_info": {
                "graphql_filters_applied": self.filter_expr.get_graphql_filters() if self.filter_expr else {},
                "client_filters_applied": len(self.filter_expr.client_filters) if self.filter_expr else 0,
                "enhanced_operators_available": [
                    "eq", "ne", "in", "nin", "has", "contains_all", "contains_any", "contains_none"
                ]
            }
        }
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
    """Enhanced command line interface with advanced multi-value filtering"""
    parser = argparse.ArgumentParser(description="Fetch RA events with advanced multi-value filtering")
    parser.add_argument("area", type=int, help="Area ID")
    parser.add_argument("start_date", help="Start date (YYYY-MM-DD)")
    parser.add_argument("end_date", help="End date (YYYY-MM-DD)")
    parser.add_argument("-o", "--output", default="events.csv", help="Output file")
    
    # Legacy filters
    parser.add_argument("-g", "--genre", help="Filter by genre")
    parser.add_argument("-t", "--event-type", help="Filter by event type")
    parser.add_argument("-s", "--sort", default="listingDate", choices=["listingDate", "score", "title"])
    parser.add_argument("--no-bumps", action="store_true", help="Exclude bumped events")
    
    # Advanced multi-value filter
    parser.add_argument("-f", "--filter", help="""Advanced filter expression with multi-value support
    
    Operators:
    - eq: equals (exact match)
    - ne: not equals  
    - in: in array (OR logic)
    - nin: not in array
    - has: has specific value (for multi-value fields)
    - contains_all: has ALL specified values (AND logic)
    - contains_any: has ANY specified values (OR logic)
    - contains_none: has NONE of specified values
    
    Examples:
    - genre:has:techno (events with techno genre)
    - genre:contains_all:techno,industrial (events with BOTH techno AND industrial)
    - genre:contains_any:techno,house (events with techno OR house)
    - genre:has:techno AND eventType:eq:club (techno club events)
    - artists:has:charlotte AND genre:contains_any:techno,minimal (Charlotte de Witte techno/minimal events)
    """)
    
    args = parser.parse_args()
    
    # Convert dates
    listing_date_gte = f"{args.start_date}T00:00:00.000Z"
    listing_date_lte = f"{args.end_date}T23:59:59.999Z"
    
    print(f"Advanced Event Fetcher - Area: {args.area}")
    print(f"Date range: {args.start_date} to {args.end_date}")
    if args.filter:
        print(f"Advanced multi-value filter: {args.filter}")
    
    # Create advanced fetcher
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
        print(f"Enhanced operators available: {', '.join(filter_info['enhanced_operators_available'])}")


if __name__ == "__main__":
    main()
