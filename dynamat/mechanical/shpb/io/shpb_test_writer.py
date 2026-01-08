"""
SHPB Test Writer - Complete Test Ingestion Workflow

Orchestrates the complete workflow for ingesting SHPB test data:
- Validates metadata and raw data
- Creates directory structure
- Saves CSV files
- Creates RDF metadata instances
- Links test to specimen
"""

import logging
from pathlib import Path
from typing import Tuple, Optional, List, Dict, Any
import pandas as pd

from dynamat.config import config
from dynamat.gui.parsers.instance_writer import InstanceWriter
from dynamat.gui.core.form_validator import ValidationResult

from .test_metadata import SHPBTestMetadata
from .csv_data_handler import CSVDataHandler
from .data_series_builder import DataSeriesBuilder

logger = logging.getLogger(__name__)


class SHPBTestWriter:
    """
    Complete workflow orchestration for SHPB test data ingestion.

    This class coordinates:
    - DataFrame validation
    - Test metadata validation
    - File organization and saving
    - RDF instance creation
    - SHACL validation
    - Specimen linking

    Example:
        >>> from dynamat.ontology import OntologyManager
        >>> from dynamat.mechanical.shpb.io import SHPBTestWriter, SHPBTestMetadata
        >>> import pandas as pd
        >>>
        >>> ontology_manager = OntologyManager()
        >>> writer = SHPBTestWriter(ontology_manager)
        >>>
        >>> # Create metadata
        >>> metadata = SHPBTestMetadata(...)
        >>>
        >>> # Create DataFrame
        >>> df = pd.DataFrame({'time': [...], 'incident': [...], 'transmitted': [...]})
        >>>
        >>> # Ingest test
        >>> test_path, validation = writer.ingest_test(metadata, df)
        >>> if test_path:
        ...     print(f"Test saved to: {test_path}")
    """

    def __init__(self, ontology_manager, qudt_manager=None):
        """
        Initialize SHPB test writer.

        Args:
            ontology_manager: OntologyManager instance
            qudt_manager: QUDTManager for unit conversions (optional)
        """
        self.ontology_manager = ontology_manager
        self.qudt_manager = qudt_manager
        self.instance_writer = InstanceWriter(ontology_manager, qudt_manager)
        self.data_series_builder = DataSeriesBuilder(ontology_manager, qudt_manager)
        self.ns = ontology_manager.namespace_manager if hasattr(ontology_manager, 'namespace_manager') else None

        logger.info("SHPBTestWriter initialized")

    def ingest_test(
        self,
        test_metadata: SHPBTestMetadata,
        raw_data_df: pd.DataFrame
    ) -> Tuple[Optional[Path], ValidationResult]:
        """
        Complete workflow for ingesting SHPB test data.

        Workflow:
            1. Validate test metadata (required fields)
            2. Validate DataFrame structure (required columns)
            3. Determine specimen directory from specimen_uri
            4. Create directory structure (raw/, processed/)
            5. Save DataFrame as CSV to raw/
            6. Create AnalysisFile instance for raw CSV
            7. Create DataSeries instances (time, incident, transmitted)
            8. Create SHPBCompression test instance
            9. Link test to specimen (update specimen TTL)
            10. Save test TTL file
            11. Return paths and validation results

        Args:
            test_metadata: SHPBTestMetadata with test configuration
            raw_data_df: DataFrame with columns 'time', 'incident', 'transmitted'

        Returns:
            Tuple of (test_file_path, validation_result):
            - test_file_path: Path to saved test TTL, or None if failed
            - validation_result: SHACL validation results

        Raises:
            ValueError: If validation fails or required fields missing
            FileNotFoundError: If specimen directory doesn't exist

        Example:
            >>> metadata = SHPBTestMetadata(...)
            >>> df = pd.DataFrame({'time': [...], 'incident': [...], 'transmitted': [...]})
            >>> test_path, validation = writer.ingest_test(metadata, df)
        """
        logger.info(f"Starting SHPB test ingestion for: {test_metadata.test_id}")

        try:
            # Step 1: Validate test metadata
            logger.info("Step 1/10: Validating test metadata...")
            test_metadata.validate()

            # Step 2: Validate DataFrame
            logger.info("Step 2/10: Validating DataFrame structure...")
            csv_handler = CSVDataHandler(raw_data_df)
            csv_handler.validate_structure()

            # Step 3: Determine specimen directory
            logger.info("Step 3/10: Resolving specimen directory...")
            specimen_dir = self._get_specimen_directory(test_metadata.specimen_uri)

            # Step 4: Create directory structure
            logger.info("Step 4/10: Creating directory structure...")
            dirs = self._create_directory_structure(specimen_dir)

            # Step 5: Save DataFrame as CSV
            logger.info("Step 5/10: Saving raw data CSV...")
            csv_path = self._save_dataframe_to_csv(
                csv_handler,
                specimen_dir,
                test_metadata.test_id,
                test_metadata.test_date
            )

            # Step 6: Create AnalysisFile instance
            logger.info("Step 6/10: Creating AnalysisFile metadata...")
            analysis_file_data, analysis_file_uri = self._create_analysis_file_instance(
                csv_path,
                csv_handler,
                specimen_dir,
                test_metadata.test_id,
                test_metadata.test_date
            )

            # Step 7: Create DataSeries instances
            logger.info("Step 7/10: Creating DataSeries metadata...")
            data_series_list = self._create_data_series_instances(
                csv_handler,
                test_metadata.test_id,
                test_metadata.test_date
            )

            # Step 8: Create SHPBCompression test instance
            logger.info("Step 8/10: Creating SHPB test metadata...")
            test_data, test_uri = self._create_test_instance(
                test_metadata,
                [uri for _, uri in data_series_list],
                analysis_file_uri
            )

            # Step 9: Link test to specimen
            logger.info("Step 9/10: Linking test to specimen...")
            self._link_test_to_specimen(
                test_metadata.specimen_uri,
                test_uri,
                specimen_dir
            )

            # Step 10: Save test file with all instances
            logger.info("Step 10/10: Saving test file with validation...")
            test_file_path, validation_result = self._save_test_file(
                test_data,
                analysis_file_data,
                data_series_list,
                test_uri,
                specimen_dir,
                test_metadata.test_id,
                test_metadata.test_date
            )

            if test_file_path:
                logger.info(f"Test ingestion completed successfully: {test_file_path}")
            else:
                logger.warning(f"Test ingestion failed validation")

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

    def _save_dataframe_to_csv(
        self,
        csv_handler: CSVDataHandler,
        specimen_dir: Path,
        test_id: str,
        test_date: str
    ) -> Path:
        """
        Save DataFrame to CSV in raw/ subdirectory.

        Args:
            csv_handler: CSVDataHandler with validated DataFrame
            specimen_dir: Specimen directory
            test_id: Test ID
            test_date: Test date (YYYY-MM-DD)

        Returns:
            Path to saved CSV file
        """
        # Construct filename
        filename = f"{test_id.replace('-', '_')}_raw.csv"
        csv_path = specimen_dir / 'raw' / filename

        # Save CSV
        csv_handler.save_to_csv(csv_path)

        return csv_path

    def _create_analysis_file_instance(
        self,
        csv_path: Path,
        csv_handler: CSVDataHandler,
        specimen_dir: Path,
        test_id: str,
        test_date: str
    ) -> Tuple[Dict[str, Any], str]:
        """
        Create AnalysisFile RDF instance metadata.

        Args:
            csv_path: Path to CSV file
            csv_handler: CSVDataHandler
            specimen_dir: Specimen directory
            test_id: Test ID
            test_date: Test date

        Returns:
            Tuple of (form_data_dict, instance_uri)
        """
        # Get file size
        file_size = csv_path.stat().st_size

        # Get file metadata
        file_metadata = csv_handler.get_file_metadata_for_saving()

        # Create form data
        form_data = self.data_series_builder.create_analysis_file(
            file_path=csv_path,
            specimen_dir=specimen_dir,
            file_size=file_size,
            **file_metadata
        )

        # Create URI
        uri_suffix = f"{test_id.replace('-', '_')}_raw_csv"
        instance_uri = f"dyn:{uri_suffix}"

        return form_data, instance_uri

    def _create_data_series_instances(
        self,
        csv_handler: CSVDataHandler,
        test_id: str,
        test_date: str
    ) -> List[Tuple[Dict[str, Any], str]]:
        """
        Create DataSeries instances for time, incident, transmitted.

        Args:
            csv_handler: CSVDataHandler
            test_id: Test ID
            test_date: Test date

        Returns:
            List of (form_data, uri) tuples for each series
        """
        data_point_count = csv_handler.get_data_point_count()

        # Build all series (no file reference in DataSeries)
        all_series = self.data_series_builder.build_all_raw_series(
            data_point_count=data_point_count
        )

        # Create URIs and form data list
        result = []
        uri_base = test_id.replace('-', '_')

        for series_type, form_data in all_series.items():
            uri = f"dyn:{uri_base}_{series_type}"
            result.append((form_data, uri))

        return result

    def _expand_list_properties(self, form_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Expand list-valued properties for InstanceWriter compatibility.

        InstanceWriter expects single values or specific handling for lists.
        This helper ensures lists are properly handled.

        Args:
            form_data: Dictionary with possible list values

        Returns:
            Dictionary with lists properly formatted
        """
        expanded = {}
        for key, value in form_data.items():
            if isinstance(value, list):
                # Keep lists as-is - InstanceWriter should handle them
                # If not, this is where we'd expand them
                expanded[key] = value
                logger.debug(f"Multi-valued property {key}: {len(value)} values")
            else:
                expanded[key] = value
        return expanded

    def _create_test_instance(
        self,
        test_metadata: SHPBTestMetadata,
        data_series_uris: List[str],
        analysis_file_uri: str
    ) -> Tuple[Dict[str, Any], str]:
        """
        Create SHPBCompression test instance metadata.

        Args:
            test_metadata: SHPBTestMetadata
            data_series_uris: List of DataSeries URIs
            analysis_file_uri: AnalysisFile URI

        Returns:
            Tuple of (form_data, test_uri)
        """
        # Get base form data from metadata
        form_data = test_metadata.to_form_data()

        # Add data file and series references
        form_data['dyn:hasRawDataFile'] = analysis_file_uri

        # Add all data series
        form_data['dyn:hasDataSeries'] = data_series_uris

        # Expand list properties if needed
        form_data = self._expand_list_properties(form_data)

        # Create test URI
        test_uri = f"dyn:{test_metadata.test_id.replace('-', '_')}"

        return form_data, test_uri

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
        test_data: Dict[str, Any],
        analysis_file_data: Dict[str, Any],
        data_series_list: List[Tuple[Dict[str, Any], str]],
        test_uri: str,
        specimen_dir: Path,
        test_id: str,
        test_date: str
    ) -> Tuple[Optional[Path], ValidationResult]:
        """
        Save test TTL file with all instances using InstanceWriter.

        Strategy: Save each instance separately using InstanceWriter, then combine graphs.
        This ensures proper unit conversion, type handling, and validation for all instances.

        Args:
            test_data: Test instance form data
            analysis_file_data: AnalysisFile form data
            data_series_list: List of (form_data, uri) for DataSeries
            test_uri: Test URI
            specimen_dir: Specimen directory
            test_id: Test ID
            test_date: Test date

        Returns:
            Tuple of (file_path, validation_result)
        """
        from rdflib import Graph
        import tempfile

        # Final output file
        test_filename = f"{test_id.replace('-', '_')}.ttl"
        test_file_path = specimen_dir / test_filename

        # Create combined graph
        combined_graph = Graph()

        # Step 1: Save test instance to temp file and load into combined graph
        with tempfile.NamedTemporaryFile(mode='w', suffix='.ttl', delete=False) as tmp:
            tmp_test_path = Path(tmp.name)

        test_path, test_validation = self.instance_writer.write_instance(
            form_data=test_data,
            class_uri='dyn:SHPBCompression',
            instance_id=test_uri.replace('dyn:', ''),
            output_path=tmp_test_path
        )

        if not test_path:
            logger.error("Test instance validation failed")
            tmp_test_path.unlink(missing_ok=True)
            return None, test_validation

        # Load test graph
        combined_graph.parse(tmp_test_path, format='turtle')
        tmp_test_path.unlink()

        # Step 2: Save AnalysisFile instance and merge
        with tempfile.NamedTemporaryFile(mode='w', suffix='.ttl', delete=False) as tmp:
            tmp_analysis_path = Path(tmp.name)

        analysis_uri = f"{test_id.replace('-', '_')}_raw_csv"
        analysis_path, analysis_validation = self.instance_writer.write_instance(
            form_data=analysis_file_data,
            class_uri='dyn:AnalysisFile',
            instance_id=analysis_uri,
            output_path=tmp_analysis_path
        )

        if analysis_path:
            combined_graph.parse(tmp_analysis_path, format='turtle')
            tmp_analysis_path.unlink()
        else:
            logger.warning(f"AnalysisFile validation warnings: {analysis_validation.get_summary()}")
            tmp_analysis_path.unlink(missing_ok=True)

        # Step 3: Save each DataSeries instance and merge
        for series_data, series_uri in data_series_list:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.ttl', delete=False) as tmp:
                tmp_series_path = Path(tmp.name)

            series_id = series_uri.replace('dyn:', '')
            series_path, series_validation = self.instance_writer.write_instance(
                form_data=series_data,
                class_uri='dyn:RawSignal',
                instance_id=series_id,
                output_path=tmp_series_path
            )

            if series_path:
                combined_graph.parse(tmp_series_path, format='turtle')
                tmp_series_path.unlink()
            else:
                logger.warning(f"DataSeries {series_id} validation warnings: {series_validation.get_summary()}")
                tmp_series_path.unlink(missing_ok=True)

        # Step 4: Save combined graph to final location
        combined_graph.serialize(test_file_path, format='turtle')

        logger.info(f"Test file saved with all instances: {test_file_path}")
        return Path(test_file_path), test_validation
