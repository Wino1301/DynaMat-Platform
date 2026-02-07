"""Tukey Window Page - Apply window function for ML applications."""

import logging
from typing import Optional

import numpy as np

from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGroupBox, QGridLayout, QSplitter, QFrame, QWidget
)
from PyQt6.QtCore import Qt

from .base_page import BaseSHPBPage
from .....mechanical.shpb.core.tukey_window import TukeyWindow
from ...base.plotting import create_plot_widget
from ....builders.customizable_form_builder import CustomizableFormBuilder

logger = logging.getLogger(__name__)

DYN_NS = "https://dynamat.utep.edu/ontology#"


class TukeyWindowPage(BaseSHPBPage):
    """Tukey window application page for SHPB analysis.

    Features:
    - Adjustable alpha parameter
    - Before/after visualization
    - Optional application for ML data preparation
    """

    def __init__(self, state, ontology_manager, qudt_manager=None, parent=None):
        super().__init__(state, ontology_manager, qudt_manager, parent)

        self.setTitle("Apply Tukey Window")
        self.setSubTitle("Apply window function to taper pulse edges (optional for ML).")

        self.tukey_window: Optional[TukeyWindow] = None

        # Ontology-driven form
        self.form_builder = CustomizableFormBuilder(ontology_manager)
        self._form_widget: Optional[QWidget] = None

    def _setup_ui(self) -> None:
        """Setup page UI with ontology-driven form."""
        layout = self._create_base_layout()

        # Info label
        info = QLabel(
            "The Tukey window tapers the edges of the signal to zero, "
            "reducing spectral leakage. This is useful for machine learning "
            "applications but is optional for standard SHPB analysis."
        )
        info.setWordWrap(True)
        info.setStyleSheet("color: gray; margin-bottom: 10px;")
        layout.addWidget(info)

        # Create splitter
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left: Parameters
        params_frame = QFrame()
        params_layout = QVBoxLayout(params_frame)

        # Ontology-driven form (checkbox + alpha spinbox)
        TUKEY_CLASS = f"{DYN_NS}TukeyWindowParams"
        self._form_widget = self.form_builder.build_form(
            TUKEY_CLASS, parent=params_frame
        )
        params_layout.addWidget(self._form_widget)

        # Wire enable checkbox to control alpha field enable state
        enable_uri = f"{DYN_NS}isTukeyEnabled"
        if enable_uri in self._form_widget.form_fields:
            enable_field = self._form_widget.form_fields[enable_uri]
            enable_field.widget.stateChanged.connect(self._on_enable_changed)

        # Alpha explanation
        alpha_info = QLabel(
            "alpha = 0.0: Rectangular (no taper)\n"
            "alpha = 0.5: 50% tapered (recommended)\n"
            "alpha = 1.0: Hann window (full taper)"
        )
        alpha_info.setStyleSheet("color: gray; font-size: 10px;")
        params_layout.addWidget(alpha_info)

        # Apply button
        apply_btn = QPushButton("Apply Window")
        apply_btn.clicked.connect(self._apply_window)
        params_layout.addWidget(apply_btn)

        # Results
        results_group = self._create_group_box("Window Statistics")
        results_layout = QGridLayout(results_group)

        results_layout.addWidget(QLabel("Taper Fraction:"), 0, 0)
        self.taper_label = QLabel("--")
        results_layout.addWidget(self.taper_label, 0, 1)

        results_layout.addWidget(QLabel("Energy Ratio:"), 1, 0)
        self.energy_label = QLabel("--")
        results_layout.addWidget(self.energy_label, 1, 1)

        params_layout.addWidget(results_group)
        params_layout.addStretch()

        splitter.addWidget(params_frame)

        # Right: Plot
        plot_frame = QFrame()
        plot_layout = QVBoxLayout(plot_frame)

        try:
            self.plot_widget = create_plot_widget(
                self.ontology_manager,
                self.qudt_manager,
                show_toolbar=True
            )
            plot_layout.addWidget(self.plot_widget)
        except Exception as e:
            logger.warning(f"Could not create plot widget: {e}")
            self.plot_widget = None
            plot_layout.addWidget(QLabel("Plot unavailable"))

        splitter.addWidget(plot_frame)
        splitter.setSizes([300, 700])

        layout.addWidget(splitter)
        self._add_status_area()

    def _is_enabled(self) -> bool:
        """Check if Tukey window is enabled from form."""
        form_data = self.form_builder.get_form_data(self._form_widget)
        return bool(form_data.get(f"{DYN_NS}isTukeyEnabled", True))

    def initializePage(self) -> None:
        """Initialize page when it becomes current."""
        super().initializePage()

        # Restore parameters from state
        self._restore_params()

        # If already applied, show results
        if self.state.tapered_pulses:
            self._update_display()

    def validatePage(self) -> bool:
        """Validate before allowing Next.

        Tukey window is optional, so always allow continuing.
        """
        # Save parameters to state
        self._save_params()

        # If enabled but not applied, apply now
        if self._is_enabled() and not self.state.tapered_pulses:
            self._apply_window()

        return True

    def _restore_params(self) -> None:
        """Restore parameters from state to ontology form."""
        form_data = {
            f"{DYN_NS}isTukeyEnabled": self.state.tukey_enabled,
            f"{DYN_NS}hasTukeyAlphaParam": self.state.tukey_alpha,
        }
        self.form_builder.set_form_data(self._form_widget, form_data)

    def _save_params(self) -> None:
        """Save parameters from ontology form to state."""
        form_data = self.form_builder.get_form_data(self._form_widget)
        self.state.tukey_enabled = bool(form_data.get(f"{DYN_NS}isTukeyEnabled", True))
        self.state.tukey_alpha = form_data.get(f"{DYN_NS}hasTukeyAlphaParam", 0.5)

    def _on_enable_changed(self, state: int) -> None:
        """Handle enable checkbox change."""
        enabled = state == Qt.CheckState.Checked.value

        # Enable/disable alpha field
        alpha_uri = f"{DYN_NS}hasTukeyAlphaParam"
        if alpha_uri in self._form_widget.form_fields:
            self._form_widget.form_fields[alpha_uri].widget.setEnabled(enabled)

        if not enabled:
            # Clear tapered pulses
            self.state.tapered_pulses = {}
            if self.plot_widget:
                self.plot_widget.clear()
                self.plot_widget.refresh()

    def _apply_window(self) -> None:
        """Apply Tukey window to aligned pulses."""
        if not self._is_enabled():
            self.set_status("Window application disabled")
            return

        self.show_progress()
        self.set_status("Applying Tukey window...")

        try:
            form_data = self.form_builder.get_form_data(self._form_widget)
            alpha = form_data.get(f"{DYN_NS}hasTukeyAlphaParam", 0.5)

            # Create Tukey window
            self.tukey_window = TukeyWindow(alpha=alpha)

            # Apply to each aligned pulse
            for pulse_type in ['incident', 'transmitted', 'reflected']:
                aligned = self.state.aligned_pulses.get(pulse_type)
                if aligned is not None:
                    tapered = self.tukey_window.apply(aligned)
                    self.state.tapered_pulses[pulse_type] = tapered

            # Save alpha
            self.state.tukey_alpha = alpha

            # Update taper label
            self.taper_label.setText(f"{alpha * 100:.0f}%")

            # Calculate energy ratio
            if self.state.aligned_pulses.get('incident') is not None:
                original = self.state.aligned_pulses['incident']
                tapered = self.state.tapered_pulses['incident']

                original_energy = np.sum(original ** 2)
                tapered_energy = np.sum(tapered ** 2)

                if original_energy > 0:
                    energy_ratio = tapered_energy / original_energy
                    self.energy_label.setText(f"{energy_ratio:.4f}")

            # Update display
            self._update_display()

            self.set_status("Window applied successfully")
            self.logger.info(f"Applied Tukey window with alpha={alpha}")

        except Exception as e:
            self.logger.error(f"Failed to apply window: {e}")
            self.set_status(f"Error: {e}", is_error=True)
            self.show_error("Window Application Failed", str(e))

        finally:
            self.hide_progress()

    def _update_display(self) -> None:
        """Update plot with before/after comparison."""
        if not self.plot_widget:
            return

        try:
            self.plot_widget.clear()

            time = self.state.time_vector
            if time is None:
                return

            # Plot incident pulse (as example)
            original = self.state.aligned_pulses.get('incident')
            tapered = self.state.tapered_pulses.get('incident')

            if original is not None:
                self.plot_widget.add_trace(
                    time[:len(original)],
                    original,
                    label="Original",
                    color="blue"
                )

            if tapered is not None:
                self.plot_widget.add_trace(
                    time[:len(tapered)],
                    tapered,
                    label="Windowed",
                    color="red"
                )

            # Plot window shape
            if self.tukey_window and original is not None:
                window = self.tukey_window.generate(len(original))
                # Scale window to match signal range for visualization
                scale = np.max(np.abs(original)) if np.max(np.abs(original)) > 0 else 1
                self.plot_widget.add_trace(
                    time[:len(window)],
                    window * scale,
                    label="Window Shape",
                    color="green"
                )

            self.plot_widget.set_xlabel("Time (ms)")
            self.plot_widget.set_ylabel("Signal")
            self.plot_widget.enable_grid()
            self.plot_widget.enable_legend()
            self.plot_widget.refresh()

        except Exception as e:
            self.logger.error(f"Failed to update plot: {e}")
