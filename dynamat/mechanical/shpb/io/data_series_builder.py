"""
DataSeries Builder for SHPB Raw Signals

Creates RDF metadata dictionaries for DataSeries and AnalysisFile instances
following the DynaMat ontology structure.
"""

import logging
from pathlib import Path
from typing import Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)


class DataSeriesBuilder:
    """
    Build RDF metadata for SHPB DataSeries and AnalysisFile instances.

    Creates form_data dictionaries compatible with InstanceWriter that follow
    the ontology structure defined in data_series_class.ttl.

    Example:
        >>> from dynamat.ontology import OntologyManager
        >>> ontology_manager = OntologyManager()
        >>> builder = DataSeriesBuilder(ontology_manager)
        >>> time_series = builder.build_time_series(
        ...     column_name='time',
        ...     file_ref='dyn:TestFile_raw_csv',
        ...     data_point_count=10000
        ... )
    """

    def __init__(self, ontology_manager, qudt_manager=None):
        """
        Initialize DataSeries builder.

        Args:
            ontology_manager: OntologyManager for namespace access
            qudt_manager: QUDTManager for unit handling (optional)
        """
        self.ontology_manager = ontology_manager
        self.qudt_manager = qudt_manager
        self.ns = ontology_manager.namespace_manager if hasattr(ontology_manager, 'namespace_manager') else None

        logger.info("DataSeriesBuilder initialized")

    def create_analysis_file(
        self,
        file_path: Path,
        specimen_dir: Path,
        file_size: int,
        **metadata
    ) -> Dict[str, Any]:
        """
        Create AnalysisFile metadata dictionary.

        Args:
            file_path: Absolute path to the CSV file
            specimen_dir: Specimen directory (for calculating relative path)
            file_size: File size in bytes
            **metadata: Additional metadata (delimiter, encoding, has_header, skip_rows)

        Returns:
            Form data dict for AnalysisFile instance

        Example:
            >>> analysis_file = builder.create_analysis_file(
            ...     file_path=Path('user_data/specimens/SPN-001/raw/data.csv'),
            ...     specimen_dir=Path('user_data/specimens/SPN-001'),
            ...     file_size=123456,
            ...     delimiter=',',
            ...     encoding='UTF-8',
            ...     has_header=True,
            ...     skip_rows=0
            ... )
        """
        # Calculate relative path from specimen directory
        try:
            relative_path = file_path.relative_to(specimen_dir)
        except ValueError:
            # If file is not under specimen dir, use absolute path
            logger.warning(f"File {file_path} is not under specimen dir {specimen_dir}, using absolute path")
            relative_path = file_path

        form_data = {
            'dyn:hasFileName': file_path.name,
            'dyn:hasFilePath': str(relative_path).replace('\\', '/'),  # Use forward slashes
            'dyn:hasFileSize': file_size,
            'dyn:hasFileFormat': metadata.get('file_format', 'CSV'),
            'dyn:hasFileEncoding': metadata.get('encoding', 'UTF-8'),
            'dyn:hasDelimiter': metadata.get('delimiter', ','),
            'dyn:hasHeaderRow': metadata.get('has_header', True),
            'dyn:hasSkipRows': metadata.get('skip_rows', 0),
            'dyn:hasProcessingDate': datetime.now().isoformat()
        }

        logger.debug(f"Created AnalysisFile metadata for: {file_path.name}")
        return form_data

    def build_time_series(
        self,
        column_name: str,
        data_point_count: int,
        column_index: int = 0
    ) -> Dict[str, Any]:
        """
        Build metadata for time data series.

        Args:
            column_name: Name of time column in CSV
            data_point_count: Number of data points
            column_index: Zero-based column index (default 0)

        Returns:
            Form data dict for time RawSignal instance

        Example:
            >>> time_series = builder.build_time_series(
            ...     column_name='time',
            ...     data_point_count=10000
            ... )
        """
        form_data = {
            # Series type and classification
            'dyn:hasSeriesType': 'Time',

            # Column reference
            'dyn:hasColumnName': column_name,
            'dyn:hasColumnIndex': column_index,
            'dyn:hasLegendName': 'Time',

            # Physical quantity metadata
            'dyn:hasSeriesUnit': 'unit:SEC',  # Seconds
            'dyn:hasQuantityKind': 'qkdv:Time',

            # Statistics
            'dyn:hasDataPointCount': data_point_count,

            # Processing flags (raw data - not processed)
            'dyn:hasFilterApplied': False,
            'dyn:isCenteredPulse': False,
            'dyn:isAlignedPulse': False,
            'dyn:isReferencePulse': False,
            'dyn:isTrainingData': False
        }

        logger.debug(f"Built time series metadata: {column_name} ({data_point_count} points)")
        return form_data

    def build_incident_pulse_series(
        self,
        column_name: str,
        data_point_count: int,
        column_index: int = 1
    ) -> Dict[str, Any]:
        """
        Build metadata for incident pulse data series.

        Args:
            column_name: Name of incident pulse column in CSV
            data_point_count: Number of data points
            column_index: Zero-based column index (default 1)

        Returns:
            Form data dict for incident pulse RawSignal instance

        Example:
            >>> incident_series = builder.build_incident_pulse_series(
            ...     column_name='incident',
            ...     data_point_count=10000
            ... )
        """
        form_data = {
            # Series type and classification
            'dyn:hasSeriesType': 'IncidentPulse',

            # Column reference
            'dyn:hasColumnName': column_name,
            'dyn:hasColumnIndex': column_index,
            'dyn:hasLegendName': 'Incident Pulse',

            # Physical quantity metadata (voltage from strain gauge)
            'dyn:hasSeriesUnit': 'unit:V',  # Volts
            'dyn:hasQuantityKind': 'qkdv:Voltage',

            # Statistics
            'dyn:hasDataPointCount': data_point_count,

            # Processing flags (raw data - not processed)
            'dyn:hasFilterApplied': False,
            'dyn:isCenteredPulse': False,
            'dyn:isAlignedPulse': False,
            'dyn:isReferencePulse': False,
            'dyn:isTrainingData': False
        }

        logger.debug(f"Built incident pulse series metadata: {column_name} ({data_point_count} points)")
        return form_data

    def build_transmitted_pulse_series(
        self,
        column_name: str,
        data_point_count: int,
        column_index: int = 2
    ) -> Dict[str, Any]:
        """
        Build metadata for transmitted pulse data series.

        Args:
            column_name: Name of transmitted pulse column in CSV
            data_point_count: Number of data points
            column_index: Zero-based column index (default 2)

        Returns:
            Form data dict for transmitted pulse RawSignal instance

        Example:
            >>> transmitted_series = builder.build_transmitted_pulse_series(
            ...     column_name='transmitted',
            ...     data_point_count=10000
            ... )
        """
        form_data = {
            # Series type and classification
            'dyn:hasSeriesType': 'TransmittedPulse',

            # Column reference
            'dyn:hasColumnName': column_name,
            'dyn:hasColumnIndex': column_index,
            'dyn:hasLegendName': 'Transmitted Pulse',

            # Physical quantity metadata (voltage from strain gauge)
            'dyn:hasSeriesUnit': 'unit:V',  # Volts
            'dyn:hasQuantityKind': 'qkdv:Voltage',

            # Statistics
            'dyn:hasDataPointCount': data_point_count,

            # Processing flags (raw data - not processed)
            'dyn:hasFilterApplied': False,
            'dyn:isCenteredPulse': False,
            'dyn:isAlignedPulse': False,
            'dyn:isReferencePulse': False,
            'dyn:isTrainingData': False
        }

        logger.debug(f"Built transmitted pulse series metadata: {column_name} ({data_point_count} points)")
        return form_data

    def build_all_raw_series(
        self,
        data_point_count: int
    ) -> Dict[str, Dict[str, Any]]:
        """
        Build metadata for all three raw signal series (time, incident, transmitted).

        Convenience method that creates all three series with standard column names.

        Args:
            data_point_count: Number of data points

        Returns:
            Dict mapping series type to form_data:
            {
                'time': {...},
                'incident': {...},
                'transmitted': {...}
            }

        Example:
            >>> all_series = builder.build_all_raw_series(
            ...     data_point_count=10000
            ... )
            >>> time_data = all_series['time']
            >>> incident_data = all_series['incident']
            >>> transmitted_data = all_series['transmitted']
        """
        return {
            'time': self.build_time_series(
                column_name='time',
                data_point_count=data_point_count,
                column_index=0
            ),
            'incident': self.build_incident_pulse_series(
                column_name='incident',
                data_point_count=data_point_count,
                column_index=1
            ),
            'transmitted': self.build_transmitted_pulse_series(
                column_name='transmitted',
                data_point_count=data_point_count,
                column_index=2
            )
        }
