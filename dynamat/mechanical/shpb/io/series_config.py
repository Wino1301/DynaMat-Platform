"""
SHPB Data Series Configuration and Builder

Contains the SERIES_METADATA lookup table and DataSeriesBuilder class for creating
DataSeries instances from DataFrames. Extracted from SHPBTestMetadata for
single responsibility and reusability.
"""

import logging
from typing import Dict, Any, List, Tuple
import pandas as pd
import numpy as np

from .rdf_helpers import apply_type_conversion_to_dict

logger = logging.getLogger(__name__)


# ==================== SERIES METADATA LOOKUP TABLE ====================
# Maps column names to their RDF metadata for DataSeries creation
SERIES_METADATA = {
    # ===== RAW SIGNALS =====
    'time': {
        'series_type': 'dyn:Time',
        'quantity_kind': 'qkdv:Time',
        'unit': 'unit:MilliSEC',
        'legend_name': 'Time',
        'class_uri': 'dyn:RawSignal'
    },
    'incident': {
        'series_type': 'dyn:IncidentPulse',
        'quantity_kind': 'qkdv:Voltage',
        'unit': 'unit:V',
        'legend_name': 'Incident Pulse',
        'class_uri': 'dyn:RawSignal',
        'requires_gauge': True
    },
    'transmitted': {
        'series_type': 'dyn:TransmittedPulse',
        'quantity_kind': 'qkdv:Voltage',
        'unit': 'unit:V',
        'legend_name': 'Transmitted Pulse',
        'class_uri': 'dyn:RawSignal',
        'requires_gauge': True
    },

    # ===== 1-WAVE PROCESSED DATA =====
    'bar_displacement_1w': {
        'series_type': 'dyn:BarDisplacement',
        'quantity_kind': 'qkdv:Length',
        'unit': 'unit:MilliM',
        'legend_name': 'Bar Displacement (1-wave)',
        'analysis_method': '1-wave',
        'class_uri': 'dyn:ProcessedData',
        'derived_from': ['transmitted']
    },
    'bar_force_1w': {
        'series_type': 'dyn:BarForce',
        'quantity_kind': 'qkdv:Force',
        'unit': 'unit:N',
        'legend_name': 'Bar Force (1-wave)',
        'analysis_method': '1-wave',
        'class_uri': 'dyn:ProcessedData',
        'derived_from': ['transmitted']
    },
    'strain_rate_1w': {
        'series_type': 'dyn:StrainRate',
        'quantity_kind': 'qkdv:StrainRate',
        'unit': 'unit:PER-SEC',
        'legend_name': 'Strain Rate (1-wave)',
        'analysis_method': '1-wave',
        'class_uri': 'dyn:ProcessedData',
        'derived_from': ['incident']
    },
    'strain_1w': {
        'series_type': 'dyn:Strain',
        'quantity_kind': 'qkdv:Dimensionless',
        'unit': 'unit:UNITLESS',
        'legend_name': 'Engineering Strain (1-wave)',
        'analysis_method': '1-wave',
        'class_uri': 'dyn:ProcessedData',
        'derived_from': ['incident']
    },
    'stress_1w': {
        'series_type': 'dyn:Stress',
        'quantity_kind': 'qkdv:Stress',
        'unit': 'unit:MegaPA',
        'legend_name': 'Engineering Stress (1-wave)',
        'analysis_method': '1-wave',
        'class_uri': 'dyn:ProcessedData',
        'derived_from': ['transmitted']
    },
    'true_strain_rate_1w': {
        'series_type': 'dyn:TrueStrainRate',
        'quantity_kind': 'qkdv:StrainRate',
        'unit': 'unit:PER-SEC',
        'legend_name': 'True Strain Rate (1-wave)',
        'analysis_method': '1-wave',
        'class_uri': 'dyn:ProcessedData',
        'derived_from': ['incident']
    },
    'true_strain_1w': {
        'series_type': 'dyn:TrueStrain',
        'quantity_kind': 'qkdv:Dimensionless',
        'unit': 'unit:UNITLESS',
        'legend_name': 'True Strain (1-wave)',
        'analysis_method': '1-wave',
        'class_uri': 'dyn:ProcessedData',
        'derived_from': ['incident']
    },
    'true_stress_1w': {
        'series_type': 'dyn:TrueStress',
        'quantity_kind': 'qkdv:Stress',
        'unit': 'unit:MegaPA',
        'legend_name': 'True Stress (1-wave)',
        'analysis_method': '1-wave',
        'class_uri': 'dyn:ProcessedData',
        'derived_from': ['transmitted']
    },

    # ===== 3-WAVE PROCESSED DATA =====
    'bar_displacement_3w': {
        'series_type': 'dyn:BarDisplacement',
        'quantity_kind': 'qkdv:Length',
        'unit': 'unit:MilliM',
        'legend_name': 'Bar Displacement (3-wave)',
        'analysis_method': '3-wave',
        'class_uri': 'dyn:ProcessedData',
        'derived_from': ['incident', 'transmitted']
    },
    'bar_force_3w': {
        'series_type': 'dyn:BarForce',
        'quantity_kind': 'qkdv:Force',
        'unit': 'unit:N',
        'legend_name': 'Bar Force (3-wave)',
        'analysis_method': '3-wave',
        'class_uri': 'dyn:ProcessedData',
        'derived_from': ['incident', 'transmitted']
    },
    'strain_rate_3w': {
        'series_type': 'dyn:StrainRate',
        'quantity_kind': 'qkdv:StrainRate',
        'unit': 'unit:PER-SEC',
        'legend_name': 'Strain Rate (3-wave)',
        'analysis_method': '3-wave',
        'class_uri': 'dyn:ProcessedData',
        'derived_from': ['incident', 'transmitted']
    },
    'strain_3w': {
        'series_type': 'dyn:Strain',
        'quantity_kind': 'qkdv:Dimensionless',
        'unit': 'unit:UNITLESS',
        'legend_name': 'Engineering Strain (3-wave)',
        'analysis_method': '3-wave',
        'class_uri': 'dyn:ProcessedData',
        'derived_from': ['incident', 'transmitted']
    },
    'stress_3w': {
        'series_type': 'dyn:Stress',
        'quantity_kind': 'qkdv:Stress',
        'unit': 'unit:MegaPA',
        'legend_name': 'Engineering Stress (3-wave)',
        'analysis_method': '3-wave',
        'class_uri': 'dyn:ProcessedData',
        'derived_from': ['incident', 'transmitted']
    },
    'true_strain_rate_3w': {
        'series_type': 'dyn:TrueStrainRate',
        'quantity_kind': 'qkdv:StrainRate',
        'unit': 'unit:PER-SEC',
        'legend_name': 'True Strain Rate (3-wave)',
        'analysis_method': '3-wave',
        'class_uri': 'dyn:ProcessedData',
        'derived_from': ['incident', 'transmitted']
    },
    'true_strain_3w': {
        'series_type': 'dyn:TrueStrain',
        'quantity_kind': 'qkdv:Dimensionless',
        'unit': 'unit:UNITLESS',
        'legend_name': 'True Strain (3-wave)',
        'analysis_method': '3-wave',
        'class_uri': 'dyn:ProcessedData',
        'derived_from': ['incident', 'transmitted']
    },
    'true_stress_3w': {
        'series_type': 'dyn:TrueStress',
        'quantity_kind': 'qkdv:Stress',
        'unit': 'unit:MegaPA',
        'legend_name': 'True Stress (3-wave)',
        'analysis_method': '3-wave',
        'class_uri': 'dyn:ProcessedData',
        'derived_from': ['incident', 'transmitted']
    }
}


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

        for column_name in ['time', 'incident', 'transmitted']:
            # Get metadata from lookup table
            series_meta = SERIES_METADATA[column_name]

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
            if column_name not in SERIES_METADATA:
                logger.warning(f"Column '{column_name}' not in SERIES_METADATA, skipping")
                continue

            # Get metadata from lookup table
            series_meta = SERIES_METADATA[column_name]

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

            # Add analysis method for processed data
            if 'analysis_method' in series_meta:
                form_data['dyn:hasAnalysisMethod'] = series_meta['analysis_method']

            # Add derivation chain (link to source windowed signals)
            if 'derived_from' in series_meta:
                source_mapping = {
                    'incident': 'incident_windowed',
                    'transmitted': 'transmitted_windowed',
                    'reflected': 'reflected_windowed'
                }

                derived_sources = []
                for source_column in series_meta['derived_from']:
                    windowed_key = source_mapping.get(source_column, source_column)
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

        # Windowed series metadata
        windowed_metadata = {
            'time_windowed': {
                'series_type': 'dyn:Time',
                'quantity_kind': 'qkdv:Time',
                'unit': 'unit:MilliSEC',
                'legend_name': 'Time (Windowed)',
                'derived_from': 'time'
            },
            'incident_windowed': {
                'series_type': 'dyn:IncidentPulse',
                'quantity_kind': 'qkdv:Dimensionless',
                'unit': 'unit:UNITLESS',
                'legend_name': 'Incident Pulse (Windowed & Normalized)',
                'derived_from': 'incident',
                'gauge_uri': self.metadata.incident_strain_gauge_uri
            },
            'transmitted_windowed': {
                'series_type': 'dyn:TransmittedPulse',
                'quantity_kind': 'qkdv:Dimensionless',
                'unit': 'unit:UNITLESS',
                'legend_name': 'Transmitted Pulse (Windowed & Normalized)',
                'derived_from': 'transmitted',
                'gauge_uri': self.metadata.transmission_strain_gauge_uri
            },
            'reflected_windowed': {
                'series_type': 'dyn:ReflectedPulse',
                'quantity_kind': 'qkdv:Dimensionless',
                'unit': 'unit:UNITLESS',
                'legend_name': 'Reflected Pulse (Windowed & Normalized)',
                'derived_from': 'incident',  # Reflected pulse is on incident bar
                'gauge_uri': self.metadata.incident_strain_gauge_uri
            }
        }

        for series_name, series_meta in windowed_metadata.items():
            # Build form data
            form_data = {
                'rdf:type': 'dyn:DataSeries',
                'dyn:hasDataFile': file_uri,
                'dyn:hasLegendName': series_meta['legend_name'],
                'dyn:hasSeriesType': series_meta['series_type'],
                'dyn:hasDataPointCount': window_length,
                'dyn:hasProcessingMethod': 'Pulse windowing and segmentation',
                'dyn:hasFilterApplied': False,
                'dyn:derivedFrom': raw_series_uris[series_meta['derived_from']],
            }

            # Add unit and quantity kind if specified
            if series_meta['unit']:
                form_data['dyn:hasSeriesUnit'] = series_meta['unit']
            if series_meta['quantity_kind']:
                form_data['dyn:hasQuantityKind'] = series_meta['quantity_kind']

            # Add gauge reference for signal series
            if 'gauge_uri' in series_meta and series_meta['gauge_uri']:
                form_data['dyn:measuredBy'] = series_meta['gauge_uri']

            # Apply type conversion
            form_data = apply_type_conversion_to_dict(form_data)

            # Create instance tuple
            instance_id = f"{self.metadata.test_id.replace('-', '_')}_{series_name}"
            instances.append((form_data, 'dyn:ProcessedData', instance_id))

            logger.debug(f"Prepared windowed DataSeries: {instance_id}")

        logger.info(f"Prepared {len(instances)} windowed DataSeries instances")
        return instances
