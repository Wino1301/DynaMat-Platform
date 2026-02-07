"""
SHPB Data Series Configuration and Builder

Contains the SERIES_METADATA lookup table and DataSeriesBuilder class for creating
DataSeries instances from DataFrames. Extracted from SHPBTestMetadata for
single responsibility and reusability.

SERIES_METADATA is now loaded from the ontology when available, with a fallback
to the hardcoded dictionary for robustness. The proxy class ensures backwards
compatibility with existing code.
"""

import logging
from typing import Dict, Any, List, Tuple
import pandas as pd
import numpy as np

from .rdf_helpers import apply_type_conversion_to_dict

logger = logging.getLogger(__name__)


# ==================== SHPB DERIVATION MAPPING ====================
# Defines which windowed signals are used to compute each processed series
# for each analysis method. Based on Kolsky bar equations (see stress_strain.py).
#
# 1-Wave Analysis:
#   - Strain quantities derive from REFLECTED pulse (not incident!)
#   - Stress quantities derive from TRANSMITTED pulse
#   - True stress uses both transmitted and reflected
#
# 3-Wave Analysis:
#   - All quantities use all three signals (incident, reflected, transmitted)
#   - Bar displacement/force use incident + reflected only

SHPB_DERIVATION_MAP = {
    '1-wave': {
        'bar_displacement': ['transmitted'],
        'bar_force': ['transmitted'],
        'strain_rate': ['reflected'],
        'strain': ['reflected'],
        'stress': ['transmitted'],
        'true_strain_rate': ['reflected'],
        'true_strain': ['reflected'],
        'true_stress': ['transmitted', 'reflected'],
    },
    '3-wave': {
        'bar_displacement': ['incident', 'reflected'],
        'bar_force': ['incident', 'reflected'],
        'strain_rate': ['incident', 'reflected', 'transmitted'],
        'strain': ['incident', 'reflected', 'transmitted'],
        'stress': ['incident', 'reflected'],
        'true_strain_rate': ['incident', 'reflected', 'transmitted'],
        'true_strain': ['incident', 'reflected', 'transmitted'],
        'true_stress': ['incident', 'reflected', 'transmitted'],
    }
}


