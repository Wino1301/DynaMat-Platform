"""
SHPB Re-Analysis Utility

Provides SHPBReanalyzer class for re-running SHPB analysis when parameters change.
Supports two modes:
1. Analysis-only mode (fast): Re-run stress-strain calculation using existing aligned pulses
2. Full re-alignment mode: Re-run from raw data with updated alignment parameters

Example:
    >>> from dynamat.mechanical.shpb.utils import SHPBReanalyzer
    >>> from dynamat.ontology import OntologyManager
    >>>
    >>> manager = OntologyManager()
    >>> reanalyzer = SHPBReanalyzer(manager)
    >>>
    >>> # Load existing test
    >>> reanalyzer.load_test("path/to/test.ttl")
    >>>
    >>> # Update bar wave speed (e.g., after recalibration)
    >>> reanalyzer.update_bar_property('incident', 'wave_speed', 5000.0)
    >>>
    >>> # Re-run analysis
    >>> results = reanalyzer.recalculate(mode='analysis_only')
"""

from __future__ import annotations
import copy
import logging
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, Literal

import numpy as np
import pandas as pd
from rdflib import Graph, Namespace, URIRef, Literal as RDFLiteral
from rdflib.namespace import RDF, XSD

from dynamat.mechanical.shpb.core import (
    PulseDetector,
    PulseAligner,
    StressStrainCalculator,
)
from dynamat.mechanical.shpb.io import (
    SpecimenLoader,
    ValidityAssessor,
)

logger = logging.getLogger(__name__)


