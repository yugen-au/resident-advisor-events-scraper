import requests
import json
import time
import csv
import sys
import argparse
from datetime import datetime, timedelta

URL = 'https://ra.co/graphql'
HEADERS = {
    'Content-Type': 'application/json',
    'Referer': 'https://ra.co/events/uk/london',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:106.0) Gecko/20100101 Firefox/106.0'
}
DELAY = 1  # Adjust this value as needed


class EnhancedEventFetcher:
    """
    Enhanced class to fetch event details from RA.co with advanced filtering support
    """

    def __init__(self, areas, listing_date_gte, listing_date_lte=None, genre=None, 
                 event_type=None, sort_by="listingDate", include_bumps=True):
        self.areas = areas
        self.listing_date_gte = listing_date_gte
        self.listing_date_lte = listing_date_lte
        self.genre = genre
        self.event_type = event_type
        self.sort_by = sort_by
        self.include_bumps = include_bumps
        self.payload = self.generate_payload()

    def generate_payload(self):
        """
        Generate the enhanced GraphQL payload with filtering support.
        """
        # Determine which operation to use
        operation_name = "GET_EVENT_LISTINGS_WITH_BUMPS" if self.include_bumps else "GET_EVENT_LISTINGS"
        
        # Base filters
        filters = {
            "areas": {"eq": self.areas},
            "listingDate": {"gte": self.listing_date_gte}
        }
        
        # Add end date if provided
        if self.listing_date_lte:
            filters["listingDate"]["lte"] = self.listing_date_lte
        
        # Add genre filter if provided
        if self.genre:
            filters["genre"] = {"eq": self.genre}
        else:
            filters["genre"] = None
            
        # Add event type filter if provided
        if self.event_type:
            filters["eventType"] = {"eq": self.event_type}

        # Configure sorting
        sort_config = self._get_sort_config()
        
        # Filter options
        filter_options = {
            "genre": True,
            "eventType": True
        }

        if self.include_bumps:
            # Enhanced query with bumps
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
            # Basic query without bumps
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

    def get_events(self, page_number):
        """
        Fetch events for the given page number.

        :param page_number: The page number for event listings.
        :return: Event data including regular events and bumped events if enabled.
        """
        self.payload["variables"]["page"] = page_number
        response = requests.post(URL, headers=HEADERS, json=self.payload)

        try:
            response.raise_for_status()
            data = response.json()
        except (requests.exceptions.RequestException, ValueError):
            print(f"Error: {response.status_code}")
            return {"events": [], "bumps": [], "filter_options": {}}

        if 'data' not in data:
            print(f"Error: {data}")
            return {"events": [], "bumps": [], "filter_options": {}}

        result = {"events": [], "bumps": [], "filter_options": {}}

        if self.include_bumps and 'eventListingsWithBumps' in data["data"]:
            event_data = data["data"]["eventListingsWithBumps"]
            result["events"] = event_data["eventListings"]["data"]
            result["bumps"] = event_data.get("bumps", {}).get("bumpDecision", [])
            result["filter_options"] = event_data["eventListings"].get("filterOptions", {})
            result["total_results"] = event_data["eventListings"].get("totalResults", 0)
        elif 'eventListings' in data["data"]:
            event_data = data["data"]["eventListings"]
            result["events"] = event_data["data"]
            result["filter_options"] = event_data.get("filterOptions", {})
            result["total_results"] = event_data.get("totalResults", 0)

        return result

    def fetch_all_events(self):
        """
        Fetch all events and return them with bumped events and filter options.

        :return: Dictionary containing events, bumped events, and filter options.
        """
        all_events = []
        all_bumps = []
        filter_options = {}
        total_results = 0
        page_number = 1

        while True:
            result = self.get_events(page_number)
            
            if not result["events"]:
                break

            all_events.extend(result["events"])
            all_bumps.extend(result["bumps"])
            filter_options = result["filter_options"]  # Latest filter options
            total_results = result.get("total_results", 0)
            
            page_number += 1
            time.sleep(DELAY)

        return {
            "events": all_events,
            "bumps": all_bumps,
            "filter_options": filter_options,
            "total_results": total_results
        }

    def save_events_to_csv(self, events_data, output_file="events.csv"):
        """
        Save events to a CSV file with enhanced data fields.

        :param events_data: Dictionary containing events data.
        :param output_file: The output file path.
        """
        events = events_data["events"]
        bumps = events_data["bumps"]
        
        with open(output_file, "w", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)
            writer.writerow([
                "Event Name", "Date", "Start Time", "End Time", "Artists",
                "Venue", "Event URL", "Interested Count", "Is Ticketed", 
                "Is Bumped", "Promoters", "Ticket Info"
            ])

            # Regular events
            for event in events:
                event_data = event["event"]
                promoters = [str(p.get("id", "")) for p in event_data.get("promoters", [])]
                tickets = event_data.get("tickets", [])
                ticket_info = f"{len(tickets)} ticket types" if tickets else "No tickets"
                
                writer.writerow([
                    event_data['title'], 
                    event_data['date'], 
                    event_data['startTime'],
                    event_data['endTime'], 
                    ', '.join([artist['name'] for artist in event_data['artists']]),
                    event_data['venue']['name'], 
                    event_data['contentUrl'], 
                    event_data.get('interestedCount', 0),
                    event_data.get('isTicketed', False),
                    False,  # Not a bumped event
                    ', '.join(promoters),
                    ticket_info
                ])

            # Bumped events
            for bump in bumps:
                event_data = bump["event"]
                promoters = [str(p.get("id", "")) for p in event_data.get("promoters", [])]
                tickets = event_data.get("tickets", [])
                ticket_info = f"{len(tickets)} ticket types" if tickets else "No tickets"
                
                writer.writerow([
                    event_data['title'], 
                    event_data['date'], 
                    event_data['startTime'],
                    event_data['endTime'], 
                    ', '.join([artist['name'] for artist in event_data['artists']]),
                    event_data['venue']['name'], 
                    event_data['contentUrl'], 
                    event_data.get('interestedCount', 0),
                    event_data.get('isTicketed', False),
                    True,  # This is a bumped event
                    ', '.join(promoters),
                    ticket_info
                ])




