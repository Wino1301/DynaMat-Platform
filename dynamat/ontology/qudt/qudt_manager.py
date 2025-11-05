"""
DynaMat Platform - QUDT Manager
Handles QUDT ontology loading, caching, and unit queries
"""

import logging
import json
import pickle
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta
import urllib.request
import urllib.error

from rdflib import Graph, Namespace, URIRef, Literal
from rdflib.namespace import RDF, RDFS
from ...config import Config

logger = logging.getLogger(__name__)


@dataclass
class QUDTUnit:
    """QUDT Unit information"""
    uri: str
    symbol: str
    label: str
    quantity_kind: str
    
    def to_dict(self) -> Dict:
        return {
            'uri': self.uri,
            'symbol': self.symbol,
            'label': self.label,
            'quantity_kind': self.quantity_kind
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'QUDTUnit':
        return cls(**data)


class QUDTManager:
    """
    Manages QUDT ontology data with persistent caching.
    
    Responsibilities:
    - Load QUDT units from online source or local files
    - Cache QUDT data to disk for fast subsequent loads
    - Query units by quantity kind
    - Manage cache freshness and updates
    """
    
    # QUDT online sources
    QUDT_UNITS_URL = "https://qudt.org/2.1/vocab/unit"
    QUDT_QUANTITYKINDS_URL = "https://qudt.org/2.1/vocab/quantitykind"
    
    def __init__(self, cache_dir: Optional[Path] = None):
        """
        Initialize QUDT manager.
        
        Args:
            cache_dir: Directory for cache files, defaults to ~/.dynamat/qudt_cache
        """
        if cache_dir is None:
            cache_dir = Config.QUDT_CACHE_DIR
        
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        self.cache_file = self.cache_dir / "qudt_units_cache.json"
        self.metadata_file = self.cache_dir / "cache_metadata.json"
        
        # Namespaces
        self.QUDT = Namespace("http://qudt.org/schema/qudt/")
        self.UNIT = Namespace("http://qudt.org/vocab/unit/")
        self.QKDV = Namespace("http://qudt.org/vocab/quantitykind/")
        
        # Cache data structures
        self.units_by_uri: Dict[str, QUDTUnit] = {}
        self.units_by_quantity_kind: Dict[str, List[QUDTUnit]] = {}
        
        self._is_loaded = False
        
        logger.info(f"QUDT Manager initialized with cache directory: {self.cache_dir}")
    
    def load(self, force_refresh: bool = False) -> bool:
        """
        Load QUDT data from cache or external source.
        
        Args:
            force_refresh: Force download from online source
            use_builtin: Use built-in minimal unit definitions if cache unavailable
            
        Returns:
            True if loaded successfully
        """
        if self._is_loaded and not force_refresh:
            logger.debug("QUDT data already loaded")
            return True
        
        # Try to load from cache first
        if not force_refresh and self._load_from_cache():
            self._is_loaded = True
            return True
        
        # Try to download and build cache
        logger.info("QUDT cache not found or expired, building cache...")
        
        if self._download_and_build_cache():
            self._is_loaded = True
            return True
        
        logger.error("Failed to load QUDT data")
        return False

    def rebuild_cache(self):
        """
        Force rebuild of QUDT cache.
        
        Useful when updating the extraction logic.
        """
        logger.info("Forcing QUDT cache rebuild...")
        self.clear_cache()
        self._is_loaded = False
        return self.load(force_refresh=True)
    
    def _load_from_cache(self) -> bool:
        """Load QUDT data from disk cache."""
        if not self.cache_file.exists():
            logger.debug("Cache file does not exist")
            return False
        
        # Check cache freshness
        if not self._is_cache_fresh():
            logger.info("Cache is stale, will rebuild")
            return False
        
        try:
            with open(self.cache_file, 'r') as f:
                cache_data = json.load(f)
            
            # Reconstruct units from cache
            for unit_data in cache_data.get('units', []):
                unit = QUDTUnit.from_dict(unit_data)
                self.units_by_uri[unit.uri] = unit
                
                # Index by quantity kind
                qk = unit.quantity_kind
                if qk not in self.units_by_quantity_kind:
                    self.units_by_quantity_kind[qk] = []
                self.units_by_quantity_kind[qk].append(unit)
            
            logger.info(f"Loaded {len(self.units_by_uri)} units from cache")
            return True
            
        except Exception as e:
            logger.error(f"Failed to load from cache: {e}")
            return False
    
    def _is_cache_fresh(self, max_age_days: int = 7) -> bool:
        """Check if cache is fresh enough to use."""
        if not self.metadata_file.exists():
            return False
        
        try:
            with open(self.metadata_file, 'r') as f:
                metadata = json.load(f)
            
            cache_time = datetime.fromisoformat(metadata['created'])
            age = datetime.now() - cache_time
            
            is_fresh = age < timedelta(days=max_age_days)
            if is_fresh == True:
                logger.debug(f"Cache age: {age.days} days, fresh: {is_fresh}")
            else:
                self.rebuild_cache()
            return is_fresh
            
        except Exception as e:
            logger.warning(f"Could not check cache freshness: {e}")
            return False
    
    def _download_and_build_cache(self) -> bool:
        """Download QUDT ontology and build cache."""
        logger.info("Downloading QUDT units ontology...")
        
        graph = Graph()
        graph.bind("qudt", self.QUDT)
        graph.bind("unit", self.UNIT)
        graph.bind("qkdv", self.QKDV)
        
        # Try to download QUDT units
        try:
            # Download with timeout
            logger.info(f"Fetching from {self.QUDT_UNITS_URL}...")
            graph.parse(self.QUDT_UNITS_URL, format='turtle')
            logger.info(f"Successfully downloaded QUDT units ({len(graph)} triples)")
            
        except (urllib.error.URLError, Exception) as e:
            logger.error(f"Failed to download QUDT from {self.QUDT_UNITS_URL}: {e}")
            return False
        
        # Extract units from graph
        self._extract_units_from_graph(graph)
        
        # Save to cache
        if self._save_to_cache():
            logger.info("QUDT cache built and saved successfully")
            return True
        
        return False
    
    def _extract_units_from_graph(self, graph: Graph):
        """Extract unit information from RDF graph, handling duplicates properly."""
        # Strategy: Query for all unit-quantityKind pairs, then aggregate by unit
        query = """
        SELECT ?unit ?symbol ?label ?quantityKind WHERE {
            ?unit a qudt:Unit .
            
            # Symbol is required
            OPTIONAL { ?unit qudt:symbol ?symbol }
            
            # English labels only
            OPTIONAL { 
                ?unit rdfs:label ?label .
                FILTER(LANG(?label) = "en" || LANG(?label) = "")
            }
            
            # Quantity kind (a unit can have multiple)
            OPTIONAL { ?unit qudt:hasQuantityKind ?quantityKind }
        }
        """
        
        results = graph.query(query)
        
        # First pass: collect all data per unit URI
        units_data = {}  # unit_uri -> {symbol, labels, quantity_kinds}
        
        for row in results:
            if not row.unit:
                continue
            
            unit_uri = str(row.unit).strip()
            
            if unit_uri not in units_data:
                units_data[unit_uri] = {
                    'symbols': set(),
                    'labels': set(),
                    'quantity_kinds': set()
                }
            
            # Collect symbol
            if row.symbol:
                units_data[unit_uri]['symbols'].add(str(row.symbol))
            
            # Collect label
            if row.label:
                units_data[unit_uri]['labels'].add(str(row.label))
            
            # Collect quantity kind
            if row.quantityKind:
                units_data[unit_uri]['quantity_kinds'].add(str(row.quantityKind).strip())
        
        # Second pass: create QUDTUnit objects
        for unit_uri, data in units_data.items():
            # Choose best symbol (prefer shortest, most common notation)
            if data['symbols']:
                symbol = min(data['symbols'], key=len)
            else:
                symbol = self._extract_symbol_from_uri(unit_uri)
            
            # Choose best label (prefer shortest English one)
            if data['labels']:
                label = min(data['labels'], key=len)
            else:
                label = symbol
            
            # Create one QUDTUnit per unit (not per quantity kind)
            # But index it under ALL its quantity kinds
            quantity_kinds = data['quantity_kinds'] if data['quantity_kinds'] else {'unknown'}
            
            for qk in quantity_kinds:
                unit = QUDTUnit(
                    uri=unit_uri,
                    symbol=symbol,
                    label=label,
                    quantity_kind=qk
                )
                
                # Store by URI (only once)
                if unit_uri not in self.units_by_uri:
                    self.units_by_uri[unit_uri] = unit
                
                # Index by quantity kind (may appear in multiple)
                if qk not in self.units_by_quantity_kind:
                    self.units_by_quantity_kind[qk] = []
                
                # Check if already in this quantity kind list
                if not any(u.uri == unit_uri for u in self.units_by_quantity_kind[qk]):
                    self.units_by_quantity_kind[qk].append(unit)
        
        logger.info(f"Extracted {len(self.units_by_uri)} unique units from graph")
        logger.info(f"Organized into {len(self.units_by_quantity_kind)} quantity kinds")
    
    def _extract_symbol_from_uri(self, uri: str) -> str:
        """Extract a reasonable symbol from unit URI."""
        # Get the last part of the URI
        parts = uri.replace('#', '/').split('/')
        symbol = parts[-1] if parts else uri
        return symbol
    
    def _save_to_cache(self) -> bool:
        """Save QUDT data to disk cache."""
        try:
            # Save units data
            cache_data = {
                'units': [unit.to_dict() for unit in self.units_by_uri.values()],
                'version': '1.0'
            }
            
            with open(self.cache_file, 'w') as f:
                json.dump(cache_data, f, indent=2)
            
            # Save metadata
            metadata = {
                'created': datetime.now().isoformat(),
                'unit_count': len(self.units_by_uri),
                'quantity_kind_count': len(self.units_by_quantity_kind)
            }
            
            with open(self.metadata_file, 'w') as f:
                json.dump(metadata, f, indent=2)
            
            logger.info(f"Saved cache to {self.cache_file}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save cache: {e}")
            return False
    
    def get_units_for_quantity_kind(self, quantity_kind_uri: str) -> List[QUDTUnit]:
        """
        Get all units for a given quantity kind, sorted by symbol.
        
        Args:
            quantity_kind_uri: URI of the quantity kind
            
        Returns:
            List of QUDTUnit objects, sorted alphabetically by symbol
        """
        if not self._is_loaded:
            self.load()
        
        units = self.units_by_quantity_kind.get(quantity_kind_uri, [])
        
        # Sort by symbol for better UX
        return sorted(units, key=lambda u: u.symbol.lower())
    
    def get_unit_by_uri(self, unit_uri: str) -> Optional[QUDTUnit]:
        """Get unit information by URI."""
        if not self._is_loaded:
            self.load()
        
        return self.units_by_uri.get(unit_uri)
    
    def clear_cache(self):
        """Clear the disk cache."""
        try:
            if self.cache_file.exists():
                self.cache_file.unlink()
            if self.metadata_file.exists():
                self.metadata_file.unlink()
            logger.info("Cache cleared")
        except Exception as e:
            logger.error(f"Failed to clear cache: {e}")
    
    def get_cache_info(self) -> Dict:
        """Get information about the cache."""
        return {
            'is_loaded': self._is_loaded,
            'cache_exists': self.cache_file.exists(),
            'cache_fresh': self._is_cache_fresh() if self.cache_file.exists() else False,
            'unit_count': len(self.units_by_uri),
            'quantity_kind_count': len(self.units_by_quantity_kind),
            'cache_file': str(self.cache_file)
        }