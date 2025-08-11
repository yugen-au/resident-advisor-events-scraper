import sqlite3
import threading
import time
import os
import json
import requests
from datetime import datetime, timedelta

# In-memory cache for fast lookups
area_cache = {}
# Last time we did a full refresh
last_full_refresh = None
# Cache expiry period
CACHE_MAX_AGE = timedelta(days=7)  # Refresh cache weekly
# Database file path
DB_PATH = 'area_cache.db'
# Cache JSON file path
CACHE_JSON_PATH = 'cache.json'

def initialize_database_from_cache_file():
    """Initialize the database from cache.json if it exists and DB doesn't"""
    # Check if database already exists and has tables
    db_exists = os.path.exists(DB_PATH)
    tables_exist = False
    
    if db_exists:
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='area_cache'")
            tables_exist = cursor.fetchone() is not None
            conn.close()
        except Exception as e:
            print(f"Error checking database tables: {e}")
            # Assume tables don't exist if there was an error
            tables_exist = False
    
    # If database with tables already exists, nothing to do
    if db_exists and tables_exist:
        print("Database already exists with tables, skipping initialization from cache file")
        return
    
    # Check if cache.json exists
    if not os.path.exists(CACHE_JSON_PATH):
        print("No cache file found, creating fresh database")
        # Just create the database structure
        init_db()
        return
    
    try:
        # Load cache data from JSON
        with open(CACHE_JSON_PATH, 'r') as f:
            cache_data = json.load(f)
        
        # Check if the JSON has the expected structure
        if not isinstance(cache_data, dict) or 'cached_areas' not in cache_data:
            print("Cache file has invalid format, creating fresh database")
            init_db()
            return
        
        # Get cached areas
        cached_areas = cache_data.get('cached_areas', [])
        if not cached_areas:
            print("No areas in cache file, creating fresh database")
            init_db()
            return
        
        print(f"Initializing database from cache file with {len(cached_areas)} areas")
        
        # Create database and tables
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Create tables
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS area_cache (
            area_name TEXT,
            country_code TEXT,
            area_id TEXT,
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (area_name, country_code)
        )
        ''')
        
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS cache_metadata (
            key TEXT PRIMARY KEY,
            value TEXT,
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        # Insert cached areas
        now_str = datetime.now().isoformat()
        for area in cached_areas:
            area_name = area.get('area_name', '').lower()
            country_code = area.get('country_code', '').lower()
            area_id = area.get('area_id')
            
            if area_name and country_code and area_id:
                cursor.execute(
                    "INSERT OR REPLACE INTO area_cache (area_name, country_code, area_id, last_updated) VALUES (?, ?, ?, ?)",
                    (area_name, country_code, area_id, now_str)
                )
        
        # Add metadata
        cursor.execute(
            "INSERT OR REPLACE INTO cache_metadata (key, value, last_updated) VALUES (?, ?, ?)",
            ('last_full_refresh', now_str, now_str)
        )
        
        # Commit and close
        conn.commit()
        conn.close()
        
        print(f"Successfully initialized database from cache file with {len(cached_areas)} areas")
        
    except Exception as e:
        print(f"Error initializing database from cache file: {e}")
        # If there was an error, try to create a fresh database
        try:
            init_db()
        except Exception as init_error:
            print(f"Error creating fresh database: {init_error}")

def init_db():
    """Initialize the SQLite database if it doesn't exist"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS area_cache (
        area_name TEXT,
        country_code TEXT,
        area_id TEXT,
        last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (area_name, country_code)
    )
    ''')
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS cache_metadata (
        key TEXT PRIMARY KEY,
        value TEXT,
        last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    conn.commit()
    conn.close()
    print("Area cache database initialized")

def load_cache_from_db():
    """Load the cache from SQLite into memory"""
    global area_cache, last_full_refresh
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Check when we last did a full refresh
    cursor.execute("SELECT value FROM cache_metadata WHERE key = 'last_full_refresh'")
    result = cursor.fetchone()
    if result:
        try:
            last_full_refresh = datetime.fromisoformat(result[0])
        except (ValueError, TypeError):
            last_full_refresh = None
    
    # Load all area mappings
    cursor.execute("SELECT area_name, country_code, area_id FROM area_cache")
    results = cursor.fetchall()
    
    for area_name, country_code, area_id in results:
        cache_key = f"{area_name}_{country_code}".lower()
        area_cache[cache_key] = area_id
    
    conn.close()
    print(f"Loaded {len(area_cache)} area mappings from database")

def save_area_to_db(area_name, country_code, area_id):
    """Save a single area mapping to the database"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    now = datetime.now().isoformat()
    cursor.execute(
        "INSERT OR REPLACE INTO area_cache (area_name, country_code, area_id, last_updated) VALUES (?, ?, ?, ?)",
        (area_name.lower(), country_code.lower(), area_id, now)
    )
    
    conn.commit()
    conn.close()

def update_full_refresh_timestamp():
    """Update the timestamp of when we last did a full refresh"""
    global last_full_refresh
    
    now = datetime.now()
    last_full_refresh = now
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute(
        "INSERT OR REPLACE INTO cache_metadata (key, value, last_updated) VALUES (?, ?, ?)",
        ('last_full_refresh', now.isoformat(), now.isoformat())
    )
    
    conn.commit()
    conn.close()

def call_ra_graphql(operation_name, variables):
    """Call the Resident Advisor GraphQL API"""
    url = "https://ra.co/graphql"
    
    # Define GraphQL queries
    queries = {
        "SEARCH_LOCATIONS_QUERY": """
        query SEARCH_LOCATIONS_QUERY($searchTerm: String, $limit: Int!) {
            areas(searchTerm: $searchTerm, limit: $limit, defaultOnError: false) {
                id
                name
                urlName
                eventsCount
                isCountry
                country {
                    id
                    name
                    urlCode
                    __typename
                }
                __typename
            }
        }
        """,
        "GET_AREA_WITH_GUIDEIMAGEURL_QUERY": """
        query GET_AREA_WITH_GUIDEIMAGEURL_QUERY($id: ID, $areaUrlName: String, $countryUrlCode: String) {
            area(id: $id, areaUrlName: $areaUrlName, countryUrlCode: $countryUrlCode) {
                id
                name
                urlName
                ianaTimeZone
                blurb
                country {
                    id
                    name
                    urlCode
                    requiresCookieConsent
                    currency {
                        id
                        code
                        exponent
                        symbol
                        __typename
                    }
                    __typename
                }
                __typename
                guideImageUrl
            }
        }
        """
    }
    
    # Prepare the request payload
    payload = {
        "operationName": operation_name,
        "variables": variables,
        "query": queries.get(operation_name, "")
    }
    
    # Make the request
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    
    response = requests.post(url, json=payload, headers=headers)
    
    # Check for errors
    if response.status_code != 200:
        raise Exception(f"GraphQL API error: {response.status_code} - {response.text}")
    
    return response.json()

def background_refresh_cache():
    """Start a background thread to refresh the cache if needed"""
    def refresh_worker():
        time.sleep(10)  # Wait for server to start fully
        
        # Check if we need a full refresh
        global last_full_refresh
        now = datetime.now()
        needs_refresh = (last_full_refresh is None or 
                         (now - last_full_refresh) > CACHE_MAX_AGE)
        
        if needs_refresh:
            try:
                print("Starting background cache refresh...")
                
                # Refresh only existing areas
                refresh_result = refresh_cache()
                
                if refresh_result["status"] == "success":
                    print(f"Background cache refresh completed: {refresh_result['message']}")
                else:
                    print(f"Background cache refresh failed: {refresh_result['message']}")
                    
            except Exception as e:
                print(f"Background cache refresh failed: {e}")
    
    thread = threading.Thread(target=refresh_worker)
    thread.daemon = True
    thread.start()

def get_area_id(area_name, country_code="au"):
    """Get area ID from name, using cache when possible"""
    # If it's already a numeric ID, just return it
    if area_name and area_name.isdigit():
        return {
            "area_id": area_name,
            "cache_status": "bypass",
            "cache_message": "Numeric ID provided, cache bypassed"
        }
        
    area_name = area_name.lower()
    country_code = country_code.lower()
    cache_key = f"{area_name}_{country_code}"
    
    # Check in-memory cache first (fastest)
    if cache_key in area_cache:
        return {
            "area_id": area_cache[cache_key],
            "cache_status": "hit_memory",
            "cache_message": "Area found in memory cache"
        }
    
    # Not in memory, check database
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT area_id FROM area_cache WHERE area_name = ? AND country_code = ?", 
        (area_name, country_code)
    )
    result = cursor.fetchone()
    conn.close()
    
    if result:
        # Found in database, update memory cache too
        area_id = result[0]
        area_cache[cache_key] = area_id
        return {
            "area_id": area_id,
            "cache_status": "hit_database",
            "cache_message": "Area found in database cache"
        }
    
    # Not found anywhere, do a direct lookup
    try:
        # Call GET_AREA_WITH_GUIDEIMAGEURL_QUERY
        response = call_ra_graphql("GET_AREA_WITH_GUIDEIMAGEURL_QUERY", 
                                  {"areaUrlName": area_name, "countryUrlCode": country_code})
        
        if "data" in response and "area" in response["data"] and response["data"]["area"]:
            area_id = response["data"]["area"]["id"]
            
            # Update both in-memory cache and database
            area_cache[cache_key] = area_id
            save_area_to_db(area_name, country_code, area_id)
            
            return {
                "area_id": area_id,
                "cache_status": "miss",
                "cache_message": "Area not found in cache, fetched from RA API"
            }
        else:
            print(f"Area '{area_name}' not found in country '{country_code}'")
            return None
    except Exception as e:
        print(f"Error looking up area: {e}")
        return None

def get_area_info(area_id=None, area_name=None, country_code="au"):
    """Get full area information by ID or name"""
    # If we have a name but not an ID, get the ID first
    if not area_id and area_name:
        area_id = get_area_id(area_name, country_code)
        if not area_id:
            return None
    
    # Call GraphQL to get full area info
    try:
        response = call_ra_graphql("GET_AREA_WITH_GUIDEIMAGEURL_QUERY", {"id": area_id})
        
        if "data" in response and "area" in response["data"]:
            return response["data"]["area"]
        else:
            print(f"Area info not found for ID '{area_id}'")
            return None
    except Exception as e:
        print(f"Error getting area info: {e}")
        return None

# Function to initialize the cache system
def initialize_area_cache():
    """Initialize the area cache system"""
    # First try to initialize from cache file
    initialize_database_from_cache_file()
    
    # Then load cache from the database (whether it was just created or already existed)
    load_cache_from_db()
    
    # Start background refresh if needed
    background_refresh_cache()

def get_cache_stats():
    """Get statistics about the area cache"""
    global area_cache, last_full_refresh
    
    # Connect to the database
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Get total count from database
    cursor.execute("SELECT COUNT(*) FROM area_cache")
    db_count = cursor.fetchone()[0]
    
    # Get last update time from database
    cursor.execute("SELECT MAX(last_updated) FROM area_cache")
    last_db_update = cursor.fetchone()[0]
    
    # Get timestamp of when we last did a full refresh
    last_refresh_str = None
    if last_full_refresh:
        last_refresh_str = last_full_refresh.isoformat()
    else:
        cursor.execute("SELECT value FROM cache_metadata WHERE key = 'last_full_refresh'")
        result = cursor.fetchone()
        if result:
            last_refresh_str = result[0]
    
    # Get database file size
    cursor.execute("PRAGMA page_count")
    page_count = cursor.fetchone()[0]
    cursor.execute("PRAGMA page_size")
    page_size = cursor.fetchone()[0]
    db_size = page_count * page_size
    
    conn.close()
    
    # Check cache file info
    cache_file_exists = os.path.exists(CACHE_JSON_PATH)
    cache_file_size = 0
    cache_file_updated = None
    cache_file_area_count = 0
    
    if cache_file_exists:
        try:
            cache_file_size = os.path.getsize(CACHE_JSON_PATH)
            cache_file_updated = datetime.fromtimestamp(os.path.getmtime(CACHE_JSON_PATH)).isoformat()
            
            # Try to read area count from cache file
            with open(CACHE_JSON_PATH, 'r') as f:
                cache_data = json.load(f)
                if 'cached_areas' in cache_data:
                    cache_file_area_count = len(cache_data['cached_areas'])
        except Exception as e:
            print(f"Error getting cache file stats: {e}")
    
    # Build stats object
    stats = {
        "memory_cache": {
            "items": len(area_cache),
            "keys": list(area_cache.keys())[:10] + ['...'] if len(area_cache) > 10 else list(area_cache.keys())
        },
        "database_cache": {
            "items": db_count,
            "last_updated": last_db_update,
            "size_bytes": db_size,
            "size_kb": round(db_size / 1024, 2)
        },
        "cache_file": {
            "exists": cache_file_exists,
            "size_bytes": cache_file_size,
            "size_kb": round(cache_file_size / 1024, 2) if cache_file_exists else 0,
            "last_updated": cache_file_updated,
            "area_count": cache_file_area_count
        },
        "refresh_info": {
            "last_full_refresh": last_refresh_str,
            "auto_refresh_period_days": CACHE_MAX_AGE.days
        }
    }
    
    return stats

def get_all_cached_areas():
    """Get all areas stored in the cache"""
    # Connect to the database
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Get all areas
    cursor.execute("SELECT area_name, country_code, area_id, last_updated FROM area_cache ORDER BY country_code, area_name")
    results = cursor.fetchall()
    
    conn.close()
    
    # Format results
    areas = []
    for area_name, country_code, area_id, last_updated in results:
        areas.append({
            "area_name": area_name,
            "country_code": country_code,
            "area_id": area_id,
            "last_updated": last_updated,
            "lookup_key": f"{area_name}_{country_code}"
        })
    
    return areas

def refresh_cache():
    """Manually trigger a cache refresh for only areas already in the database"""
    global last_full_refresh
    
    try:
        # First, get all areas currently in the database
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute("SELECT area_name, country_code, area_id FROM area_cache")
        existing_areas = cursor.fetchall()
        conn.close()
        
        if not existing_areas:
            return {
                "status": "success",
                "message": "No areas in database to refresh",
                "areas_count": 0
            }
        
        print(f"Starting cache refresh for {len(existing_areas)} existing areas...")
        
        # Open a single database connection for all updates
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        updated_count = 0
        error_count = 0
        
        # Update each area individually
        for area_name, country_code, old_area_id in existing_areas:
            try:
                # Call GET_AREA_WITH_GUIDEIMAGEURL_QUERY for this specific area
                response = call_ra_graphql("GET_AREA_WITH_GUIDEIMAGEURL_QUERY", 
                                         {"areaUrlName": area_name, "countryUrlCode": country_code})
                
                if "data" in response and "area" in response["data"] and response["data"]["area"]:
                    area_id = response["data"]["area"]["id"]
                    cache_key = f"{area_name}_{country_code}"
                    
                    # Update in-memory cache
                    area_cache[cache_key] = area_id
                    
                    # Update database only if the ID has changed or to refresh timestamp
                    now_str = datetime.now().isoformat()
                    cursor.execute(
                        "UPDATE area_cache SET area_id = ?, last_updated = ? WHERE area_name = ? AND country_code = ?",
                        (area_id, now_str, area_name, country_code)
                    )
                    
                    updated_count += 1
                    
                    # Be polite to the RA API - add a small delay between requests
                    time.sleep(0.5)
                else:
                    print(f"Warning: Area '{area_name}' in country '{country_code}' no longer found in RA API")
                    error_count += 1
            except Exception as e:
                print(f"Error refreshing area '{area_name}' in country '{country_code}': {e}")
                error_count += 1
        
        # Update the full refresh timestamp
        update_full_refresh_timestamp()
        
        # Commit all changes at once
        conn.commit()
        conn.close()
        
        print(f"Cache refresh completed. Updated {updated_count} areas, {error_count} errors.")
        
        return {
            "status": "success",
            "message": f"Cache refresh completed. Updated {updated_count} areas, {error_count} errors.",
            "areas_count": updated_count,
            "errors": error_count
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Cache refresh failed: {str(e)}"
        }
