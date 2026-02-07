"""Results Page - Calculate and display stress-strain results."""

import logging
from typing import Optional, Dict

import numpy as np

from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGroupBox, QGridLayout, QSplitter, QFrame,
    QTabWidget, QWidget
)
from PyQt6.QtCore import Qt

from .base_page import BaseSHPBPage
from .....mechanical.shpb.core.stress_strain import StressStrainCalculator
from ...base.plotting import create_plot_widget
from ....builders.customizable_form_builder import CustomizableFormBuilder

logger = logging.getLogger(__name__)

DYN_NS = "https://dynamat.utep.edu/ontology#"

# Metric URI to metrics dict key mapping
METRIC_URI_MAP = {
    f"{DYN_NS}hasFBC": "FBC",
    f"{DYN_NS}hasSEQI": "SEQI",
    f"{DYN_NS}hasSOI": "SOI",
    f"{DYN_NS}hasDSUF": "DSUF",
    f"{DYN_NS}hasFBCLoading": "windowed_FBC_loading",
    f"{DYN_NS}hasDSUFLoading": "windowed_DSUF_loading",
    f"{DYN_NS}hasFBCPlateau": "windowed_FBC_plateau",
    f"{DYN_NS}hasDSUFPlateau": "windowed_DSUF_plateau",
    f"{DYN_NS}hasFBCUnloading": "windowed_FBC_unloading",
    f"{DYN_NS}hasDSUFUnloading": "windowed_DSUF_unloading",
}

# Color thresholds for overall metrics
METRIC_THRESHOLDS = {
    "FBC": lambda v: "green" if v > 0.95 else "orange" if v > 0.90 else "red",
    "SEQI": lambda v: "green" if v > 0.90 else "orange" if v > 0.80 else "red",
    "SOI": lambda v: "green" if v < 0.05 else "orange" if v < 0.10 else "red",
    "DSUF": lambda v: "green" if v > 0.98 else "orange" if v > 0.95 else "red",
}


