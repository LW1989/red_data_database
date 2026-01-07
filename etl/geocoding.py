"""
Geocoding module for converting German addresses to coordinates.
Uses Nominatim (OpenStreetMap) API with proper rate limiting and caching.
"""

import time
import hashlib
import json
from typing import Dict, Optional, Tuple
from pathlib import Path
import requests
from sqlalchemy import text

from etl.utils import logger, get_db_engine


class GeocodingCache:
    """
    Database-backed cache for geocoding results to avoid repeated API calls.
    """
    
    def __init__(self, engine=None):
        """
        Initialize the geocoding cache.
        
        Args:
            engine: SQLAlchemy engine (optional, will create if not provided)
        """
        self.engine = engine or get_db_engine()
        self._ensure_cache_table()
    
    def _ensure_cache_table(self):
        """Create the geocoding cache table if it doesn't exist."""
        create_table_sql = """
            CREATE SCHEMA IF NOT EXISTS housing;
            
            CREATE TABLE IF NOT EXISTS housing.geocoding_cache (
                address_hash TEXT PRIMARY KEY,
                address TEXT NOT NULL,
                latitude DOUBLE PRECISION,
                longitude DOUBLE PRECISION,
                display_name TEXT,
                quality NUMERIC,
                provider TEXT,
                success BOOLEAN NOT NULL,
                error_message TEXT,
                cached_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                hit_count INTEGER DEFAULT 1
            );
            
            CREATE INDEX IF NOT EXISTS idx_geocoding_cache_address ON housing.geocoding_cache (address);
            CREATE INDEX IF NOT EXISTS idx_geocoding_cache_success ON housing.geocoding_cache (success);
        """
        
        try:
            with self.engine.connect() as conn:
                conn.execute(text(create_table_sql))
                conn.commit()
                logger.debug("Geocoding cache table ensured")
        except Exception as e:
            logger.warning(f"Could not create geocoding cache table: {e}")
    
    def _hash_address(self, address: str) -> str:
        """Generate a hash for an address string."""
        return hashlib.md5(address.lower().strip().encode()).hexdigest()
    
    def get(self, address: str) -> Optional[Dict]:
        """
        Get cached geocoding result for an address.
        
        Args:
            address: Address string
            
        Returns:
            Dict with geocoding result or None if not cached
        """
        address_hash = self._hash_address(address)
        
        try:
            with self.engine.connect() as conn:
                result = conn.execute(
                    text("""
                        UPDATE housing.geocoding_cache 
                        SET hit_count = hit_count + 1 
                        WHERE address_hash = :hash
                        RETURNING *
                    """),
                    {"hash": address_hash}
                )
                conn.commit()
                
                row = result.fetchone()
                if row:
                    logger.debug(f"Cache HIT for address: {address[:50]}")
                    return {
                        'success': row[7],  # success column
                        'latitude': row[2],
                        'longitude': row[3],
                        'display_name': row[4],
                        'quality': float(row[5]) if row[5] else None,
                        'provider': row[6],
                        'error_message': row[8],
                        'cached': True
                    }
                else:
                    logger.debug(f"Cache MISS for address: {address[:50]}")
                    return None
        except Exception as e:
            logger.warning(f"Cache lookup failed: {e}")
            return None
    
    def put(self, address: str, result: Dict):
        """
        Store geocoding result in cache.
        
        Args:
            address: Address string
            result: Geocoding result dict
        """
        address_hash = self._hash_address(address)
        
        try:
            with self.engine.connect() as conn:
                conn.execute(
                    text("""
                        INSERT INTO housing.geocoding_cache 
                        (address_hash, address, latitude, longitude, display_name, 
                         quality, provider, success, error_message)
                        VALUES (:hash, :address, :lat, :lon, :display, :quality, 
                                :provider, :success, :error)
                        ON CONFLICT (address_hash) DO UPDATE SET
                            latitude = EXCLUDED.latitude,
                            longitude = EXCLUDED.longitude,
                            display_name = EXCLUDED.display_name,
                            quality = EXCLUDED.quality,
                            provider = EXCLUDED.provider,
                            success = EXCLUDED.success,
                            error_message = EXCLUDED.error_message,
                            cached_at = CURRENT_TIMESTAMP,
                            hit_count = housing.geocoding_cache.hit_count + 1
                    """),
                    {
                        "hash": address_hash,
                        "address": address,
                        "lat": result.get('latitude'),
                        "lon": result.get('longitude'),
                        "display": result.get('display_name'),
                        "quality": result.get('quality'),
                        "provider": result.get('provider', 'nominatim'),
                        "success": result.get('success', False),
                        "error": result.get('error_message')
                    }
                )
                conn.commit()
                logger.debug(f"Cached result for address: {address[:50]}")
        except Exception as e:
            logger.warning(f"Failed to cache result: {e}")


