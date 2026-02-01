"""Equipment Configuration Page - Configure bars and gauges for SHPB analysis."""

import logging
from typing import Optional, Dict, Any, List, Tuple
from datetime import date

from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGroupBox, QGridLayout, QComboBox, QLineEdit,
    QDateEdit, QCheckBox, QScrollArea,
    QWidget, QFrame
)
from PyQt6.QtCore import Qt, QDate

from .base_page import BaseSHPBPage
from .....mechanical.shpb.io.specimen_loader import SpecimenLoader
from .....config import config
from ....base.unit_value_widget import UnitValueWidget

logger = logging.getLogger(__name__)


class EquipmentPage(BaseSHPBPage):
    """Equipment configuration page for SHPB analysis.

    Features:
    - Bar selection (striker, incident, transmission)
    - Gauge selection (incident, transmission)
    - Test conditions (velocity, pressure)
    - Equipment property display
    """

    def __init__(self, state, ontology_manager, qudt_manager=None, parent=None):
        super().__init__(state, ontology_manager, qudt_manager, parent)

        self.setTitle("Configure Equipment")
        self.setSubTitle("Select the SHPB equipment and test conditions.")

        self.specimen_loader: Optional[SpecimenLoader] = None

        # Property metadata cache
        self._property_metadata: Dict[str, Any] = {}
        self._class_metadata = None

    def _setup_ui(self) -> None:
        """Setup page UI."""
        layout = self._create_base_layout()

        # Create scrollable content
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        content = QWidget()
        content_layout = QVBoxLayout(content)

        # Bars section - ontology-driven
        bars_group = self._create_group_box("Pressure Bars")
        bars_layout = QGridLayout(bars_group)

        # Striker Bar
        prop = self._get_property_metadata("https://dynamat.utep.edu/ontology#hasStrikerBar")
        bars_layout.addWidget(QLabel(f"{prop.display_name}:" if prop else "Striker Bar:"), 0, 0)
        self.striker_combo = self._create_equipment_combo(
            "https://dynamat.utep.edu/ontology#hasStrikerBar"
        )
        self.striker_combo.currentIndexChanged.connect(self._on_equipment_changed)
        bars_layout.addWidget(self.striker_combo, 0, 1)

        # Incident Bar
        prop = self._get_property_metadata("https://dynamat.utep.edu/ontology#hasIncidentBar")
        bars_layout.addWidget(QLabel(f"{prop.display_name}:" if prop else "Incident Bar:"), 1, 0)
        self.incident_bar_combo = self._create_equipment_combo(
            "https://dynamat.utep.edu/ontology#hasIncidentBar"
        )
        self.incident_bar_combo.currentIndexChanged.connect(self._on_equipment_changed)
        bars_layout.addWidget(self.incident_bar_combo, 1, 1)

        # Transmission Bar
        prop = self._get_property_metadata("https://dynamat.utep.edu/ontology#hasTransmissionBar")
        bars_layout.addWidget(QLabel(f"{prop.display_name}:" if prop else "Transmission Bar:"), 2, 0)
        self.transmission_bar_combo = self._create_equipment_combo(
            "https://dynamat.utep.edu/ontology#hasTransmissionBar"
        )
        self.transmission_bar_combo.currentIndexChanged.connect(self._on_equipment_changed)
        bars_layout.addWidget(self.transmission_bar_combo, 2, 1)

        content_layout.addWidget(bars_group)

        # Gauges section - ontology-driven
        gauges_group = self._create_group_box("Strain Gauges")
        gauges_layout = QGridLayout(gauges_group)

        # Incident Strain Gauge
        prop = self._get_property_metadata("https://dynamat.utep.edu/ontology#hasIncidentStrainGauge")
        gauges_layout.addWidget(QLabel(f"{prop.display_name}:" if prop else "Incident Gauge:"), 0, 0)
        self.incident_gauge_combo = self._create_equipment_combo(
            "https://dynamat.utep.edu/ontology#hasIncidentStrainGauge"
        )
        self.incident_gauge_combo.currentIndexChanged.connect(self._on_equipment_changed)
        gauges_layout.addWidget(self.incident_gauge_combo, 0, 1)

        # Transmission Strain Gauge
        prop = self._get_property_metadata("https://dynamat.utep.edu/ontology#hasTransmissionStrainGauge")
        gauges_layout.addWidget(QLabel(f"{prop.display_name}:" if prop else "Transmission Gauge:"), 1, 0)
        self.transmission_gauge_combo = self._create_equipment_combo(
            "https://dynamat.utep.edu/ontology#hasTransmissionStrainGauge"
        )
        self.transmission_gauge_combo.currentIndexChanged.connect(self._on_equipment_changed)
        gauges_layout.addWidget(self.transmission_gauge_combo, 1, 1)

        content_layout.addWidget(gauges_group)

        # Optional equipment section - ontology-driven
        optional_group = self._create_group_box("Optional Equipment")
        optional_layout = QGridLayout(optional_group)

        # Momentum Trap
        prop = self._get_property_metadata("https://dynamat.utep.edu/ontology#hasMomentumTrap")
        optional_layout.addWidget(QLabel(f"{prop.display_name}:" if prop else "Momentum Trap:"), 0, 0)
        self.momentum_trap_combo = self._create_equipment_combo(
            "https://dynamat.utep.edu/ontology#hasMomentumTrap",
            placeholder="-- None --"
        )
        optional_layout.addWidget(self.momentum_trap_combo, 0, 1)

        # Pulse Shaper
        prop = self._get_property_metadata("https://dynamat.utep.edu/ontology#hasPulseShaper")
        optional_layout.addWidget(QLabel(f"{prop.display_name}:" if prop else "Pulse Shaper:"), 1, 0)
        self.pulse_shaper_combo = self._create_equipment_combo(
            "https://dynamat.utep.edu/ontology#hasPulseShaper",
            placeholder="-- None --"
        )
        optional_layout.addWidget(self.pulse_shaper_combo, 1, 1)

        content_layout.addWidget(optional_group)

        # Test conditions section - ontology-driven
        conditions_group = self._create_group_box("Test Conditions")
        conditions_layout = QGridLayout(conditions_group)

        # Test Date (no ontology unit)
        conditions_layout.addWidget(QLabel("Test Date:"), 0, 0)
        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDate(QDate.currentDate())
        conditions_layout.addWidget(self.date_edit, 0, 1)

        # Striker Velocity - UnitValueWidget from ontology
        prop = self._get_property_metadata("https://dynamat.utep.edu/ontology#hasStrikerVelocity")
        conditions_layout.addWidget(QLabel(f"{prop.display_name}:" if prop else "Striker Velocity:"), 1, 0)
        self.velocity_widget = self._create_measurement_widget(
            "https://dynamat.utep.edu/ontology#hasStrikerVelocity"
        )
        self.velocity_widget.setRange(0, 100)
        self.velocity_widget.setDecimals(2)
        conditions_layout.addWidget(self.velocity_widget, 1, 1)

        # Launch Pressure - UnitValueWidget from ontology
        prop = self._get_property_metadata("https://dynamat.utep.edu/ontology#hasStrikerLaunchPressure")
        conditions_layout.addWidget(QLabel(f"{prop.display_name}:" if prop else "Launch Pressure:"), 2, 0)
        self.pressure_widget = self._create_measurement_widget(
            "https://dynamat.utep.edu/ontology#hasStrikerLaunchPressure"
        )
        self.pressure_widget.setRange(0, 5000000)
        self.pressure_widget.setDecimals(1)
        conditions_layout.addWidget(self.pressure_widget, 2, 1)

        # Barrel Offset - UnitValueWidget from ontology (NEW FIELD)
        prop = self._get_property_metadata("https://dynamat.utep.edu/ontology#hasBarrelOffset")
        conditions_layout.addWidget(QLabel(f"{prop.display_name}:" if prop else "Barrel Offset:"), 3, 0)
        self.barrel_offset_widget = self._create_measurement_widget(
            "https://dynamat.utep.edu/ontology#hasBarrelOffset"
        )
        self.barrel_offset_widget.setRange(0, 500)
        self.barrel_offset_widget.setDecimals(1)
        conditions_layout.addWidget(self.barrel_offset_widget, 3, 1)

        # Momentum Trap Distance - UnitValueWidget from ontology (NEW FIELD)
        prop = self._get_property_metadata("https://dynamat.utep.edu/ontology#hasMomentumTrapTailoredDistance")
        conditions_layout.addWidget(QLabel(f"{prop.display_name}:" if prop else "Momentum Trap Distance:"), 4, 0)
        self.momentum_trap_distance_widget = self._create_measurement_widget(
            "https://dynamat.utep.edu/ontology#hasMomentumTrapTailoredDistance"
        )
        self.momentum_trap_distance_widget.setRange(0, 1000)
        self.momentum_trap_distance_widget.setDecimals(1)
        conditions_layout.addWidget(self.momentum_trap_distance_widget, 4, 1)

        # Lubrication checkbox (boolean property)
        self.lubrication_check = QCheckBox("Lubrication Applied")
        conditions_layout.addWidget(self.lubrication_check, 5, 0, 1, 2)

        content_layout.addWidget(conditions_group)

        # Equipment properties display
        props_group = self._create_group_box("Equipment Properties")
        props_layout = QGridLayout(props_group)

        # Bar properties
        props_layout.addWidget(QLabel("Bar Wave Speed:"), 0, 0)
        self.wave_speed_label = QLabel("--")
        props_layout.addWidget(self.wave_speed_label, 0, 1)

        props_layout.addWidget(QLabel("Bar Cross Section:"), 1, 0)
        self.cross_section_label = QLabel("--")
        props_layout.addWidget(self.cross_section_label, 1, 1)

        props_layout.addWidget(QLabel("Bar Elastic Modulus:"), 2, 0)
        self.elastic_modulus_label = QLabel("--")
        props_layout.addWidget(self.elastic_modulus_label, 2, 1)

        props_layout.addWidget(QLabel("Incident Gauge Factor:"), 3, 0)
        self.inc_gauge_factor_label = QLabel("--")
        props_layout.addWidget(self.inc_gauge_factor_label, 3, 1)

        props_layout.addWidget(QLabel("Transmission Gauge Factor:"), 4, 0)
        self.trans_gauge_factor_label = QLabel("--")
        props_layout.addWidget(self.trans_gauge_factor_label, 4, 1)

        content_layout.addWidget(props_group)
        content_layout.addStretch()

        scroll.setWidget(content)
        layout.addWidget(scroll)

        self._add_status_area()

    def initializePage(self) -> None:
        """Initialize page when it becomes current."""
        super().initializePage()

        # Initialize specimen loader
        if self.specimen_loader is None:
            self._initialize_specimen_loader()

        # Restore previous selections if any
        self._restore_selections()

        # Update properties display
        self._update_properties_display()

    def validatePage(self) -> bool:
        """Validate before allowing Next."""
        # Check required equipment
        required = [
            ("Striker Bar", self.striker_combo.currentData()),
            ("Incident Bar", self.incident_bar_combo.currentData()),
            ("Transmission Bar", self.transmission_bar_combo.currentData()),
            ("Incident Gauge", self.incident_gauge_combo.currentData()),
            ("Transmission Gauge", self.transmission_gauge_combo.currentData()),
        ]

        missing = [name for name, value in required if not value]

        if missing:
            self.show_warning(
                "Equipment Required",
                f"Please select: {', '.join(missing)}"
            )
            return False

        # Validate test date
        if not self.date_edit.date().isValid():
            self.show_warning("Invalid Date", "Please select a valid test date.")
            return False

        # Save to state
        self._save_to_state()

        # Extract equipment properties
        if not self._extract_equipment_properties():
            self.show_warning(
                "Property Error",
                "Could not extract equipment properties. Please verify selections."
            )
            return False

        return True

    def _initialize_specimen_loader(self) -> None:
        """Initialize the specimen loader for property queries."""
        try:
            self.specimen_loader = SpecimenLoader(self.ontology_manager)

            # Load specimen files if available
            if config.SPECIMENS_DIR.exists():
                self.specimen_loader.load_specimen_files(config.SPECIMENS_DIR)

            self.logger.info("Specimen loader initialized")

        except Exception as e:
            self.logger.error(f"Failed to initialize specimen loader: {e}")

    def _get_class_metadata(self):
        """Get and cache SHPBCompression class metadata from ontology."""
        if self._class_metadata is None:
            try:
                self._class_metadata = self.ontology_manager.get_class_metadata_for_form(
                    "https://dynamat.utep.edu/ontology#SHPBCompression"
                )
                # Build property lookup dict
                for prop in self._class_metadata.properties:
                    self._property_metadata[prop.uri] = prop
            except Exception as e:
                self.logger.error(f"Failed to get class metadata: {e}")
        return self._class_metadata

    def _get_property_metadata(self, property_uri: str):
        """Get property metadata for a specific property."""
        self._get_class_metadata()  # Ensure metadata is loaded
        return self._property_metadata.get(property_uri)

    def _create_equipment_combo(self, property_uri: str, placeholder: str = None) -> QComboBox:
        """Create a combo box for an object property, populated from ontology.

        Reads the range class from property metadata and queries for individuals.
        """
        combo = QComboBox()
        prop_meta = self._get_property_metadata(property_uri)

        if prop_meta and prop_meta.range_class:
            # Use placeholder from ontology display_name or provided
            display_placeholder = placeholder or f"-- Select {prop_meta.display_name} --"
            combo.addItem(display_placeholder, None)

            try:
                individuals = self.ontology_manager.get_available_individuals(prop_meta.range_class)
                for uri, label in individuals:
                    display_name = label or (uri.split('#')[-1] if '#' in uri else uri)
                    combo.addItem(display_name, uri)
            except Exception as e:
                self.logger.warning(f"Failed to load individuals for {prop_meta.range_class}: {e}")
        else:
            combo.addItem(placeholder or "-- Select --", None)

        return combo

    def _create_measurement_widget(self, property_uri: str) -> UnitValueWidget:
        """Create a UnitValueWidget for a measurement property.

        Uses quantity kind and default unit from ontology to populate units.
        """
        prop_meta = self._get_property_metadata(property_uri)

        if prop_meta and prop_meta.compatible_units:
            widget = UnitValueWidget(
                default_unit=prop_meta.default_unit,
                available_units=prop_meta.compatible_units,
                property_uri=prop_meta.uri,
                reference_unit_uri=prop_meta.default_unit
            )
        else:
            # Fallback if ontology query fails
            self.logger.warning(f"No compatible units for {property_uri}")
            widget = UnitValueWidget()

        return widget


    def _on_equipment_changed(self) -> None:
        """Handle equipment selection change."""
        # Update properties display
        self._update_properties_display()

    def _update_properties_display(self) -> None:
        """Update equipment properties display."""
        if not self.specimen_loader:
            return

        try:
            # Get incident bar properties (use for display)
            incident_bar_uri = self.incident_bar_combo.currentData()

            if incident_bar_uri:
                # Get bar properties
                bar_props = self.specimen_loader.get_multiple_properties(
                    incident_bar_uri,
                    ['hasCrossSection', 'hasMaterial']
                )

                cross_section = bar_props.get('hasCrossSection')
                if cross_section:
                    self.cross_section_label.setText(f"{cross_section:.2f} mm²")
                else:
                    self.cross_section_label.setText("--")

                # Get material properties
                material_uri = bar_props.get('hasMaterial')
                if material_uri:
                    mat_props = self.specimen_loader.get_multiple_properties(
                        material_uri,
                        ['hasWaveSpeed', 'hasElasticModulus']
                    )

                    wave_speed = mat_props.get('hasWaveSpeed')
                    elastic_mod = mat_props.get('hasElasticModulus')

                    if wave_speed:
                        self.wave_speed_label.setText(f"{wave_speed:.1f} m/s")
                    else:
                        self.wave_speed_label.setText("--")

                    if elastic_mod:
                        self.elastic_modulus_label.setText(f"{elastic_mod:.1f} GPa")
                    else:
                        self.elastic_modulus_label.setText("--")

            # Get gauge factors
            inc_gauge_uri = self.incident_gauge_combo.currentData()
            trans_gauge_uri = self.transmission_gauge_combo.currentData()

            if inc_gauge_uri:
                gauge_props = self.specimen_loader.get_multiple_properties(
                    inc_gauge_uri, ['hasGaugeFactor']
                )
                gf = gauge_props.get('hasGaugeFactor')
                self.inc_gauge_factor_label.setText(f"{gf:.3f}" if gf else "--")
            else:
                self.inc_gauge_factor_label.setText("--")

            if trans_gauge_uri:
                gauge_props = self.specimen_loader.get_multiple_properties(
                    trans_gauge_uri, ['hasGaugeFactor']
                )
                gf = gauge_props.get('hasGaugeFactor')
                self.trans_gauge_factor_label.setText(f"{gf:.3f}" if gf else "--")
            else:
                self.trans_gauge_factor_label.setText("--")

        except Exception as e:
            self.logger.warning(f"Failed to update properties display: {e}")

    def _restore_selections(self) -> None:
        """Restore previous equipment selections from state."""
        def select_by_uri(combo: QComboBox, uri: Optional[str]):
            if uri:
                for i in range(combo.count()):
                    if combo.itemData(i) == uri:
                        combo.setCurrentIndex(i)
                        return

        # Equipment combos
        select_by_uri(self.striker_combo, self.state.striker_bar_uri)
        select_by_uri(self.incident_bar_combo, self.state.incident_bar_uri)
        select_by_uri(self.transmission_bar_combo, self.state.transmission_bar_uri)
        select_by_uri(self.incident_gauge_combo, self.state.incident_gauge_uri)
        select_by_uri(self.transmission_gauge_combo, self.state.transmission_gauge_uri)
        select_by_uri(self.momentum_trap_combo, self.state.momentum_trap_uri)
        select_by_uri(self.pulse_shaper_combo, self.state.pulse_shaper_uri)

        # Test date
        if self.state.test_date:
            try:
                qdate = QDate.fromString(self.state.test_date, "yyyy-MM-dd")
                if qdate.isValid():
                    self.date_edit.setDate(qdate)
            except:
                pass

        # Measurement widgets - use setData()
        if self.state.striker_velocity:
            self.velocity_widget.setData(self.state.striker_velocity)

        if self.state.striker_launch_pressure:
            self.pressure_widget.setData(self.state.striker_launch_pressure)

        if hasattr(self.state, 'barrel_offset') and self.state.barrel_offset:
            self.barrel_offset_widget.setData(self.state.barrel_offset)

        if hasattr(self.state, 'momentum_trap_distance') and self.state.momentum_trap_distance:
            self.momentum_trap_distance_widget.setData(self.state.momentum_trap_distance)

    def _save_to_state(self) -> None:
        """Save current selections to state."""
        # Equipment URIs
        self.state.striker_bar_uri = self.striker_combo.currentData()
        self.state.incident_bar_uri = self.incident_bar_combo.currentData()
        self.state.transmission_bar_uri = self.transmission_bar_combo.currentData()
        self.state.incident_gauge_uri = self.incident_gauge_combo.currentData()
        self.state.transmission_gauge_uri = self.transmission_gauge_combo.currentData()
        self.state.momentum_trap_uri = self.momentum_trap_combo.currentData()
        self.state.pulse_shaper_uri = self.pulse_shaper_combo.currentData()

        # Test date
        self.state.test_date = self.date_edit.date().toString("yyyy-MM-dd")

        # Measurement widgets - use getData()
        velocity_data = self.velocity_widget.getData()
        if velocity_data.get('value', 0) > 0:
            self.state.striker_velocity = velocity_data

        pressure_data = self.pressure_widget.getData()
        if pressure_data.get('value', 0) > 0:
            self.state.striker_launch_pressure = pressure_data

        barrel_data = self.barrel_offset_widget.getData()
        if barrel_data.get('value', 0) > 0:
            self.state.barrel_offset = barrel_data

        mtrap_data = self.momentum_trap_distance_widget.getData()
        if mtrap_data.get('value', 0) > 0:
            self.state.momentum_trap_distance = mtrap_data

        # Get user
        self.state.user_uri = self.get_current_user()

    def _extract_equipment_properties(self) -> bool:
        """Extract full equipment properties from ontology.

        Returns:
            True if successful, False otherwise
        """
        if not self.specimen_loader:
            self.logger.error("Specimen loader not available")
            return False

        try:
            equipment = {}

            # Extract bar properties
            for bar_type, uri_attr in [
                ('striker_bar', self.state.striker_bar_uri),
                ('incident_bar', self.state.incident_bar_uri),
                ('transmission_bar', self.state.transmission_bar_uri),
            ]:
                if uri_attr:
                    bar_props = self.specimen_loader.get_multiple_properties(
                        uri_attr,
                        ['hasLength', 'hasDiameter', 'hasCrossSection', 'hasMaterial']
                    )

                    equipment[bar_type] = {
                        'uri': uri_attr,
                        'length': bar_props.get('hasLength'),
                        'diameter': bar_props.get('hasDiameter'),
                        'cross_section': bar_props.get('hasCrossSection'),
                        'material_uri': bar_props.get('hasMaterial'),
                    }

                    # Get material properties
                    material_uri = bar_props.get('hasMaterial')
                    if material_uri:
                        mat_props = self.specimen_loader.get_multiple_properties(
                            material_uri,
                            ['hasWaveSpeed', 'hasElasticModulus', 'hasDensity']
                        )
                        equipment[bar_type]['wave_speed'] = mat_props.get('hasWaveSpeed')
                        equipment[bar_type]['elastic_modulus'] = mat_props.get('hasElasticModulus')
                        equipment[bar_type]['density'] = mat_props.get('hasDensity')

            # Extract gauge properties
            for gauge_type, uri_attr in [
                ('incident_gauge', self.state.incident_gauge_uri),
                ('transmission_gauge', self.state.transmission_gauge_uri),
            ]:
                if uri_attr:
                    gauge_props = self.specimen_loader.get_multiple_properties(
                        uri_attr,
                        ['hasGaugeFactor', 'hasGaugeResistance',
                         'hasCalibrationVoltage', 'hasCalibrationResistance',
                         'hasDistanceFromSpecimen']
                    )

                    equipment[gauge_type] = {
                        'uri': uri_attr,
                        'gauge_factor': gauge_props.get('hasGaugeFactor'),
                        'gauge_resistance': gauge_props.get('hasGaugeResistance'),
                        'calibration_voltage': gauge_props.get('hasCalibrationVoltage'),
                        'calibration_resistance': gauge_props.get('hasCalibrationResistance'),
                        'distance_from_specimen': gauge_props.get('hasDistanceFromSpecimen'),
                    }

            self.state.equipment_properties = equipment
            self.logger.info("Equipment properties extracted successfully")
            return True

        except Exception as e:
            self.logger.error(f"Failed to extract equipment properties: {e}")
            return False
