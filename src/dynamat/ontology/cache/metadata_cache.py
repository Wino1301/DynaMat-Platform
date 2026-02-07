"""
DynaMat Platform - Metadata Cache
Manages caching of class and property metadata for performance
Extracted from manager.py for better separation of concerns
"""

import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import time

logger = logging.getLogger(__name__)


@dataclass
class CacheStats:
    """Cache statistics and status information."""
    classes_cached: int
    properties_cached: int
    qudt_units_cached: int
    last_updated: Optional[float]
    cache_hits: int
    cache_misses: int


class MetadataCache:
    """
    Manages caching of frequently accessed metadata.
    
    Responsibilities:
    - Cache class metadata for GUI building
    - Cache property metadata
    - Cache QUDT units and quantity kinds
    - Provide cache statistics and management
    """
    
    def __init__(self):
        """Initialize the metadata cache."""
        # Core metadata caches
        self.classes_cache = {}
        self.properties_cache = {}
        
        # QUDT caches
        self.quantity_kinds_cache = {}
        self.units_cache = {}
        
        # Cache statistics
        self._cache_hits = 0
        self._cache_misses = 0
        self._last_updated = None
        
        logger.info("Metadata cache initialized")
    
    def cache_class_metadata(self, class_uri: str, metadata: Any):
        """
        Cache class metadata.
        
        Args:
            class_uri: URI of the class
            metadata: ClassMetadata object
        """
        self.classes_cache[class_uri] = metadata
        self._last_updated = time.time()
        logger.debug(f"Cached metadata for class: {class_uri}")
    
    def get_cached_class_metadata(self, class_uri: str) -> Optional[Any]:
        """
        Get cached class metadata.
        
        Args:
            class_uri: URI of the class
            
        Returns:
            ClassMetadata object if cached, None otherwise
        """
        if class_uri in self.classes_cache:
            self._cache_hits += 1
            logger.debug(f"Cache hit for class: {class_uri}")
            return self.classes_cache[class_uri]
        else:
            self._cache_misses += 1
            logger.debug(f"Cache miss for class: {class_uri}")
            return None
    
    def cache_property_metadata(self, property_uri: str, metadata: Any):
        """
        Cache property metadata.
        
        Args:
            property_uri: URI of the property
            metadata: PropertyMetadata object
        """
        self.properties_cache[property_uri] = metadata
        self._last_updated = time.time()
        logger.debug(f"Cached metadata for property: {property_uri}")
    
    def get_cached_property_metadata(self, property_uri: str) -> Optional[Any]:
        """
        Get cached property metadata.
        
        Args:
            property_uri: URI of the property
            
        Returns:
            PropertyMetadata object if cached, None otherwise
        """
        if property_uri in self.properties_cache:
            self._cache_hits += 1
            return self.properties_cache[property_uri]
        else:
            self._cache_misses += 1
            return None
    
    def cache_quantity_kind(self, qk_uri: str, qk_data: Dict[str, Any]):
        """
        Cache QUDT quantity kind data.
        
        Args:
            qk_uri: URI of the quantity kind
            qk_data: Quantity kind metadata
        """
        self.quantity_kinds_cache[qk_uri] = qk_data
        self._last_updated = time.time()
    
    def get_cached_quantity_kind(self, qk_uri: str) -> Optional[Dict[str, Any]]:
        """Get cached quantity kind data."""
        if qk_uri in self.quantity_kinds_cache:
            self._cache_hits += 1
            return self.quantity_kinds_cache[qk_uri]
        else:
            self._cache_misses += 1
            return None
    
    def cache_unit(self, unit_uri: str, unit_data: Dict[str, Any]):
        """
        Cache QUDT unit data.
        
        Args:
            unit_uri: URI of the unit
            unit_data: Unit metadata
        """
        self.units_cache[unit_uri] = unit_data
        self._last_updated = time.time()
    
    def get_cached_unit(self, unit_uri: str) -> Optional[Dict[str, Any]]:
        """Get cached unit data."""
        if unit_uri in self.units_cache:
            self._cache_hits += 1
            return self.units_cache[unit_uri]
        else:
            self._cache_misses += 1
            return None
    
    def clear_all_caches(self):
        """Clear all caches."""
        self.classes_cache.clear()
        self.properties_cache.clear()
        self.quantity_kinds_cache.clear()
        self.units_cache.clear()
        
        self._cache_hits = 0
        self._cache_misses = 0
        self._last_updated = time.time()
        
        logger.info("All caches cleared")
    
    def clear_class_cache(self):
        """Clear only the class metadata cache."""
        self.classes_cache.clear()
        logger.info("Class metadata cache cleared")
    
    def clear_property_cache(self):
        """Clear only the property metadata cache."""
        self.properties_cache.clear()
        logger.info("Property metadata cache cleared")
    
    def clear_qudt_cache(self):
        """Clear QUDT-related caches."""
        self.quantity_kinds_cache.clear()
        self.units_cache.clear()
        logger.info("QUDT caches cleared")
    
    def get_cache_stats(self) -> CacheStats:
        """
        Get comprehensive cache statistics.
        
        Returns:
            CacheStats object with current statistics
        """
        return CacheStats(
            classes_cached=len(self.classes_cache),
            properties_cached=len(self.properties_cache),
            qudt_units_cached=len(self.units_cache),
            last_updated=self._last_updated,
            cache_hits=self._cache_hits,
            cache_misses=self._cache_misses
        )
    
    def get_cached_class_uris(self) -> List[str]:
        """Get list of all cached class URIs."""
        return list(self.classes_cache.keys())
    
    def get_cached_property_uris(self) -> List[str]:
        """Get list of all cached property URIs."""
        return list(self.properties_cache.keys())
    
    def is_class_cached(self, class_uri: str) -> bool:
        """Check if a class is cached."""
        return class_uri in self.classes_cache
    
    def is_property_cached(self, property_uri: str) -> bool:
        """Check if a property is cached."""
        return property_uri in self.properties_cache
    
    def get_cache_hit_ratio(self) -> float:
        """Get the cache hit ratio as a percentage."""
        total_requests = self._cache_hits + self._cache_misses
        if total_requests == 0:
            return 0.0
        return (self._cache_hits / total_requests) * 100.0