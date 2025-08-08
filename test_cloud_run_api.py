#!/usr/bin/env python3
"""
Test script for the enhanced RA Events API deployed on Google Cloud Run
Tests all functionality including the new batch processing capabilities
"""

import requests
import json
import time
from datetime import datetime, timedelta

def get_api_base():
    """Get the API base URL - modify this for your Cloud Run deployment"""
    print("🔧 API Configuration")
    print("Please enter your Google Cloud Run API URL:")
    print("Format: https://your-service-name-hash-region.a.run.app")
    print("Example: https://ra-events-api-123456-uc.a.run.app")
    print()
    
    api_url = input("Enter your Cloud Run URL: ").strip()
    
    if not api_url:
        print("❌ No URL provided, using local development URL")
        return "http://localhost:8080"
    
    if not api_url.startswith("http"):
        api_url = "https://" + api_url
    
    # Remove trailing slash
    api_url = api_url.rstrip('/')
    
    print(f"✅ Using API: {api_url}")
    return api_url

def test_endpoint(api_base, endpoint, description, method="GET", data=None):
    """Test an API endpoint and display results"""
    print(f"\n🧪 Testing: {description}")
    print(f"📡 Endpoint: {method} {endpoint}")
    
    try:
        url = f"{api_base}{endpoint}"
        
        if method == "GET":
            response = requests.get(url, timeout=30)
        elif method == "POST":
            response = requests.post(url, json=data, headers={'Content-Type': 'application/json'}, timeout=30)
        
        if response.status_code == 200:
            json_data = response.json()
            print(f"✅ Success: {response.status_code}")
            
            # Display relevant info based on endpoint
            if '/events' in endpoint and 'batch' not in endpoint:
                if 'counts' in json_data:
                    counts = json_data['counts']
                    print(f"   📊 Total Results: {counts.get('total_results', 0)}")
                    print(f"   📅 Regular Events: {counts.get('regular_events', 0)}")
                    print(f"   🎯 Bumped Events: {counts.get('bumped_events', 0)}")
                    
                    if json_data.get('filters'):
                        filters = json_data['filters']
                        active_filters = [f"{k}={v}" for k, v in filters.items() if v is not None and v != 'listingDate']
                        if active_filters:
                            print(f"   🔍 Active Filters: {', '.join(active_filters)}")
                            
            elif '/filters' in endpoint:
                if 'available_filters' in json_data:
                    af = json_data['available_filters']
                    if 'genres' in af:
                        print(f"   🎵 Genres Found: {len(af['genres'])}")
                        if af['genres']:
                            print(f"   🎵 Sample Genres: {[g['label'] for g in af['genres'][:5]]}")
                    if 'event_types' in af:
                        print(f"   🎪 Event Types Found: {len(af['event_types'])}")
                        if af['event_types']:
                            print(f"   🎪 Sample Types: {[et['value'] for et in af['event_types'][:3]]}")
                            
            elif '/areas' in endpoint:
                if 'areas' in json_data:
                    print(f"   🌍 Areas Found: {len(json_data['areas'])}")
                    
            elif 'batch' in endpoint:
                if 'batch_summary' in json_data:
                    bs = json_data['batch_summary']
                    print(f"   📊 Total Queries: {bs.get('total_queries', 0)}")
                    print(f"   ✅ Successful: {bs.get('successful_queries', 0)}")
                    print(f"   ❌ Failed: {bs.get('failed_queries', 0)}")
                    
                    if 'total_artists_found' in bs:
                        print(f"   🎧 Artists Found: {bs['total_artists_found']}")
                    elif 'total_labels_found' in bs:
                        print(f"   🏷️ Labels Found: {bs['total_labels_found']}")
                    elif 'total_events_found' in bs:
                        print(f"   🎉 Events Found: {bs['total_events_found']}")
                    elif 'total_results_found' in bs:
                        print(f"   🔍 Total Results: {bs['total_results_found']}")
                        
        else:
            print(f"❌ Failed: {response.status_code}")
            error_text = response.text[:300] if response.text else "No error message"
            print(f"   Error: {error_text}")
            
    except requests.exceptions.ConnectionError:
        print("❌ Connection Error: Unable to connect to the API")
        print("   • Check your Cloud Run URL is correct")
        print("   • Ensure your Cloud Run service is deployed and running")
        print("   • Verify your internet connection")
    except requests.exceptions.Timeout:
        print("❌ Timeout: Request took too long (>30 seconds)")
        print("   • Cloud Run cold start might be slow")
        print("   • Try again in a moment")
    except requests.exceptions.HTTPError as e:
        print(f"❌ HTTP Error: {e}")
    except Exception as e:
        print(f"❌ Unexpected Error: {str(e)}")

