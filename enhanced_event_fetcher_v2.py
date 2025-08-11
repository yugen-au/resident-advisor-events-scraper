# Enhanced Event Fetcher V2 with Native GraphQL Multi-Genre Support
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

class V2FilterExpression:
    """Parse and apply V2 filter expressions with native GraphQL multi-genre support"""
    
    def __init__(self, expression: str = None):
        self.expression = expression
        self.graphql_filters = {}
        self.unsupported_filters = []
        
        if expression:
            self._parse_expression(expression)
    
    def _parse_expression(self, expression: str):
        """Parse filter expression into GraphQL filters"""
        # Simple parser for expressions like:
        # "genre:any:techno,house" 
        # "genre:eq:techno"
        # "eventType:eq:club"
        
        # Split by logical operators (for now, just handle simple cases)
        parts = re.split(r'\s+(AND|OR|NOT)\s+', expression)
        
        for i, part in enumerate(parts):
            part = part.strip()
            
            if part in ['AND', 'OR', 'NOT']:
                continue  # Skip logical operators for now
                
            if ':' in part:
                field, operator, values = part.split(':', 2)
                self._add_graphql_filter(field, operator, values)
    
    def _add_graphql_filter(self, field: str, operator: str, values: str):
        """Add filter that can be handled by GraphQL"""
        
        # Parse values
        value_list = [v.strip() for v in values.split(',')]
        
        if field == "genre":
            if operator == "eq":
                self.graphql_filters["genre"] = {"eq": value_list[0]}
            elif operator == "any":
                self.graphql_filters["genre"] = {"any": value_list}
            elif operator == "ne":
                self.graphql_filters["genre"] = {"ne": value_list[0]}
            else:
                self.unsupported_filters.append(f"{field}:{operator}:{values}")
        
        elif field == "eventType":
            if operator == "eq":
                self.graphql_filters["eventType"] = {"eq": value_list[0]}
            elif operator == "ne":
                self.graphql_filters["eventType"] = {"ne": value_list[0]}
            else:
                self.unsupported_filters.append(f"{field}:{operator}:{values}")
        
        else:
            self.unsupported_filters.append(f"{field}:{operator}:{values}")
    
    def get_graphql_filters(self) -> Dict[str, Any]:
        """Get filters that can be applied at GraphQL level"""
        return self.graphql_filters
    
    def get_unsupported_filters(self) -> List[str]:
        """Get filters that are not supported in V2"""
        return self.unsupported_filters


