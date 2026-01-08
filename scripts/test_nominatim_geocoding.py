"""
Test Nominatim API for geocoding German addresses.
Nominatim is the official OpenStreetMap geocoding service.
"""

import requests
import time
import json
from typing import Dict, List, Optional


def geocode_with_nominatim(address: str, timeout: int = 10) -> Optional[Dict]:
    """
    Geocode an address using the Nominatim API.
    
    Args:
        address: Full address string
        timeout: Request timeout in seconds
        
    Returns:
        Dict with geocoding results or None if failed
    """
    # Nominatim API endpoint
    url = "https://nominatim.openstreetmap.org/search"
    
    headers = {
        'User-Agent': 'RedDataGeocodingTest/1.0 (Housing Database)'
    }
    
    params = {
        'q': address,
        'format': 'json',
        'addressdetails': 1,
        'limit': 1,
        'countrycodes': 'de'  # Limit to Germany
    }
    
    try:
        response = requests.get(url, params=params, headers=headers, timeout=timeout)
        response.raise_for_status()
        
        data = response.json()
        
        if data and len(data) > 0:
            result = data[0]
            address_details = result.get('address', {})
            
            return {
                'success': True,
                'latitude': float(result['lat']),
                'longitude': float(result['lon']),
                'display_name': result.get('display_name', ''),
                'house_number': address_details.get('house_number', ''),
                'road': address_details.get('road', ''),
                'postcode': address_details.get('postcode', ''),
                'city': address_details.get('city', address_details.get('town', address_details.get('village', ''))),
                'state': address_details.get('state', ''),
                'country': address_details.get('country', ''),
                'osm_type': result.get('osm_type', ''),
                'osm_id': result.get('osm_id', ''),
                'importance': result.get('importance', 0),
                'raw_response': result
            }
        else:
            return {
                'success': False,
                'error': 'No results found',
                'raw_response': data
            }
            
    except requests.exceptions.Timeout:
        return {
            'success': False,
            'error': f'Request timeout after {timeout} seconds'
        }
    except requests.exceptions.RequestException as e:
        return {
            'success': False,
            'error': f'Request failed: {str(e)}'
        }
    except Exception as e:
        return {
            'success': False,
            'error': f'Unexpected error: {str(e)}'
        }


def test_nominatim_api():
    """Test Nominatim API with various German addresses."""
    
    # Test addresses
    test_addresses = [
        # Complete addresses with street numbers
        "Brandenburger Tor, 10117 Berlin",
        "Marienplatz 1, 80331 München",
        "Reeperbahn 1, 20359 Hamburg",
        "Königsallee 1, 40212 Düsseldorf",
        "Römerberg 27, 60311 Frankfurt am Main",
        
        # Street + city without number
        "Kurfürstendamm, Berlin",
        "Elbphilharmonie, Hamburg",
        
        # Just city names
        "Berlin",
        "München",
        "Köln",
        
        # Problematic cases
        "XYZ Invalid Street 999, 99999 Nonexistent City",
        "",
    ]
    
    print("=" * 80)
    print("NOMINATIM API GEOCODING TEST")
    print("=" * 80)
    print()
    print("⚠️  NOTE: Nominatim usage policy requires:")
    print("   - Maximum 1 request per second")
    print("   - Proper User-Agent header")
    print("   - No heavy usage (we're testing only)")
    print()
    
    results = []
    successful = 0
    failed = 0
    total_time = 0
    
    for i, address in enumerate(test_addresses, 1):
        print(f"Test {i}/{len(test_addresses)}: {address[:60]}...")
        
        start_time = time.time()
        result = geocode_with_nominatim(address)
        elapsed = time.time() - start_time
        total_time += elapsed
        
        if result['success']:
            successful += 1
            print(f"  ✓ SUCCESS in {elapsed:.2f}s")
            print(f"    Coordinates: {result['latitude']:.6f}, {result['longitude']:.6f}")
            print(f"    Matched: {result.get('display_name', 'N/A')[:80]}")
            if result.get('road') and result.get('house_number'):
                print(f"    Address: {result['road']} {result['house_number']}, {result.get('postcode', '')} {result.get('city', '')}")
        else:
            failed += 1
            print(f"  ✗ FAILED in {elapsed:.2f}s")
            print(f"    Error: {result.get('error', 'Unknown error')}")
        
        results.append({
            'address': address,
            'result': result,
            'elapsed': elapsed
        })
        
        print()
        
        # Respect Nominatim's usage policy: max 1 request per second
        if i < len(test_addresses):
            time.sleep(1.0)
    
    # Summary
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Total tests: {len(test_addresses)}")
    print(f"Successful: {successful} ({successful/len(test_addresses)*100:.1f}%)")
    print(f"Failed: {failed} ({failed/len(test_addresses)*100:.1f}%)")
    print(f"Average response time: {total_time/len(test_addresses):.2f}s")
    print(f"Total time: {total_time:.2f}s")
    print()
    
    # Detailed results
    print("=" * 80)
    print("DETAILED RESULTS")
    print("=" * 80)
    
    for i, item in enumerate(results, 1):
        print(f"\n{i}. {item['address']}")
        if item['result']['success']:
            r = item['result']
            print(f"   Status: ✓ SUCCESS")
            print(f"   Lat/Lon: {r['latitude']:.6f}, {r['longitude']:.6f}")
            print(f"   Display: {r.get('display_name', 'N/A')[:80]}")
            print(f"   City: {r.get('city', 'N/A')}, {r.get('state', 'N/A')}")
            print(f"   OSM Type: {r.get('osm_type', 'N/A')}, ID: {r.get('osm_id', 'N/A')}")
            print(f"   Importance: {r.get('importance', 0):.3f}")
        else:
            print(f"   Status: ✗ FAILED")
            print(f"   Error: {item['result'].get('error', 'Unknown')}")
        print(f"   Response time: {item['elapsed']:.2f}s")
    
    print("\n" + "=" * 80)
    print("RECOMMENDATION")
    print("=" * 80)
    
    # Exclude invalid test cases
    valid_tests = [r for r in results if r['address'] and r['address'] != "XYZ Invalid Street 999, 99999 Nonexistent City"]
    valid_successful = sum(1 for r in valid_tests if r['result']['success'])
    valid_rate = valid_successful / len(valid_tests) * 100 if valid_tests else 0
    avg_time = total_time / len(test_addresses)
    
    print(f"\nValid address success rate: {valid_rate:.1f}%")
    print(f"Average response time: {avg_time:.2f}s")
    print(f"\n⚠️  RATE LIMIT: 1 request per second maximum")
    
    if valid_rate >= 80:
        print("\n✓ NOMINATIM API is SUITABLE for this project")
        print("  - Good success rate for German addresses")
        print("  - FREE and reliable")
        print("  - IMPORTANT: Implement 1 req/sec rate limiting!")
        print("  - Use caching to minimize API calls")
    elif valid_rate >= 60:
        print("\n⚠ NOMINATIM API is ACCEPTABLE but not ideal")
        print("  - Moderate success rate")
        print("  - Must implement strict rate limiting")
    else:
        print("\n✗ NOMINATIM API may NOT BE SUITABLE")
        print("  - Low success rate for German addresses")
    
    return results


if __name__ == '__main__':
    try:
        results = test_nominatim_api()
        print("\n✓ Test completed successfully")
    except KeyboardInterrupt:
        print("\n\n⚠ Test interrupted by user")
    except Exception as e:
        print(f"\n\n✗ Test failed with error: {e}")
        import traceback
        traceback.print_exc()

