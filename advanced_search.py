"""
Advanced Search Module with V3 Filter Support
"""
import requests
import json
import time
import re
from typing import Dict, List, Any, Union, Optional

# Import the full filtering system from events
from advanced_event_fetcher import AdvancedFilterExpression

URL = 'https://ra.co/graphql'
HEADERS = {
    'Content-Type': 'application/json',
    'Referer': 'https://ra.co/search',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:106.0) Gecko/20100101 Firefox/106.0'
}
DELAY = 1  # Rate limiting delay

class SearchFilterExpression(AdvancedFilterExpression):
    """Search-specific version that reuses events filtering logic but with search field mapping"""
    
    def get_graphql_indices(self) -> List[str]:
        """Get GraphQL indices from type filter (search-specific method)"""
        type_filter = self.graphql_filters.get('type', {})
        if 'any' in type_filter:
            return type_filter['any']
        elif 'eq' in type_filter:
            return [type_filter['eq']]
        else:
            # Default to all indices if no type filter
            return ["AREA", "ARTIST", "CLUB", "LABEL", "PROMOTER", "EVENT"]
    
    def _parse_expression(self, expression: str):
        """Parse filter expression with search-specific type handling"""
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
                
                # Special case for type filtering which maps to GraphQL indices
                if field == 'type':
                    self._add_type_filter(operator, values)
                else:
                    # Handle other fields (will be client-side)
                    self._add_client_filter(field, operator, values, current_operator)
    
    def _add_type_filter(self, operator: str, values: str):
        """Add special handling for type filter which maps to GraphQL indices"""
        if operator in ['any', 'contains_any', 'in']:
            # Multi-type search
            value_list = [v.strip().upper() for v in values.split(',')]
            # Map to valid GraphQL index types
            valid_indices = []
            for value in value_list:
                if value in ['ARTIST', 'LABEL', 'EVENT', 'CLUB', 'AREA', 'PROMOTER']:
                    valid_indices.append(value)
            
            if valid_indices:
                self.graphql_filters['type'] = {"any": valid_indices}
        
        elif operator == 'eq':
            # Single type
            value = values.strip().upper()
            if value in ['ARTIST', 'LABEL', 'EVENT', 'CLUB', 'AREA', 'PROMOTER']:
                self.graphql_filters['type'] = {"eq": value}
        else:
            # Other type operators go to client-side
            self._add_client_filter('type', operator, values, 'AND')
    
    def apply_client_filters(self, search_results: List[Dict]) -> List[Dict]:
        """Apply client-side filters to search results with search-specific field extraction"""
        if not self.client_filters:
            return search_results
        
        filtered_results = []
        
        for result in search_results:
            if self._search_result_matches_client_filters(result):
                filtered_results.append(result)
        
        return filtered_results
    
    def _search_result_matches_client_filters(self, result: Dict) -> bool:
        """Check if search result matches all client-side filters with search-specific logic"""
        for filter_def in self.client_filters:
            field = filter_def['field']
            operator = filter_def['operator']
            values = filter_def['values']
            logical_op = filter_def.get('logical_op', 'AND')
            
            # Get field value from search result (search-specific)
            result_values = self._get_search_result_field_values(result, field)
            
            # Apply filter with enhanced operators (reuse parent method)
            matches = self._apply_filter_operator(result_values, operator, values, logical_op)
            
            # For now, use AND logic (all filters must match)
            if not matches:
                return False
        
        return True
    
    def _get_search_result_field_values(self, result: Dict, field: str) -> Union[str, List[str]]:
        """Extract field values from search result object (search-specific field mapping)"""
        
        if field == 'type':
            # Map searchType to lowercase for filtering
            search_type = result.get('searchType', '').lower()
            return [search_type] if search_type else []
        
        elif field == 'area':
            # Area name filtering
            area_name = result.get('areaName', '')
            return [area_name.lower()] if area_name else []
        
        elif field == 'country':
            # Country name and code filtering
            country_name = result.get('countryName', '')
            country_code = result.get('countryCode', '')
            values = []
            if country_name:
                values.append(country_name.lower())
            if country_code:
                values.append(country_code.lower())
            return values
        
        elif field == 'score':
            # Numeric score filtering
            score = result.get('score', 0)
            return [score] if score else [0]
        
        elif field == 'name' or field == 'title' or field == 'value':
            # Name/title/value filtering (main content)
            value = result.get('value', '')
            return [value.lower()] if value else []
        
        elif field == 'artist' or field == 'artists':
            # For artist search results, map to the value field
            if result.get('searchType', '').lower() == 'artist':
                value = result.get('value', '')
                return [value.lower()] if value else []
            return []
        
        elif field == 'venue' or field == 'club':
            # For event search results, map to clubName
            if result.get('searchType', '').lower() in ['upcomingevent', 'event']:
                club_name = result.get('clubName', '')
                return [club_name.lower()] if club_name else []
            elif result.get('searchType', '').lower() == 'club':
                value = result.get('value', '')
                return [value.lower()] if value else []
            return []
        
        elif field == 'date':
            # Event date filtering
            if result.get('searchType', '').lower() in ['upcomingevent', 'event']:
                date = result.get('date', '')
                return [date] if date else []
            return []
        
        elif field == 'label':
            # For label search results
            if result.get('searchType', '').lower() == 'label':
                value = result.get('value', '')
                return [value.lower()] if value else []
            return []
        
        elif field == 'promoter':
            # For promoter search results
            if result.get('searchType', '').lower() == 'promoter':
                value = result.get('value', '')
                return [value.lower()] if value else []
            return []
        
        # Default: try direct access to result data
        value = result.get(field, '')
        return [str(value).lower()] if value else []