# ==================== FALLBACK SERIES METADATA ====================
# Hardcoded fallback used when ontology is unavailable
# Maps column names to their RDF metadata (aligned with ontology SeriesType pattern):
#   - unit: Full QUDT unit URI (matches dyn:hasUnit annotation on SeriesType individuals)
#   - quantity_kind: Full QUDT quantity kind URI (matches qudt:hasQuantityKind annotation)
# NOTE: Derivation chains (derived_from) are NOT included here - they are handled
# by SHPB_DERIVATION_MAP since derivations depend on the analysis method.
_FALLBACK_SERIES_METADATA = {
    # ===== RAW SIGNALS =====
    'time': {
        'series_type': 'https://dynamat.utep.edu/ontology#Time',
        'quantity_kind': 'http://qudt.org/vocab/quantitykind/Time',
        'unit': 'http://qudt.org/vocab/unit/MilliSEC',
        'legend_name': 'Time',
        'class_uri': 'https://dynamat.utep.edu/ontology#RawSignal'
    },
    'incident': {
        'series_type': 'https://dynamat.utep.edu/ontology#IncidentPulse',
        'quantity_kind': 'http://qudt.org/vocab/quantitykind/Voltage',
        'unit': 'http://qudt.org/vocab/unit/V',
        'legend_name': 'Incident Pulse',
        'class_uri': 'https://dynamat.utep.edu/ontology#RawSignal',
        'requires_gauge': True
    },
    'transmitted': {
        'series_type': 'https://dynamat.utep.edu/ontology#TransmittedPulse',
        'quantity_kind': 'http://qudt.org/vocab/quantitykind/Voltage',
        'unit': 'http://qudt.org/vocab/unit/V',
        'legend_name': 'Transmitted Pulse',
        'class_uri': 'https://dynamat.utep.edu/ontology#RawSignal',
        'requires_gauge': True
    },

    # ===== 1-WAVE PROCESSED DATA =====
    'bar_displacement_1w': {
        'series_type': 'https://dynamat.utep.edu/ontology#BarDisplacement',
        'quantity_kind': 'http://qudt.org/vocab/quantitykind/Length',
        'unit': 'http://qudt.org/vocab/unit/MilliM',
        'legend_name': 'Bar Displacement (1-wave)',
        'analysis_method': '1-wave',
        'class_uri': 'https://dynamat.utep.edu/ontology#ProcessedData'
    },
    'bar_force_1w': {
        'series_type': 'https://dynamat.utep.edu/ontology#BarForce',
        'quantity_kind': 'http://qudt.org/vocab/quantitykind/Force',
        'unit': 'http://qudt.org/vocab/unit/N',
        'legend_name': 'Bar Force (1-wave)',
        'analysis_method': '1-wave',
        'class_uri': 'https://dynamat.utep.edu/ontology#ProcessedData'
    },
    'strain_rate_1w': {
        'series_type': 'https://dynamat.utep.edu/ontology#StrainRate',
        'quantity_kind': 'http://qudt.org/vocab/quantitykind/StrainRate',
        'unit': 'http://qudt.org/vocab/unit/PER-SEC',
        'legend_name': 'Strain Rate (1-wave)',
        'analysis_method': '1-wave',
        'class_uri': 'https://dynamat.utep.edu/ontology#ProcessedData'
    },
    'strain_1w': {
        'series_type': 'https://dynamat.utep.edu/ontology#Strain',
        'quantity_kind': 'http://qudt.org/vocab/quantitykind/Dimensionless',
        'unit': 'http://qudt.org/vocab/unit/UNITLESS',
        'legend_name': 'Engineering Strain (1-wave)',
        'analysis_method': '1-wave',
        'class_uri': 'https://dynamat.utep.edu/ontology#ProcessedData'
    },
    'stress_1w': {
        'series_type': 'https://dynamat.utep.edu/ontology#Stress',
        'quantity_kind': 'http://qudt.org/vocab/quantitykind/Stress',
        'unit': 'http://qudt.org/vocab/unit/MegaPA',
        'legend_name': 'Engineering Stress (1-wave)',
        'analysis_method': '1-wave',
        'class_uri': 'https://dynamat.utep.edu/ontology#ProcessedData'
    },
    'true_strain_rate_1w': {
        'series_type': 'https://dynamat.utep.edu/ontology#TrueStrainRate',
        'quantity_kind': 'http://qudt.org/vocab/quantitykind/StrainRate',
        'unit': 'http://qudt.org/vocab/unit/PER-SEC',
        'legend_name': 'True Strain Rate (1-wave)',
        'analysis_method': '1-wave',
        'class_uri': 'https://dynamat.utep.edu/ontology#ProcessedData'
    },
    'true_strain_1w': {
        'series_type': 'https://dynamat.utep.edu/ontology#TrueStrain',
        'quantity_kind': 'http://qudt.org/vocab/quantitykind/Dimensionless',
        'unit': 'http://qudt.org/vocab/unit/UNITLESS',
        'legend_name': 'True Strain (1-wave)',
        'analysis_method': '1-wave',
        'class_uri': 'https://dynamat.utep.edu/ontology#ProcessedData'
    },
    'true_stress_1w': {
        'series_type': 'https://dynamat.utep.edu/ontology#TrueStress',
        'quantity_kind': 'http://qudt.org/vocab/quantitykind/Stress',
        'unit': 'http://qudt.org/vocab/unit/MegaPA',
        'legend_name': 'True Stress (1-wave)',
        'analysis_method': '1-wave',
        'class_uri': 'https://dynamat.utep.edu/ontology#ProcessedData'
    },

    # ===== 3-WAVE PROCESSED DATA =====
    'bar_displacement_3w': {
        'series_type': 'https://dynamat.utep.edu/ontology#BarDisplacement',
        'quantity_kind': 'http://qudt.org/vocab/quantitykind/Length',
        'unit': 'http://qudt.org/vocab/unit/MilliM',
        'legend_name': 'Bar Displacement (3-wave)',
        'analysis_method': '3-wave',
        'class_uri': 'https://dynamat.utep.edu/ontology#ProcessedData'
    },
    'bar_force_3w': {
        'series_type': 'https://dynamat.utep.edu/ontology#BarForce',
        'quantity_kind': 'http://qudt.org/vocab/quantitykind/Force',
        'unit': 'http://qudt.org/vocab/unit/N',
        'legend_name': 'Bar Force (3-wave)',
        'analysis_method': '3-wave',
        'class_uri': 'https://dynamat.utep.edu/ontology#ProcessedData'
    },
    'strain_rate_3w': {
        'series_type': 'https://dynamat.utep.edu/ontology#StrainRate',
        'quantity_kind': 'http://qudt.org/vocab/quantitykind/StrainRate',
        'unit': 'http://qudt.org/vocab/unit/PER-SEC',
        'legend_name': 'Strain Rate (3-wave)',
        'analysis_method': '3-wave',
        'class_uri': 'https://dynamat.utep.edu/ontology#ProcessedData'
    },
    'strain_3w': {
        'series_type': 'https://dynamat.utep.edu/ontology#Strain',
        'quantity_kind': 'http://qudt.org/vocab/quantitykind/Dimensionless',
        'unit': 'http://qudt.org/vocab/unit/UNITLESS',
        'legend_name': 'Engineering Strain (3-wave)',
        'analysis_method': '3-wave',
        'class_uri': 'https://dynamat.utep.edu/ontology#ProcessedData'
    },
    'stress_3w': {
        'series_type': 'https://dynamat.utep.edu/ontology#Stress',
        'quantity_kind': 'http://qudt.org/vocab/quantitykind/Stress',
        'unit': 'http://qudt.org/vocab/unit/MegaPA',
        'legend_name': 'Engineering Stress (3-wave)',
        'analysis_method': '3-wave',
        'class_uri': 'https://dynamat.utep.edu/ontology#ProcessedData'
    },
    'true_strain_rate_3w': {
        'series_type': 'https://dynamat.utep.edu/ontology#TrueStrainRate',
        'quantity_kind': 'http://qudt.org/vocab/quantitykind/StrainRate',
        'unit': 'http://qudt.org/vocab/unit/PER-SEC',
        'legend_name': 'True Strain Rate (3-wave)',
        'analysis_method': '3-wave',
        'class_uri': 'https://dynamat.utep.edu/ontology#ProcessedData'
    },
    'true_strain_3w': {
        'series_type': 'https://dynamat.utep.edu/ontology#TrueStrain',
        'quantity_kind': 'http://qudt.org/vocab/quantitykind/Dimensionless',
        'unit': 'http://qudt.org/vocab/unit/UNITLESS',
        'legend_name': 'True Strain (3-wave)',
        'analysis_method': '3-wave',
        'class_uri': 'https://dynamat.utep.edu/ontology#ProcessedData'
    },
    'true_stress_3w': {
        'series_type': 'https://dynamat.utep.edu/ontology#TrueStress',
        'quantity_kind': 'http://qudt.org/vocab/quantitykind/Stress',
        'unit': 'http://qudt.org/vocab/unit/MegaPA',
        'legend_name': 'True Stress (3-wave)',
        'analysis_method': '3-wave',
        'class_uri': 'https://dynamat.utep.edu/ontology#ProcessedData'
    }
}


