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
    quantity_kinds: List[str]  # Changed from singular to support multiple quantity kinds
    conversion_multiplier: float = 1.0  # Multiplier to convert to SI base unit
    conversion_offset: float = 0.0  # Offset for interval scales (temperature, etc.)

    def to_dict(self) -> Dict:
        return {
            'uri': self.uri,
            'symbol': self.symbol,
            'label': self.label,
            'quantity_kinds': self.quantity_kinds,
            'conversion_multiplier': self.conversion_multiplier,
            'conversion_offset': self.conversion_offset
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'QUDTUnit':
        # Handle both old format (quantity_kind) and new format (quantity_kinds)
        if 'quantity_kind' in data and 'quantity_kinds' not in data:
            data = data.copy()
            data['quantity_kinds'] = [data.pop('quantity_kind')]
        return cls(**data)

    @property
    def quantity_kind(self) -> str:
        """Backwards compatibility: return first/primary quantity kind."""
        return self.quantity_kinds[0] if self.quantity_kinds else 'unknown'


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

                # Index by ALL quantity kinds
                for qk in unit.quantity_kinds:
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
        SELECT ?unit ?symbol ?label ?quantityKind ?conversionMultiplier ?conversionOffset WHERE {
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

            # Conversion multiplier to SI base unit
            OPTIONAL { ?unit qudt:conversionMultiplier ?conversionMultiplier }

            # Conversion offset for interval scales (temperature, etc.)
            OPTIONAL { ?unit qudt:conversionOffset ?conversionOffset }
        }
        """
        
        results = graph.query(query)

        # First pass: collect all data per unit URI
        units_data = {}  # unit_uri -> {symbol, labels, quantity_kinds, conversion_multiplier, conversion_offset}

        for row in results:
            if not row.unit:
                continue

            unit_uri = str(row.unit).strip()

            if unit_uri not in units_data:
                units_data[unit_uri] = {
                    'symbols': set(),
                    'labels': set(),
                    'quantity_kinds': set(),
                    'conversion_multiplier': 1.0,  # Default if not specified
                    'conversion_offset': 0.0  # Default if not specified
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

            # Collect conversion multiplier (should be same for all rows with same unit)
            if row.conversionMultiplier:
                units_data[unit_uri]['conversion_multiplier'] = float(row.conversionMultiplier)

            # Collect conversion offset (should be same for all rows with same unit)
            if row.conversionOffset:
                units_data[unit_uri]['conversion_offset'] = float(row.conversionOffset)
        
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
            
            # Create ONE QUDTUnit per unit with ALL its quantity kinds
            quantity_kinds_list = list(data['quantity_kinds']) if data['quantity_kinds'] else ['unknown']

            # Create single unit instance with all quantity kinds
            unit = QUDTUnit(
                uri=unit_uri,
                symbol=symbol,
                label=label,
                quantity_kinds=quantity_kinds_list,
                conversion_multiplier=data['conversion_multiplier'],
                conversion_offset=data['conversion_offset']
            )

            # Store by URI (one instance per unit)
            self.units_by_uri[unit_uri] = unit

            # Index under ALL its quantity kinds
            for qk in quantity_kinds_list:
                if qk not in self.units_by_quantity_kind:
                    self.units_by_quantity_kind[qk] = []

                # Add this unit to the quantity kind index
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

    def convert_value(self, value: float, from_unit_uri: str, to_unit_uri: str) -> float:
        """
        Convert a value between two units using QUDT conversionMultipliers and conversionOffsets.

        Uses the full QUDT formula for ratio and interval scales:
            SI_value = (value × from_multiplier) + from_offset
            target_value = (SI_value - to_offset) / to_multiplier

        This handles both:
        - Ratio scales (length, mass, force): offset = 0
        - Interval scales (temperature): offset ≠ 0

        Args:
            value: The numeric value in from_unit
            from_unit_uri: Source unit URI (e.g., "http://qudt.org/vocab/unit/IN")
            to_unit_uri: Target unit URI (e.g., "http://qudt.org/vocab/unit/MilliM")

        Returns:
            Converted value in to_unit

        Raises:
            ValueError: If units are not found or incompatible

        Examples:
            >>> manager.convert_value(10.0, "unit:IN", "unit:MilliM")
            254.0  # 10 inches = 254 millimeters (ratio scale, offset = 0)

            >>> manager.convert_value(100.0, "unit:DEG_C", "unit:K")
            373.15  # 100°C = 373.15 K (interval scale, offset = 273.15)
        """
        if not self._is_loaded:
            self.load()

        # Normalize URIs (handle both full URIs and prefixed forms)
        from_unit_uri = self._normalize_unit_uri(from_unit_uri)
        to_unit_uri = self._normalize_unit_uri(to_unit_uri)

        # If same unit, no conversion needed
        if from_unit_uri == to_unit_uri:
            return value

        # Get unit information
        from_unit = self.get_unit_by_uri(from_unit_uri)
        to_unit = self.get_unit_by_uri(to_unit_uri)

        if not from_unit:
            raise ValueError(f"Source unit not found in QUDT: {from_unit_uri}")
        if not to_unit:
            raise ValueError(f"Target unit not found in QUDT: {to_unit_uri}")

        # Check if units are compatible (share at least one quantity kind)
        common_qks = set(from_unit.quantity_kinds) & set(to_unit.quantity_kinds)
        if not common_qks:
            logger.warning(
                f"Unit conversion between different quantity kinds: "
                f"{from_unit.quantity_kinds} → {to_unit.quantity_kinds}"
            )

        # Perform conversion through SI base unit with full QUDT formula
        # Step 1: Convert to SI base unit (handles both ratio and interval scales)
        si_value = (value * from_unit.conversion_multiplier) + from_unit.conversion_offset

        # Step 2: Convert from SI base unit to target unit
        target_value = (si_value - to_unit.conversion_offset) / to_unit.conversion_multiplier

        logger.debug(
            f"Converted {value} {from_unit.symbol} → {target_value} {to_unit.symbol} "
            f"(via {si_value} SI, from_offset={from_unit.conversion_offset}, "
            f"to_offset={to_unit.conversion_offset})"
        )

        return target_value

    def _normalize_unit_uri(self, unit_uri: str) -> str:
        """
        Normalize unit URI to full form.

        Handles both prefixed forms (unit:MilliM) and full URIs.
        """
        if not unit_uri:
            return ""

        unit_uri = str(unit_uri).strip().strip('"\'')

        # Handle namespace prefixes
        if ':' in unit_uri and not unit_uri.startswith('http'):
            prefix, local = unit_uri.split(':', 1)
            if prefix == 'unit':
                return f'http://qudt.org/vocab/unit/{local}'
            elif prefix == 'qkdv':
                return f'http://qudt.org/vocab/quantitykind/{local}'

        return unit_uri

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