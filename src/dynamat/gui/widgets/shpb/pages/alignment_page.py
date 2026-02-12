"""Alignment Page - Optimize pulse alignment for equilibrium."""

import logging
from typing import Optional, Dict

import numpy as np

from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGroupBox, QGridLayout, QSplitter, QFrame, QTabWidget, QWidget
)
from PyQt6.QtCore import Qt
from rdflib import Graph

from .base_page import BaseSHPBPage
from .....mechanical.shpb.core.pulse_alignment import PulseAligner
from ...base.plotting import create_plot_widget
from ....builders.customizable_form_builder import CustomizableFormBuilder

logger = logging.getLogger(__name__)

DYN_NS = "https://dynamat.utep.edu/ontology#"


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

        # Ontology-driven form
        self.form_builder = CustomizableFormBuilder(ontology_manager)
        self._form_widget: Optional[QWidget] = None

    def _setup_ui(self) -> None:
        """Setup page UI with ontology-driven form."""
        layout = self._create_base_layout()

        # Create splitter
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left: Parameters (ontology-driven form)
        params_frame = QFrame()
        params_layout = QVBoxLayout(params_frame)

        ALIGNMENT_CLASS = f"{DYN_NS}AlignmentParams"
        self._form_widget = self.form_builder.build_form(
            ALIGNMENT_CLASS, parent=params_frame
        )
        params_layout.addWidget(self._form_widget)

        # "Linear Region" display label (not persisted, display-only)
        self.linear_label = QLabel("Linear Region: --")
        self.linear_label.setStyleSheet("color: gray; font-size: 10px;")
        params_layout.addWidget(self.linear_label)

        # Align button
        align_btn = QPushButton("Run Alignment")
        align_btn.clicked.connect(self._run_alignment)
        params_layout.addWidget(align_btn)

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
        self._restore_params()

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

        # Run SHACL validation on partial graph
        validation_graph = self._build_validation_graph()
        if validation_graph and not self._validate_page_data(
            validation_graph, page_key="alignment"
        ):
            return False

        return True

    def _build_validation_graph(self) -> Optional[Graph]:
        """Build partial RDF graph for SHACL validation of alignment data.

        Returns:
            RDF graph with AlignmentParams instance, or None on error.
        """
        if not self.state.alignment_form_data:
            return None

        try:
            return self._build_graph_from_form_data(
                self.state.alignment_form_data,
                f"{DYN_NS}AlignmentParams",
                "_val_alignment",
            )
        except Exception as e:
            self.logger.error(f"Failed to build validation graph: {e}")
            return None

    def _restore_params(self) -> None:
        """Restore parameters from state form data to ontology form."""
        if self.state.alignment_form_data:
            self.form_builder.set_form_data(self._form_widget, self.state.alignment_form_data)

    def _save_params(self) -> None:
        """Save parameters from ontology form to state as form-data dict."""
        self.state.alignment_form_data = self.form_builder.get_form_data(self._form_widget)

    def _run_alignment(self) -> None:
        """Run pulse alignment optimization."""
        self.show_progress()
        self.set_status("Running alignment optimization...")

        try:
            # Get parameters from form
            form_data = self.form_builder.get_form_data(self._form_widget)

            k_linear = form_data.get(f"{DYN_NS}hasKLinear", 0.35)
            weights = {
                'corr': form_data.get(f"{DYN_NS}hasCorrelationWeight", 0.3),
                'u': form_data.get(f"{DYN_NS}hasDisplacementWeight", 0.3),
                'sr': form_data.get(f"{DYN_NS}hasStrainRateWeight", 0.3),
                'e': form_data.get(f"{DYN_NS}hasStrainWeight", 0.1),
            }
            search_bounds_t = (
                form_data.get(f"{DYN_NS}hasTransmittedSearchMin", -100),
                form_data.get(f"{DYN_NS}hasTransmittedSearchMax", 100),
            )
            search_bounds_r = (
                form_data.get(f"{DYN_NS}hasReflectedSearchMin", -100),
                form_data.get(f"{DYN_NS}hasReflectedSearchMax", 100),
            )

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
                f'{DYN_NS}hasOriginalHeight'
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

            # Store aligned pulse arrays
            self.state.aligned_pulses = {
                'incident': aligned_inc,
                'transmitted': aligned_trans,
                'reflected': aligned_ref
            }
            self.state.time_vector = time_vector

            # Calculate front index and linear region
            front_thresh = 0.05 * np.max(np.abs(aligned_inc))
            front_idx = int(np.argmax(np.abs(aligned_inc) > front_thresh))

            linear_start = front_idx
            linear_end = int(front_idx + k_linear * len(aligned_inc))

            # Save form data with injected computed values
            form_data = self.form_builder.get_form_data(self._form_widget)
            form_data[f"{DYN_NS}hasTransmittedShiftValue"] = shift_t
            form_data[f"{DYN_NS}hasReflectedShiftValue"] = shift_r
            form_data[f"{DYN_NS}hasFrontIndex"] = front_idx
            form_data[f"{DYN_NS}hasCenteredSegmentPoints"] = self.state.get_segmentation_param('hasSegmentPoints')
            form_data[f"{DYN_NS}hasThresholdRatio"] = self.state.get_segmentation_param('hasSegmentThreshold')
            self.state.alignment_form_data = form_data

            # Update read-only fields in form display
            result_data = {
                f"{DYN_NS}hasTransmittedShiftValue": shift_t,
                f"{DYN_NS}hasReflectedShiftValue": shift_r,
                f"{DYN_NS}hasFrontIndex": front_idx,
            }
            self.form_builder.set_form_data(self._form_widget, result_data)

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
        """Update display-only linear region label."""
        front_idx = self.state.get_alignment_param('hasFrontIndex')
        k_linear = self.state.get_alignment_param('hasKLinear')
        if front_idx is not None and k_linear is not None:
            incident = self.state.aligned_pulses.get('incident')
            if incident is not None:
                linear_end = int(front_idx + k_linear * len(incident))
                self.linear_label.setText(f"Linear Region: [{front_idx}, {linear_end}]")
                return
        self.linear_label.setText("Linear Region: --")

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
            self.aligned_plot.enable_grid()
            self.aligned_plot.enable_legend()
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
            self.equilibrium_plot.enable_grid()
            self.equilibrium_plot.enable_legend()
            self.equilibrium_plot.refresh()

        except Exception as e:
            self.logger.error(f"Failed to update equilibrium plot: {e}")