# ==================== FALLBACK WINDOWED SERIES METADATA ====================
# Hardcoded fallback used when ontology is unavailable for windowed series
_FALLBACK_WINDOWED_METADATA = {
    'time_windowed': {
        'series_type': 'https://dynamat.utep.edu/ontology#WindowedTime',
        'quantity_kind': 'http://qudt.org/vocab/quantitykind/Time',
        'unit': 'http://qudt.org/vocab/unit/MilliSEC',
        'legend_name': 'Time (Windowed)',
        'raw_source': 'time'
    },
    'incident_windowed': {
        'series_type': 'https://dynamat.utep.edu/ontology#WindowedIncidentPulse',
        'quantity_kind': 'http://qudt.org/vocab/quantitykind/Dimensionless',
        'unit': 'http://qudt.org/vocab/unit/UNITLESS',
        'legend_name': 'Incident Pulse (Windowed)',
        'raw_source': 'incident',
        'requires_gauge': True
    },
    'transmitted_windowed': {
        'series_type': 'https://dynamat.utep.edu/ontology#WindowedTransmittedPulse',
        'quantity_kind': 'http://qudt.org/vocab/quantitykind/Dimensionless',
        'unit': 'http://qudt.org/vocab/unit/UNITLESS',
        'legend_name': 'Transmitted Pulse (Windowed)',
        'raw_source': 'transmitted',
        'requires_gauge': True
    },
    'reflected_windowed': {
        'series_type': 'https://dynamat.utep.edu/ontology#WindowedReflectedPulse',
        'quantity_kind': 'http://qudt.org/vocab/quantitykind/Dimensionless',
        'unit': 'http://qudt.org/vocab/unit/UNITLESS',
        'legend_name': 'Reflected Pulse (Windowed)',
        'raw_source': 'incident',  # Reflected pulse is on incident bar
        'requires_gauge': True
    }
}