def main():
    print("🚀 RA Events API Enhanced Functionality Test (Cloud Run)")
    print("=" * 70)
    
    # Get API URL
    api_base = get_api_base()
    print("\n" + "=" * 70)
    
    # Get dates for testing
    today = datetime.now()
    tomorrow = today + timedelta(days=1)
    next_week = today + timedelta(days=7)
    
    start_date = tomorrow.strftime("%Y-%m-%d")
    end_date = next_week.strftime("%Y-%m-%d")
    
    print(f"📅 Test Date Range: {start_date} to {end_date}")
    print(f"🏙️ Test Areas: 1 (Sydney), 2 (Melbourne), 3 (Perth)")
    
    # Test basic functionality
    print("\n" + "🔸" * 30 + " BASIC ENDPOINTS " + "🔸" * 30)
    
    test_endpoint(api_base, "/", "API Health Check")
    test_endpoint(api_base, "/areas", "Available Areas")
    test_endpoint(api_base, "/filters?area=1", "Available Filters for Sydney")
    
    # Test enhanced events
    print("\n" + "🔸" * 30 + " ENHANCED EVENTS " + "🔸" * 30)
    
    test_endpoint(api_base, f"/events?area=1&start_date={start_date}&end_date={end_date}", 
                 "Basic Events Query")
    
    test_endpoint(api_base, f"/events?area=1&start_date={start_date}&end_date={end_date}&genre=techno", 
                 "Filter by Genre (Techno)")
    
    test_endpoint(api_base, f"/events?area=1&start_date={start_date}&end_date={end_date}&sort=score", 
                 "Sort by Popularity Score")
    
    # Test batch endpoints
    print("\n" + "🔸" * 30 + " BATCH PROCESSING " + "🔸" * 30)
    
    # Batch artist search
    artist_data = {"queries": ["charlotte de witte", "amelie lens", "adam beyer"]}
    test_endpoint(api_base, "/artists/batch", "Batch Artist Search", "POST", artist_data)
    
    # Batch label search
    label_data = {"queries": ["drumcode", "hotflush", "minus"]}
    test_endpoint(api_base, "/labels/batch", "Batch Label Search", "POST", label_data)
    
    # Batch events
    events_data = {
        "areas": [1, 2, 3],
        "start_date": start_date,
        "end_date": end_date,
        "genre": "techno",
        "sort": "score"
    }
    test_endpoint(api_base, "/events/batch", "Batch Events (Multi-Area)", "POST", events_data)
    
    # Mixed batch search
    mixed_data = {
        "artists": ["charlotte de witte", "amelie lens"],
        "labels": ["drumcode", "hotflush"],
        "general": ["berlin techno", "minimal house"]
    }
    test_endpoint(api_base, "/search/batch", "Mixed Batch Search", "POST", mixed_data)
    
    # Performance test
    print("\n" + "🔸" * 30 + " PERFORMANCE TEST " + "🔸" * 30)
    
    print("\n⏱️ Testing batch vs individual requests...")
    
    # Time individual requests
    start_time = time.time()
    test_endpoint(api_base, "/artist/search?q=charlotte+de+witte", "Individual Artist 1", "GET")
    test_endpoint(api_base, "/artist/search?q=amelie+lens", "Individual Artist 2", "GET")
    test_endpoint(api_base, "/artist/search?q=adam+beyer", "Individual Artist 3", "GET")
    individual_time = time.time() - start_time
    
    # Time batch request
    start_time = time.time()
    batch_artist_data = {"queries": ["charlotte de witte", "amelie lens", "adam beyer"]}
    test_endpoint(api_base, "/artists/batch", "Batch Artist Search (Performance)", "POST", batch_artist_data)
    batch_time = time.time() - start_time
    
    print(f"\n📊 Performance Comparison:")
    print(f"   Individual Requests: {individual_time:.2f} seconds")
    print(f"   Batch Request: {batch_time:.2f} seconds")
    if individual_time > batch_time:
        improvement = ((individual_time - batch_time) / individual_time) * 100
        print(f"   🚀 Batch is {improvement:.1f}% faster!")
    else:
        print(f"   ⚡ Individual requests were faster (likely due to Cloud Run optimizations)")
    
    print("\n" + "=" * 70)
    print("🎉 Test Complete!")
    print("\n💡 Tips for Cloud Run:")
    print("   • First requests may be slower due to cold starts")
    print("   • Batch requests are more efficient for multiple queries")
    print("   • Check Cloud Run logs if you encounter errors")
    print("   • Monitor your Cloud Run quotas and billing")
    print("\n🔗 Useful Cloud Run commands:")
    print("   gcloud run services list")
    print("   gcloud run services describe [SERVICE-NAME] --region=[REGION]")
    print("   gcloud logging read 'resource.type=cloud_run_revision'")

if __name__ == "__main__":
    main()
