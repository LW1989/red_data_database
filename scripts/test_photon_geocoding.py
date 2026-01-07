"""
Test Photon API for geocoding German addresses.
This script tests the Photon geocoding API with various German addresses
to verify it works well before implementing the full sync pipeline.
"""

import requests
import time
import json
from typing import Dict, List, Optional, Tuple


def geocode_with_photon(address: str, timeout: int = 10) -> Optional[Dict]:
    """
    Geocode an address using the Photon API.
    
    Args:
        address: Full address string
        timeout: Request timeout in seconds
        
    Returns:
        Dict with geocoding results or None if failed
    """
    # Photon API endpoint
    url = "https://photon.komoot.io/api/"
    
    params = {
        'q': address,
        'lang': 'de',  # German language preference
        'limit': 1  # Only get the best match
    }
    
    try:
        response = requests.get(url, params=params, timeout=timeout)
        response.raise_for_status()
        
        data = response.json()
        
        if data.get('features') and len(data['features']) > 0:
            feature = data['features'][0]
            coords = feature['geometry']['coordinates']
            properties = feature['properties']
            
            return {
                'success': True,
                'latitude': coords[1],  # GeoJSON is [lon, lat]
                'longitude': coords[0],
                'name': properties.get('name', ''),
                'street': properties.get('street', ''),
                'housenumber': properties.get('housenumber', ''),
                'postcode': properties.get('postcode', ''),
                'city': properties.get('city', ''),
                'state': properties.get('state', ''),
                'country': properties.get('country', ''),
                'osm_type': properties.get('osm_type', ''),
                'osm_id': properties.get('osm_id', ''),
                'extent': properties.get('extent', []),
                'raw_response': feature
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


def test_photon_api():
    """Test Photon API with various German addresses."""
    
    # Test addresses covering different cities and formats
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
        "XYZ Invalid Street 999, 99999 Nonexistent City",  # Invalid address
        "",  # Empty string
    ]
    
    print("=" * 80)
    print("PHOTON API GEOCODING TEST")
    print("=" * 80)
    print()
    
    results = []
    successful = 0
    failed = 0
    total_time = 0
    
    for i, address in enumerate(test_addresses, 1):
        print(f"Test {i}/{len(test_addresses)}: {address[:60]}...")
        
        start_time = time.time()
        result = geocode_with_photon(address)
        elapsed = time.time() - start_time
        total_time += elapsed
        
        if result['success']:
            successful += 1
            print(f"  ✓ SUCCESS in {elapsed:.2f}s")
            print(f"    Coordinates: {result['latitude']:.6f}, {result['longitude']:.6f}")
            print(f"    Matched: {result.get('name', 'N/A')}, {result.get('city', 'N/A')}")
            if result.get('street') and result.get('housenumber'):
                print(f"    Address: {result['street']} {result['housenumber']}, {result.get('postcode', '')} {result.get('city', '')}")
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
        
        # Be nice to the API - add a small delay between requests
        if i < len(test_addresses):
            time.sleep(0.5)
    
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
            print(f"   Match: {r.get('name', 'N/A')}")
            print(f"   City: {r.get('city', 'N/A')}, {r.get('state', 'N/A')}")
            print(f"   OSM Type: {r.get('osm_type', 'N/A')}, ID: {r.get('osm_id', 'N/A')}")
        else:
            print(f"   Status: ✗ FAILED")
            print(f"   Error: {item['result'].get('error', 'Unknown')}")
        print(f"   Response time: {item['elapsed']:.2f}s")
    
    print("\n" + "=" * 80)
    print("RECOMMENDATION")
    print("=" * 80)
    
    success_rate = successful / len(test_addresses) * 100
    avg_time = total_time / len(test_addresses)
    
    # Exclude invalid test cases from success rate calculation
    valid_tests = [r for r in results if r['address'] and r['address'] != "XYZ Invalid Street 999, 99999 Nonexistent City"]
    valid_successful = sum(1 for r in valid_tests if r['result']['success'])
    valid_rate = valid_successful / len(valid_tests) * 100 if valid_tests else 0
    
    print(f"\nValid address success rate: {valid_rate:.1f}%")
    print(f"Average response time: {avg_time:.2f}s")
    
    if valid_rate >= 80 and avg_time < 2.0:
        print("\n✓ PHOTON API is SUITABLE for this project")
        print("  - Good success rate for German addresses")
        print("  - Fast response times")
        print("  - Proceed with implementation using Photon")
    elif valid_rate >= 60:
        print("\n⚠ PHOTON API is ACCEPTABLE but not ideal")
        print("  - Moderate success rate")
        print("  - Consider implementing additional validation")
        print("  - Have fallback plan ready (Overpass)")
    else:
        print("\n✗ PHOTON API may NOT BE SUITABLE")
        print("  - Low success rate for German addresses")
        print("  - Consider testing Overpass API as alternative")
    
    return results


if __name__ == '__main__':
    try:
        results = test_photon_api()
        print("\n✓ Test completed successfully")
    except KeyboardInterrupt:
        print("\n\n⚠ Test interrupted by user")
    except Exception as e:
        print(f"\n\n✗ Test failed with error: {e}")
        import traceback
        traceback.print_exc()