# ==================== LAZY-LOADED ONTOLOGY METADATA ====================
_series_metadata_cache = None
_windowed_metadata_cache = None


def get_series_metadata() -> Dict[str, Dict[str, Any]]:
    """
    Load series metadata from ontology, with fallback to hardcoded dict.

    Returns:
        Dict mapping column names to their RDF metadata for DataSeries creation.
        Tries ontology first, falls back to _FALLBACK_SERIES_METADATA.
    """
    global _series_metadata_cache

    if _series_metadata_cache is None:
        try:
            from dynamat.ontology import OntologyManager
            manager = OntologyManager()
            _series_metadata_cache = manager.domain_queries.get_series_metadata_for_shpb()
            logger.info(f"Loaded {len(_series_metadata_cache)} series metadata entries from ontology")
        except Exception as e:
            logger.warning(f"Ontology load failed: {e}, using fallback SERIES_METADATA")
            _series_metadata_cache = _FALLBACK_SERIES_METADATA

    return _series_metadata_cache


def clear_series_metadata_cache():
    """Clear the cached metadata, forcing reload on next access."""
    global _series_metadata_cache, _windowed_metadata_cache
    _series_metadata_cache = None
    _windowed_metadata_cache = None
    logger.debug("Cleared series metadata cache")


def get_windowed_series_metadata() -> Dict[str, Dict[str, Any]]:
    """
    Load windowed series metadata from ontology, with fallback to hardcoded dict.

    Returns:
        Dict mapping windowed column names (e.g., 'incident_windowed') to metadata:
            - series_type: dyn:SeriesType URI
            - quantity_kind: QUDT quantity kind
            - unit: QUDT unit
            - legend_name: Display legend
            - raw_source: Source raw column name
            - requires_gauge: Whether strain gauge is required
    """
    global _windowed_metadata_cache

    if _windowed_metadata_cache is None:
        try:
            from dynamat.ontology import OntologyManager
            manager = OntologyManager()
            _windowed_metadata_cache = manager.domain_queries.get_windowed_series_metadata()
            logger.info(f"Loaded {len(_windowed_metadata_cache)} windowed metadata entries from ontology")
        except Exception as e:
            logger.warning(f"Ontology load failed for windowed metadata: {e}, using fallback")
            _windowed_metadata_cache = _FALLBACK_WINDOWED_METADATA

    return _windowed_metadata_cache


class _SeriesMetadataProxy:
    """
    Proxy class for backwards-compatible SERIES_METADATA access.

    Provides dict-like interface that loads from ontology on first access.
    Existing code using SERIES_METADATA['stress_1w'] continues to work.
    """

    def __getitem__(self, key: str) -> Dict[str, Any]:
        return get_series_metadata()[key]

    def __contains__(self, key: str) -> bool:
        return key in get_series_metadata()

    def __len__(self) -> int:
        return len(get_series_metadata())

    def __iter__(self):
        return iter(get_series_metadata())

    def keys(self):
        return get_series_metadata().keys()

    def values(self):
        return get_series_metadata().values()

    def items(self):
        return get_series_metadata().items()

    def get(self, key: str, default=None):
        return get_series_metadata().get(key, default)


