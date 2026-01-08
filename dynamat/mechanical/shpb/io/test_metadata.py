"""
SHPB Test Metadata - Equipment Property Extraction

Minimal metadata container focused on extracting equipment characteristics
from the ontology for SHPB data pre-processing.

Design philosophy:
- Store only essential test identifiers and equipment URIs
- Provide methods to extract bar material properties from ontology
- Provide methods to extract strain gauge characteristics from ontology
- Additional test conditions (velocity, distances, etc.) added later in workflow
"""

from dataclasses import dataclass
from typing import Dict, Any, Optional
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class SHPBTestMetadata:
    """
    Minimal SHPB test metadata for equipment property extraction.

    Core purpose: Link test to specimen and equipment, then extract
    equipment properties needed for SHPB analysis calculations.

    Required fields (for test identification):
    - test_id: Unique test identifier
    - specimen_uri: URI of specimen being tested
    - test_date: Date of test (YYYY-MM-DD)
    - user: Operator name (converted to User URI)

    Required equipment (URIs to ontology individuals):
    - striker_bar_uri: Striker bar individual
    - incident_bar_uri: Incident bar individual
    - transmission_bar_uri: Transmission bar individual
    - incident_strain_gauge_uri: Incident strain gauge individual
    - transmission_strain_gauge_uri: Transmission strain gauge individual

    Optional equipment (URIs to ontology individuals):
    - momentum_trap_uri: Momentum trap individual (optional)
    - pulse_shaper_uri: Pulse shaper individual (optional)

    Initial test conditions:
    - striker_velocity: Impact velocity of striker bar in m/s (optional)
    - momentum_trap_distance: Distance from specimen to momentum trap in mm (optional)

    Equipment property extraction:
    - Use extract_bar_properties() to get bar dimensions and material properties
    - Use extract_gauge_properties() to get gauge factors and resistance

    Example:
        >>> from dynamat.ontology import OntologyManager
        >>> from dynamat.mechanical.shpb.io import SpecimenLoader
        >>>
        >>> ontology_manager = OntologyManager()
        >>> specimen_loader = SpecimenLoader(ontology_manager)
        >>> specimen_loader.load_specimen_files()
        >>>
        >>> metadata = SHPBTestMetadata(
        ...     test_id="DYNML_A356_00001_SHPB_2025_01_15",
        ...     specimen_uri="dyn:DYNML_A356_00001",
        ...     test_date="2025-01-15",
        ...     user="ErwinCazares",
        ...     striker_bar_uri="dyn:StrikerBar_C350_2ft",
        ...     incident_bar_uri="dyn:IncidentBar_C350_6ft",
        ...     transmission_bar_uri="dyn:TransmissionBar_C350_6ft",
        ...     incident_strain_gauge_uri="dyn:StrainGauge_INC_SG1",
        ...     transmission_strain_gauge_uri="dyn:StrainGauge_TRA_SG1",
        ...     pulse_shaper_uri="dyn:PulseShaper_Cu101_3mm",  # Optional
        ...     striker_velocity=12.5,  # m/s, optional
        ...     momentum_trap_distance=915.0  # mm, optional
        ... )
        >>>
        >>> # Extract equipment properties from ontology
        >>> striker_props = metadata.extract_bar_properties(specimen_loader, 'striker')
        >>> incident_gauge = metadata.extract_gauge_properties(specimen_loader, 'incident')
    """

    # ===== CORE TEST IDENTIFICATION =====
    test_id: str
    specimen_uri: str
    test_date: str
    user: str

    # ===== REQUIRED EQUIPMENT URIs =====
    striker_bar_uri: str
    incident_bar_uri: str
    transmission_bar_uri: str
    incident_strain_gauge_uri: str
    transmission_strain_gauge_uri: str

    # ===== OPTIONAL EQUIPMENT URIs =====
    momentum_trap_uri: Optional[str] = None
    pulse_shaper_uri: Optional[str] = None

    # ===== INITIAL TEST CONDITIONS =====
    striker_velocity: Optional[float] = None  # m/s
    momentum_trap_distance: Optional[float] = None  # mm

    def extract_bar_properties(self, specimen_loader, bar_type: str) -> Dict[str, Any]:
        """
        Extract bar properties from ontology including material characteristics.

        Args:
            specimen_loader: SpecimenLoader instance with loaded ontology
            bar_type: 'striker', 'incident', or 'transmission'

        Returns:
            Dictionary with bar properties:
            {
                'uri': 'dyn:IncidentBar_C350_6ft',
                'length': 1828.8,          # mm
                'diameter': 19.05,         # mm
                'cross_section': 285.024,  # mm²
                'material_uri': 'dyn:C530_Maraging',
                'wave_speed': 5000.0,      # m/s
                'elastic_modulus': None    # GPa (if available)
            }

        Example:
            >>> striker_props = metadata.extract_bar_properties(specimen_loader, 'striker')
            >>> print(f"Wave speed: {striker_props['wave_speed']} m/s")
            >>> print(f"Cross-section: {striker_props['cross_section']} mm²")
        """
        # Map bar type to URI attribute
        bar_uri_map = {
            'striker': self.striker_bar_uri,
            'incident': self.incident_bar_uri,
            'transmission': self.transmission_bar_uri
        }

        if bar_type not in bar_uri_map:
            raise ValueError(f"Invalid bar_type '{bar_type}'. Must be 'striker', 'incident', or 'transmission'")

        bar_uri = bar_uri_map[bar_type]

        # Extract bar properties
        bar_props = specimen_loader.get_multiple_properties(
            bar_uri,
            ['hasLength', 'hasDiameter', 'hasCrossSection', 'hasMaterial']
        )

        # Extract material properties
        material_uri = bar_props.get('hasMaterial')
        wave_speed = None
        elastic_modulus = None
        density = None

        if material_uri:
            material_props = specimen_loader.get_multiple_properties(
                material_uri,
                ['hasWaveSpeed', 'hasElasticModulus', 'hasDensity']
            )
            wave_speed = material_props.get('hasWaveSpeed', None)
            elastic_modulus = material_props.get('hasElasticModulus', None)
            density = material_props.get('hasDensity', None)

        result = {
            'uri': bar_uri,
            'length': bar_props.get('hasLength'),
            'diameter': bar_props.get('hasDiameter'),
            'cross_section': bar_props.get('hasCrossSection'),
            'material_uri': material_uri,
            'wave_speed': wave_speed,
            'elastic_modulus': elastic_modulus,
            'density': density
        }

        logger.debug(f"Extracted {bar_type} bar properties: {result}")
        return result

    def extract_gauge_properties(self, specimen_loader, gauge_type: str) -> Dict[str, Any]:
        """
        Extract strain gauge properties from ontology.

        Args:
            specimen_loader: SpecimenLoader instance with loaded ontology
            gauge_type: 'incident' or 'transmission'

        Returns:
            Dictionary with gauge properties:
            {
                'uri': 'dyn:StrainGauge_INC_SG1',
                'gauge_factor': 2.12,
                'gauge_resistance': 350.0,    # Ω
                'distance_from_specimen': None  # mm (if defined on gauge)
            }

        Example:
            >>> incident_gauge = metadata.extract_gauge_properties(specimen_loader, 'incident')
            >>> print(f"Gauge factor: {incident_gauge['gauge_factor']}")
            >>> print(f"Resistance: {incident_gauge['gauge_resistance']} Ω")
        """
        # Map gauge type to URI attribute
        gauge_uri_map = {
            'incident': self.incident_strain_gauge_uri,
            'transmission': self.transmission_strain_gauge_uri
        }

        if gauge_type not in gauge_uri_map:
            raise ValueError(f"Invalid gauge_type '{gauge_type}'. Must be 'incident' or 'transmission'")

        gauge_uri = gauge_uri_map[gauge_type]

        # Extract gauge properties
        gauge_props = specimen_loader.get_multiple_properties(
            gauge_uri,
            ['hasGaugeFactor', 'hasGaugeResistance', 'hasCalibrationVoltage',
             'hasCalibrationResistance', 'hasDistanceFromSpecimen']
        )

        result = {
            'uri': gauge_uri,
            'gauge_factor': gauge_props.get('hasGaugeFactor'),
            'gauge_resistance': gauge_props.get('hasGaugeResistance'),
            'calibration_voltage': gauge_props.get('hasCalibrationVoltage'),
            'calibration_resistance': gauge_props.get('hasCalibrationResistance'),
            'distance_from_specimen': gauge_props.get('hasDistanceFromSpecimen')
        }

        logger.debug(f"Extracted {gauge_type} gauge properties: {result}")
        return result

    def extract_all_equipment_properties(self, specimen_loader) -> Dict[str, Any]:
        """
        Extract all equipment properties in one call.

        Args:
            specimen_loader: SpecimenLoader instance with loaded ontology

        Returns:
            Dictionary with all equipment properties:
            {
                'striker_bar': {...},
                'incident_bar': {...},
                'transmission_bar': {...},
                'incident_gauge': {...},
                'transmission_gauge': {...}
            }

        Example:
            >>> equipment = metadata.extract_all_equipment_properties(specimen_loader)
            >>> bar_cross_section = equipment['incident_bar']['cross_section']
            >>> bar_wave_speed = equipment['incident_bar']['wave_speed']
            >>> gauge_factor = equipment['incident_gauge']['gauge_factor']
        """
        equipment = {
            'striker_bar': self.extract_bar_properties(specimen_loader, 'striker'),
            'incident_bar': self.extract_bar_properties(specimen_loader, 'incident'),
            'transmission_bar': self.extract_bar_properties(specimen_loader, 'transmission'),
            'incident_gauge': self.extract_gauge_properties(specimen_loader, 'incident'),
            'transmission_gauge': self.extract_gauge_properties(specimen_loader, 'transmission')
        }

        logger.info(f"Extracted all equipment properties for test {self.test_id}")
        return equipment

    def to_form_data(self) -> Dict[str, Any]:
        """
        Convert to minimal form data for InstanceWriter.

        Returns core test identification, equipment URIs, and initial test conditions.
        Additional test conditions (bar lengths, pulse characteristics, etc.) should be
        added separately in the workflow after analysis.

        Returns:
            Dict with core properties mapped to ontology URIs

        Example:
            >>> form_data = metadata.to_form_data()
            >>> # Initial test conditions already included if provided
            >>> # Add additional properties after analysis before saving
            >>> form_data['dyn:hasIncidentStrainGaugeDistance'] = 915.0
            >>> form_data['dyn:hasPulseDuration'] = 150.0
        """
        form_data = {}

        # Core test identification
        form_data['dyn:hasTestID'] = self.test_id
        form_data['dyn:performedOn'] = self.specimen_uri
        form_data['dyn:hasTestDate'] = self.test_date

        # Convert user name to User URI
        if self.user.startswith('dyn:User_'):
            form_data['dyn:hasUser'] = self.user
        else:
            form_data['dyn:hasUser'] = f"dyn:User_{self.user}"

        # Equipment URIs
        form_data['dyn:hasStrikerBar'] = self.striker_bar_uri
        form_data['dyn:hasIncidentBar'] = self.incident_bar_uri
        form_data['dyn:hasTransmissionBar'] = self.transmission_bar_uri

        # Optional equipment URIs
        if self.momentum_trap_uri:
            form_data['dyn:hasMomentumTrap'] = self.momentum_trap_uri
        if self.pulse_shaper_uri:
            form_data['dyn:hasPulseShaper'] = self.pulse_shaper_uri

        # Strain gauges (multiple values)
        form_data['dyn:hasStrainGauge'] = [
            self.incident_strain_gauge_uri,
            self.transmission_strain_gauge_uri
        ]

        # Initial test conditions (if provided)
        if self.striker_velocity is not None:
            form_data['dyn:hasStrikerVelocity'] = self.striker_velocity
        if self.momentum_trap_distance is not None:
            form_data['dyn:hasMomentumTrapTailoredDistance'] = self.momentum_trap_distance

        logger.debug(f"Created minimal form_data with {len(form_data)} core properties")
        return form_data

    def validate(self):
        """
        Validate required fields.

        Raises:
            ValueError: If any required field is missing or invalid

        Example:
            >>> metadata = SHPBTestMetadata(...)
            >>> metadata.validate()
        """
        # Check required fields are not empty
        required_fields = [
            ('test_id', self.test_id),
            ('specimen_uri', self.specimen_uri),
            ('test_date', self.test_date),
            ('user', self.user),
            ('striker_bar_uri', self.striker_bar_uri),
            ('incident_bar_uri', self.incident_bar_uri),
            ('transmission_bar_uri', self.transmission_bar_uri),
            ('incident_strain_gauge_uri', self.incident_strain_gauge_uri),
            ('transmission_strain_gauge_uri', self.transmission_strain_gauge_uri),
        ]

        for field_name, value in required_fields:
            if not value:
                raise ValueError(f"Required field '{field_name}' is missing or empty")

        # Validate date format
        try:
            datetime.strptime(self.test_date, "%Y-%m-%d")
        except ValueError:
            raise ValueError(f"test_date must be in YYYY-MM-DD format, got: {self.test_date}")

        # Validate URIs
        uri_fields = [
            ('specimen_uri', self.specimen_uri),
            ('striker_bar_uri', self.striker_bar_uri),
            ('incident_bar_uri', self.incident_bar_uri),
            ('transmission_bar_uri', self.transmission_bar_uri),
            ('incident_strain_gauge_uri', self.incident_strain_gauge_uri),
            ('transmission_strain_gauge_uri', self.transmission_strain_gauge_uri),
        ]

        for field_name, uri in uri_fields:
            if not (uri.startswith('dyn:') or uri.startswith('http')):
                raise ValueError(f"{field_name} must be a valid URI (dyn: or http), got: {uri}")

        # Validate optional URIs if provided
        optional_uri_fields = [
            ('momentum_trap_uri', self.momentum_trap_uri),
            ('pulse_shaper_uri', self.pulse_shaper_uri),
        ]

        for field_name, uri in optional_uri_fields:
            if uri and not (uri.startswith('dyn:') or uri.startswith('http')):
                raise ValueError(f"{field_name} must be a valid URI (dyn: or http), got: {uri}")

        # Validate test conditions if provided
        if self.striker_velocity is not None:
            if self.striker_velocity <= 0:
                raise ValueError(f"striker_velocity must be positive, got: {self.striker_velocity}")

        if self.momentum_trap_distance is not None:
            if self.momentum_trap_distance <= 0:
                raise ValueError(f"momentum_trap_distance must be positive, got: {self.momentum_trap_distance}")

        logger.info(f"SHPBTestMetadata validation passed for test_id: {self.test_id}")