class AdvancedSearchFilterExpression:
    """Parse and apply V3 search filter expressions with advanced operators"""
    
    def __init__(self, expression: str = None):
        self.expression = expression
        self.graphql_filters = {}
        self.client_filters = []
        
        if expression:
            self._parse_expression(expression)
    
    def _parse_expression(self, expression: str):
        """Parse filter expression into GraphQL and client-side filters"""
        # Debug output
        print(f"Parsing filter expression: '{expression}'")
        
        # Split by logical operators
        parts = re.split(r'\s+(AND|OR|NOT)\s+', expression)
        
        current_operator = 'AND'
        
        for i, part in enumerate(parts):
            part = part.strip()
            
            if part in ['AND', 'OR', 'NOT']:
                current_operator = part
                print(f"Found logical operator: {part}")
                continue
                
            if ':' in part:
                print(f"Parsing filter part: {part}")
                field, operator, values = part.split(':', 2)
                
                # Special case for type filtering which maps to GraphQL indices
                if field == 'type':
                    print(f"Processing type filter: {operator}:{values}")
                    self._add_type_filter(operator, values)
                else:
                    # Handle other fields (will be client-side)
                    print(f"Adding client-side filter for {field}:{operator}:{values}")
                    self._add_client_filter(field, operator, values, current_operator)
    
    def _add_type_filter(self, operator: str, values: str):
        """Add special handling for type filter which maps to GraphQL indices"""
        # Map to GraphQL indices
        if operator in ['any', 'contains_any', 'in']:
            # Multi-type search
            value_list = [v.strip().upper() for v in values.split(',')]
            
            # Map to GraphQL index types
            indices = []
            for value in value_list:
                if value.upper() in ['ARTIST', 'LABEL', 'EVENT', 'AREA', 'CLUB', 'PROMOTER']:
                    indices.append(value.upper())
            
            if indices:
                print(f"Adding GraphQL type filter with 'any' operator: {indices}")
                self.graphql_filters['type'] = {'any': indices}
            else:
                print(f"Warning: No valid indices found in values: {values}")
        
        elif operator == 'eq':
            # Single type search
            value = values.strip().upper()
            if value in ['ARTIST', 'LABEL', 'EVENT', 'AREA', 'CLUB', 'PROMOTER']:
                print(f"Adding GraphQL type filter with 'eq' operator: {value}")
                self.graphql_filters['type'] = {'eq': value}
            else:
                print(f"Warning: Invalid index type: {value}")
        
        else:
            # Other operators will be handled client-side
            print(f"Adding client-side type filter with operator '{operator}'")
            self._add_client_filter('type', operator, values, 'AND')
    
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
    
    def get_graphql_indices(self) -> List[str]:
        """Get GraphQL indices from type filter"""
        type_filter = self.graphql_filters.get('type', {})
        if 'any' in type_filter:
            # Debug output
            print(f"Using 'any' type filter with indices: {type_filter['any']}")
            return type_filter['any']
        elif 'eq' in type_filter:
            # Debug output
            print(f"Using 'eq' type filter with index: {type_filter['eq']}")
            return [type_filter['eq']]
        else:
            # Debug output
            print("No type filter found, using all indices")
            return ["AREA", "ARTIST", "CLUB", "LABEL", "PROMOTER", "EVENT"]
    
    def apply_client_filters(self, results: List[Dict]) -> List[Dict]:
        """Apply client-side filters to search results"""
        if not self.client_filters:
            return results
        
        filtered_results = []
        
        for result in results:
            if self._result_matches_client_filters(result):
                filtered_results.append(result)
        
        return filtered_results
    
    def _result_matches_client_filters(self, result: Dict) -> bool:
        """Check if search result matches all client-side filters"""
        for filter_def in self.client_filters:
            field = filter_def['field']
            operator = filter_def['operator']
            values = filter_def['values']
            logical_op = filter_def.get('logical_op', 'AND')
            
            # Get field value from search result
            result_values = self._get_result_field_values(result, field)
            
            # Apply filter with advanced operators
            matches = self._apply_filter_operator(result_values, operator, values, logical_op)
            
            # For now, use AND logic (all filters must match)
            if not matches:
                return False
        
        return True
    
    def _apply_filter_operator(self, result_values: Union[str, List[str]], operator: str, 
                             filter_values: List[str], logical_op: str) -> bool:
        """Apply filter operator with support for V3 operators"""
        
        # Ensure result_values is a list for consistent processing
        if isinstance(result_values, str):
            result_values = [result_values] if result_values else []
        elif not isinstance(result_values, list):
            result_values = []
        
        # Normalize for comparison (lowercase, strip)
        result_values = [str(v).lower().strip() for v in result_values if v]
        filter_values = [str(v).lower().strip() for v in filter_values if v]
        
        if operator == 'eq':
            # Exact match (any result value equals any filter value)
            return any(rv == fv for rv in result_values for fv in filter_values)
        
        elif operator == 'ne':
            # Not equals (no result value equals any filter value)
            return not any(rv == fv for rv in result_values for fv in filter_values)
        
        elif operator in ['in', 'any', 'contains_any']:
            # In array (any result value is in filter values)
            return any(rv in filter_values for rv in result_values)
        
        elif operator in ['nin', 'contains_none']:
            # Not in array (no result value is in filter values)
            return not any(rv in filter_values for rv in result_values)
        
        elif operator == 'has':
            # Result has this specific value as substring
            return any(any(fv.lower() in rv.lower() for rv in result_values) for fv in filter_values)
        
        elif operator in ['contains_all', 'all']:
            # Result has ALL of the specified values
            return all(any(fv.lower() in rv.lower() for rv in result_values) for fv in filter_values)
        
        elif operator == 'starts':
            # String prefix matching
            return any(any(rv.startswith(fv) for rv in result_values) for fv in filter_values)
        
        elif operator == 'ends':
            # String suffix matching
            return any(any(rv.endswith(fv) for rv in result_values) for fv in filter_values)
        
        # Numeric operators not very applicable for search results, but include for completeness
        elif operator in ['gt', 'lt', 'gte', 'lte', 'between']:
            # Try to convert to numeric values
            try:
                numeric_result_values = [float(rv) for rv in result_values]
                
                if operator == 'gt':
                    return any(rv > float(filter_values[0]) for rv in numeric_result_values)
                elif operator == 'lt':
                    return any(rv < float(filter_values[0]) for rv in numeric_result_values)
                elif operator == 'gte':
                    return any(rv >= float(filter_values[0]) for rv in numeric_result_values)
                elif operator == 'lte':
                    return any(rv <= float(filter_values[0]) for rv in numeric_result_values)
                elif operator == 'between' and len(filter_values) >= 2:
                    min_val = float(filter_values[0])
                    max_val = float(filter_values[1])
                    return any(min_val <= rv <= max_val for rv in numeric_result_values)
            except (ValueError, TypeError, IndexError):
                # If conversion fails or values missing, treat as false
                return False
        
        # Unknown operator, don't filter
        return True
    
    def _get_result_field_values(self, result: Dict, field: str) -> Union[str, List[str]]:
        """Extract field values from search result"""
        # Type/searchType is a special case
        if field == 'type':
            search_type = result.get('searchType', '').lower()
            return [search_type] if search_type else []
        
        # Handle common fields
        elif field == 'name' or field == 'value':
            value = result.get('value', '')
            return [value.lower()] if value else []
        
        elif field == 'area' or field == 'areaName':
            area = result.get('areaName', '')
            return [area.lower()] if area else []
        
        elif field == 'country' or field == 'countryName':
            country = result.get('countryName', '')
            return [country.lower()] if country else []
        
        elif field == 'club' or field == 'clubName':
            club = result.get('clubName', '')
            return [club.lower()] if club else []
        
        elif field == 'date':
            date = result.get('date', '')
            return [date] if date else []
        
        # Direct field access for any other fields
        value = result.get(field, '')
        return [value.lower()] if value else []