# Backwards-compatible module-level export
SERIES_METADATA = _SeriesMetadataProxy()


class DataSeriesBuilder:
    """
    Builds DataSeries instances from DataFrames using SERIES_METADATA.

    Handles creation of RawSignal, ProcessedData, and windowed DataSeries
    instances with proper RDF metadata, units, and derivation chains.

    Args:
        test_metadata: SHPBTestMetadata instance providing test ID and equipment URIs

    Example:
        >>> builder = DataSeriesBuilder(test_metadata)
        >>> raw_series = builder.prepare_raw_data_series(raw_df, file_uri, gauge_params)
        >>> windowed_series = builder.prepare_windowed_data_series(raw_uris, length, file_uri)
        >>> processed_series = builder.prepare_processed_data_series(results, file_uri, windowed_uris)
    """

    def __init__(self, test_metadata):
        """
        Initialize the builder with test metadata.

        Args:
            test_metadata: SHPBTestMetadata instance with test_id, equipment URIs, etc.
        """
        self.metadata = test_metadata

    def prepare_raw_data_series(
        self,
        raw_df: pd.DataFrame,
        file_uri: str,
        gauge_params: Dict[str, str]
    ) -> List[Tuple[Dict[str, Any], str, str]]:
        """
        Convert raw DataFrame columns to DataSeries instances.

        Creates 3 RawSignal instances (time, incident, transmitted) with full metadata.

        Args:
            raw_df: DataFrame with columns ['time', 'incident', 'transmitted']
            file_uri: URI of the AnalysisFile instance (e.g., 'dyn:TEST_001_raw_csv')
            gauge_params: Dict mapping column names to equipment URIs

        Returns:
            List of (form_data, class_uri, instance_id) tuples for InstanceWriter

        See Also:
            prepare_processed_data_series: For processed stress-strain data
            prepare_windowed_data_series: For intermediate windowed signals
        """
        instances = []
        data_point_count = len(raw_df)
        series_meta_dict = get_series_metadata()

        for column_name in ['time', 'incident', 'transmitted']:
            # Get metadata from lookup table
            series_meta = series_meta_dict[column_name]

            # Build form data
            form_data = {
                # Explicit type declaration for SHACL validation (parent class)
                'rdf:type': 'dyn:DataSeries',

                # File reference
                'dyn:hasDataFile': file_uri,
                'dyn:hasColumnName': column_name,
                'dyn:hasColumnIndex': raw_df.columns.get_loc(column_name),
                'dyn:hasLegendName': series_meta['legend_name'],

                # Series metadata
                'dyn:hasSeriesType': series_meta['series_type'],
                'dyn:hasDataPointCount': data_point_count,
            }

            # Add unit and quantity kind if specified
            if series_meta['unit']:
                form_data['dyn:hasSeriesUnit'] = series_meta['unit']
            if series_meta['quantity_kind']:
                form_data['dyn:hasQuantityKind'] = series_meta['quantity_kind']

            # Add equipment reference for signals that require it
            if series_meta.get('requires_gauge', False) and column_name in gauge_params:
                form_data['dyn:measuredBy'] = gauge_params[column_name]

            # Add sampling interval (series-level metadata)
            if self.metadata.sampling_interval is not None:
                form_data['dyn:hasSamplingInterval'] = self.metadata.sampling_interval

            # Add pulse detection params references
            if column_name == 'incident':
                # Incident bar has TWO detection params: incident pulse and reflected pulse
                detection_params = []
                if self.metadata.incident_detection_params_uri:
                    detection_params.append(self.metadata.incident_detection_params_uri)
                if self.metadata.reflected_detection_params_uri:
                    detection_params.append(self.metadata.reflected_detection_params_uri)
                if detection_params:
                    form_data['dyn:hasPulseDetectionParams'] = detection_params
            elif column_name == 'transmitted':
                # Transmitted bar has ONE detection params: transmitted pulse
                if self.metadata.transmitted_detection_params_uri:
                    form_data['dyn:hasPulseDetectionParams'] = self.metadata.transmitted_detection_params_uri

            # Apply type conversion to ensure proper XSD datatypes
            form_data = apply_type_conversion_to_dict(form_data)

            # Create instance tuple
            instance_id = f"{self.metadata.test_id.replace('-', '_')}_{column_name}"
            instances.append((form_data, series_meta['class_uri'], instance_id))

            logger.debug(f"Prepared {column_name} DataSeries: {instance_id}")

        logger.info(f"Prepared {len(instances)} raw DataSeries instances")
        return instances

    def prepare_processed_data_series(
        self,
        results: Dict[str, np.ndarray],
        file_uri: str,
        windowed_series_uris: Dict[str, str]
    ) -> List[Tuple[Dict[str, Any], str, str]]:
        """
        Convert processed results dictionary to DataSeries instances.

        Creates ProcessedData instances with analysis method, derivation chain,
        QUDT units, and processing method. Similar to prepare_raw_data_series
        but for calculated stress-strain curves.

        Args:
            results: Dictionary from StressStrainCalculator.calculate()
            file_uri: URI of processed data AnalysisFile
            windowed_series_uris: URIs of windowed DataSeries for derivation chain

        Returns:
            List of (form_data, class_uri, instance_id) tuples

        See Also:
            prepare_raw_data_series: Full parameter documentation
        """
        instances = []
        series_meta_dict = get_series_metadata()

        # Create temporary DataFrame to get column indices
        processed_df = pd.DataFrame(results)
        data_point_count = len(processed_df)

        for column_name in results.keys():
            # Skip columns that don't need DataSeries instances
            if column_name == 'time':
                logger.debug("Skipping 'time' column - using windowed time series instead")
                continue
            if column_name in ['incident', 'transmitted', 'reflected']:
                logger.debug(f"Skipping '{column_name}' pulse window - already represented by windowed series")
                continue
            if column_name not in series_meta_dict:
                logger.warning(f"Column '{column_name}' not in SERIES_METADATA, skipping")
                continue

            # Get metadata from lookup table
            series_meta = series_meta_dict[column_name]

            # Build form data
            form_data = {
                'rdf:type': 'dyn:DataSeries',
                'dyn:hasDataFile': file_uri,
                'dyn:hasColumnName': column_name,
                'dyn:hasColumnIndex': processed_df.columns.get_loc(column_name),
                'dyn:hasLegendName': series_meta['legend_name'],
                'dyn:hasSeriesType': series_meta['series_type'],
                'dyn:hasDataPointCount': data_point_count,
                'dyn:hasProcessingMethod': 'SHPB stress-strain calculation',
                'dyn:hasFilterApplied': False,
            }

            # Add unit and quantity kind if specified
            if series_meta['unit']:
                form_data['dyn:hasSeriesUnit'] = series_meta['unit']
            if series_meta['quantity_kind']:
                form_data['dyn:hasQuantityKind'] = series_meta['quantity_kind']

            # Determine analysis method and base series name from column name suffix
            # e.g., 'strain_1w' -> method='1-wave', base_name='strain'
            if column_name.endswith('_1w'):
                method = '1-wave'
                base_name = column_name[:-3]  # Remove '_1w' suffix
            elif column_name.endswith('_3w'):
                method = '3-wave'
                base_name = column_name[:-3]  # Remove '_3w' suffix
            else:
                method = None
                base_name = column_name

            # Add analysis method for processed data
            if method:
                form_data['dyn:hasAnalysisMethod'] = method
            elif 'analysis_method' in series_meta:
                form_data['dyn:hasAnalysisMethod'] = series_meta['analysis_method']

            # Add derivation chain using SHPB_DERIVATION_MAP (physics-based mapping)
            # This defines which windowed signals are used to compute each processed series
            derivation_sources = SHPB_DERIVATION_MAP.get(method, {}).get(base_name, []) if method else []

            if derivation_sources:
                derived_sources = []
                for source in derivation_sources:
                    windowed_key = f'{source}_windowed'
                    if windowed_key in windowed_series_uris:
                        derived_sources.append(windowed_series_uris[windowed_key])

                if len(derived_sources) == 1:
                    form_data['dyn:derivedFrom'] = derived_sources[0]
                elif len(derived_sources) > 1:
                    form_data['dyn:derivedFrom'] = derived_sources

            # Apply type conversion
            form_data = apply_type_conversion_to_dict(form_data)

            # Create instance tuple
            instance_id = f"{self.metadata.test_id.replace('-', '_')}_{column_name}"
            instances.append((form_data, series_meta['class_uri'], instance_id))

            logger.debug(f"Prepared {column_name} DataSeries: {instance_id}")

        logger.info(f"Prepared {len(instances)} processed DataSeries instances")
        return instances

    def prepare_windowed_data_series(
        self,
        raw_series_uris: Dict[str, str],
        window_length: int,
        file_uri: str
    ) -> List[Tuple[Dict[str, Any], str, str]]:
        """
        Create DataSeries instances for windowed/segmented signals.

        Creates 4 windowed DataSeries representing intermediate signals between
        raw oscilloscope data and processed stress-strain curves. Similar to
        prepare_raw_data_series but for extracted pulse windows.

        Args:
            raw_series_uris: URIs of raw DataSeries for derivation
            window_length: Number of data points in windowed signals
            file_uri: URI of windowed data file

        Returns:
            List of (form_data, class_uri, instance_id) tuples for windowed series

        See Also:
            prepare_raw_data_series: Full parameter documentation
        """
        instances = []

        # Load windowed series metadata from ontology with fallback
        windowed_metadata = get_windowed_series_metadata()

        # Map series names to their strain gauge URIs (runtime values from test metadata)
        gauge_uri_mapping = {
            'incident_windowed': self.metadata.incident_strain_gauge_uri,
            'transmitted_windowed': self.metadata.transmission_strain_gauge_uri,
            'reflected_windowed': self.metadata.incident_strain_gauge_uri,  # Reflected is on incident bar
        }

        for series_name, series_meta in windowed_metadata.items():
            # Determine raw source for derivation chain
            raw_source = series_meta.get('raw_source')
            if not raw_source:
                logger.warning(f"No raw_source for windowed series {series_name}, skipping")
                continue

            # Skip if raw source not available in this test
            if raw_source not in raw_series_uris:
                logger.debug(f"Raw source {raw_source} not in raw_series_uris, skipping {series_name}")
                continue

            # Build form data
            form_data = {
                'rdf:type': 'dyn:DataSeries',
                'dyn:hasDataFile': file_uri,
                'dyn:hasLegendName': series_meta['legend_name'],
                'dyn:hasSeriesType': series_meta['series_type'],
                'dyn:hasDataPointCount': window_length,
                'dyn:hasProcessingMethod': 'Pulse windowing and segmentation',
                'dyn:hasFilterApplied': False,
                'dyn:derivedFrom': raw_series_uris[raw_source],
            }

            # Add unit and quantity kind if specified
            if series_meta.get('unit'):
                form_data['dyn:hasSeriesUnit'] = series_meta['unit']
            if series_meta.get('quantity_kind'):
                form_data['dyn:hasQuantityKind'] = series_meta['quantity_kind']

            # Add gauge reference for signal series (using runtime mapping)
            gauge_uri = gauge_uri_mapping.get(series_name)
            if gauge_uri and series_meta.get('requires_gauge'):
                form_data['dyn:measuredBy'] = gauge_uri

            # Apply type conversion
            form_data = apply_type_conversion_to_dict(form_data)

            # Create instance tuple
            instance_id = f"{self.metadata.test_id.replace('-', '_')}_{series_name}"
            instances.append((form_data, 'dyn:ProcessedData', instance_id))

            logger.debug(f"Prepared windowed DataSeries: {instance_id}")

        logger.info(f"Prepared {len(instances)} windowed DataSeries instances")
        return instances
