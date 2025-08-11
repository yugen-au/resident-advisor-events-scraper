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

class AdvancedFilterManager:
    """Generic manager for handling complex filtering operations for fields not directly in JSON"""
    
    def __init__(self, base_fetcher):
        self.base_fetcher = base_fetcher  # Reference to the EnhancedEventFetcher instance
        self.cache = {}  # Cache for query results
    
    def get_events_with_filter(self, field, value, operator="eq"):
        """Get events with a specific field filter"""
        cache_key = f"{field}_{operator}_{value}"
        
        if cache_key in self.cache:
            return self.cache[cache_key]
        
        # Create a new fetcher instance with just this filter
        from enhanced_event_fetcher_v2 import EnhancedEventFetcherV2
        
        # Build appropriate filter expression based on field and operator
        filter_expression = f"{field}:{operator}:{value}"
        
        fetcher = EnhancedEventFetcherV2(
            areas=self.base_fetcher.areas,
            listing_date_gte=self.base_fetcher.listing_date_gte,
            listing_date_lte=self.base_fetcher.listing_date_lte,
            sort_by=self.base_fetcher.sort_by,
            include_bumps=self.base_fetcher.include_bumps,
            filter_expression=filter_expression
        )
        
        # Fetch events with this specific filter
        events_data = fetcher.fetch_all_events()
        
        # Cache the results
        self.cache[cache_key] = {
            "events": events_data.get("events", []),
            "bumps": events_data.get("bumps", [])
        }
        
        return self.cache[cache_key]
    
    def contains_all(self, field, values):
        """Get events that contain ALL of the specified values for the field"""
        if not values:
            return {"events": [], "bumps": []}
        
        # Get events for the first value
        result = self.get_events_with_filter(field, values[0])
        events = result["events"]
        bumps = result["bumps"]
        
        # For each additional value, intersect the results
        for value in values[1:]:
            value_result = self.get_events_with_filter(field, value)
            
            # Create sets of event IDs for intersection
            current_event_ids = {event.get('event', {}).get('id') for event in events}
            value_event_ids = {event.get('event', {}).get('id') for event in value_result["events"]}
            
            # Intersect the sets
            common_ids = current_event_ids.intersection(value_event_ids)
            
            # Filter events to only those in the intersection
            events = [event for event in events if event.get('event', {}).get('id') in common_ids]
            
            # Do the same for bumps
            current_bump_ids = {bump.get('event', {}).get('id') for bump in bumps}
            value_bump_ids = {bump.get('event', {}).get('id') for bump in value_result["bumps"]}
            common_bump_ids = current_bump_ids.intersection(value_bump_ids)
            bumps = [bump for bump in bumps if bump.get('event', {}).get('id') in common_bump_ids]
        
        return {"events": events, "bumps": bumps}
    
    def contains_any(self, field, values):
        """Get events that contain ANY of the specified values for the field
        This maps directly to the V2 'any' operator"""
        
        # For contains_any, we can use the native GraphQL 'any' operator
        from enhanced_event_fetcher_v2 import EnhancedEventFetcherV2
        
        # For all fields, use the filter expression approach
        filter_expression = f"{field}:any:{','.join(values)}"
        
        fetcher = EnhancedEventFetcherV2(
            areas=self.base_fetcher.areas,
            listing_date_gte=self.base_fetcher.listing_date_gte,
            listing_date_lte=self.base_fetcher.listing_date_lte,
            sort_by=self.base_fetcher.sort_by,
            include_bumps=self.base_fetcher.include_bumps,
            filter_expression=filter_expression
        )
        
        # Fetch events with ANY of these values
        events_data = fetcher.fetch_all_events()
        
        return {
            "events": events_data.get("events", []),
            "bumps": events_data.get("bumps", [])
        }
    
    def contains_none(self, field, values):
        """Get events that contain NONE of the specified values for the field
        This is the inverse of contains_any"""
        
        # First, get all events without any filter
        from enhanced_event_fetcher_v2 import EnhancedEventFetcherV2
        
        fetcher = EnhancedEventFetcherV2(
            areas=self.base_fetcher.areas,
            listing_date_gte=self.base_fetcher.listing_date_gte,
            listing_date_lte=self.base_fetcher.listing_date_lte,
            sort_by=self.base_fetcher.sort_by,
            include_bumps=self.base_fetcher.include_bumps
        )
        
        # Fetch all events
        all_events_data = fetcher.fetch_all_events()
        all_events = all_events_data.get("events", [])
        all_bumps = all_events_data.get("bumps", [])
        
        # Then get events with any of these values
        any_result = self.contains_any(field, values)
        any_event_ids = {event.get('event', {}).get('id') for event in any_result["events"]}
        any_bump_ids = {bump.get('event', {}).get('id') for bump in any_result["bumps"]}
        
        # Exclude events with any of these values
        events = [event for event in all_events if event.get('event', {}).get('id') not in any_event_ids]
        bumps = [bump for bump in all_bumps if bump.get('event', {}).get('id') not in any_bump_ids]
        
        return {"events": events, "bumps": bumps}
    
    def greater_than(self, field, value):
        """Get events with field value greater than the specified value"""
        # This would require custom implementation since GraphQL doesn't support it directly
        # For now, fetch all events and filter client-side
        from enhanced_event_fetcher_v2 import EnhancedEventFetcherV2
        
        fetcher = EnhancedEventFetcherV2(
            areas=self.base_fetcher.areas,
            listing_date_gte=self.base_fetcher.listing_date_gte,
            listing_date_lte=self.base_fetcher.listing_date_lte,
            sort_by=self.base_fetcher.sort_by,
            include_bumps=self.base_fetcher.include_bumps
        )
        
        # Fetch all events
        all_events_data = fetcher.fetch_all_events()
        all_events = all_events_data.get("events", [])
        all_bumps = all_events_data.get("bumps", [])
        
        # Filter events client-side
        # This is a simplified implementation - actual implementation would need
        # to properly extract field values and handle numeric comparison
        threshold = float(value)
        filtered_events = []
        filtered_bumps = []
        
        for event in all_events:
            event_data = event.get('event', {})
            event_value = None
            
            # Extract appropriate field value based on field type
            if field == 'price':
                # Price might be in various formats
                # For demo purposes, we'll just extract numeric part
                price_str = event_data.get('price', '0')
                try:
                    event_value = float(re.sub(r'[^\d.]', '', price_str))
                except ValueError:
                    event_value = 0
            elif field == 'interested' or field == 'interestedCount':
                event_value = float(event_data.get('interestedCount', 0))
            
            # Add event if value exceeds threshold
            if event_value is not None and event_value > threshold:
                filtered_events.append(event)
        
        # Similar logic for bumps
        for bump in all_bumps:
            bump_data = bump.get('event', {})
            bump_value = None
            
            if field == 'price':
                price_str = bump_data.get('price', '0')
                try:
                    bump_value = float(re.sub(r'[^\d.]', '', price_str))
                except ValueError:
                    bump_value = 0
            elif field == 'interested' or field == 'interestedCount':
                bump_value = float(bump_data.get('interestedCount', 0))
            
            if bump_value is not None and bump_value > threshold:
                filtered_bumps.append(bump)
        
        return {"events": filtered_events, "bumps": filtered_bumps}
    
    def less_than(self, field, value):
        """Get events with field value less than the specified value"""
        # Similar to greater_than but with opposite comparison
        # Implementation follows same pattern as greater_than
        from enhanced_event_fetcher_v2 import EnhancedEventFetcherV2
        
        fetcher = EnhancedEventFetcherV2(
            areas=self.base_fetcher.areas,
            listing_date_gte=self.base_fetcher.listing_date_gte,
            listing_date_lte=self.base_fetcher.listing_date_lte,
            sort_by=self.base_fetcher.sort_by,
            include_bumps=self.base_fetcher.include_bumps
        )
        
        all_events_data = fetcher.fetch_all_events()
        all_events = all_events_data.get("events", [])
        all_bumps = all_events_data.get("bumps", [])
        
        threshold = float(value)
        filtered_events = []
        filtered_bumps = []
        
        for event in all_events:
            event_data = event.get('event', {})
            event_value = None
            
            if field == 'price':
                price_str = event_data.get('price', '0')
                try:
                    event_value = float(re.sub(r'[^\d.]', '', price_str))
                except ValueError:
                    event_value = 0
            elif field == 'interested' or field == 'interestedCount':
                event_value = float(event_data.get('interestedCount', 0))
            
            if event_value is not None and event_value < threshold:
                filtered_events.append(event)
        
        for bump in all_bumps:
            bump_data = bump.get('event', {})
            bump_value = None
            
            if field == 'price':
                price_str = bump_data.get('price', '0')
                try:
                    bump_value = float(re.sub(r'[^\d.]', '', price_str))
                except ValueError:
                    bump_value = 0
            elif field == 'interested' or field == 'interestedCount':
                bump_value = float(bump_data.get('interestedCount', 0))
            
            if bump_value is not None and bump_value < threshold:
                filtered_bumps.append(bump)
        
        return {"events": filtered_events, "bumps": filtered_bumps}
    
    def between(self, field, min_value, max_value):
        """Get events with field value between min and max (inclusive)"""
        # Implementation combines greater_than_equal and less_than_equal
        from enhanced_event_fetcher_v2 import EnhancedEventFetcherV2
        
        fetcher = EnhancedEventFetcherV2(
            areas=self.base_fetcher.areas,
            listing_date_gte=self.base_fetcher.listing_date_gte,
            listing_date_lte=self.base_fetcher.listing_date_lte,
            sort_by=self.base_fetcher.sort_by,
            include_bumps=self.base_fetcher.include_bumps
        )
        
        all_events_data = fetcher.fetch_all_events()
        all_events = all_events_data.get("events", [])
        all_bumps = all_events_data.get("bumps", [])
        
        min_threshold = float(min_value)
        max_threshold = float(max_value)
        filtered_events = []
        filtered_bumps = []
        
        for event in all_events:
            event_data = event.get('event', {})
            event_value = None
            
            if field == 'price':
                price_str = event_data.get('price', '0')
                try:
                    event_value = float(re.sub(r'[^\d.]', '', price_str))
                except ValueError:
                    event_value = 0
            elif field == 'interested' or field == 'interestedCount':
                event_value = float(event_data.get('interestedCount', 0))
            
            if event_value is not None and min_threshold <= event_value <= max_threshold:
                filtered_events.append(event)
        
        for bump in all_bumps:
            bump_data = bump.get('event', {})
            bump_value = None
            
            if field == 'price':
                price_str = bump_data.get('price', '0')
                try:
                    bump_value = float(re.sub(r'[^\d.]', '', price_str))
                except ValueError:
                    bump_value = 0
            elif field == 'interested' or field == 'interestedCount':
                bump_value = float(bump_data.get('interestedCount', 0))
            
            if bump_value is not None and min_threshold <= bump_value <= max_threshold:
                filtered_bumps.append(bump)
        
        return {"events": filtered_events, "bumps": filtered_bumps}