class AdvancedSearch:
    """V3 Search with advanced filtering capabilities"""
    
    def __init__(self, query: str, filter_expression: str = None, limit: int = 50):
        self.query = query
        self.limit = limit
        # Use the new SearchFilterExpression that inherits from events system
        self.filter_expr = SearchFilterExpression(filter_expression) if filter_expression else None
    
    def search(self) -> Dict[str, Any]:
        """Perform advanced search with filtering"""
        # Get GraphQL indices from filter expression
        indices = self.filter_expr.get_graphql_indices() if self.filter_expr else None
        
        # If no specific indices specified, search all
        if not indices:
            indices = ["AREA", "ARTIST", "CLUB", "LABEL", "PROMOTER", "EVENT"]
        
        # Perform global search
        search_results = self._perform_global_search(indices)
        
        # Apply client-side filters if needed
        if self.filter_expr and self.filter_expr.get_client_filters():
            original_results = search_results
            search_results = self.filter_expr.apply_client_filters(search_results)
            print(f"Client-side filtering: {len(original_results)} -> {len(search_results)} results")
        
        # Group results by type
        grouped_results = self._group_results_by_type(search_results)
        
        # Return formatted results
        return {
            "results": search_results,
            "grouped_results": grouped_results,
            "total_results": len(search_results),
            "filter_info": {
                "graphql_filters": self.filter_expr.get_graphql_filters() if self.filter_expr else {},
                "client_filters": self.filter_expr.get_client_filters() if self.filter_expr else [],
                "indices": indices
            }
        }
    
    def _perform_global_search(self, indices: List[str]) -> List[Dict]:
        """Perform global search using GraphQL API"""
        # Debug output
        print(f"Performing global search with query: '{self.query}', indices: {indices}")
        
        payload = {
            "operationName": "GET_GLOBAL_SEARCH_RESULTS",
            "variables": {
                "searchTerm": self.query,
                "indices": indices,
                "limit": self.limit
            },
            "query": """query GET_GLOBAL_SEARCH_RESULTS($searchTerm: String!, $indices: [IndexType!], $limit: Int) {
                search(
                    searchTerm: $searchTerm
                    limit: $limit
                    indices: $indices
                    includeNonLive: false
                ) {
                    searchType
                    id
                    value
                    areaName
                    countryId
                    countryName
                    countryCode
                    contentUrl
                    imageUrl
                    score
                    clubName
                    clubContentUrl
                    date
                    __typename
                }
            }"""
        }
        
        try:
            # Debug output
            print(f"Sending GraphQL payload: {json.dumps(payload['variables'])}")
            
            response = requests.post(URL, headers=HEADERS, json=payload, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if 'errors' in data:
                print(f"GraphQL errors: {data['errors']}")
                return []
            
            results = data.get('data', {}).get('search', [])
            print(f"Received {len(results)} results from GraphQL API")
            return results
            
        except Exception as e:
            print(f"Error performing global search: {e}")
            return []
    
    def _group_results_by_type(self, results: List[Dict]) -> Dict[str, List[Dict]]:
        """Group search results by searchType"""
        grouped = {}
        
        for result in results:
            search_type = result.get('searchType', '').lower()
            if search_type not in grouped:
                grouped[search_type] = []
            
            grouped[search_type].append(result)
        
        return grouped
    
    def format_results(self, search_data: Dict) -> Dict:
        """Format search results in a consistent way for API response"""
        results = search_data.get("results", [])
        grouped = search_data.get("grouped_results", {})
        
        # Build formatted response structure
        formatted_results = {
            "artists": [],
            "labels": [],
            "events": [],
            "clubs": [],
            "promoters": [],
            "areas": []
        }
        
        # Process artists
        for artist in grouped.get('artist', []):
            formatted_results['artists'].append({
                "id": artist.get('id'),
                "name": artist.get('value'),
                "area": artist.get('areaName'),
                "country": artist.get('countryName'),
                "content_url": artist.get('contentUrl'),
                "image_url": artist.get('imageUrl'),
                "score": artist.get('score')
            })
        
        # Process labels
        for label in grouped.get('label', []):
            formatted_results['labels'].append({
                "id": label.get('id'),
                "name": label.get('value'),
                "area": label.get('areaName'),
                "country": label.get('countryName'),
                "content_url": label.get('contentUrl'),
                "image_url": label.get('imageUrl'),
                "score": label.get('score')
            })
        
        # Process events
        for event in grouped.get('upcomingevent', []):
            formatted_results['events'].append({
                "id": event.get('id'),
                "title": event.get('value'),
                "date": event.get('date'),
                "venue": {
                    "name": event.get('clubName'),
                    "content_url": event.get('clubContentUrl')
                },
                "area": event.get('areaName'),
                "country": event.get('countryName'),
                "content_url": event.get('contentUrl'),
                "image_url": event.get('imageUrl'),
                "score": event.get('score')
            })
        
        # Process clubs
        for club in grouped.get('club', []):
            formatted_results['clubs'].append({
                "id": club.get('id'),
                "name": club.get('value'),
                "area": club.get('areaName'),
                "country": club.get('countryName'),
                "content_url": club.get('contentUrl'),
                "image_url": club.get('imageUrl'),
                "score": club.get('score')
            })
        
        # Process promoters
        for promoter in grouped.get('promoter', []):
            formatted_results['promoters'].append({
                "id": promoter.get('id'),
                "name": promoter.get('value'),
                "area": promoter.get('areaName'),
                "country": promoter.get('countryName'),
                "content_url": promoter.get('contentUrl'),
                "image_url": promoter.get('imageUrl'),
                "score": promoter.get('score')
            })
        
        # Process areas
        for area in grouped.get('area', []):
            formatted_results['areas'].append({
                "id": area.get('id'),
                "name": area.get('value'),
                "country": area.get('countryName'),
                "country_code": area.get('countryCode'),
                "content_url": area.get('contentUrl'),
                "image_url": area.get('imageUrl'),
                "score": area.get('score')
            })
        
        return formatted_results


# Example usage
if __name__ == "__main__":
    search = AdvancedSearch("techno", filter_expression="type:any:artist,event AND area:has:berlin")
    results = search.search()
    formatted = search.format_results(results)
    
    print(f"Found {results['total_results']} results")
    print(f"Artists: {len(formatted['artists'])}")
    print(f"Events: {len(formatted['events'])}")
    print(f"Applied filters: {results['filter_info']['graphql_filters']}")
    print(f"Client filters: {results['filter_info']['client_filters']}")
