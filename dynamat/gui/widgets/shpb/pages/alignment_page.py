"""Alignment Page - Optimize pulse alignment for equilibrium."""

import logging
from typing import Optional, Dict

import numpy as np

from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGroupBox, QGridLayout, QSpinBox, QDoubleSpinBox,
    QSplitter, QFrame, QTabWidget, QWidget
)
from PyQt6.QtCore import Qt

from .base_page import BaseSHPBPage
from .....mechanical.shpb.core.pulse_alignment import PulseAligner
from ...base.plot_widget_factory import create_plot_widget

logger = logging.getLogger(__name__)


class AlignmentPage(BaseSHPBPage):
    """Pulse alignment page for SHPB analysis.

    Features:
    - Configure alignment weights
    - Set k_linear parameter
    - Define search bounds for shifts
    - Visualize aligned pulses and equilibrium
    """

    def __init__(self, state, ontology_manager, qudt_manager=None, parent=None):
        super().__init__(state, ontology_manager, qudt_manager, parent)

        self.setTitle("Align Pulses")
        self.setSubTitle("Optimize pulse alignment for stress equilibrium.")

        self.aligner: Optional[PulseAligner] = None
        self.plot_tabs: Optional[QTabWidget] = None

    def _setup_ui(self) -> None:
        """Setup page UI."""
        layout = self._create_base_layout()

        # Create splitter
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left: Parameters
        params_frame = QFrame()
        params_layout = QVBoxLayout(params_frame)

        # Alignment parameters
        params_group = self._create_group_box("Alignment Parameters")
        params_grid = QGridLayout(params_group)

        params_grid.addWidget(QLabel("k_linear:"), 0, 0)
        self.k_linear_spin = QDoubleSpinBox()
        self.k_linear_spin.setRange(0.1, 0.9)
        self.k_linear_spin.setValue(0.35)
        self.k_linear_spin.setDecimals(2)
        self.k_linear_spin.setSingleStep(0.05)
        params_grid.addWidget(self.k_linear_spin, 0, 1)

        info = QLabel("Fraction of pulse for linear region detection")
        info.setStyleSheet("color: gray; font-size: 10px;")
        params_grid.addWidget(info, 1, 0, 1, 2)

        params_layout.addWidget(params_group)

        # Weights
        weights_group = self._create_group_box("Fitness Weights")
        weights_grid = QGridLayout(weights_group)

        weight_labels = [
            ("Correlation (corr):", "corr", 0.3),
            ("Displacement (u):", "u", 0.3),
            ("Strain Rate (sr):", "sr", 0.3),
            ("Strain (e):", "e", 0.1),
        ]

        self.weight_spins = {}
        for row, (label, key, default) in enumerate(weight_labels):
            weights_grid.addWidget(QLabel(label), row, 0)
            spin = QDoubleSpinBox()
            spin.setRange(0.0, 1.0)
            spin.setValue(default)
            spin.setDecimals(2)
            spin.setSingleStep(0.05)
            self.weight_spins[key] = spin
            weights_grid.addWidget(spin, row, 1)

        weights_info = QLabel("Weights should sum to ~1.0")
        weights_info.setStyleSheet("color: gray; font-size: 10px;")
        weights_grid.addWidget(weights_info, len(weight_labels), 0, 1, 2)

        params_layout.addWidget(weights_group)

        # Search bounds
        bounds_group = self._create_group_box("Search Bounds (samples)")
        bounds_grid = QGridLayout(bounds_group)

        bounds_grid.addWidget(QLabel("Transmitted Min:"), 0, 0)
        self.t_min_spin = QSpinBox()
        self.t_min_spin.setRange(-5000, 5000)
        self.t_min_spin.setValue(-100)
        bounds_grid.addWidget(self.t_min_spin, 0, 1)

        bounds_grid.addWidget(QLabel("Transmitted Max:"), 1, 0)
        self.t_max_spin = QSpinBox()
        self.t_max_spin.setRange(-5000, 5000)
        self.t_max_spin.setValue(100)
        bounds_grid.addWidget(self.t_max_spin, 1, 1)

        bounds_grid.addWidget(QLabel("Reflected Min:"), 2, 0)
        self.r_min_spin = QSpinBox()
        self.r_min_spin.setRange(-5000, 5000)
        self.r_min_spin.setValue(-100)
        bounds_grid.addWidget(self.r_min_spin, 2, 1)

        bounds_grid.addWidget(QLabel("Reflected Max:"), 3, 0)
        self.r_max_spin = QSpinBox()
        self.r_max_spin.setRange(-5000, 5000)
        self.r_max_spin.setValue(100)
        bounds_grid.addWidget(self.r_max_spin, 3, 1)

        params_layout.addWidget(bounds_group)

        # Align button
        align_btn = QPushButton("Run Alignment")
        align_btn.clicked.connect(self._run_alignment)
        params_layout.addWidget(align_btn)

        # Results
        results_group = self._create_group_box("Alignment Results")
        results_layout = QGridLayout(results_group)

        results_layout.addWidget(QLabel("Transmitted Shift:"), 0, 0)
        self.t_shift_label = QLabel("--")
        results_layout.addWidget(self.t_shift_label, 0, 1)

        results_layout.addWidget(QLabel("Reflected Shift:"), 1, 0)
        self.r_shift_label = QLabel("--")
        results_layout.addWidget(self.r_shift_label, 1, 1)

        results_layout.addWidget(QLabel("Front Index:"), 2, 0)
        self.front_label = QLabel("--")
        results_layout.addWidget(self.front_label, 2, 1)

        results_layout.addWidget(QLabel("Linear Region:"), 3, 0)
        self.linear_label = QLabel("--")
        results_layout.addWidget(self.linear_label, 3, 1)

        params_layout.addWidget(results_group)
        params_layout.addStretch()

        splitter.addWidget(params_frame)

        # Right: Plots
        plot_frame = QFrame()
        plot_layout = QVBoxLayout(plot_frame)

        self.plot_tabs = QTabWidget()

        # Aligned pulses plot
        self.aligned_plot = None
        try:
            self.aligned_plot = create_plot_widget(
                self.ontology_manager,
                self.qudt_manager,
                show_toolbar=True
            )
            self.plot_tabs.addTab(self.aligned_plot, "Aligned Pulses")
        except Exception as e:
            logger.warning(f"Could not create aligned plot: {e}")
            self.plot_tabs.addTab(QLabel("Plot unavailable"), "Aligned Pulses")

        # Equilibrium plot
        self.equilibrium_plot = None
        try:
            self.equilibrium_plot = create_plot_widget(
                self.ontology_manager,
                self.qudt_manager,
                show_toolbar=True
            )
            self.plot_tabs.addTab(self.equilibrium_plot, "Equilibrium Check")
        except Exception as e:
            logger.warning(f"Could not create equilibrium plot: {e}")
            self.plot_tabs.addTab(QLabel("Plot unavailable"), "Equilibrium Check")

        plot_layout.addWidget(self.plot_tabs)
        splitter.addWidget(plot_frame)
        splitter.setSizes([350, 650])

        layout.addWidget(splitter)
        self._add_status_area()

    def initializePage(self) -> None:
        """Initialize page when it becomes current."""
        super().initializePage()

        # Restore parameters from state
        self.k_linear_spin.setValue(self.state.k_linear)

        for key, spin in self.weight_spins.items():
            weight = self.state.alignment_weights.get(key, 0.25)
            spin.setValue(weight)

        if self.state.search_bounds_t:
            self.t_min_spin.setValue(self.state.search_bounds_t[0])
            self.t_max_spin.setValue(self.state.search_bounds_t[1])

        if self.state.search_bounds_r:
            self.r_min_spin.setValue(self.state.search_bounds_r[0])
            self.r_max_spin.setValue(self.state.search_bounds_r[1])

        # If already aligned, show results
        if self.state.has_aligned_pulses():
            self._update_results_display()
            self._update_plots()

    def validatePage(self) -> bool:
        """Validate before allowing Next."""
        if not self.state.has_aligned_pulses():
            self.show_warning(
                "Alignment Required",
                "Please run alignment before continuing."
            )
            return False

        # Save parameters
        self._save_params()

        return True

    def _save_params(self) -> None:
        """Save parameters to state."""
        self.state.k_linear = self.k_linear_spin.value()

        self.state.alignment_weights = {
            key: spin.value() for key, spin in self.weight_spins.items()
        }

        self.state.search_bounds_t = (self.t_min_spin.value(), self.t_max_spin.value())
        self.state.search_bounds_r = (self.r_min_spin.value(), self.r_max_spin.value())

    def _run_alignment(self) -> None:
        """Run pulse alignment optimization."""
        self.show_progress()
        self.set_status("Running alignment optimization...")

        try:
            # Get parameters
            k_linear = self.k_linear_spin.value()
            weights = {key: spin.value() for key, spin in self.weight_spins.items()}
            search_bounds_t = (self.t_min_spin.value(), self.t_max_spin.value())
            search_bounds_r = (self.r_min_spin.value(), self.r_max_spin.value())

            # Get equipment properties
            equipment = self.state.equipment_properties
            if not equipment:
                raise ValueError("Equipment properties not available")

            # Get bar wave speed and specimen height
            bar_wave_speed = equipment.get('incident_bar', {}).get('wave_speed')
            if not bar_wave_speed:
                raise ValueError("Bar wave speed not available")

            # Get specimen height
            specimen_data = self.state.specimen_data or {}
            specimen_height = specimen_data.get(
                'https://dynamat.utep.edu/ontology#hasOriginalHeight'
            )

            if isinstance(specimen_height, dict):
                specimen_height = specimen_height.get('value')

            if not specimen_height:
                raise ValueError("Specimen height not available")

            # Get segmented pulses
            incident = self.state.segmented_pulses.get('incident')
            transmitted = self.state.segmented_pulses.get('transmitted')
            reflected = self.state.segmented_pulses.get('reflected')

            if incident is None or transmitted is None or reflected is None:
                raise ValueError("Segmented pulses not available")

            # Create time vector
            sampling_interval = self.state.sampling_interval or 0.001  # ms
            time_vector = np.arange(len(incident)) * sampling_interval

            # Create aligner
            self.aligner = PulseAligner(
                bar_wave_speed=bar_wave_speed,
                specimen_height=float(specimen_height),
                k_linear=k_linear,
                weights=weights
            )

            # Run alignment
            aligned_inc, aligned_trans, aligned_ref, shift_t, shift_r = self.aligner.align(
                incident,
                transmitted,
                reflected,
                time_vector,
                search_bounds_t=search_bounds_t,
                search_bounds_r=search_bounds_r,
                debug=True
            )

            # Store results
            self.state.aligned_pulses = {
                'incident': aligned_inc,
                'transmitted': aligned_trans,
                'reflected': aligned_ref
            }
            self.state.shift_transmitted = shift_t
            self.state.shift_reflected = shift_r
            self.state.time_vector = time_vector

            # Calculate front index and linear region
            # (These are approximations - actual values come from aligner internals)
            front_thresh = 0.05 * np.max(np.abs(aligned_inc))
            front_idx = np.argmax(np.abs(aligned_inc) > front_thresh)
            self.state.alignment_front_idx = int(front_idx)

            linear_start = front_idx
            linear_end = int(front_idx + k_linear * len(aligned_inc))
            self.state.linear_region = (linear_start, linear_end)

            # Save parameters
            self._save_params()

            # Update display
            self._update_results_display()
            self._update_plots()

            self.set_status("Alignment completed successfully")
            self.logger.info(f"Alignment: shift_t={shift_t}, shift_r={shift_r}")

        except Exception as e:
            self.logger.error(f"Alignment failed: {e}")
            self.set_status(f"Error: {e}", is_error=True)
            self.show_error("Alignment Failed", str(e))

        finally:
            self.hide_progress()

    def _update_results_display(self) -> None:
        """Update results labels."""
        if self.state.shift_transmitted is not None:
            self.t_shift_label.setText(f"{self.state.shift_transmitted:+d} samples")
        else:
            self.t_shift_label.setText("--")

        if self.state.shift_reflected is not None:
            self.r_shift_label.setText(f"{self.state.shift_reflected:+d} samples")
        else:
            self.r_shift_label.setText("--")

        if self.state.alignment_front_idx is not None:
            self.front_label.setText(f"{self.state.alignment_front_idx}")
        else:
            self.front_label.setText("--")

        if self.state.linear_region:
            start, end = self.state.linear_region
            self.linear_label.setText(f"[{start}, {end}]")
        else:
            self.linear_label.setText("--")

    def _update_plots(self) -> None:
        """Update plots with aligned pulses."""
        self._update_aligned_plot()
        self._update_equilibrium_plot()

    def _update_aligned_plot(self) -> None:
        """Update aligned pulses plot."""
        if not self.aligned_plot:
            return

        try:
            self.aligned_plot.clear()

            time = self.state.time_vector
            if time is None:
                return

            pulses = self.state.aligned_pulses
            colors = {
                'incident': 'blue',
                'transmitted': 'red',
                'reflected': 'green'
            }

            for pulse_type, signal in pulses.items():
                if signal is not None:
                    self.aligned_plot.add_trace(
                        time[:len(signal)],
                        signal,
                        label=pulse_type.capitalize(),
                        color=colors.get(pulse_type, 'gray')
                    )

            self.aligned_plot.set_xlabel("Time (ms)")
            self.aligned_plot.set_ylabel("Signal")
            self.aligned_plot.refresh()

        except Exception as e:
            self.logger.error(f"Failed to update aligned plot: {e}")

    def _update_equilibrium_plot(self) -> None:
        """Update equilibrium check plot."""
        if not self.equilibrium_plot:
            return

        try:
            self.equilibrium_plot.clear()

            # Get aligned pulses
            incident = self.state.aligned_pulses.get('incident')
            transmitted = self.state.aligned_pulses.get('transmitted')
            reflected = self.state.aligned_pulses.get('reflected')
            time = self.state.time_vector

            if incident is None or transmitted is None or reflected is None:
                return

            # Calculate equilibrium signals
            # Front face: incident + reflected
            # Back face: transmitted
            front = incident + reflected
            back = transmitted

            self.equilibrium_plot.add_trace(
                time[:len(front)],
                front,
                label="Front Face (I+R)",
                color="blue"
            )

            self.equilibrium_plot.add_trace(
                time[:len(back)],
                back,
                label="Back Face (T)",
                color="red"
            )

            self.equilibrium_plot.set_xlabel("Time (ms)")
            self.equilibrium_plot.set_ylabel("Signal")
            self.equilibrium_plot.refresh()

        except Exception as e:
            self.logger.error(f"Failed to update equilibrium plot: {e}")