class RateLimiter:
    """
    Rate limiter to respect API usage policies.
    Nominatim requires max 1 request per second.
    """
    
    def __init__(self, max_per_second: float = 1.0):
        """
        Initialize rate limiter.
        
        Args:
            max_per_second: Maximum requests per second
        """
        self.min_interval = 1.0 / max_per_second
        self.last_request_time = 0
    
    def wait_if_needed(self):
        """Wait if necessary to respect rate limit."""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        
        if time_since_last < self.min_interval:
            wait_time = self.min_interval - time_since_last
            logger.debug(f"Rate limiting: waiting {wait_time:.2f}s")
            time.sleep(wait_time)
        
        self.last_request_time = time.time()


class NominatimGeocoder:
    """
    Geocoder using Nominatim (OpenStreetMap) API.
    Includes rate limiting, caching, and retry logic.
    """
    
    def __init__(self, cache_enabled: bool = True, rate_limit: float = 1.0):
        """
        Initialize Nominatim geocoder.
        
        Args:
            cache_enabled: Whether to use caching
            rate_limit: Requests per second (default 1.0 for Nominatim)
        """
        self.base_url = "https://nominatim.openstreetmap.org/search"
        self.cache = GeocodingCache() if cache_enabled else None
        self.rate_limiter = RateLimiter(max_per_second=rate_limit)
        self.user_agent = "RedDataHousingDatabase/1.0"
        self.timeout = 10
        
        logger.info(f"Nominatim geocoder initialized (cache: {cache_enabled}, rate: {rate_limit} req/s)")
    
    def normalize_address(self, street: str = None, house_number: str = None, 
                         postal_code: str = None, city: str = None) -> str:
        """
        Normalize address components into a single string.
        
        Args:
            street: Street name
            house_number: House number
            postal_code: Postal code (PLZ)
            city: City name
            
        Returns:
            Normalized address string
        """
        parts = []
        
        if street and house_number:
            parts.append(f"{street} {house_number}")
        elif street:
            parts.append(street)
        
        if postal_code:
            parts.append(postal_code)
        
        if city:
            parts.append(city)
        
        address = ", ".join(parts)
        
        # Add country for better results
        if address:
            address += ", Germany"
        
        return address
    
    def geocode(self, address: str, max_retries: int = 3) -> Dict:
        """
        Geocode an address using Nominatim API.
        
        Args:
            address: Full address string
            max_retries: Maximum number of retry attempts
            
        Returns:
            Dict with geocoding results
        """
        # Check cache first
        if self.cache:
            cached_result = self.cache.get(address)
            if cached_result:
                return cached_result
        
        # Make API request with retries
        for attempt in range(max_retries):
            try:
                # Respect rate limit
                self.rate_limiter.wait_if_needed()
                
                # Make request
                headers = {'User-Agent': self.user_agent}
                params = {
                    'q': address,
                    'format': 'json',
                    'addressdetails': 1,
                    'limit': 1,
                    'countrycodes': 'de'
                }
                
                logger.debug(f"Geocoding attempt {attempt + 1}/{max_retries}: {address[:50]}")
                
                response = requests.get(
                    self.base_url,
                    params=params,
                    headers=headers,
                    timeout=self.timeout
                )
                response.raise_for_status()
                
                data = response.json()
                
                if data and len(data) > 0:
                    result_data = data[0]
                    address_details = result_data.get('address', {})
                    
                    result = {
                        'success': True,
                        'latitude': float(result_data['lat']),
                        'longitude': float(result_data['lon']),
                        'display_name': result_data.get('display_name', ''),
                        'quality': result_data.get('importance', 0.5),
                        'provider': 'nominatim',
                        'osm_type': result_data.get('osm_type', ''),
                        'osm_id': result_data.get('osm_id', ''),
                        'house_number': address_details.get('house_number', ''),
                        'road': address_details.get('road', ''),
                        'postcode': address_details.get('postcode', ''),
                        'city': address_details.get('city', address_details.get('town', address_details.get('village', ''))),
                        'state': address_details.get('state', ''),
                        'cached': False
                    }
                    
                    logger.info(f"✓ Geocoded: {address[:50]} → {result['latitude']:.6f}, {result['longitude']:.6f}")
                    
                    # Cache the result
                    if self.cache:
                        self.cache.put(address, result)
                    
                    return result
                else:
                    # No results found
                    result = {
                        'success': False,
                        'error_message': 'No results found',
                        'provider': 'nominatim',
                        'cached': False
                    }
                    
                    logger.warning(f"✗ No results for: {address[:50]}")
                    
                    # Cache failed result to avoid repeated attempts
                    if self.cache:
                        self.cache.put(address, result)
                    
                    return result
                    
            except requests.exceptions.Timeout:
                logger.warning(f"Timeout on attempt {attempt + 1}/{max_retries} for: {address[:50]}")
                if attempt == max_retries - 1:
                    result = {
                        'success': False,
                        'error_message': 'Request timeout',
                        'provider': 'nominatim',
                        'cached': False
                    }
                    if self.cache:
                        self.cache.put(address, result)
                    return result
                time.sleep(2 ** attempt)  # Exponential backoff
                
            except requests.exceptions.RequestException as e:
                logger.warning(f"Request error on attempt {attempt + 1}/{max_retries}: {e}")
                if attempt == max_retries - 1:
                    result = {
                        'success': False,
                        'error_message': f'Request failed: {str(e)}',
                        'provider': 'nominatim',
                        'cached': False
                    }
                    if self.cache:
                        self.cache.put(address, result)
                    return result
                time.sleep(2 ** attempt)
                
            except Exception as e:
                logger.error(f"Unexpected error on attempt {attempt + 1}/{max_retries}: {e}")
                if attempt == max_retries - 1:
                    result = {
                        'success': False,
                        'error_message': f'Unexpected error: {str(e)}',
                        'provider': 'nominatim',
                        'cached': False
                    }
                    if self.cache:
                        self.cache.put(address, result)
                    return result
                time.sleep(2 ** attempt)
        
        # Should never reach here, but just in case
        return {
            'success': False,
            'error_message': 'Max retries exceeded',
            'provider': 'nominatim',
            'cached': False
        }
    
    def geocode_components(self, street: str = None, house_number: str = None,
                          postal_code: str = None, city: str = None) -> Dict:
        """
        Geocode from address components.
        
        Args:
            street: Street name
            house_number: House number
            postal_code: Postal code
            city: City name
            
        Returns:
            Dict with geocoding results
        """
        address = self.normalize_address(street, house_number, postal_code, city)
        return self.geocode(address)


# Convenience function for easy import
def create_geocoder(cache_enabled: bool = True, rate_limit: float = 1.0) -> NominatimGeocoder:
    """
    Create a geocoder instance.
    
    Args:
        cache_enabled: Whether to enable caching
        rate_limit: Requests per second
        
    Returns:
        Geocoder instance
    """
    return NominatimGeocoder(cache_enabled=cache_enabled, rate_limit=rate_limit)

