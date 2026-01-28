"""Tukey Window Page - Apply window function for ML applications."""

import logging
from typing import Optional

import numpy as np

from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGroupBox, QGridLayout, QSlider, QDoubleSpinBox,
    QSplitter, QFrame, QCheckBox
)
from PyQt6.QtCore import Qt

from .base_page import BaseSHPBPage
from .....mechanical.shpb.core.tukey_window import TukeyWindow
from ...base.plot_widget_factory import create_plot_widget

logger = logging.getLogger(__name__)


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

    def _setup_ui(self) -> None:
        """Setup page UI."""
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

        # Enable checkbox
        self.enable_check = QCheckBox("Apply Tukey Window")
        self.enable_check.setChecked(True)
        self.enable_check.stateChanged.connect(self._on_enable_changed)
        params_layout.addWidget(self.enable_check)

        # Alpha parameter
        alpha_group = self._create_group_box("Window Parameter")
        alpha_layout = QGridLayout(alpha_group)

        alpha_layout.addWidget(QLabel("Alpha:"), 0, 0)

        self.alpha_spin = QDoubleSpinBox()
        self.alpha_spin.setRange(0.0, 1.0)
        self.alpha_spin.setValue(0.5)
        self.alpha_spin.setDecimals(2)
        self.alpha_spin.setSingleStep(0.05)
        self.alpha_spin.valueChanged.connect(self._on_alpha_changed)
        alpha_layout.addWidget(self.alpha_spin, 0, 1)

        # Alpha slider
        self.alpha_slider = QSlider(Qt.Orientation.Horizontal)
        self.alpha_slider.setRange(0, 100)
        self.alpha_slider.setValue(50)
        self.alpha_slider.valueChanged.connect(self._on_slider_changed)
        alpha_layout.addWidget(self.alpha_slider, 1, 0, 1, 2)

        # Alpha explanation
        alpha_info = QLabel(
            "alpha = 0.0: Rectangular (no taper)\n"
            "alpha = 0.5: 50% tapered (recommended)\n"
            "alpha = 1.0: Hann window (full taper)"
        )
        alpha_info.setStyleSheet("color: gray; font-size: 10px;")
        alpha_layout.addWidget(alpha_info, 2, 0, 1, 2)

        params_layout.addWidget(alpha_group)

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

    def initializePage(self) -> None:
        """Initialize page when it becomes current."""
        super().initializePage()

        # Restore alpha from state
        self.alpha_spin.setValue(self.state.tukey_alpha)
        self.alpha_slider.setValue(int(self.state.tukey_alpha * 100))

        # If already applied, show results
        if self.state.tapered_pulses:
            self._update_display()

    def validatePage(self) -> bool:
        """Validate before allowing Next.

        Tukey window is optional, so always allow continuing.
        """
        # Save alpha to state
        self.state.tukey_alpha = self.alpha_spin.value()

        # If enabled but not applied, apply now
        if self.enable_check.isChecked() and not self.state.tapered_pulses:
            self._apply_window()

        return True

    def _on_enable_changed(self, state: int) -> None:
        """Handle enable checkbox change."""
        enabled = state == Qt.CheckState.Checked.value
        self.alpha_spin.setEnabled(enabled)
        self.alpha_slider.setEnabled(enabled)

        if not enabled:
            # Clear tapered pulses
            self.state.tapered_pulses = {}
            if self.plot_widget:
                self.plot_widget.clear()
                self.plot_widget.refresh()

    def _on_alpha_changed(self, value: float) -> None:
        """Handle alpha spinbox change."""
        # Update slider (avoid signal loop)
        self.alpha_slider.blockSignals(True)
        self.alpha_slider.setValue(int(value * 100))
        self.alpha_slider.blockSignals(False)

        # Update taper label
        self.taper_label.setText(f"{value * 100:.0f}%")

    def _on_slider_changed(self, value: int) -> None:
        """Handle alpha slider change."""
        alpha = value / 100.0

        # Update spinbox (avoid signal loop)
        self.alpha_spin.blockSignals(True)
        self.alpha_spin.setValue(alpha)
        self.alpha_spin.blockSignals(False)

        # Update taper label
        self.taper_label.setText(f"{value}%")

    def _apply_window(self) -> None:
        """Apply Tukey window to aligned pulses."""
        if not self.enable_check.isChecked():
            self.set_status("Window application disabled")
            return

        self.show_progress()
        self.set_status("Applying Tukey window...")

        try:
            alpha = self.alpha_spin.value()

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
            self.plot_widget.refresh()

        except Exception as e:
            self.logger.error(f"Failed to update plot: {e}")