class ResultsPage(BaseSHPBPage):
    """Results calculation page for SHPB analysis.

    Features:
    - Calculate 1-wave and 3-wave stress-strain curves
    - Display equilibrium metrics (ontology-driven)
    - Visualize stress-strain plots
    """

    def __init__(self, state, ontology_manager, qudt_manager=None, parent=None):
        super().__init__(state, ontology_manager, qudt_manager, parent)

        self.setTitle("Analysis Results")
        self.setSubTitle("Calculate stress-strain curves and equilibrium metrics.")

        self.calculator: Optional[StressStrainCalculator] = None

        # Ontology-driven form for metrics
        self.form_builder = CustomizableFormBuilder(ontology_manager)
        self._metrics_form: Optional[QWidget] = None

    def _setup_ui(self) -> None:
        """Setup page UI with ontology-driven metrics form."""
        layout = self._create_base_layout()

        # Create splitter
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left: Metrics and controls
        left_frame = QFrame()
        left_layout = QVBoxLayout(left_frame)

        # Calculate button
        calc_btn = QPushButton("Calculate Results")
        calc_btn.clicked.connect(self._calculate_results)
        left_layout.addWidget(calc_btn)

        # Ontology-driven equilibrium metrics form (read-only)
        METRICS_CLASS = f"{DYN_NS}EquilibriumMetrics"
        self._metrics_form = self.form_builder.build_form(
            METRICS_CLASS, parent=left_frame
        )
        left_layout.addWidget(self._metrics_form)

        # Calculated characteristics (hardcoded for now - future ontology-driven)
        chars_group = self._create_group_box("Calculated Characteristics")
        chars_layout = QGridLayout(chars_group)

        char_labels = [
            ("Peak Stress (1-wave):", "peak_stress_1w"),
            ("Peak Strain (1-wave):", "peak_strain_1w"),
            ("Max Strain Rate:", "max_strain_rate"),
            ("Flow Stress:", "flow_stress"),
        ]

        self.char_labels = {}
        for row, (label, key) in enumerate(char_labels):
            chars_layout.addWidget(QLabel(label), row, 0)
            value_label = QLabel("--")
            self.char_labels[key] = value_label
            chars_layout.addWidget(value_label, row, 1)

        left_layout.addWidget(chars_group)
        left_layout.addStretch()

        splitter.addWidget(left_frame)

        # Right: Plots
        right_frame = QFrame()
        right_layout = QVBoxLayout(right_frame)

        self.plot_tabs = QTabWidget()

        # Stress-strain plot
        try:
            self.stress_strain_plot = create_plot_widget(
                self.ontology_manager,
                self.qudt_manager,
                show_toolbar=True
            )
            self.plot_tabs.addTab(self.stress_strain_plot, "Stress-Strain")
        except Exception as e:
            logger.warning(f"Could not create stress-strain plot: {e}")
            self.stress_strain_plot = None
            self.plot_tabs.addTab(QLabel("Plot unavailable"), "Stress-Strain")

        # Strain rate plot
        try:
            self.strain_rate_plot = create_plot_widget(
                self.ontology_manager,
                self.qudt_manager,
                show_toolbar=True
            )
            self.plot_tabs.addTab(self.strain_rate_plot, "Strain Rate")
        except Exception as e:
            logger.warning(f"Could not create strain rate plot: {e}")
            self.strain_rate_plot = None
            self.plot_tabs.addTab(QLabel("Plot unavailable"), "Strain Rate")

        right_layout.addWidget(self.plot_tabs)
        splitter.addWidget(right_frame)
        splitter.setSizes([350, 650])

        layout.addWidget(splitter)
        self._add_status_area()

    def initializePage(self) -> None:
        """Initialize page when it becomes current."""
        super().initializePage()

        # If results already calculated, show them
        if self.state.has_results():
            self._update_metrics_display()
            self._update_plots()

    def validatePage(self) -> bool:
        """Validate before allowing Next."""
        if not self.state.has_results():
            self.show_warning(
                "Calculation Required",
                "Please calculate results before continuing."
            )
            return False

        return True

    def _calculate_results(self) -> None:
        """Calculate stress-strain results."""
        self.show_progress()
        self.set_status("Calculating stress-strain curves...")

        try:
            # Get equipment properties
            equipment = self.state.equipment_properties
            if not equipment:
                raise ValueError("Equipment properties not available")

            # Get bar properties
            bar_area = equipment.get('incident_bar', {}).get('cross_section')
            bar_wave_speed = equipment.get('incident_bar', {}).get('wave_speed')
            bar_modulus = equipment.get('incident_bar', {}).get('elastic_modulus')

            if not all([bar_area, bar_wave_speed, bar_modulus]):
                raise ValueError("Missing bar properties")

            # Get specimen properties
            specimen_data = self.state.specimen_data or {}

            specimen_area = specimen_data.get(
                f'{DYN_NS}hasOriginalCrossSection'
            )
            specimen_height = specimen_data.get(
                f'{DYN_NS}hasOriginalHeight'
            )

            # Handle measurement dictionaries
            if isinstance(specimen_area, dict):
                specimen_area = specimen_area.get('value')
            if isinstance(specimen_height, dict):
                specimen_height = specimen_height.get('value')

            if not specimen_area or not specimen_height:
                raise ValueError("Missing specimen dimensions")

            # Get aligned pulses
            incident = self.state.aligned_pulses.get('incident')
            transmitted = self.state.aligned_pulses.get('transmitted')
            reflected = self.state.aligned_pulses.get('reflected')
            time_vector = self.state.time_vector

            if incident is None or transmitted is None or reflected is None:
                raise ValueError("Aligned pulses not available")

            # Create calculator
            self.calculator = StressStrainCalculator(
                bar_area=float(bar_area),
                bar_wave_speed=float(bar_wave_speed),
                bar_elastic_modulus=float(bar_modulus),
                specimen_area=float(specimen_area),
                specimen_height=float(specimen_height),
                strain_scale_factor=1e4,  # Assuming voltage input
                use_voltage_input=False
            )

            # Calculate results
            results = self.calculator.calculate(
                incident,
                transmitted,
                reflected,
                time_vector
            )

            # Store results
            self.state.calculation_results = results

            # Calculate equilibrium metrics
            metrics = self.calculator.calculate_equilibrium_metrics(results)
            self.state.equilibrium_metrics = metrics

            # Store calculated characteristics
            self.state.pulse_stress_amplitude = {
                'value': float(np.max(np.abs(results.get('stress_1w', [0])))),
                'unit': 'unit:MegaPA',
                'reference_unit': 'unit:MegaPA'
            }

            self.state.pulse_strain_amplitude = float(np.max(np.abs(results.get('strain_1w', [0]))))

            # Update display
            self._update_metrics_display()
            self._update_plots()

            self.set_status("Calculation completed successfully")
            self.logger.info("Stress-strain calculation completed")

        except Exception as e:
            self.logger.error(f"Calculation failed: {e}")
            self.set_status(f"Error: {e}", is_error=True)
            self.show_error("Calculation Failed", str(e))

        finally:
            self.hide_progress()

    def _update_metrics_display(self) -> None:
        """Update metrics display using ontology form and color coding."""
        metrics = self.state.equilibrium_metrics
        if not metrics:
            return

        # Build form data from metrics dict using URI map
        form_data = {}
        for uri, metric_key in METRIC_URI_MAP.items():
            value = metrics.get(metric_key)
            if value is not None:
                form_data[uri] = value

        # Populate the ontology form with metric values
        self.form_builder.set_form_data(self._metrics_form, form_data)

        # Apply color coding to overall metrics
        self._apply_metric_colors(metrics)

        # Update calculated characteristics
        self._update_characteristics()

    def _apply_metric_colors(self, metrics: Dict[str, float]) -> None:
        """Apply color stylesheets to FBC/SEQI/SOI/DSUF fields based on thresholds."""
        for metric_key, threshold_fn in METRIC_THRESHOLDS.items():
            value = metrics.get(metric_key)
            if value is None:
                continue

            # Find the URI for this metric
            uri = f"{DYN_NS}has{metric_key}"
            form_fields = self._metrics_form.form_fields
            if uri in form_fields:
                color = threshold_fn(value)
                form_fields[uri].widget.setStyleSheet(
                    f"color: {color}; font-weight: bold;"
                )

    def _update_characteristics(self) -> None:
        """Update calculated characteristics labels."""
        results = self.state.calculation_results
        if not results:
            return

        stress_1w = results.get('stress_1w', [])
        strain_1w = results.get('strain_1w', [])
        strain_rate_1w = results.get('strain_rate_1w', [])

        if len(stress_1w) > 0:
            self.char_labels['peak_stress_1w'].setText(f"{np.max(np.abs(stress_1w)):.1f} MPa")

        if len(strain_1w) > 0:
            self.char_labels['peak_strain_1w'].setText(f"{np.max(np.abs(strain_1w)):.4f}")

        if len(strain_rate_1w) > 0:
            self.char_labels['max_strain_rate'].setText(f"{np.max(np.abs(strain_rate_1w)):.0f} /s")

        # Flow stress (simplified: use plateau region)
        if len(stress_1w) > 10:
            mid_start = len(stress_1w) // 4
            mid_end = 3 * len(stress_1w) // 4
            flow = np.mean(np.abs(stress_1w[mid_start:mid_end]))
            self.char_labels['flow_stress'].setText(f"{flow:.1f} MPa")

    def _update_plots(self) -> None:
        """Update plots with results."""
        results = self.state.calculation_results
        if not results:
            return

        # Stress-strain plot
        if self.stress_strain_plot:
            try:
                self.stress_strain_plot.clear()

                strain_1w = results.get('strain_1w', [])
                stress_1w = results.get('stress_1w', [])
                strain_3w = results.get('strain_3w', [])
                stress_3w = results.get('stress_3w', [])

                if len(strain_1w) > 0 and len(stress_1w) > 0:
                    self.stress_strain_plot.add_ontology_trace(
                        np.abs(strain_1w),
                        np.abs(stress_1w),
                        x_series_type_uri='dyn:Strain',
                        y_series_type_uri='dyn:Stress',
                        analysis_method='1-wave',
                        label="1-Wave",
                        color="blue"
                    )

                if len(strain_3w) > 0 and len(stress_3w) > 0:
                    self.stress_strain_plot.add_ontology_trace(
                        np.abs(strain_3w),
                        np.abs(stress_3w),
                        y_series_type_uri='dyn:Stress',
                        analysis_method='3-wave',
                        label="3-Wave",
                        color="red"
                    )

                self.stress_strain_plot.enable_grid()
                self.stress_strain_plot.enable_legend()
                self.stress_strain_plot.refresh()

            except Exception as e:
                self.logger.error(f"Failed to update stress-strain plot: {e}")

        # Strain rate plot
        if self.strain_rate_plot:
            try:
                self.strain_rate_plot.clear()

                time = results.get('time', [])
                strain_rate_1w = results.get('strain_rate_1w', [])

                if len(time) > 0 and len(strain_rate_1w) > 0:
                    self.strain_rate_plot.add_ontology_trace(
                        time,
                        np.abs(strain_rate_1w),
                        x_series_type_uri='dyn:Time',
                        y_series_type_uri='dyn:StrainRate',
                        label="Strain Rate",
                        color="green"
                    )

                self.strain_rate_plot.enable_grid()
                self.strain_rate_plot.enable_legend()
                self.strain_rate_plot.refresh()

            except Exception as e:
                self.logger.error(f"Failed to update strain rate plot: {e}")