class EnhancedEventFetcherV2:
    """V2 Event Fetcher with Native GraphQL Multi-Genre Support"""

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
        
        # V2: Native GraphQL filtering
        self.filter_expr = V2FilterExpression(filter_expression) if filter_expression else None
        
        self.payload = self.generate_payload()

    def generate_payload(self):
        """Generate GraphQL payload with native multi-genre filtering"""
        
        # Start with base filters
        filters = {
            "areas": {"eq": self.areas},
            "listingDate": {"gte": self.listing_date_gte}
        }
        
        if self.listing_date_lte:
            filters["listingDate"]["lte"] = self.listing_date_lte
        
        # Handle legacy comma-separated genres (convert to native GraphQL)
        if self.genre:
            with open("debug_log.txt", "a") as f:
                f.write(f"V2 DEBUG: Processing genre parameter: '{self.genre}'\n")
                
            if ',' in self.genre:
                # Multi-genre: use native GraphQL 'any' operator
                genres = [g.strip() for g in self.genre.split(',')]
                filters["genre"] = {"any": genres}
                with open("debug_log.txt", "a") as f:
                    f.write(f"V2 DEBUG: Converting multi-genre '{self.genre}' to native GraphQL: {filters['genre']}\n")
                    f.write(f"V2 DEBUG: Number of genres: {len(genres)}\n")
            else:
                # Single genre: use 'eq' operator
                filters["genre"] = {"eq": self.genre}
                with open("debug_log.txt", "a") as f:
                    f.write(f"V2 DEBUG: Single genre filter: {filters['genre']}\n")
        
        # Add legacy event type filter
        if self.event_type:
            filters["eventType"] = {"eq": self.event_type}
        
        # Add advanced GraphQL filters from filter expression
        if self.filter_expr:
            graphql_filters = self.filter_expr.get_graphql_filters()
            for field, filter_def in graphql_filters.items():
                filters[field] = filter_def
                with open("debug_log.txt", "a") as f:
                    f.write(f"V2 DEBUG: Added filter expression: {field} = {filter_def}\n")
            
            # Warn about unsupported filters
            unsupported = self.filter_expr.get_unsupported_filters()
            if unsupported:
                with open("debug_log.txt", "a") as f:
                    f.write(f"V2 DEBUG: Unsupported filters (use V3 for these): {unsupported}\n")
        
        # Configure sorting
        sort_config = self._get_sort_config()
        
        filter_options = {
            "genre": True,
            "eventType": True
        }

        payload = {
            "operationName": "GET_EVENT_LISTINGS_WITH_BUMPS" if self.include_bumps else "GET_EVENT_LISTINGS",
            "variables": {
                "filters": filters,
                "filterOptions": filter_options,
                "pageSize": 20,
                "page": 1,
                "sort": sort_config,
                "areaId": self.areas
            },
            "query": self._get_query()
        }
        
        # Debug output for comparison
        with open("debug_log.txt", "a") as f:
            f.write(f"V2 DEBUG: Final payload filters:\n")
            import json
            f.write(json.dumps(payload["variables"]["filters"], indent=2) + "\n")

        return payload

    def fetch_all_events(self):
        """Fetch all events with V2 native GraphQL filtering"""
        print(f"V2: Fetching events with native GraphQL multi-genre support...")
        
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
        
        return {
            "events": all_events,
            "bumps": all_bumps,
            "total_events": len(all_events),
            "total_bumps": len(all_bumps),
            "filter_info": {
                "version": "v2",
                "native_graphql_filters": self.filter_expr.get_graphql_filters() if self.filter_expr else {},
                "unsupported_filters": self.filter_expr.get_unsupported_filters() if self.filter_expr else [],
                "legacy_genre": self.genre,
                "legacy_event_type": self.event_type
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
        
        # Process bumps to extract events
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
        """Save events to CSV"""
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

    def _get_query(self):
        """Get the appropriate GraphQL query."""
        if self.include_bumps:
            return self._get_enhanced_query()
        else:
            return self._get_basic_query()

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
    """V2 command line interface with native GraphQL multi-genre support"""
    parser = argparse.ArgumentParser(description="V2: Fetch RA events with native GraphQL multi-genre filtering")
    parser.add_argument("area", type=int, help="Area ID")
    parser.add_argument("start_date", help="Start date (YYYY-MM-DD)")
    parser.add_argument("end_date", help="End date (YYYY-MM-DD)")
    parser.add_argument("-o", "--output", default="events_v2.csv", help="Output file")
    
    # Legacy filters (now with native multi-genre support)
    parser.add_argument("-g", "--genre", help="Single genre or comma-separated multiple genres")
    parser.add_argument("-t", "--event-type", help="Filter by event type")
    parser.add_argument("-s", "--sort", default="listingDate", choices=["listingDate", "score", "title"])
    parser.add_argument("--no-bumps", action="store_true", help="Exclude bumped events")
    
    # V2 native filter expressions
    parser.add_argument("-f", "--filter", help="V2 filter expression (e.g., 'genre:any:techno,house')")
    
    args = parser.parse_args()
    
    # Convert dates
    listing_date_gte = f"{args.start_date}T00:00:00.000Z"
    listing_date_lte = f"{args.end_date}T23:59:59.999Z"
    
    print(f"V2 Enhanced Event Fetcher - Area: {args.area}")
    print(f"Date range: {args.start_date} to {args.end_date}")
    if args.genre:
        print(f"Genre filter: {args.genre}")
    if args.filter:
        print(f"V2 filter expression: {args.filter}")
    
    # Create V2 fetcher
    fetcher = EnhancedEventFetcherV2(
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
    filter_info = events_data.get('filter_info', {})
    print(f"V2 native GraphQL filters: {filter_info.get('native_graphql_filters', {})}")
    if filter_info.get('unsupported_filters'):
        print(f"Unsupported filters (use V3): {filter_info['unsupported_filters']}")


if __name__ == "__main__":
    main()
