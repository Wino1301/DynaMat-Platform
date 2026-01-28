"""Results Page - Calculate and display stress-strain results."""

import logging
from typing import Optional, Dict

import numpy as np

from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGroupBox, QGridLayout, QSplitter, QFrame,
    QTabWidget, QTableWidget, QTableWidgetItem, QHeaderView
)
from PyQt6.QtCore import Qt

from .base_page import BaseSHPBPage
from .....mechanical.shpb.core.stress_strain import StressStrainCalculator
from ...base.plot_widget_factory import create_plot_widget

logger = logging.getLogger(__name__)


class ResultsPage(BaseSHPBPage):
    """Results calculation page for SHPB analysis.

    Features:
    - Calculate 1-wave and 3-wave stress-strain curves
    - Display equilibrium metrics
    - Visualize stress-strain plots
    """

    def __init__(self, state, ontology_manager, qudt_manager=None, parent=None):
        super().__init__(state, ontology_manager, qudt_manager, parent)

        self.setTitle("Analysis Results")
        self.setSubTitle("Calculate stress-strain curves and equilibrium metrics.")

        self.calculator: Optional[StressStrainCalculator] = None

    def _setup_ui(self) -> None:
        """Setup page UI."""
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

        # Equilibrium metrics
        metrics_group = self._create_group_box("Equilibrium Metrics")
        metrics_layout = QGridLayout(metrics_group)

        metric_labels = [
            ("FBC (Force Balance):", "FBC", "> 0.95"),
            ("SEQI (Stress Equilibrium):", "SEQI", "> 0.90"),
            ("SOI (Strain Offset):", "SOI", "< 0.05"),
            ("DSUF (Uniformity):", "DSUF", "> 0.98"),
        ]

        self.metric_labels = {}
        for row, (label, key, target) in enumerate(metric_labels):
            metrics_layout.addWidget(QLabel(label), row, 0)

            value_label = QLabel("--")
            self.metric_labels[key] = value_label
            metrics_layout.addWidget(value_label, row, 1)

            target_label = QLabel(f"(target {target})")
            target_label.setStyleSheet("color: gray; font-size: 10px;")
            metrics_layout.addWidget(target_label, row, 2)

        left_layout.addWidget(metrics_group)

        # Windowed metrics
        windowed_group = self._create_group_box("Windowed Metrics")
        windowed_layout = QGridLayout(windowed_group)

        windowed_layout.addWidget(QLabel(""), 0, 0)
        windowed_layout.addWidget(QLabel("Loading"), 0, 1)
        windowed_layout.addWidget(QLabel("Plateau"), 0, 2)
        windowed_layout.addWidget(QLabel("Unloading"), 0, 3)

        self.windowed_labels = {}
        for row, metric in enumerate(['FBC', 'DSUF'], start=1):
            windowed_layout.addWidget(QLabel(f"{metric}:"), row, 0)

            for col, phase in enumerate(['loading', 'plateau', 'unloading'], start=1):
                key = f"windowed_{metric}_{phase}"
                label = QLabel("--")
                self.windowed_labels[key] = label
                windowed_layout.addWidget(label, row, col)

        left_layout.addWidget(windowed_group)

        # Calculated characteristics
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
                'https://dynamat.utep.edu/ontology#hasOriginalCrossSection'
            )
            specimen_height = specimen_data.get(
                'https://dynamat.utep.edu/ontology#hasOriginalHeight'
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
        """Update metrics labels."""
        metrics = self.state.equilibrium_metrics
        if not metrics:
            return

        # Main metrics
        metric_map = {
            'FBC': 'FBC',
            'SEQI': 'SEQI',
            'SOI': 'SOI',
            'DSUF': 'DSUF'
        }

        for display_key, metric_key in metric_map.items():
            value = metrics.get(metric_key)
            label = self.metric_labels.get(display_key)
            if label and value is not None:
                # Color code based on quality
                if display_key == 'FBC':
                    color = "green" if value > 0.95 else "orange" if value > 0.90 else "red"
                elif display_key == 'SEQI':
                    color = "green" if value > 0.90 else "orange" if value > 0.80 else "red"
                elif display_key == 'SOI':
                    color = "green" if value < 0.05 else "orange" if value < 0.10 else "red"
                elif display_key == 'DSUF':
                    color = "green" if value > 0.98 else "orange" if value > 0.95 else "red"
                else:
                    color = "black"

                label.setText(f"{value:.4f}")
                label.setStyleSheet(f"color: {color}; font-weight: bold;")

        # Windowed metrics
        for phase in ['loading', 'plateau', 'unloading']:
            for metric in ['FBC', 'DSUF']:
                key = f"windowed_{metric}_{phase}"
                metric_key = f"windowed_{metric}_{phase}"
                value = metrics.get(metric_key)
                label = self.windowed_labels.get(key)
                if label and value is not None:
                    label.setText(f"{value:.3f}")

        # Calculated characteristics
        results = self.state.calculation_results
        if results:
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
                    self.stress_strain_plot.add_trace(
                        np.abs(strain_1w),
                        np.abs(stress_1w),
                        label="1-Wave",
                        color="blue"
                    )

                if len(strain_3w) > 0 and len(stress_3w) > 0:
                    self.stress_strain_plot.add_trace(
                        np.abs(strain_3w),
                        np.abs(stress_3w),
                        label="3-Wave",
                        color="red"
                    )

                self.stress_strain_plot.set_xlabel("Strain")
                self.stress_strain_plot.set_ylabel("Stress (MPa)")
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
                    self.strain_rate_plot.add_trace(
                        time,
                        np.abs(strain_rate_1w),
                        label="Strain Rate",
                        color="green"
                    )

                self.strain_rate_plot.set_xlabel("Time (ms)")
                self.strain_rate_plot.set_ylabel("Strain Rate (/s)")
                self.strain_rate_plot.refresh()

            except Exception as e:
                self.logger.error(f"Failed to update strain rate plot: {e}")
