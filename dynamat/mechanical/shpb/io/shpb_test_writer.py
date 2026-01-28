"""
SHPB Test Writer - Simplified Test Ingestion Workflow

Simplified workflow orchestrator that delegates all RDF generation to InstanceWriter.
All metadata is contained in SHPBTestMetadata, making the workflow clean and direct.

Architecture:
- SHPBTestMetadata: Contains all data and RDF structure knowledge
- SHPBTestWriter: Thin orchestrator for the ingestion workflow
- InstanceWriter: Generic RDF engine (handles all TTL generation)
"""

import logging
from pathlib import Path
from typing import Tuple, Optional, List, Dict, Any, TYPE_CHECKING
import pandas as pd
import numpy as np
from datetime import datetime

from dynamat.config import config

from .test_metadata import SHPBTestMetadata
from .csv_data_handler import CSVDataHandler

# Type hints only - avoid circular import at runtime
if TYPE_CHECKING:
    from dynamat.gui.parsers.instance_writer import InstanceWriter
    from dynamat.gui.core.form_validator import ValidationResult

logger = logging.getLogger(__name__)


class SHPBTestWriter:
    """
    Simplified workflow orchestrator for SHPB test data ingestion.

    All RDF generation is delegated to InstanceWriter using batch creation methods.
    SHPBTestMetadata contains complete analysis provenance (120+ parameters).

    Workflow:
    1. Validate metadata and DataFrame
    2. Save CSV file
    3. Create AnalysisFile instance
    4. Create DataSeries instances (time, incident, transmitted)
    5. Create processing instances (windows, shifts, params, metrics) via batch
    6. Create SHPBCompression test instance linking to all above
    7. Save all to single TTL file
    8. Update specimen with test link

    Example:
        >>> ontology_manager = OntologyManager()
        >>> writer = SHPBTestWriter(ontology_manager, qudt_manager)
        >>>
        >>> # Create comprehensive metadata with all analysis parameters
        >>> metadata = SHPBTestMetadata(
        ...     test_id='TEST_001',
        ...     specimen_uri='dyn:SPECIMEN_001',
        ...     # ... (120+ parameters)
        ... )
        >>>
        >>> # Ingest test with full provenance
        >>> test_path, validation = writer.ingest_test(metadata, raw_df)
    """

    def __init__(self, ontology_manager, qudt_manager=None):
        """
        Initialize SHPB test writer.

        Args:
            ontology_manager: OntologyManager instance
            qudt_manager: QUDTManager for unit conversions
        """
        # Lazy import to avoid circular dependency
        from dynamat.gui.parsers.instance_writer import InstanceWriter

        self.ontology_manager = ontology_manager
        self.qudt_manager = qudt_manager
        self.instance_writer = InstanceWriter(ontology_manager, qudt_manager)

        logger.info("SHPBTestWriter initialized (simplified architecture)")

    def ingest_test(
        self,
        test_metadata: SHPBTestMetadata,
        raw_data_df: pd.DataFrame,
        processed_results: Optional[Dict[str, np.ndarray]] = None
    ) -> Tuple[Optional[Path], "ValidationResult"]:
        """
        Ingest complete SHPB test with full analysis provenance.

        Simplified workflow using batch instance creation:
        1. Validate metadata and DataFrame
        2. Save CSV file(s) (raw, and processed if provided)
        3. Build all instances (AnalysisFile, DataSeries, processing objects, test)
        4. Save all instances to single TTL file using batch write
        5. Update specimen with test link

        Args:
            test_metadata: Complete SHPBTestMetadata with all 120+ parameters
            raw_data_df: DataFrame with columns 'time', 'incident', 'transmitted'
            processed_results: Optional dict from StressStrainCalculator.calculate()
                              If provided, creates processed DataSeries instances and saves CSV

        Returns:
            Tuple of (test_file_path, validation_result):
            - test_file_path: Path to saved test TTL, or None if validation failed
            - validation_result: SHACL validation results

        Example:
            >>> metadata = SHPBTestMetadata(...)  # With all analysis parameters
            >>> df = pd.DataFrame({'time': [...], 'incident': [...], 'transmitted': [...]})
            >>> # Optional: calculate stress-strain curves
            >>> calculator = StressStrainCalculator(...)
            >>> results = calculator.calculate(inc, trs, ref, time)
            >>> # Ingest with or without processed results
            >>> test_path, validation = writer.ingest_test(metadata, df, results)
        """
        logger.info(f"Starting SHPB test ingestion for: {test_metadata.test_id}")

        try:
            # Step 1: Validate
            logger.info("Step 1/5: Validating metadata and DataFrame...")
            test_metadata.validate()
            csv_handler = CSVDataHandler(raw_data_df)
            csv_handler.validate_structure()

            # Step 2: Save CSV
            logger.info("Step 2/5: Saving raw data CSV...")
            specimen_dir = self._get_specimen_directory(test_metadata.specimen_uri)
            self._create_directory_structure(specimen_dir)
            csv_path = self._save_csv(test_metadata, specimen_dir, csv_handler)

            # Step 2b: Save processed CSV if provided
            processed_csv_path = None
            if processed_results is not None:
                logger.info("Step 2b/5: Saving processed data CSV...")
                processed_csv_path = self._save_processed_csv(
                    processed_results,
                    specimen_dir,
                    test_metadata.test_id
                )

            # Step 3: Build all instances
            logger.info("Step 3/5: Building all RDF instances...")
            all_instances = self._build_all_instances(
                test_metadata,
                csv_path,
                csv_handler,
                processed_results,
                processed_csv_path
            )

            # Step 4: Save to TTL
            logger.info("Step 4/5: Saving test file with batch validation...")
            test_file_path, validation_result = self._save_test_file(
                all_instances,
                specimen_dir,
                test_metadata.test_id
            )

            if not test_file_path:
                logger.warning("Test ingestion failed validation")
                return None, validation_result

            # Step 5: Link test to specimen
            logger.info("Step 5/5: Linking test to specimen...")
            test_uri = f"dyn:{test_metadata.test_id.replace('-', '_')}"
            self._link_test_to_specimen(test_metadata.specimen_uri, test_uri, specimen_dir)

            logger.info(f"Test ingestion completed successfully: {test_file_path}")
            return test_file_path, validation_result

        except Exception as e:
            logger.error(f"Test ingestion failed: {e}", exc_info=True)
            raise

    def _get_specimen_directory(self, specimen_uri: str) -> Path:
        """
        Resolve specimen URI to directory path.

        Args:
            specimen_uri: Specimen URI (e.g., "dyn:DYNML_A356_00001")

        Returns:
            Path to specimen directory

        Raises:
            FileNotFoundError: If specimen directory doesn't exist
        """
        # Extract specimen ID from URI
        if specimen_uri.startswith('dyn:'):
            specimen_id = specimen_uri.replace('dyn:', '')
        elif '#' in specimen_uri:
            specimen_id = specimen_uri.split('#')[-1]
        else:
            specimen_id = specimen_uri

        # Convert underscores to hyphens for directory name
        specimen_dir_name = specimen_id.replace('_', '-')

        # Construct path
        specimen_dir = config.SPECIMENS_DIR / specimen_dir_name

        # Check if directory exists
        if not specimen_dir.exists():
            raise FileNotFoundError(
                f"Specimen directory not found: {specimen_dir}. "
                f"Please ensure specimen '{specimen_id}' exists."
            )

        logger.debug(f"Resolved specimen URI '{specimen_uri}' to directory: {specimen_dir}")
        return specimen_dir

    def _create_directory_structure(self, specimen_dir: Path) -> Dict[str, Path]:
        """
        Create raw/ and processed/ subdirectories.

        Args:
            specimen_dir: Specimen directory path

        Returns:
            Dict with 'raw' and 'processed' paths
        """
        raw_dir = specimen_dir / 'raw'
        processed_dir = specimen_dir / 'processed'

        raw_dir.mkdir(parents=True, exist_ok=True)
        processed_dir.mkdir(parents=True, exist_ok=True)

        logger.debug(f"Created directories: raw/, processed/ in {specimen_dir}")

        return {
            'raw': raw_dir,
            'processed': processed_dir
        }

    def _save_csv(
        self,
        test_metadata: SHPBTestMetadata,
        specimen_dir: Path,
        csv_handler: CSVDataHandler
    ) -> Path:
        """
        Save DataFrame to CSV in raw/ subdirectory.

        Args:
            test_metadata: Test metadata
            specimen_dir: Specimen directory
            csv_handler: CSVDataHandler with validated DataFrame

        Returns:
            Path to saved CSV file
        """
        filename = f"{test_metadata.test_id.replace('-', '_')}_raw.csv"
        csv_path = specimen_dir / 'raw' / filename
        csv_handler.save_to_csv(csv_path)
        logger.debug(f"Saved CSV: {csv_path}")
        return csv_path

    def _save_processed_csv(
        self,
        results: Dict[str, np.ndarray],
        specimen_dir: Path,
        test_id: str
    ) -> Path:
        """
        Save processed results dictionary to CSV in processed/ subdirectory.

        Args:
            results: Dictionary from StressStrainCalculator.calculate()
            specimen_dir: Specimen directory
            test_id: Test ID

        Returns:
            Path to saved CSV file
        """
        # Create DataFrame from results dictionary
        processed_df = pd.DataFrame(results)

        # Define filename and path
        filename = f"{test_id.replace('-', '_')}_processed.csv"
        csv_path = specimen_dir / 'processed' / filename

        # Save with scientific notation for precision
        processed_df.to_csv(csv_path, index=False, float_format='%.6e')

        logger.debug(f"Saved processed CSV: {csv_path} ({len(processed_df)} rows, {len(results)} columns)")
        return csv_path

    def _build_all_instances(
        self,
        test_metadata: SHPBTestMetadata,
        csv_path: Path,
        csv_handler: CSVDataHandler,
        processed_results: Optional[Dict[str, np.ndarray]] = None,
        processed_csv_path: Optional[Path] = None
    ) -> List[tuple]:
        """
        Build list of ALL instances to create for this test.

        This method creates instances for:
        1. AnalysisFile (raw CSV metadata)
        2. DataSeries (time, incident, transmitted)
        3. PulseWindow instances (3x: incident, transmitted, reflected)
        4. PulseShift instances (2x: transmitted, reflected)
        5. PulseDetectionParams instances (3x)
        6. AlignmentParams instance
        7. EquilibriumMetrics instance
        8. SHPBCompression test (links to all above)

        Args:
            test_metadata: Complete SHPBTestMetadata
            csv_path: Path to saved CSV file
            csv_handler: CSVDataHandler

        Returns:
            List of (form_data, class_uri, instance_id) tuples for batch creation
        """
        instances = []
        test_id_clean = test_metadata.test_id.replace('-', '_')

        # === ANALYSIS FILE ===
        file_size = csv_path.stat().st_size
        file_metadata = csv_handler.get_file_metadata_for_saving()

        # Get data point count and column count from DataFrame
        data_point_count = len(csv_handler.data)
        column_count = len(csv_handler.data.columns)

        analysis_file_form = SHPBTestMetadata._apply_type_conversion_to_dict({
            'dyn:hasFilePath': str(csv_path.relative_to(csv_path.parent.parent)),
            'dyn:hasFileFormat': 'csv',
            'dyn:hasFileSize': file_size,
            'dyn:hasDataPointCount': data_point_count,
            'dyn:hasColumnCount': column_count,
            'dyn:hasCreatedDate': datetime.now().strftime('%Y-%m-%d')
        })
        instances.append((analysis_file_form, 'dyn:AnalysisFile', f'{test_id_clean}_raw_csv'))

        # === DATA SERIES - RAW ===
        gauge_params = {
            'incident': test_metadata.incident_strain_gauge_uri,
            'transmitted': test_metadata.transmission_strain_gauge_uri
        }

        raw_series = test_metadata.prepare_raw_data_series(
            csv_handler.data,
            f'dyn:{test_id_clean}_raw_csv',
            gauge_params
        )
        instances.extend(raw_series)

        # Store raw series URIs
        raw_series_uris = {
            'time': f'dyn:{test_id_clean}_time',
            'incident': f'dyn:{test_id_clean}_incident',
            'transmitted': f'dyn:{test_id_clean}_transmitted'
        }

        # === DATA SERIES - WINDOWED ===
        # Create windowed series (extracted pulses after detection/segmentation)
        # These are the intermediate step between raw and processed
        if test_metadata.segment_n_points:
            # Determine file URI for windowed series
            # If processed CSV exists, windowed series reference it (windowed data is in processed file)
            # Otherwise, create windowed file URI placeholder
            if processed_csv_path is not None:
                windowed_file_uri = f'dyn:{test_id_clean}_processed_csv'
            else:
                windowed_file_uri = f'dyn:{test_id_clean}_windowed_csv'

            windowed_series = test_metadata.prepare_windowed_data_series(
                raw_series_uris,
                test_metadata.segment_n_points,
                windowed_file_uri
            )
            instances.extend(windowed_series)

            # Store windowed series URIs for processed data derivation
            windowed_series_uris = {
                'time_windowed': f'dyn:{test_id_clean}_time_windowed',
                'incident_windowed': f'dyn:{test_id_clean}_incident_windowed',
                'transmitted_windowed': f'dyn:{test_id_clean}_transmitted_windowed',
                'reflected_windowed': f'dyn:{test_id_clean}_reflected_windowed'
            }

            logger.info(f"Added {len(windowed_series)} windowed DataSeries instances")
        else:
            # No windowing, use raw series directly (fallback)
            windowed_series_uris = raw_series_uris
            logger.warning("No segment_n_points defined, skipping windowed series creation")

        # === DATA SERIES - PROCESSED (if available) ===
        if processed_results is not None and processed_csv_path is not None:
            # Create AnalysisFile for processed CSV
            file_size = processed_csv_path.stat().st_size
            processed_file_form = SHPBTestMetadata._apply_type_conversion_to_dict({
                'dyn:hasFilePath': str(processed_csv_path.relative_to(processed_csv_path.parent.parent)),
                'dyn:hasFileFormat': 'csv',
                'dyn:hasFileSize': file_size,
                'dyn:hasDataPointCount': len(next(iter(processed_results.values()))),
                'dyn:hasColumnCount': len(processed_results),
                'dyn:hasCreatedDate': datetime.now().strftime('%Y-%m-%d')
            })
            instances.append((processed_file_form, 'dyn:AnalysisFile', f'{test_id_clean}_processed_csv'))

            # Create processed DataSeries instances (derive from windowed series)
            processed_series = test_metadata.prepare_processed_data_series(
                processed_results,
                f'dyn:{test_id_clean}_processed_csv',
                windowed_series_uris
            )
            instances.extend(processed_series)

            logger.info(f"Added {len(processed_series)} processed DataSeries instances")

        # === PROCESSING INSTANCES (from metadata) ===
        processing_instances = test_metadata.get_processing_instances()
        for instance_type, type_instances in processing_instances.items():
            instances.extend(type_instances)

        # === TEST INSTANCE ===
        test_form = test_metadata.to_form_data()

        # Add all DataSeries references (raw + windowed + processed)
        # Note: File references are now at DataSeries level via hasDataFile
        series_refs = list(raw_series_uris.values())  # Raw signals

        # Add windowed series URIs
        if test_metadata.segment_n_points:
            series_refs.extend(windowed_series_uris.values())

        # Add processed series URIs
        # Skip 'time', 'incident', 'transmitted', 'reflected' - these are intermediate data
        # represented by raw and windowed series, not final processed results
        if processed_results is not None:
            for column_name in processed_results.keys():
                if column_name not in ['time', 'incident', 'transmitted', 'reflected']:
                    series_refs.append(f'dyn:{test_id_clean}_{column_name}')

        test_form['dyn:hasDataSeries'] = series_refs

        instances.append((test_form, 'dyn:SHPBCompression', test_id_clean))

        logger.info(f"Built {len(instances)} instances for test {test_metadata.test_id}")
        return instances

    def _link_test_to_specimen(
        self,
        specimen_uri: str,
        test_uri: str,
        specimen_dir: Path
    ):
        """
        Link test to specimen by updating specimen TTL.

        Args:
            specimen_uri: Specimen URI
            test_uri: Test URI
            specimen_dir: Specimen directory
        """
        # Extract specimen ID from URI (consistent with _get_specimen_directory)
        if specimen_uri.startswith('dyn:'):
            specimen_id = specimen_uri.replace('dyn:', '')
        elif '#' in specimen_uri:
            specimen_id = specimen_uri.split('#')[-1]
        else:
            specimen_id = specimen_uri

        # Convert underscores to hyphens for filename
        specimen_id = specimen_id.replace('_', '-')

        # Find specimen TTL file
        specimen_ttl = specimen_dir / f"{specimen_id}_specimen.ttl"

        if not specimen_ttl.exists():
            logger.warning(f"Specimen TTL not found: {specimen_ttl}. Test link will not be created.")
            return

        # Update specimen with test link
        updates = {
            'dyn:hasSHPBCompressionTest': test_uri
        }

        try:
            self.instance_writer.update_instance(
                instance_uri=specimen_uri,
                updates=updates,
                ttl_file=specimen_ttl
            )
            logger.info(f"Linked test {test_uri} to specimen {specimen_uri}")

        except Exception as e:
            logger.error(f"Failed to link test to specimen: {e}")
            # Don't raise - test can still be saved even if link fails

    def _save_test_file(
        self,
        all_instances: List[tuple],
        specimen_dir: Path,
        test_id: str
    ) -> Tuple[Optional[Path], "ValidationResult"]:
        """
        Save test TTL file with all instances using batch write.

        Uses InstanceWriter.write_multi_instance_file() for atomic batch operation
        with single validation pass.

        Args:
            all_instances: List of (form_data, class_uri, instance_id) tuples
            specimen_dir: Specimen directory
            test_id: Test ID

        Returns:
            Tuple of (file_path, validation_result)
        """
        test_filename = f"{test_id.replace('-', '_')}.ttl"
        test_file_path = specimen_dir / test_filename

        # Use batch write method
        file_path, validation_result = self.instance_writer.write_multi_instance_file(
            instances=all_instances,
            output_path=test_file_path,
            skip_validation=True
        )

        if file_path:
            logger.info(f"Test file saved with {len(all_instances)} instances: {test_file_path}")
        else:
            logger.error(f"Batch validation failed: {validation_result.get_summary()}")

        return Path(file_path) if file_path else None, validation_result