def main():
    parser = argparse.ArgumentParser(description="Fetch events from ra.co with advanced filtering support.")
    parser.add_argument("areas", type=int, help="The area code to filter events.")
    parser.add_argument("start_date", type=str, help="The start date for event listings (format: YYYY-MM-DD).")
    parser.add_argument("end_date", type=str, help="The end date for event listings (format: YYYY-MM-DD).")
    parser.add_argument("-o", "--output", type=str, default="events.csv", help="The output file path.")
    parser.add_argument("-g", "--genre", type=str, help="Filter by genre (e.g., 'techno', 'house').")
    parser.add_argument("-t", "--event-type", type=str, help="Filter by event type.")
    parser.add_argument("-s", "--sort", type=str, choices=["listingDate", "score", "title"], 
                       default="listingDate", help="Sort events by date, score, or title.")
    parser.add_argument("--no-bumps", action="store_true", help="Exclude bumped/promoted events.")
    
    args = parser.parse_args()

    listing_date_gte = f"{args.start_date}T00:00:00.000Z"
    listing_date_lte = f"{args.end_date}T23:59:59.999Z"

    event_fetcher = EnhancedEventFetcher(
        areas=args.areas,
        listing_date_gte=listing_date_gte,
        listing_date_lte=listing_date_lte,
        genre=args.genre,
        event_type=args.event_type,
        sort_by=args.sort,
        include_bumps=not args.no_bumps
    )

    print(f"Fetching events for area {args.areas} from {args.start_date} to {args.end_date}")
    if args.genre:
        print(f"Genre filter: {args.genre}")
    if args.event_type:
        print(f"Event type filter: {args.event_type}")
    print(f"Sort by: {args.sort}")
    print(f"Include bumped events: {not args.no_bumps}")
    print()

    events_data = event_fetcher.fetch_all_events()
    
    print(f"Found {len(events_data['events'])} regular events")
    print(f"Found {len(events_data['bumps'])} bumped events")
    print(f"Total results: {events_data['total_results']}")
    
    event_fetcher.save_events_to_csv(events_data, args.output)
    print(f"Events saved to {args.output}")


if __name__ == "__main__":
    main()