class GenreQueryManager(AdvancedFilterManager):
    """Specialized manager for genre filtering operations"""
    
    def __init__(self, base_fetcher):
        super().__init__(base_fetcher)
    
    def contains_all(self, values):
        """Specialized version that always uses 'genre' as the field"""
        return super().contains_all('genre', values)
    
    def contains_any(self, values):
        """Specialized version that always uses 'genre' as the field"""
        return super().contains_any('genre', values)
    
    def contains_none(self, values):
        """Specialized version that always uses 'genre' as the field"""
        return super().contains_none('genre', values)

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
                
                # Special case for genre:contains_any which maps to GraphQL genre:any
                if field == 'genre' and operator == 'contains_any':
                    self._add_graphql_filter(field, 'any', values)
                    continue
                
                # Check if we can handle this in GraphQL
                if self._can_handle_in_graphql(field, operator, values):
                    self._add_graphql_filter(field, operator, values)
                else:
                    self._add_client_filter(field, operator, values, current_operator)
    
    def _can_handle_in_graphql(self, field: str, operator: str, values: str) -> bool:
        """Check if this filter can be handled by GraphQL"""
        # Only 'eq' and 'any' operators are supported by GraphQL in V2
        if operator in ['eq', 'any']:
            return True
        # All other operators require client-side processing
        if operator in ['in', 'has', 'contains_all', 'contains_any', 'all', 
                       'gt', 'lt', 'gte', 'lte', 'between', 'starts', 'ends', 'nin']:
            return False
        return False
    
    def _add_graphql_filter(self, field: str, operator: str, values: str):
        """Add filter that can be handled by GraphQL"""
        if operator == 'eq':
            self.graphql_filters[field] = {"eq": values}
        elif operator == 'any':
            # For multi-value OR filtering
            value_list = [v.strip() for v in values.split(',')]
            self.graphql_filters[field] = {"any": value_list}
    
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
        
        elif operator == 'in':
            # Same as eq for multi-value fields (OR logic)
            return any(ev in filter_values for ev in event_values)
        
        elif operator == 'nin':
            # Not in array (no event value is in filter values)
            return not any(ev in filter_values for ev in event_values)
        
        elif operator == 'has':
            # Event has this specific value (for single value checks)
            for fv in filter_values:
                if any(fv.lower() in ev.lower() for ev in event_values):
                    return True
            return False
        
        elif operator == 'contains_all':
            # Event has ALL of the specified values (AND logic)
            return all(fv in event_values for fv in filter_values)
        
        elif operator == 'contains_any':
            # Event has ANY of the specified values (OR logic)
            # Note: For genres, this is handled differently using V2's native any operator
            # This client-side filtering is only a fallback for other fields
            return any(fv in event_values for fv in filter_values)
        
        elif operator == 'contains_none':
            # Event has NONE of the specified values
            return not any(fv in event_values for fv in filter_values)

        elif operator == 'all':
            # Same as contains_all but more readable
            return all(fv in event_values for fv in filter_values)
            
        elif operator == 'gt' or operator == 'lt' or operator == 'gte' or operator == 'lte':
            # Numeric comparisons
            if not event_values or not filter_values:
                return False
                
            try:
                # Convert to numeric values
                numeric_event_values = [float(ev) for ev in event_values]
                numeric_filter_value = float(filter_values[0])  # Use first value only
                
                if operator == 'gt':
                    return any(ev > numeric_filter_value for ev in numeric_event_values)
                elif operator == 'lt':
                    return any(ev < numeric_filter_value for ev in numeric_event_values)
                elif operator == 'gte':
                    return any(ev >= numeric_filter_value for ev in numeric_event_values)
                elif operator == 'lte':
                    return any(ev <= numeric_filter_value for ev in numeric_event_values)
            except (ValueError, TypeError):
                # If conversion fails, treat as false
                return False
                
        elif operator == 'between':
            # Range filtering (requires two values: min and max)
            if not event_values or len(filter_values) < 2:
                return False
                
            try:
                # Convert to numeric values
                numeric_event_values = [float(ev) for ev in event_values]
                min_val = float(filter_values[0])
                max_val = float(filter_values[1])
                
                # Check if any event value is within range
                return any(min_val <= ev <= max_val for ev in numeric_event_values)
            except (ValueError, TypeError):
                # If conversion fails, treat as false
                return False
                
        elif operator == 'starts':
            # String prefix matching
            if not event_values or not filter_values:
                return False
                
            prefix = filter_values[0].lower()
            return any(ev.startswith(prefix) for ev in event_values)
            
        elif operator == 'ends':
            # String suffix matching
            if not event_values or not filter_values:
                return False
                
            suffix = filter_values[0].lower()
            return any(ev.endswith(suffix) for ev in event_values)
        
        else:
            # Unknown operator, don't filter
            return True
    
    def _get_event_field_values(self, event: Dict, field: str) -> Union[str, List[str]]:
        """Extract field values from event object (can return single value or array)"""
        
        event_data = event.get('event', {})
        
        if field == 'genre':
            # Extract genres from filter options
            # Since genre data isn't directly available in the event object,
            # we need to use filter_options to map genre values or implement a lookup system
            
            # We can access filter options when we make the request but it's not in the event object
            # For now, we'll check if there's a genre match based on the current filter
            # and later implement a more robust approach
            
            # This is a placeholder for the genre extraction logic
            # In a real implementation, we would need to either:
            # 1. Use a separate request to get genre info for each event
            # 2. Parse from other fields like title, description, or metadata
            # 3. Implement a caching mechanism for genre information
            
            # For testing, extract any genre-like keywords from the title
            title = event_data.get('title', '').lower()
            common_genres = [
                'techno', 'house', 'ambient', 'trance', 'drum and bass', 'dnb',
                'minimal', 'deep house', 'tech house', 'progressive', 'disco',
                'funk', 'jazz', 'experimental', 'hip-hop', 'dubstep', 'garage'
            ]
            
            found_genres = []
            for genre in common_genres:
                if genre in title:
                    found_genres.append(genre)
            
            # Add extra handling for multi-word genres
            if 'drum' in title and 'bass' in title:
                found_genres.append('drum and bass')
            if 'deep' in title and 'house' in title:
                found_genres.append('deep house')
            if 'tech' in title and 'house' in title:
                found_genres.append('tech house')
            
            return found_genres
        
        elif field == 'artists':
            # Get artist names
            artists = event_data.get('artists', [])
            return [artist.get('name', '').lower() for artist in artists if artist.get('name')]
        
        elif field == 'eventType':
            event_type = event_data.get('eventType', '')
            return [event_type.lower()] if event_type else []
        
        elif field == 'venue':
            venue = event_data.get('venue', {})
            venue_name = venue.get('name', '')
            return [venue_name.lower()] if venue_name else []
        
        elif field == 'area':
            # Area would be in the venue or location
            venue = event_data.get('venue', {})
            area = venue.get('area', '')
            return [area.lower()] if area else []
            
        elif field == 'price' or field == 'cost':
            # Try to extract price/cost information if available
            # This would need to be adjusted based on actual data structure
            price = event_data.get('price', '')
            if not price:
                price = event_data.get('cost', '')
            return [price] if price else []
            
        elif field == 'title':
            title = event_data.get('title', '')
            return [title.lower()] if title else []
            
        elif field == 'date':
            date = event_data.get('date', '')
            return [date] if date else []
            
        elif field == 'time' or field == 'startTime':
            time = event_data.get('startTime', '')
            return [time] if time else []
            
        elif field == 'endTime':
            time = event_data.get('endTime', '')
            return [time] if time else []
            
        elif field == 'interested' or field == 'interestedCount':
            count = event_data.get('interestedCount', '')
            return [str(count)] if count != '' else []
            
        elif field == 'isTicketed':
            is_ticketed = event_data.get('isTicketed', '')
            return [str(is_ticketed).lower()] if is_ticketed != '' else []
        
        # Default: try direct access to event data
        value = event_data.get(field, '')
        return [value.lower()] if value else []


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
        
        # Extract any filters that need special handling
        special_filters = []
        other_filters = []
        
        if self.filter_expr and self.filter_expr.client_filters:
            print(f"DEBUG: Processing {len(self.filter_expr.client_filters)} client-side filters")
            
            for cf in self.filter_expr.client_filters:
                print(f"DEBUG: Client filter - {cf['field']} {cf['operator']} {cf['values']}")
                
                # Special handling for certain fields and operators
                needs_special_handling = False
                
                # Genre filters
                if cf['field'] == 'genre':
                    print(f"DEBUG: Found genre filter with operator {cf['operator']}")
                    if cf['operator'] in ['contains_all', 'all', 'contains_none', 'contains_any']:
                        needs_special_handling = True
                        print(f"DEBUG: Using special handling for genre:{cf['operator']}")
                
                # Price filters
                elif cf['field'] == 'price' and cf['operator'] in ['gt', 'lt', 'between']:
                    needs_special_handling = True
                
                # Interested count filters
                elif cf['field'] in ['interested', 'interestedCount'] and cf['operator'] in ['gt', 'lt', 'between']:
                    needs_special_handling = True
                
                if needs_special_handling:
                    special_filters.append(cf)
                else:
                    other_filters.append(cf)
        
        # First phase: Handle special filters that need custom approach
        events_data = None
        if special_filters:
            # Initialize filter manager
            filter_manager = AdvancedFilterManager(self)
            
            # Start with all events (or we'll use the first filter as a base)
            if len(special_filters) > 1:
                # For multiple special filters, we'll start with the first and then apply the rest
                first_filter = special_filters[0]
                field = first_filter['field']
                operator = first_filter['operator']
                values = first_filter['values']
                
                # Apply the first filter
                if field == 'genre':
                    # Use the specialized GenreQueryManager for genre filters
                    genre_manager = GenreQueryManager(self)
                    
                    if operator == 'contains_all' or operator == 'all':
                        print(f"Using GenreQueryManager for contains_all with genres: {values}")
                        events_data = genre_manager.contains_all(values)
                    
                    elif operator == 'contains_none':
                        print(f"Using GenreQueryManager for contains_none with genres: {values}")
                        events_data = genre_manager.contains_none(values)
                
                elif field == 'price':
                    if operator == 'gt':
                        print(f"Using AdvancedFilterManager for price > {values[0]}")
                        events_data = filter_manager.greater_than('price', values[0])
                    
                    elif operator == 'lt':
                        print(f"Using AdvancedFilterManager for price < {values[0]}")
                        events_data = filter_manager.less_than('price', values[0])
                    
                    elif operator == 'between' and len(values) >= 2:
                        print(f"Using AdvancedFilterManager for price between {values[0]} and {values[1]}")
                        events_data = filter_manager.between('price', values[0], values[1])
                
                elif field in ['interested', 'interestedCount']:
                    if operator == 'gt':
                        print(f"Using AdvancedFilterManager for interested > {values[0]}")
                        events_data = filter_manager.greater_than('interested', values[0])
                    
                    elif operator == 'lt':
                        print(f"Using AdvancedFilterManager for interested < {values[0]}")
                        events_data = filter_manager.less_than('interested', values[0])
                    
                    elif operator == 'between' and len(values) >= 2:
                        print(f"Using AdvancedFilterManager for interested between {values[0]} and {values[1]}")
                        events_data = filter_manager.between('interested', values[0], values[1])
                
                # Apply remaining special filters
                for sf in special_filters[1:]:
                    if not events_data or not events_data["events"]:
                        # If no events left, stop filtering
                        break
                    
                    field = sf['field']
                    operator = sf['operator']
                    values = sf['values']
                    
                    # Filter the existing results
                    all_events = events_data["events"]
                    all_bumps = events_data["bumps"]
                    
                    # Apply the filter
                    if field == 'genre':
                        # Genre filters
                        genre_manager = GenreQueryManager(self)
                        
                        if operator == 'contains_all' or operator == 'all':
                            temp_result = genre_manager.contains_all(values)
                            
                            # Intersect with current results
                            temp_event_ids = {event.get('event', {}).get('id') for event in temp_result["events"]}
                            current_event_ids = {event.get('event', {}).get('id') for event in all_events}
                            common_ids = current_event_ids.intersection(temp_event_ids)
                            
                            # Filter events to only those in the intersection
                            all_events = [event for event in all_events if event.get('event', {}).get('id') in common_ids]
                            
                            # Do the same for bumps
                            temp_bump_ids = {bump.get('event', {}).get('id') for bump in temp_result["bumps"]}
                            current_bump_ids = {bump.get('event', {}).get('id') for bump in all_bumps}
                            common_bump_ids = current_bump_ids.intersection(temp_bump_ids)
                            all_bumps = [bump for bump in all_bumps if bump.get('event', {}).get('id') in common_bump_ids]
                        
                        elif operator == 'contains_none':
                            temp_result = genre_manager.contains_any(values)
                            
                            # Remove events that match any of these genres
                            temp_event_ids = {event.get('event', {}).get('id') for event in temp_result["events"]}
                            all_events = [event for event in all_events if event.get('event', {}).get('id') not in temp_event_ids]
                            
                            # Do the same for bumps
                            temp_bump_ids = {bump.get('event', {}).get('id') for bump in temp_result["bumps"]}
                            all_bumps = [bump for bump in all_bumps if bump.get('event', {}).get('id') not in temp_bump_ids]
                    
                    elif field in ['price', 'interested', 'interestedCount']:
                        # Numeric filters
                        if operator == 'gt':
                            # Filter events client-side
                            threshold = float(values[0])
                            
                            # Extract field value based on field type
                            if field == 'price':
                                all_events = [
                                    event for event in all_events 
                                    if float(event.get('event', {}).get('price', '0') or 0) > threshold
                                ]
                                all_bumps = [
                                    bump for bump in all_bumps 
                                    if float(bump.get('event', {}).get('price', '0') or 0) > threshold
                                ]
                            else:  # interested/interestedCount
                                all_events = [
                                    event for event in all_events 
                                    if event.get('event', {}).get('interestedCount', 0) > threshold
                                ]
                                all_bumps = [
                                    bump for bump in all_bumps 
                                    if bump.get('event', {}).get('interestedCount', 0) > threshold
                                ]
                        
                        elif operator == 'lt':
                            # Filter events client-side
                            threshold = float(values[0])
                            
                            # Extract field value based on field type
                            if field == 'price':
                                all_events = [
                                    event for event in all_events 
                                    if float(event.get('event', {}).get('price', '0') or 0) < threshold
                                ]
                                all_bumps = [
                                    bump for bump in all_bumps 
                                    if float(bump.get('event', {}).get('price', '0') or 0) < threshold
                                ]
                            else:  # interested/interestedCount
                                all_events = [
                                    event for event in all_events 
                                    if event.get('event', {}).get('interestedCount', 0) < threshold
                                ]
                                all_bumps = [
                                    bump for bump in all_bumps 
                                    if bump.get('event', {}).get('interestedCount', 0) < threshold
                                ]
                        
                        elif operator == 'between' and len(values) >= 2:
                            # Filter events client-side
                            min_threshold = float(values[0])
                            max_threshold = float(values[1])
                            
                            # Extract field value based on field type
                            if field == 'price':
                                all_events = [
                                    event for event in all_events 
                                    if min_threshold <= float(event.get('event', {}).get('price', '0') or 0) <= max_threshold
                                ]
                                all_bumps = [
                                    bump for bump in all_bumps 
                                    if min_threshold <= float(bump.get('event', {}).get('price', '0') or 0) <= max_threshold
                                ]
                            else:  # interested/interestedCount
                                all_events = [
                                    event for event in all_events 
                                    if min_threshold <= event.get('event', {}).get('interestedCount', 0) <= max_threshold
                                ]
                                all_bumps = [
                                    bump for bump in all_bumps 
                                    if min_threshold <= bump.get('event', {}).get('interestedCount', 0) <= max_threshold
                                ]
                    
                    # Update events_data for next iteration
                    events_data = {
                        "events": all_events,
                        "bumps": all_bumps
                    }
            
            else:
                # Just one special filter
                sf = special_filters[0]
                field = sf['field']
                operator = sf['operator']
                values = sf['values']
                
                if field == 'genre':
                    # Genre filters
                    genre_manager = GenreQueryManager(self)
                    
                    if operator == 'contains_all' or operator == 'all':
                        print(f"Using GenreQueryManager for contains_all with genres: {values}")
                        events_data = genre_manager.contains_all(values)
                    
                    elif operator == 'contains_none':
                        print(f"Using GenreQueryManager for contains_none with genres: {values}")
                        events_data = genre_manager.contains_none(values)
                
                elif field == 'price':
                    if operator == 'gt':
                        print(f"Using AdvancedFilterManager for price > {values[0]}")
                        events_data = filter_manager.greater_than('price', values[0])
                    
                    elif operator == 'lt':
                        print(f"Using AdvancedFilterManager for price < {values[0]}")
                        events_data = filter_manager.less_than('price', values[0])
                    
                    elif operator == 'between' and len(values) >= 2:
                        print(f"Using AdvancedFilterManager for price between {values[0]} and {values[1]}")
                        events_data = filter_manager.between('price', values[0], values[1])
                
                elif field in ['interested', 'interestedCount']:
                    if operator == 'gt':
                        print(f"Using AdvancedFilterManager for interested > {values[0]}")
                        events_data = filter_manager.greater_than('interested', values[0])
                    
                    elif operator == 'lt':
                        print(f"Using AdvancedFilterManager for interested < {values[0]}")
                        events_data = filter_manager.less_than('interested', values[0])
                    
                    elif operator == 'between' and len(values) >= 2:
                        print(f"Using AdvancedFilterManager for interested between {values[0]} and {values[1]}")
                        events_data = filter_manager.between('interested', values[0], values[1])
        
        # If no special handling needed, proceed with standard approach
        if not events_data:
            # Store the original client_filters
            original_client_filters = self.filter_expr.client_filters if self.filter_expr else []
            
            # If we've extracted filters, update the client_filters
            if self.filter_expr and special_filters:
                self.filter_expr.client_filters = other_filters
            
            # Standard event fetching logic
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
            if self.filter_expr and other_filters:
                print(f"Applying enhanced client-side filters to {len(all_events)} events...")
                all_events = self.filter_expr.apply_client_filters(all_events)
                all_bumps = self.filter_expr.apply_client_filters(all_bumps)
                print(f"After enhanced filtering: {len(all_events)} events")
            
            # Restore original client_filters
            if self.filter_expr:
                self.filter_expr.client_filters = original_client_filters
            
            events_data = {
                "events": all_events,
                "bumps": all_bumps
            }
        
        return {
            "events": events_data["events"],
            "bumps": events_data["bumps"],
            "total_events": len(events_data["events"]),
            "total_bumps": len(events_data["bumps"]),
            "filter_info": {
                "graphql_filters_applied": self.filter_expr.get_graphql_filters() if self.filter_expr else {},
                "client_filters_applied": len(self.filter_expr.client_filters) if self.filter_expr else 0,
                "special_filters_applied": len(special_filters) if special_filters else 0,
                "enhanced_operators_available": [
                    "eq", "in", "nin", "has", "contains_all", "contains_any", "contains_none",
                    "all", "gt", "lt", "gte", "lte", "between", "starts", "ends"
                ],
                "filterable_fields": [
                    "genre", "artists", "venue", "eventType", "area", "title", 
                    "date", "time", "startTime", "endTime", "interested", "isTicketed", "price"
                ],
                "specialized_handling": ["genre", "price", "interested"] if special_filters else []
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
        location {
          value {
            from
            to
            __typename
          }
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
    parser.add_argument("-f", "--filter", help="Advanced filter expression with multi-value support")
    
    args = parser.parse_args()
    
    # Convert dates
    listing_date_gte = f"{args.start_date}T00:00:00.000Z"
    listing_date_lte = f"{args.end_date}T23:59:59.999Z"
    
    print(f"Advanced Event Fetcher - Area: {args.area}")
    print(f"Date range: {args.start_date} to {args.end_date}")
    if args.filter:
        print(f"Advanced multi-value filter: {args.filter}")
        print("Available operators: eq, in, nin, has, contains_all, contains_any, contains_none, all, gt, lt, gte, lte, between, starts, ends")
        print("Filter examples:")
        print("  artists:has:charlotte")
        print("  venue:has:fabric")
        print("  genre:contains_all:techno,industrial")
        print("  genre:contains_any:techno,house,minimal")
        print("  interested:gt:100")
        print("  price:between:10,30")
        print("  title:starts:opening")
    
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
        print(f"Filterable fields: {', '.join(filter_info.get('filterable_fields', []))}")


if __name__ == "__main__":
    main()
