"""
DynaMat Platform - Data Series Widget
Backend storage container for processing results with URI mapping.
Not rendered to user - serves as a data container for plotting widgets.
"""

import logging
from typing import Dict, List, Optional, Any, Union
import numpy as np

from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import pyqtSignal

from rdflib import URIRef

logger = logging.getLogger(__name__)


class DataSeriesWidget(QWidget):
    """
    Backend storage container for processing results.

    Maps numpy arrays to URIRefs with unit/legend metadata. This widget is not
    rendered to the user - it serves as a data container that can be connected
    to plotting widgets via signals.

    Signals:
        dataChanged(str): Emitted when data is updated, passes URI as string
        dataCleared(): Emitted when all data is cleared
        seriesAdded(str): Emitted when a new series is added, passes URI as string
        seriesRemoved(str): Emitted when a series is removed, passes URI as string

    Container Structure:
        Each series is stored as a dict with keys:
            - array: np.ndarray of data values
            - unit: QUDT unit URI (e.g., 'http://qudt.org/vocab/unit/MegaPA')
            - ref_unit: Reference unit from ontology (for storage)
            - legend: Display legend text
            - metadata: Additional metadata dict

    Example:
        >>> container = DataSeriesWidget()
        >>> container.add_series(
        ...     uri=URIRef("dyn:Stress"),
        ...     array=stress_array,
        ...     unit="http://qudt.org/vocab/unit/MegaPA",
        ...     ref_unit="http://qudt.org/vocab/unit/MegaPA",
        ...     legend="Engineering Stress (1-wave)"
        ... )
        >>> container.get_series(URIRef("dyn:Stress"))
        {'array': array([...]), 'unit': '...', 'ref_unit': '...', 'legend': '...', 'metadata': {...}}
    """

    # Signals
    dataChanged = pyqtSignal(str)      # uri - when data updated
    dataCleared = pyqtSignal()         # when all data cleared
    seriesAdded = pyqtSignal(str)      # uri - when new series added
    seriesRemoved = pyqtSignal(str)    # uri - when series removed

    # DynaMat namespace for URI handling
    DYN_NS = "https://dynamat.utep.edu/ontology#"

    def __init__(self, parent=None):
        """
        Initialize the data series container.

        Args:
            parent: Parent widget (optional)
        """
        super().__init__(parent)

        # Internal container mapping URIs to data dicts
        self._container: Dict[str, Dict[str, Any]] = {}

        # Hide widget since it's not meant for display
        self.hide()

        logger.debug("DataSeriesWidget initialized")

    def _normalize_uri(self, uri: Union[URIRef, str]) -> str:
        """
        Normalize a URI to string form for consistent storage.

        Args:
            uri: URIRef or string URI

        Returns:
            String form of the URI
        """
        if isinstance(uri, URIRef):
            return str(uri)

        uri = str(uri).strip()

        # Handle prefixed forms
        if uri.startswith('dyn:'):
            return self.DYN_NS + uri[4:]

        return uri

    def add_series(
        self,
        uri: Union[URIRef, str],
        array: np.ndarray,
        unit: str = "",
        ref_unit: str = "",
        legend: str = "",
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Add or update a data series in the container.

        Args:
            uri: URIRef or string identifying the series (e.g., dyn:Stress)
            array: numpy array of data values
            unit: QUDT unit URI for the data (current display unit)
            ref_unit: Reference unit from ontology (storage unit)
            legend: Display legend text for plots
            metadata: Additional metadata dict (series_type, quantity_kind, etc.)

        Returns:
            True if series was added, False on error

        Emits:
            seriesAdded: If this is a new series
            dataChanged: If an existing series was updated
        """
        try:
            normalized_uri = self._normalize_uri(uri)

            is_new = normalized_uri not in self._container

            self._container[normalized_uri] = {
                'array': np.asarray(array),
                'unit': str(unit) if unit else "",
                'ref_unit': str(ref_unit) if ref_unit else str(unit) if unit else "",
                'legend': str(legend) if legend else "",
                'metadata': metadata or {}
            }

            if is_new:
                self.seriesAdded.emit(normalized_uri)
                logger.debug(f"Added new series: {normalized_uri} ({len(array)} points)")
            else:
                self.dataChanged.emit(normalized_uri)
                logger.debug(f"Updated series: {normalized_uri} ({len(array)} points)")

            return True

        except Exception as e:
            logger.error(f"Error adding series {uri}: {e}")
            return False

    def get_series(self, uri: Union[URIRef, str]) -> Optional[Dict[str, Any]]:
        """
        Get a data series by URI.

        Args:
            uri: URIRef or string identifying the series

        Returns:
            Dict with keys {array, unit, ref_unit, legend, metadata}, or None if not found
        """
        normalized_uri = self._normalize_uri(uri)
        return self._container.get(normalized_uri)

    def get_array(self, uri: Union[URIRef, str]) -> Optional[np.ndarray]:
        """
        Get just the numpy array for a series.

        Args:
            uri: URIRef or string identifying the series

        Returns:
            numpy array, or None if series not found
        """
        series = self.get_series(uri)
        if series:
            return series['array']
        return None

    def remove_series(self, uri: Union[URIRef, str]) -> bool:
        """
        Remove a data series from the container.

        Args:
            uri: URIRef or string identifying the series

        Returns:
            True if series was removed, False if not found

        Emits:
            seriesRemoved: When series is removed
        """
        normalized_uri = self._normalize_uri(uri)

        if normalized_uri in self._container:
            del self._container[normalized_uri]
            self.seriesRemoved.emit(normalized_uri)
            logger.debug(f"Removed series: {normalized_uri}")
            return True

        logger.warning(f"Series not found for removal: {normalized_uri}")
        return False

    def clear(self):
        """
        Clear all data series from the container.

        Emits:
            dataCleared: After all data is cleared
        """
        self._container.clear()
        self.dataCleared.emit()
        logger.debug("All series cleared from container")

    def get_all_uris(self) -> List[str]:
        """
        Get list of all URIs in the container.

        Returns:
            List of URI strings
        """
        return list(self._container.keys())

    def has_series(self, uri: Union[URIRef, str]) -> bool:
        """
        Check if a series exists in the container.

        Args:
            uri: URIRef or string identifying the series

        Returns:
            True if series exists
        """
        normalized_uri = self._normalize_uri(uri)
        return normalized_uri in self._container

    def get_series_count(self) -> int:
        """
        Get the number of series in the container.

        Returns:
            Number of series stored
        """
        return len(self._container)

    def capture_from_results(
        self,
        results: Dict[str, np.ndarray],
        series_metadata: Dict[str, Dict[str, Any]]
    ) -> int:
        """
        Bulk capture data from a results dictionary using series metadata.

        Maps column names in results to URIs using the series_metadata lookup.
        This is the primary way to populate the container from SHPB analysis.

        Args:
            results: Dict mapping column names (e.g., 'stress_1w') to numpy arrays
            series_metadata: SERIES_METADATA dict with column->metadata mapping

        Returns:
            Number of series successfully added

        Example:
            >>> results = calculator.calculate(incident, transmitted, reflected, time)
            >>> count = container.capture_from_results(results, SERIES_METADATA)
            >>> print(f"Captured {count} series")
        """
        added_count = 0

        for column_name, array in results.items():
            if column_name not in series_metadata:
                logger.debug(f"Column '{column_name}' not in series_metadata, skipping")
                continue

            meta = series_metadata[column_name]

            # Get the series type URI
            series_type = meta.get('series_type', '')
            if not series_type:
                logger.warning(f"No series_type for column '{column_name}', skipping")
                continue

            # Build metadata dict
            entry_metadata = {
                'series_type': series_type,
                'quantity_kind': meta.get('quantity_kind', ''),
                'column_name': column_name,
                'analysis_method': meta.get('analysis_method', ''),
                'class_uri': meta.get('class_uri', ''),
            }

            success = self.add_series(
                uri=series_type,
                array=array,
                unit=meta.get('unit', ''),
                ref_unit=meta.get('unit', ''),
                legend=meta.get('legend_name', column_name),
                metadata=entry_metadata
            )

            if success:
                added_count += 1

        logger.info(f"Captured {added_count} series from results")
        return added_count

    def capture_from_results_with_suffix(
        self,
        results: Dict[str, np.ndarray],
        series_metadata: Dict[str, Dict[str, Any]],
        uri_suffix: str = ""
    ) -> int:
        """
        Capture results with a suffix appended to URIs (for multiple datasets).

        Useful when storing results from multiple tests or analysis methods
        that use the same series types.

        Args:
            results: Dict mapping column names to numpy arrays
            series_metadata: SERIES_METADATA dict
            uri_suffix: Suffix to append to each URI (e.g., '_test1', '_1w')

        Returns:
            Number of series successfully added
        """
        added_count = 0

        for column_name, array in results.items():
            if column_name not in series_metadata:
                continue

            meta = series_metadata[column_name]
            series_type = meta.get('series_type', '')
            if not series_type:
                continue

            # Append suffix to URI
            suffixed_uri = f"{series_type}{uri_suffix}"

            entry_metadata = {
                'series_type': series_type,
                'quantity_kind': meta.get('quantity_kind', ''),
                'column_name': column_name,
                'analysis_method': meta.get('analysis_method', ''),
                'class_uri': meta.get('class_uri', ''),
                'original_uri': series_type,
            }

            success = self.add_series(
                uri=suffixed_uri,
                array=array,
                unit=meta.get('unit', ''),
                ref_unit=meta.get('unit', ''),
                legend=meta.get('legend_name', column_name),
                metadata=entry_metadata
            )

            if success:
                added_count += 1

        logger.info(f"Captured {added_count} series with suffix '{uri_suffix}'")
        return added_count

    def getData(self) -> Dict[str, Any]:
        """
        Get all data for form compatibility.

        Returns a dict suitable for serialization/storage.

        Returns:
            Dict with 'series' key containing list of series data
        """
        series_list = []
        for uri, data in self._container.items():
            series_list.append({
                'uri': uri,
                'array': data['array'].tolist(),  # Convert to list for JSON
                'unit': data['unit'],
                'ref_unit': data['ref_unit'],
                'legend': data['legend'],
                'metadata': data['metadata']
            })

        return {'series': series_list}

    def setData(self, data: Dict[str, Any]):
        """
        Restore data from a saved state for form compatibility.

        Args:
            data: Dict with 'series' key containing list of series data
        """
        self.clear()

        series_list = data.get('series', [])
        for series_data in series_list:
            self.add_series(
                uri=series_data['uri'],
                array=np.array(series_data['array']),
                unit=series_data.get('unit', ''),
                ref_unit=series_data.get('ref_unit', ''),
                legend=series_data.get('legend', ''),
                metadata=series_data.get('metadata', {})
            )

        logger.debug(f"Restored {len(series_list)} series from data")

    def get_series_by_type(self, series_type_uri: str) -> List[Dict[str, Any]]:
        """
        Get all series matching a specific SeriesType.

        Useful when multiple series share the same type (e.g., stress from different methods).

        Args:
            series_type_uri: SeriesType URI to match

        Returns:
            List of series data dicts that match the type
        """
        normalized_type = self._normalize_uri(series_type_uri)
        matches = []

        for uri, data in self._container.items():
            meta = data.get('metadata', {})
            if self._normalize_uri(meta.get('series_type', '')) == normalized_type:
                matches.append({
                    'uri': uri,
                    **data
                })

        return matches

    def get_series_by_analysis_method(self, method: str) -> Dict[str, Dict[str, Any]]:
        """
        Get all series for a specific analysis method.

        Args:
            method: Analysis method string (e.g., '1-wave', '3-wave')

        Returns:
            Dict mapping URIs to series data for matching series
        """
        matches = {}

        for uri, data in self._container.items():
            meta = data.get('metadata', {})
            if meta.get('analysis_method') == method:
                matches[uri] = data

        return matches
