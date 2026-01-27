"""
DynaMat Platform - Series Metadata Resolver
Resolves SeriesType URIs to axis labels and legend text using ontology queries and QUDTManager.
"""

import logging
from typing import Dict, Optional, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from dynamat.ontology import OntologyManager
    from dynamat.ontology.qudt import QUDTManager

logger = logging.getLogger(__name__)


class SeriesMetadataResolver:
    """
    Resolves SeriesType URIs to display-friendly axis labels and legend text.

    Uses ontology queries to get quantity kind and unit information, then
    QUDTManager to resolve unit symbols for axis labels.

    Data Flow:
        series_type_uri (e.g., 'dyn:Stress')
            |
            +---> DomainQueries.get_series_type_metadata()
            |        Returns: {quantity_kind, unit, legend_template}
            |
            +---> QUDTManager.get_unit_by_uri(unit_uri)
                     Returns: QUDTUnit with .symbol (e.g., 'MPa')
            |
            v
        Axis label: "Stress (MPa)"

    Example:
        >>> resolver = SeriesMetadataResolver(ontology_manager, qudt_manager)
        >>> resolver.get_axis_label('https://dynamat.utep.edu/ontology#Stress')
        'Stress (MPa)'
        >>> resolver.get_legend_text('https://dynamat.utep.edu/ontology#Stress', '1-wave')
        'Engineering Stress (1-wave)'
    """

    # Namespace prefixes for URI normalization
    DYN_NS = "https://dynamat.utep.edu/ontology#"
    QUDT_UNIT_NS = "http://qudt.org/vocab/unit/"
    QUDT_QK_NS = "http://qudt.org/vocab/quantitykind/"

    def __init__(self, ontology_manager: 'OntologyManager', qudt_manager: 'QUDTManager'):
        """
        Initialize the resolver with ontology and QUDT managers.

        Args:
            ontology_manager: OntologyManager for querying SeriesType metadata
            qudt_manager: QUDTManager for resolving unit symbols
        """
        self.ontology_manager = ontology_manager
        self.qudt_manager = qudt_manager

        # Cache for resolved metadata to avoid repeated queries
        self._metadata_cache: Dict[str, Dict[str, Any]] = {}
        self._label_cache: Dict[str, str] = {}

        logger.debug("SeriesMetadataResolver initialized")

    def _normalize_uri(self, uri: str) -> str:
        """
        Normalize URI to full form for consistent lookups.

        Handles prefixed forms like 'dyn:Stress' and 'unit:MegaPA'.
        """
        if not uri:
            return ""

        uri = str(uri).strip()

        # Handle namespace prefixes
        if uri.startswith('dyn:'):
            return self.DYN_NS + uri[4:]
        elif uri.startswith('unit:'):
            return self.QUDT_UNIT_NS + uri[5:]
        elif uri.startswith('qkdv:'):
            return self.QUDT_QK_NS + uri[5:]

        return uri

    def _get_series_metadata(self, series_type_uri: str) -> Optional[Dict[str, Any]]:
        """
        Get metadata for a SeriesType from cache or ontology.

        Args:
            series_type_uri: URI of the SeriesType individual

        Returns:
            Dict with quantity_kind, unit, legend_template, or None if not found
        """
        normalized_uri = self._normalize_uri(series_type_uri)

        # Check cache first
        if normalized_uri in self._metadata_cache:
            return self._metadata_cache[normalized_uri]

        try:
            # Query ontology for all series type metadata
            all_metadata = self.ontology_manager.domain_queries.get_series_type_metadata()

            # Find entry matching our series type URI
            for column_name, meta in all_metadata.items():
                meta_series_uri = self._normalize_uri(meta.get('series_type', ''))
                if meta_series_uri == normalized_uri:
                    self._metadata_cache[normalized_uri] = meta
                    return meta

            logger.debug(f"No metadata found for series type: {series_type_uri}")
            return None

        except Exception as e:
            logger.error(f"Error querying series metadata for {series_type_uri}: {e}")
            return None

    def _extract_display_name(self, series_type_uri: str) -> str:
        """
        Extract a display name from the SeriesType URI.

        Falls back to extracting from URI if ontology lookup fails.
        """
        normalized_uri = self._normalize_uri(series_type_uri)

        # Try to get from ontology metadata first
        metadata = self._get_series_metadata(series_type_uri)
        if metadata:
            legend_template = metadata.get('legend_template', '')
            # Remove placeholder and clean up
            display_name = legend_template.replace('{analysis_method}', '').strip()
            display_name = display_name.replace('()', '').strip()
            if display_name:
                return display_name

        # Fallback: extract from URI
        if '#' in normalized_uri:
            local_name = normalized_uri.split('#')[-1]
        else:
            local_name = normalized_uri.split('/')[-1]

        # Convert camelCase/PascalCase to readable format
        # e.g., "TrueStress" -> "True Stress"
        result = []
        for char in local_name:
            if char.isupper() and result:
                result.append(' ')
            result.append(char)

        return ''.join(result)

    # Known dimensionless unit URIs (symbols should not be displayed)
    DIMENSIONLESS_URIS = {
        'http://qudt.org/vocab/unit/UNITLESS',
        'http://qudt.org/vocab/unit/NUM',
        'http://qudt.org/vocab/unit/FRACTION',
        'http://qudt.org/vocab/unit/PERCENT',
    }

    def _is_dimensionless_unit(self, unit_uri: str, symbol: str) -> bool:
        """
        Check if a unit is dimensionless (should not display symbol in axis label).

        Args:
            unit_uri: Normalized unit URI
            symbol: Resolved unit symbol

        Returns:
            True if the unit is dimensionless
        """
        # Check known dimensionless URIs
        if unit_uri in self.DIMENSIONLESS_URIS:
            return True

        # Check if URI ends with known dimensionless patterns
        uri_lower = unit_uri.lower()
        if any(pattern in uri_lower for pattern in ['unitless', 'dimensionless', '/num']):
            return True

        # Check symbol for known dimensionless patterns
        symbol_upper = symbol.upper() if symbol else ''
        if symbol_upper in ('', '1', 'UNITLESS', '-'):
            return True

        # Check for non-ASCII symbols that are likely dimensionless placeholders
        # (e.g., QUDT uses CJK '一' (one) for UNITLESS)
        if symbol and not symbol.isascii():
            return True

        return False

    def resolve_unit_symbol(self, unit_uri: str) -> str:
        """
        Resolve a QUDT unit URI to its display symbol.

        Args:
            unit_uri: Full URI or prefixed form (e.g., 'unit:MegaPA')

        Returns:
            Unit symbol string (e.g., 'MPa'), or empty string if dimensionless/not found
        """
        if not unit_uri:
            return ""

        normalized_uri = self._normalize_uri(unit_uri)

        # Quick check for known dimensionless units
        if normalized_uri in self.DIMENSIONLESS_URIS:
            return ""

        try:
            # Ensure QUDT is loaded
            if not self.qudt_manager._is_loaded:
                self.qudt_manager.load()

            unit = self.qudt_manager.get_unit_by_uri(normalized_uri)
            if unit:
                symbol = unit.symbol

                # Check if this is a dimensionless unit
                if self._is_dimensionless_unit(normalized_uri, symbol):
                    return ""

                return symbol

            # Fallback: extract from URI
            if '/' in normalized_uri:
                return normalized_uri.split('/')[-1]
            return ""

        except Exception as e:
            logger.error(f"Error resolving unit symbol for {unit_uri}: {e}")
            return ""

    def get_axis_label(self, series_type_uri: str, include_unit: bool = True) -> str:
        """
        Get the axis label for a SeriesType.

        Combines the display name with the unit symbol in parentheses.

        Args:
            series_type_uri: URI of the SeriesType individual (e.g., 'dyn:Stress')
            include_unit: Whether to append unit symbol in parentheses

        Returns:
            Formatted axis label (e.g., "Stress (MPa)", "Time (ms)", "Strain")

        Example:
            >>> resolver.get_axis_label('dyn:Stress')
            'Stress (MPa)'
            >>> resolver.get_axis_label('dyn:Strain')
            'Strain'
            >>> resolver.get_axis_label('dyn:Time', include_unit=False)
            'Time'
        """
        # Check cache
        cache_key = f"{series_type_uri}_{include_unit}"
        if cache_key in self._label_cache:
            return self._label_cache[cache_key]

        # Get display name
        display_name = self._extract_display_name(series_type_uri)

        if not include_unit:
            self._label_cache[cache_key] = display_name
            return display_name

        # Get unit symbol
        metadata = self._get_series_metadata(series_type_uri)
        if metadata:
            unit_uri = metadata.get('unit', '')
            unit_symbol = self.resolve_unit_symbol(unit_uri)

            # Don't add parentheses for dimensionless/unitless
            if unit_symbol and unit_symbol.upper() not in ('UNITLESS', '1', ''):
                label = f"{display_name} ({unit_symbol})"
                self._label_cache[cache_key] = label
                return label

        self._label_cache[cache_key] = display_name
        return display_name

    def get_axis_label_with_custom_unit(self, series_type_uri: str, unit_uri: str) -> str:
        """
        Get axis label with a specific unit (overriding the default).

        Useful when data has been converted to a different unit than the default.

        Args:
            series_type_uri: URI of the SeriesType individual
            unit_uri: URI of the unit to display

        Returns:
            Formatted axis label with the specified unit
        """
        display_name = self._extract_display_name(series_type_uri)
        unit_symbol = self.resolve_unit_symbol(unit_uri)

        if unit_symbol and unit_symbol.upper() not in ('UNITLESS', '1', ''):
            return f"{display_name} ({unit_symbol})"

        return display_name

    def get_legend_text(self, series_type_uri: str, analysis_method: str = None) -> str:
        """
        Get legend text for a data series.

        Uses the dyn:hasLegendTemplate property from the ontology, substituting
        the {analysis_method} placeholder if provided.

        Args:
            series_type_uri: URI of the SeriesType individual
            analysis_method: Analysis method string to substitute (e.g., '1-wave', '3-wave')

        Returns:
            Formatted legend text (e.g., "Engineering Stress (1-wave)")

        Example:
            >>> resolver.get_legend_text('dyn:Stress', '1-wave')
            'Engineering Stress (1-wave)'
            >>> resolver.get_legend_text('dyn:Time')
            'Time'
        """
        metadata = self._get_series_metadata(series_type_uri)

        if metadata:
            legend_template = metadata.get('legend_template', '')
            if legend_template:
                if analysis_method and '{analysis_method}' in legend_template:
                    return legend_template.format(analysis_method=analysis_method)
                elif '{analysis_method}' in legend_template:
                    # Remove placeholder if no method provided
                    return legend_template.replace(' ({analysis_method})', '').replace('({analysis_method})', '').strip()
                return legend_template

        # Fallback to display name
        return self._extract_display_name(series_type_uri)

    def get_quantity_kind(self, series_type_uri: str) -> Optional[str]:
        """
        Get the QUDT quantity kind URI for a SeriesType.

        Args:
            series_type_uri: URI of the SeriesType individual

        Returns:
            Full URI of the quantity kind, or None if not found
        """
        metadata = self._get_series_metadata(series_type_uri)
        if metadata:
            return metadata.get('quantity_kind')
        return None

    def get_default_unit(self, series_type_uri: str) -> Optional[str]:
        """
        Get the default QUDT unit URI for a SeriesType.

        Args:
            series_type_uri: URI of the SeriesType individual

        Returns:
            Full URI of the default unit, or None if not found
        """
        metadata = self._get_series_metadata(series_type_uri)
        if metadata:
            return metadata.get('unit')
        return None

    def clear_cache(self):
        """Clear the metadata and label caches."""
        self._metadata_cache.clear()
        self._label_cache.clear()
        logger.debug("SeriesMetadataResolver cache cleared")