class SHPBReanalyzer:
    """Re-analyze SHPB test data with updated parameters.

    Provides methods to load existing test data, update analysis parameters,
    and re-run calculations without modifying the original files.

    Parameters
    ----------
    ontology_manager : OntologyManager
        Ontology manager instance for RDF queries.
    qudt_manager : QUDTManager, optional
        QUDT manager for unit conversions.

    Examples
    --------
    >>> reanalyzer = SHPBReanalyzer(ontology_manager)
    >>> reanalyzer.load_test("user_data/specimens/DYNML-SS316A356-0050/test.ttl")
    >>> reanalyzer.update_bar_property('incident', 'wave_speed', 5000.0)
    >>> results = reanalyzer.recalculate(mode='analysis_only')
    >>> csv_path, ttl_path = reanalyzer.save(version_suffix="_recalibrated")
    """

    # DynaMat ontology namespace
    DYN_NS = "https://dynamat.utep.edu/ontology#"

    def __init__(self, ontology_manager, qudt_manager=None):
        """Initialize the reanalyzer.

        Args:
            ontology_manager: OntologyManager instance for RDF queries
            qudt_manager: Optional QUDTManager for unit conversions
        """
        self.ontology_manager = ontology_manager
        self.qudt_manager = qudt_manager
        self.specimen_loader = SpecimenLoader(ontology_manager)
        self.validity_assessor = ValidityAssessor()

        # Data storage
        self._test_uri: Optional[str] = None
        self._test_ttl_path: Optional[Path] = None
        self._raw_csv_path: Optional[Path] = None
        self._processed_csv_path: Optional[Path] = None
        self._specimens_dir: Optional[Path] = None

        # Loaded data
        self._test_graph: Optional[Graph] = None
        self._raw_df: Optional[pd.DataFrame] = None
        self._processed_df: Optional[pd.DataFrame] = None
        self._aligned_pulses: Optional[Dict[str, np.ndarray]] = None

        # Parameters
        self._original_params: Dict[str, Any] = {}
        self._current_params: Dict[str, Any] = {}

        # Detection parameters for full re-alignment
        self._detection_params: Dict[str, Any] = {}
        self._alignment_params: Dict[str, Any] = {}

        # Results
        self._results: Optional[Dict[str, np.ndarray]] = None
        self._metrics: Optional[Dict[str, float]] = None

        logger.info("SHPBReanalyzer initialized")

    def load_test(
        self,
        test_uri_or_path: str,
        specimens_dir: Optional[Path] = None
    ) -> "SHPBReanalyzer":
        """Load an existing SHPB test for re-analysis.

        Args:
            test_uri_or_path: Test TTL file path or test URI
            specimens_dir: Base specimens directory (defaults to config.SPECIMENS_DIR)

        Returns:
            self for method chaining

        Raises:
            FileNotFoundError: If test file or data files not found
            ValueError: If test data is invalid
        """
        from dynamat.config import config

        # Resolve specimens directory
        if specimens_dir is None:
            specimens_dir = config.SPECIMENS_DIR
        self._specimens_dir = Path(specimens_dir)

        # Resolve test path
        test_path = Path(test_uri_or_path)
        if not test_path.is_absolute():
            test_path = self._specimens_dir / test_uri_or_path

        if not test_path.exists():
            raise FileNotFoundError(f"Test file not found: {test_path}")

        self._test_ttl_path = test_path
        logger.info(f"Loading test from: {test_path}")

        # Parse TTL file
        self._test_graph = Graph()
        self._test_graph.parse(test_path, format="turtle")

        # Extract test URI
        dyn = Namespace(self.DYN_NS)
        test_uris = list(self._test_graph.subjects(RDF.type, dyn.SHPBCompression))
        if not test_uris:
            raise ValueError(f"No SHPBCompression test found in {test_path}")
        self._test_uri = str(test_uris[0])
        logger.debug(f"Test URI: {self._test_uri}")

        # Load specimen files to get equipment properties
        self.specimen_loader.load_specimen_files(self._specimens_dir)

        # Extract file paths from TTL
        self._extract_file_paths()

        # Load CSV data
        self._load_csv_data()

        # Extract parameters from TTL and ontology
        self._extract_parameters()

        logger.info(f"Test loaded successfully: {self._test_uri}")
        return self

    def _extract_file_paths(self):
        """Extract raw and processed CSV file paths from TTL."""
        dyn = Namespace(self.DYN_NS)
        specimen_dir = self._test_ttl_path.parent

        # Query for raw file path
        raw_query = """
        PREFIX dyn: <https://dynamat.utep.edu/ontology#>
        SELECT ?filePath WHERE {
            ?file a dyn:AnalysisFile ;
                  dyn:hasFilePath ?filePath .
            FILTER(CONTAINS(STR(?filePath), "raw"))
        }
        """
        raw_results = list(self._test_graph.query(raw_query))
        if raw_results:
            raw_rel_path = str(raw_results[0][0])
            self._raw_csv_path = specimen_dir / raw_rel_path
            logger.debug(f"Raw CSV path: {self._raw_csv_path}")

        # Query for processed file path
        proc_query = """
        PREFIX dyn: <https://dynamat.utep.edu/ontology#>
        SELECT ?filePath WHERE {
            ?file a dyn:AnalysisFile ;
                  dyn:hasFilePath ?filePath .
            FILTER(CONTAINS(STR(?filePath), "processed"))
        }
        """
        proc_results = list(self._test_graph.query(proc_query))
        if proc_results:
            proc_rel_path = str(proc_results[0][0])
            self._processed_csv_path = specimen_dir / proc_rel_path
            logger.debug(f"Processed CSV path: {self._processed_csv_path}")

    def _load_csv_data(self):
        """Load raw and processed CSV data."""
        # Load processed CSV (contains aligned pulses)
        if self._processed_csv_path and self._processed_csv_path.exists():
            self._processed_df = pd.read_csv(self._processed_csv_path)
            logger.debug(f"Loaded processed CSV: {self._processed_df.shape}")

            # Extract aligned pulses
            self._aligned_pulses = {
                'time': self._processed_df['time'].values,
                'incident': self._processed_df['incident'].values,
                'transmitted': self._processed_df['transmitted'].values,
                'reflected': self._processed_df['reflected'].values,
            }
        else:
            logger.warning(f"Processed CSV not found: {self._processed_csv_path}")

        # Load raw CSV (for full re-alignment)
        if self._raw_csv_path and self._raw_csv_path.exists():
            self._raw_df = pd.read_csv(self._raw_csv_path)
            logger.debug(f"Loaded raw CSV: {self._raw_df.shape}")
        else:
            logger.warning(f"Raw CSV not found: {self._raw_csv_path}")

    def _extract_parameters(self):
        """Extract analysis parameters from TTL and ontology."""
        dyn = Namespace(self.DYN_NS)
        test_uri = URIRef(self._test_uri)

        # Extract equipment URIs from test
        equipment_query = """
        PREFIX dyn: <https://dynamat.utep.edu/ontology#>
        SELECT ?strikerBar ?incidentBar ?transmissionBar ?incGauge ?trsGauge ?specimen WHERE {
            ?test dyn:hasStrikerBar ?strikerBar ;
                  dyn:hasIncidentBar ?incidentBar ;
                  dyn:hasTransmissionBar ?transmissionBar ;
                  dyn:hasStrainGauge ?incGauge, ?trsGauge ;
                  dyn:performedOn ?specimen .
            FILTER(?incGauge != ?trsGauge)
        }
        """
        equip_results = list(self._test_graph.query(equipment_query))
        if not equip_results:
            raise ValueError("Could not extract equipment URIs from test TTL")

        # Get first result
        result = equip_results[0]
        striker_uri = str(result[0])
        incident_bar_uri = str(result[1])
        transmission_bar_uri = str(result[2])
        specimen_uri = str(result[5])

        # Identify gauges (incident vs transmission based on naming convention)
        gauge1, gauge2 = str(result[3]), str(result[4])
        if '001' in gauge1 or 'INC' in gauge1.upper():
            incident_gauge_uri, transmission_gauge_uri = gauge1, gauge2
        else:
            incident_gauge_uri, transmission_gauge_uri = gauge2, gauge1

        # Get bar properties from ontology
        bar_props = ['hasLength', 'hasDiameter', 'hasCrossSection', 'hasMaterial']
        material_props = ['hasWaveSpeed', 'hasElasticModulus', 'hasDensity']

        def get_bar_with_material(bar_uri):
            """Get bar properties including material properties."""
            props = self.specimen_loader.get_multiple_properties(bar_uri, bar_props)
            material_uri = props.get('hasMaterial')
            if material_uri:
                mat_props = self.specimen_loader.get_multiple_properties(material_uri, material_props)
                props.update({
                    'wave_speed': mat_props.get('hasWaveSpeed'),
                    'elastic_modulus': mat_props.get('hasElasticModulus'),
                    'density': mat_props.get('hasDensity'),
                })
            return props

        striker_props = get_bar_with_material(striker_uri)
        incident_props = get_bar_with_material(incident_bar_uri)
        transmission_props = get_bar_with_material(transmission_bar_uri)

        # Get gauge properties
        gauge_props = ['hasGaugeFactor', 'hasGaugeResistance',
                       'hasCalibrationVoltage', 'hasCalibrationResistance']
        inc_gauge_props = self.specimen_loader.get_multiple_properties(
            incident_gauge_uri, gauge_props)
        trs_gauge_props = self.specimen_loader.get_multiple_properties(
            transmission_gauge_uri, gauge_props)

        # Get specimen properties
        specimen_data = self.specimen_loader.get_specimen_data(specimen_uri)
        specimen_cross_section = specimen_data['dimensions'].get('hasOriginalCrossSection')
        specimen_height = specimen_data['dimensions'].get('hasOriginalHeight')

        # Build parameters dictionary
        self._original_params = {
            'striker_bar': {
                'uri': striker_uri,
                'length': striker_props.get('hasLength'),
                'diameter': striker_props.get('hasDiameter'),
                'cross_section': striker_props.get('hasCrossSection'),
                'wave_speed': striker_props.get('wave_speed'),
                'elastic_modulus': striker_props.get('elastic_modulus'),
                'density': striker_props.get('density'),
            },
            'incident_bar': {
                'uri': incident_bar_uri,
                'length': incident_props.get('hasLength'),
                'diameter': incident_props.get('hasDiameter'),
                'cross_section': incident_props.get('hasCrossSection'),
                'wave_speed': incident_props.get('wave_speed'),
                'elastic_modulus': incident_props.get('elastic_modulus'),
                'density': incident_props.get('density'),
            },
            'transmission_bar': {
                'uri': transmission_bar_uri,
                'length': transmission_props.get('hasLength'),
                'diameter': transmission_props.get('hasDiameter'),
                'cross_section': transmission_props.get('hasCrossSection'),
                'wave_speed': transmission_props.get('wave_speed'),
                'elastic_modulus': transmission_props.get('elastic_modulus'),
                'density': transmission_props.get('density'),
            },
            'specimen': {
                'uri': specimen_uri,
                'cross_section': float(specimen_cross_section) if specimen_cross_section else None,
                'height': float(specimen_height) if specimen_height else None,
            },
            'incident_gauge': {
                'uri': incident_gauge_uri,
                'gauge_factor': inc_gauge_props.get('hasGaugeFactor'),
                'gauge_resistance': inc_gauge_props.get('hasGaugeResistance'),
                'calibration_voltage': inc_gauge_props.get('hasCalibrationVoltage'),
                'calibration_resistance': inc_gauge_props.get('hasCalibrationResistance'),
            },
            'transmission_gauge': {
                'uri': transmission_gauge_uri,
                'gauge_factor': trs_gauge_props.get('hasGaugeFactor'),
                'gauge_resistance': trs_gauge_props.get('hasGaugeResistance'),
                'calibration_voltage': trs_gauge_props.get('hasCalibrationVoltage'),
                'calibration_resistance': trs_gauge_props.get('hasCalibrationResistance'),
            },
            'test_conditions': {
                'striker_velocity': self._get_ttl_value('hasStrikerVelocity'),
            },
        }

        # Extract alignment parameters from TTL
        self._extract_alignment_params()

        # Extract detection parameters from TTL
        self._extract_detection_params()

        # Copy to current params
        self._current_params = copy.deepcopy(self._original_params)

        logger.debug(f"Parameters extracted: {list(self._original_params.keys())}")

    def _get_ttl_value(self, property_name: str) -> Optional[float]:
        """Get a property value from the test TTL."""
        query = f"""
        PREFIX dyn: <https://dynamat.utep.edu/ontology#>
        SELECT ?value WHERE {{
            ?test dyn:{property_name} ?value .
        }}
        """
        results = list(self._test_graph.query(query))
        if results:
            value = results[0][0]
            if hasattr(value, 'toPython'):
                return value.toPython()
            return float(value)
        return None

    def _extract_alignment_params(self):
        """Extract alignment parameters from TTL."""
        alignment_query = """
        PREFIX dyn: <https://dynamat.utep.edu/ontology#>
        SELECT ?kLinear ?weightCorr ?weightU ?weightSR ?weightE
               ?tMin ?tMax ?rMin ?rMax ?shiftT ?shiftR ?nPoints WHERE {
            ?test dyn:hasAlignmentParams ?params .
            OPTIONAL { ?params dyn:hasKLinear ?kLinear }
            OPTIONAL { ?params dyn:hasCorrelationWeight ?weightCorr }
            OPTIONAL { ?params dyn:hasDisplacementWeight ?weightU }
            OPTIONAL { ?params dyn:hasStrainRateWeight ?weightSR }
            OPTIONAL { ?params dyn:hasStrainWeight ?weightE }
            OPTIONAL { ?params dyn:hasTransmittedSearchMin ?tMin }
            OPTIONAL { ?params dyn:hasTransmittedSearchMax ?tMax }
            OPTIONAL { ?params dyn:hasReflectedSearchMin ?rMin }
            OPTIONAL { ?params dyn:hasReflectedSearchMax ?rMax }
            OPTIONAL { ?params dyn:hasTransmittedShiftValue ?shiftT }
            OPTIONAL { ?params dyn:hasReflectedShiftValue ?shiftR }
            OPTIONAL { ?params dyn:hasCenteredSegmentPoints ?nPoints }
        }
        """
        results = list(self._test_graph.query(alignment_query))
        if results:
            r = results[0]
            self._alignment_params = {
                'k_linear': float(r[0]) if r[0] else 0.35,
                'weight_corr': float(r[1]) if r[1] else 0.3,
                'weight_u': float(r[2]) if r[2] else 0.3,
                'weight_sr': float(r[3]) if r[3] else 0.3,
                'weight_e': float(r[4]) if r[4] else 0.1,
                'search_bounds_t': (int(r[5]) if r[5] else None, int(r[6]) if r[6] else None),
                'search_bounds_r': (int(r[7]) if r[7] else None, int(r[8]) if r[8] else None),
                'shift_t': int(r[9]) if r[9] else None,
                'shift_r': int(r[10]) if r[10] else None,
                'n_points': int(r[11]) if r[11] else 25000,
            }
            logger.debug(f"Alignment params: {self._alignment_params}")

        # Extract thresh_ratio from SegmentationParams
        seg_query = """
        PREFIX dyn: <https://dynamat.utep.edu/ontology#>
        SELECT ?thresh WHERE {
            ?test dyn:hasSegmentationParams ?seg .
            OPTIONAL { ?seg dyn:hasSegmentThreshold ?thresh }
        }
        """
        seg_results = list(self._test_graph.query(seg_query))
        if seg_results and seg_results[0][0]:
            self._alignment_params['thresh_ratio'] = float(seg_results[0][0])
        else:
            self._alignment_params.setdefault('thresh_ratio', 0.0)

    def _extract_detection_params(self):
        """Extract pulse detection parameters from TTL."""
        detection_query = """
        PREFIX dyn: <https://dynamat.utep.edu/ontology#>
        SELECT ?type ?pulsePoints ?kTrials ?polarity ?minSep ?lb ?ub ?metric ?start ?end WHERE {
            ?detect a dyn:PulseDetectionParams ;
                    dyn:hasPulsePoints ?pulsePoints .
            OPTIONAL { ?detect dyn:hasKTrials ?kTrials }
            OPTIONAL { ?detect dyn:hasDetectionPolarity ?polarity }
            OPTIONAL { ?detect dyn:hasMinSeparation ?minSep }
            OPTIONAL { ?detect dyn:hasDetectionLowerBound ?lb }
            OPTIONAL { ?detect dyn:hasDetectionUpperBound ?ub }
            OPTIONAL { ?detect dyn:hasSelectionMetric ?metric }
            OPTIONAL { ?detect dyn:hasStartIndex ?start }
            OPTIONAL { ?detect dyn:hasEndIndex ?end }
            BIND(
                IF(CONTAINS(STR(?detect), "inc_detect"), "incident",
                IF(CONTAINS(STR(?detect), "trs_detect"), "transmitted",
                IF(CONTAINS(STR(?detect), "ref_detect"), "reflected", "unknown"))) AS ?type
            )
        }
        """
        results = list(self._test_graph.query(detection_query))
        for r in results:
            detect_type = str(r[0])
            if detect_type in ['incident', 'transmitted', 'reflected']:
                self._detection_params[detect_type] = {
                    'pulse_points': int(r[1]) if r[1] else None,
                    'k_trials': tuple(map(int, str(r[2]).split(','))) if r[2] else (5000, 2000, 1000),
                    'polarity': str(r[3]) if r[3] else 'compressive',
                    'min_separation': int(r[4]) if r[4] else None,
                    'lower_bound': int(r[5]) if r[5] else None,
                    'upper_bound': int(r[6]) if r[6] else None,
                    'metric': str(r[7]) if r[7] else 'median',
                    'window_start': int(r[8]) if r[8] else None,
                    'window_end': int(r[9]) if r[9] else None,
                }
        logger.debug(f"Detection params: {list(self._detection_params.keys())}")

    # ==================== Parameter Updates (Analysis) ====================

    def update_bar_property(
        self,
        bar_type: Literal['striker', 'incident', 'transmission'],
        property_name: str,
        new_value: float
    ) -> "SHPBReanalyzer":
        """Update a bar property for re-analysis.

        Args:
            bar_type: 'striker', 'incident', or 'transmission'
            property_name: 'wave_speed', 'elastic_modulus', 'cross_section', 'density'
            new_value: New value for the property

        Returns:
            self for method chaining
        """
        bar_key = f"{bar_type}_bar"
        if bar_key not in self._current_params:
            raise ValueError(f"Unknown bar type: {bar_type}")

        if property_name not in self._current_params[bar_key]:
            raise ValueError(f"Unknown property: {property_name}")

        old_value = self._current_params[bar_key][property_name]
        self._current_params[bar_key][property_name] = new_value
        logger.info(f"Updated {bar_key}.{property_name}: {old_value} -> {new_value}")
        return self

    def update_specimen_property(
        self,
        property_name: str,
        new_value: float
    ) -> "SHPBReanalyzer":
        """Update a specimen property for re-analysis.

        Args:
            property_name: 'cross_section' or 'height'
            new_value: New value for the property

        Returns:
            self for method chaining
        """
        if property_name not in self._current_params['specimen']:
            raise ValueError(f"Unknown specimen property: {property_name}")

        old_value = self._current_params['specimen'][property_name]
        self._current_params['specimen'][property_name] = new_value
        logger.info(f"Updated specimen.{property_name}: {old_value} -> {new_value}")
        return self

    def update_gauge_property(
        self,
        gauge_type: Literal['incident', 'transmission'],
        property_name: str,
        new_value: float
    ) -> "SHPBReanalyzer":
        """Update a strain gauge property for re-analysis.

        Args:
            gauge_type: 'incident' or 'transmission'
            property_name: 'gauge_factor', 'gauge_resistance', etc.
            new_value: New value for the property

        Returns:
            self for method chaining
        """
        gauge_key = f"{gauge_type}_gauge"
        if gauge_key not in self._current_params:
            raise ValueError(f"Unknown gauge type: {gauge_type}")

        if property_name not in self._current_params[gauge_key]:
            raise ValueError(f"Unknown gauge property: {property_name}")

        old_value = self._current_params[gauge_key][property_name]
        self._current_params[gauge_key][property_name] = new_value
        logger.info(f"Updated {gauge_key}.{property_name}: {old_value} -> {new_value}")
        return self

    def update_test_condition(
        self,
        property_name: str,
        new_value: float
    ) -> "SHPBReanalyzer":
        """Update a test condition for re-analysis.

        Args:
            property_name: 'striker_velocity'
            new_value: New value for the condition

        Returns:
            self for method chaining
        """
        if property_name not in self._current_params['test_conditions']:
            raise ValueError(f"Unknown test condition: {property_name}")

        old_value = self._current_params['test_conditions'][property_name]
        self._current_params['test_conditions'][property_name] = new_value
        logger.info(f"Updated test_conditions.{property_name}: {old_value} -> {new_value}")
        return self

    # ==================== Parameter Updates (Alignment) ====================

    def update_alignment_param(
        self,
        param_name: str,
        new_value
    ) -> "SHPBReanalyzer":
        """Update an alignment parameter for full re-alignment.

        Args:
            param_name: 'k_linear', 'search_bounds_t', 'search_bounds_r',
                       'weight_corr', 'weight_u', 'weight_sr', 'weight_e'
            new_value: New value (tuple for bounds, float for others)

        Returns:
            self for method chaining
        """
        if param_name not in self._alignment_params:
            raise ValueError(f"Unknown alignment parameter: {param_name}")

        old_value = self._alignment_params[param_name]
        self._alignment_params[param_name] = new_value
        logger.info(f"Updated alignment.{param_name}: {old_value} -> {new_value}")
        return self

    # ==================== Inspection ====================

    def get_current_parameters(self) -> Dict[str, Any]:
        """Get the current analysis parameters.

        Returns:
            Dictionary of current parameters (may differ from original)
        """
        return copy.deepcopy(self._current_params)

    def get_original_parameters(self) -> Dict[str, Any]:
        """Get the original analysis parameters as loaded.

        Returns:
            Dictionary of original parameters
        """
        return copy.deepcopy(self._original_params)

    def get_parameter_changes(self) -> Dict[str, Tuple[Any, Any]]:
        """Get differences between original and current parameters.

        Returns:
            Dictionary mapping changed parameter paths to (original, current) tuples
        """
        changes = {}

        def compare_dict(orig, curr, path=""):
            for key in orig:
                current_path = f"{path}.{key}" if path else key
                if isinstance(orig[key], dict) and isinstance(curr.get(key), dict):
                    compare_dict(orig[key], curr[key], current_path)
                elif orig[key] != curr.get(key):
                    changes[current_path] = (orig[key], curr[key])

        compare_dict(self._original_params, self._current_params)
        return changes

    def get_alignment_parameters(self) -> Dict[str, Any]:
        """Get current alignment parameters.

        Returns:
            Dictionary of alignment parameters
        """
        return copy.deepcopy(self._alignment_params)

    # ==================== Execution ====================

    def recalculate(
        self,
        mode: Literal['analysis_only', 'full'] = 'analysis_only'
    ) -> Dict[str, np.ndarray]:
        """Re-run SHPB analysis with current parameters.

        Args:
            mode: 'analysis_only' uses existing aligned pulses (fast)
                  'full' re-runs alignment from raw data

        Returns:
            Dictionary with all calculated series (same format as StressStrainCalculator)
        """
        if mode == 'full':
            return self._recalculate_full()
        else:
            return self._recalculate_analysis_only()

    def _recalculate_analysis_only(self) -> Dict[str, np.ndarray]:
        """Re-run stress-strain calculation using existing aligned pulses."""
        if self._aligned_pulses is None:
            raise ValueError("No aligned pulses loaded. Use load_test() first.")

        logger.info("Running analysis-only recalculation...")

        # Get current parameters
        bar = self._current_params['incident_bar']
        specimen = self._current_params['specimen']

        # Create calculator
        calculator = StressStrainCalculator(
            bar_area=bar['cross_section'],
            bar_wave_speed=bar['wave_speed'],
            bar_elastic_modulus=bar['elastic_modulus'],
            specimen_area=specimen['cross_section'],
            specimen_height=specimen['height'],
            strain_scale_factor=1,  # Already processed in CSV
            use_voltage_input=False,  # CSV has strain values, not voltage
        )

        # Run calculation
        self._results = calculator.calculate(
            incident=self._aligned_pulses['incident'],
            transmitted=self._aligned_pulses['transmitted'],
            reflected=self._aligned_pulses['reflected'],
            time_vector=self._aligned_pulses['time']
        )

        # Calculate equilibrium metrics
        self._metrics = calculator.calculate_equilibrium_metrics(self._results)

        logger.info(f"Recalculation complete. FBC={self._metrics['FBC']:.4f}, "
                   f"DSUF={self._metrics['DSUF']:.4f}")
        return self._results

    def _recalculate_full(self) -> Dict[str, np.ndarray]:
        """Re-run full analysis from raw data including alignment."""
        if self._raw_df is None:
            raise ValueError("No raw data loaded. Use load_test() first or "
                           "ensure raw CSV exists.")

        logger.info("Running full re-alignment and recalculation...")

        # Get current parameters
        bar = self._current_params['incident_bar']
        specimen = self._current_params['specimen']
        inc_gauge = self._current_params['incident_gauge']
        trs_gauge = self._current_params['transmission_gauge']

        # Get alignment parameters
        align = self._alignment_params
        n_pts = align.get('n_points', 25000)
        thresh_ratio = align.get('thresh_ratio', 0.0)

        # Get detection parameters
        inc_detect = self._detection_params.get('incident', {})
        trs_detect = self._detection_params.get('transmitted', {})
        ref_detect = self._detection_params.get('reflected', {})

        # Create detectors
        inc_detector = PulseDetector(
            pulse_points=inc_detect.get('pulse_points', 14768),
            k_trials=inc_detect.get('k_trials', (5000, 2000, 1000)),
            polarity=inc_detect.get('polarity', 'compressive'),
        )

        trs_detector = PulseDetector(
            pulse_points=trs_detect.get('pulse_points', 14768),
            k_trials=trs_detect.get('k_trials', (1500, 1000, 800)),
            polarity=trs_detect.get('polarity', 'compressive'),
        )

        ref_detector = PulseDetector(
            pulse_points=ref_detect.get('pulse_points', 14768),
            k_trials=ref_detect.get('k_trials', (1500, 1000, 500)),
            polarity='tensile',
        )

        # Detect windows
        logger.debug("Detecting pulse windows...")
        inc_window = inc_detector.find_window(
            self._raw_df['incident'].values,
            lower_bound=inc_detect.get('lower_bound'),
            upper_bound=inc_detect.get('upper_bound'),
            metric=inc_detect.get('metric', 'median'),
        )

        trs_window = trs_detector.find_window(
            self._raw_df['transmitted'].values,
            lower_bound=trs_detect.get('lower_bound'),
            upper_bound=trs_detect.get('upper_bound'),
            metric=trs_detect.get('metric', 'median'),
        )

        ref_window = ref_detector.find_window(
            self._raw_df['incident'].values,
            lower_bound=ref_detect.get('lower_bound'),
            upper_bound=ref_detect.get('upper_bound'),
            metric=ref_detect.get('metric', 'median'),
        )

        # Segment and center
        logger.debug("Segmenting and centering pulses...")
        inc_seg = inc_detector.segment_and_center(
            self._raw_df['incident'].values,
            inc_window,
            n_points=n_pts,
            polarity='compressive',
            thresh_ratio=thresh_ratio,
        )

        trs_seg = trs_detector.segment_and_center(
            self._raw_df['transmitted'].values,
            trs_window,
            n_points=n_pts,
            polarity='compressive',
            thresh_ratio=thresh_ratio,
        )

        ref_seg = ref_detector.segment_and_center(
            self._raw_df['incident'].values,
            ref_window,
            n_points=n_pts,
            polarity='tensile',
            thresh_ratio=thresh_ratio,
        )

        # Create time vector
        dt = np.median(np.diff(self._raw_df['time'].values))
        time_seg = np.arange(n_pts) * dt

        # Align pulses
        logger.debug("Running pulse alignment...")
        weights = {
            'corr': align.get('weight_corr', 0.3),
            'u': align.get('weight_u', 0.3),
            'sr': align.get('weight_sr', 0.3),
            'e': align.get('weight_e', 0.1),
        }

        aligner = PulseAligner(
            bar_wave_speed=bar['wave_speed'],
            specimen_height=specimen['height'],
            k_linear=align.get('k_linear', 0.35),
            weights=weights,
        )

        search_bounds_t = align.get('search_bounds_t')
        search_bounds_r = align.get('search_bounds_r')

        inc_aligned, trs_aligned, ref_aligned, shift_t, shift_r = aligner.align(
            incident=inc_seg,
            transmitted=trs_seg,
            reflected=ref_seg,
            time_vector=time_seg,
            search_bounds_t=search_bounds_t if all(search_bounds_t) else None,
            search_bounds_r=search_bounds_r if all(search_bounds_r) else None,
        )

        # Update alignment params with new shifts
        self._alignment_params['shift_t'] = shift_t
        self._alignment_params['shift_r'] = shift_r

        # Center time on rise front
        front_thresh = 0.08
        inc_abs = np.abs(inc_aligned)
        front_idx = np.argmax(inc_abs > front_thresh * inc_abs.max())
        time_aligned = (np.arange(n_pts) - front_idx) * dt

        # Update aligned pulses
        self._aligned_pulses = {
            'time': time_aligned,
            'incident': inc_aligned,
            'transmitted': trs_aligned,
            'reflected': ref_aligned,
        }

        logger.debug(f"Alignment complete. shift_t={shift_t}, shift_r={shift_r}")

        # Now run stress-strain calculation
        # Build gauge params for voltage conversion
        inc_gauge_params = {
            'gauge_res': inc_gauge['gauge_resistance'],
            'gauge_factor': inc_gauge['gauge_factor'],
            'cal_voltage': inc_gauge['calibration_voltage'],
            'cal_resistance': inc_gauge['calibration_resistance'],
        }
        trs_gauge_params = {
            'gauge_res': trs_gauge['gauge_resistance'],
            'gauge_factor': trs_gauge['gauge_factor'],
            'cal_voltage': trs_gauge['calibration_voltage'],
            'cal_resistance': trs_gauge['calibration_resistance'],
        }

        calculator = StressStrainCalculator(
            bar_area=bar['cross_section'],
            bar_wave_speed=bar['wave_speed'],
            bar_elastic_modulus=bar['elastic_modulus'],
            specimen_area=specimen['cross_section'],
            specimen_height=specimen['height'],
            strain_scale_factor=1,
            use_voltage_input=True,
            incident_reflected_gauge_params=inc_gauge_params,
            transmitted_gauge_params=trs_gauge_params,
        )

        # Run calculation
        self._results = calculator.calculate(
            incident=inc_aligned,
            transmitted=trs_aligned,
            reflected=ref_aligned,
            time_vector=time_aligned
        )

        # Calculate equilibrium metrics
        self._metrics = calculator.calculate_equilibrium_metrics(self._results)

        logger.info(f"Full recalculation complete. FBC={self._metrics['FBC']:.4f}, "
                   f"DSUF={self._metrics['DSUF']:.4f}")
        return self._results

    def get_results(self) -> Optional[Dict[str, np.ndarray]]:
        """Get the last calculated results.

        Returns:
            Results dictionary or None if not calculated
        """
        return self._results

    def get_metrics(self) -> Optional[Dict[str, float]]:
        """Get the last calculated equilibrium metrics.

        Returns:
            Metrics dictionary or None if not calculated
        """
        return self._metrics

    # ==================== Output ====================

    def save(
        self,
        version_suffix: str = "_reanalyzed",
        overwrite: bool = False
    ) -> Tuple[Path, Path]:
        """Save re-analyzed results.

        Args:
            version_suffix: Suffix to add to filenames (ignored if overwrite=True)
            overwrite: If True, replace original files

        Returns:
            Tuple of (csv_path, ttl_path) for saved files
        """
        if self._results is None:
            raise ValueError("No results to save. Run recalculate() first.")

        specimen_dir = self._test_ttl_path.parent
        test_name = self._test_ttl_path.stem

        # Determine output paths
        if overwrite:
            csv_path = self._processed_csv_path
            ttl_path = self._test_ttl_path
            logger.warning(f"Overwriting original files: {csv_path}, {ttl_path}")
        else:
            csv_path = specimen_dir / "processed" / f"{test_name}{version_suffix}_processed.csv"
            ttl_path = specimen_dir / f"{test_name}{version_suffix}.ttl"

        # Save processed CSV
        csv_path.parent.mkdir(parents=True, exist_ok=True)
        results_df = pd.DataFrame(self._results)
        results_df.to_csv(csv_path, index=False, float_format='%.6f')
        logger.info(f"Saved processed CSV: {csv_path}")

        # Save TTL with updated parameters
        self._save_ttl(ttl_path, csv_path)
        logger.info(f"Saved TTL: {ttl_path}")

        return csv_path, ttl_path

    def _save_ttl(self, ttl_path: Path, csv_path: Path):
        """Save updated TTL file with re-analysis parameters."""
        # For now, create a simple TTL with reanalysis info
        # A full implementation would update the original TTL structure

        dyn_prefix = f"@prefix dyn: <{self.DYN_NS}> ."
        xsd_prefix = "@prefix xsd: <http://www.w3.org/2001/XMLSchema#> ."

        test_local = self._test_uri.replace(self.DYN_NS, "dyn:")

        # Get parameter changes for documentation
        changes = self.get_parameter_changes()
        changes_str = "; ".join([f"{k}: {v[0]} -> {v[1]}" for k, v in changes.items()])

        # Build TTL content
        ttl_lines = [
            dyn_prefix,
            xsd_prefix,
            "",
            f"# Reanalysis of {test_local}",
            f"# Parameter changes: {changes_str if changes_str else 'None'}",
            "",
            f"{test_local}_reanalysis a dyn:SHPBReanalysis ;",
            f'    dyn:reanalyzedFrom {test_local} ;',
            f'    dyn:hasProcessedDataFile "{csv_path.name}"^^xsd:string ;',
        ]

        # Add equilibrium metrics
        if self._metrics:
            ttl_lines.extend([
                f'    dyn:hasFBC "{self._metrics["FBC"]:.6f}"^^xsd:double ;',
                f'    dyn:hasSEQI "{self._metrics["SEQI"]:.6f}"^^xsd:double ;',
                f'    dyn:hasSOI "{self._metrics["SOI"]:.6f}"^^xsd:double ;',
                f'    dyn:hasDSUF "{self._metrics["DSUF"]:.6f}"^^xsd:double ;',
            ])

        # Add validity assessment
        validity = self.validity_assessor.assess_validity_from_metrics(self._metrics)
        ttl_lines.extend([
            f'    dyn:hasTestValidity {validity["test_validity"]} ;',
            f'    dyn:hasValidityNotes "{validity["validity_notes"]}"^^xsd:string .',
        ])

        # Write file
        with open(ttl_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(ttl_lines))

    def __repr__(self) -> str:
        status = "loaded" if self._test_uri else "not loaded"
        return f"SHPBReanalyzer({status})"
