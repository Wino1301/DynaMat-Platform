"""Export Page - Save SHPB test results to RDF."""

import logging
from typing import Optional
from datetime import datetime

from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGroupBox, QGridLayout, QLineEdit, QComboBox,
    QTextEdit, QCheckBox, QScrollArea, QWidget, QFrame
)
from PyQt6.QtCore import Qt

from .base_page import BaseSHPBPage
from .....mechanical.shpb.io.test_metadata import SHPBTestMetadata
from .....mechanical.shpb.io.shpb_test_writer import SHPBTestWriter
from .....config import config

logger = logging.getLogger(__name__)


class ExportPage(BaseSHPBPage):
    """Export page for SHPB analysis.

    Features:
    - Auto-generate or customize test ID
    - Set test type (specimen, calibration, elastic)
    - Display validity assessment
    - Override validity if needed
    - Export to RDF/TTL
    """

    def __init__(self, state, ontology_manager, qudt_manager=None, parent=None):
        super().__init__(state, ontology_manager, qudt_manager, parent)

        self.setTitle("Export Test")
        self.setSubTitle("Review and save the SHPB test results.")

        self.test_writer: Optional[SHPBTestWriter] = None

    def _setup_ui(self) -> None:
        """Setup page UI."""
        layout = self._create_base_layout()

        # Create scrollable content
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        content = QWidget()
        content_layout = QVBoxLayout(content)

        # Test identification
        id_group = self._create_group_box("Test Identification")
        id_layout = QGridLayout(id_group)

        id_layout.addWidget(QLabel("Test ID:"), 0, 0)
        self.test_id_edit = QLineEdit()
        self.test_id_edit.setPlaceholderText("Auto-generated if empty")
        id_layout.addWidget(self.test_id_edit, 0, 1)

        generate_btn = QPushButton("Generate")
        generate_btn.clicked.connect(self._generate_test_id)
        id_layout.addWidget(generate_btn, 0, 2)

        id_layout.addWidget(QLabel("Test Type:"), 1, 0)
        self.test_type_combo = QComboBox()
        self.test_type_combo.addItem("Specimen Test", "specimen")
        self.test_type_combo.addItem("Calibration Test", "calibration")
        self.test_type_combo.addItem("Elastic Test", "elastic")
        id_layout.addWidget(self.test_type_combo, 1, 1, 1, 2)

        content_layout.addWidget(id_group)

        # Validity assessment
        validity_group = self._create_group_box("Validity Assessment")
        validity_layout = QGridLayout(validity_group)

        validity_layout.addWidget(QLabel("Assessed Validity:"), 0, 0)
        self.validity_label = QLabel("--")
        self.validity_label.setStyleSheet("font-weight: bold;")
        validity_layout.addWidget(self.validity_label, 0, 1)

        validity_layout.addWidget(QLabel("Criteria Met:"), 1, 0)
        self.criteria_label = QLabel("--")
        self.criteria_label.setWordWrap(True)
        validity_layout.addWidget(self.criteria_label, 1, 1)

        validity_layout.addWidget(QLabel("Notes:"), 2, 0)
        self.notes_edit = QTextEdit()
        self.notes_edit.setMaximumHeight(80)
        self.notes_edit.setPlaceholderText("Auto-generated validity notes...")
        validity_layout.addWidget(self.notes_edit, 2, 1)

        # Override section
        self.override_check = QCheckBox("Override Validity Assessment")
        self.override_check.stateChanged.connect(self._on_override_changed)
        validity_layout.addWidget(self.override_check, 3, 0, 1, 2)

        validity_layout.addWidget(QLabel("Override To:"), 4, 0)
        self.override_combo = QComboBox()
        self.override_combo.addItem("Valid Test", "dyn:ValidTest")
        self.override_combo.addItem("Questionable Test", "dyn:QuestionableTest")
        self.override_combo.addItem("Invalid Test", "dyn:InvalidTest")
        self.override_combo.setEnabled(False)
        validity_layout.addWidget(self.override_combo, 4, 1)

        validity_layout.addWidget(QLabel("Override Reason:"), 5, 0)
        self.override_reason_edit = QLineEdit()
        self.override_reason_edit.setEnabled(False)
        self.override_reason_edit.setPlaceholderText("Reason for override...")
        validity_layout.addWidget(self.override_reason_edit, 5, 1)

        content_layout.addWidget(validity_group)

        # Summary
        summary_group = self._create_group_box("Test Summary")
        summary_layout = QGridLayout(summary_group)

        summary_items = [
            ("Specimen:", "specimen"),
            ("Test Date:", "date"),
            ("Equipment:", "equipment"),
            ("Peak Stress:", "stress"),
            ("Peak Strain:", "strain"),
            ("FBC Metric:", "fbc"),
        ]

        self.summary_labels = {}
        for row, (label, key) in enumerate(summary_items):
            summary_layout.addWidget(QLabel(label), row, 0)
            value_label = QLabel("--")
            self.summary_labels[key] = value_label
            summary_layout.addWidget(value_label, row, 1)

        content_layout.addWidget(summary_group)

        # Output path
        output_group = self._create_group_box("Output")
        output_layout = QGridLayout(output_group)

        output_layout.addWidget(QLabel("Output File:"), 0, 0)
        self.output_label = QLabel("--")
        self.output_label.setWordWrap(True)
        self.output_label.setStyleSheet("color: gray;")
        output_layout.addWidget(self.output_label, 0, 1)

        content_layout.addWidget(output_group)

        scroll.setWidget(content)
        layout.addWidget(scroll)

        self._add_status_area()

    def initializePage(self) -> None:
        """Initialize page when it becomes current."""
        super().initializePage()

        # Auto-generate test ID if not set
        if not self.state.test_id:
            self._generate_test_id()
        else:
            self.test_id_edit.setText(self.state.test_id)

        # Assess validity from metrics
        self._assess_validity()

        # Update summary
        self._update_summary()

        # Update output path
        self._update_output_path()

    def validatePage(self) -> bool:
        """Validate and export test."""
        # Get test ID
        test_id = self.test_id_edit.text().strip()
        if not test_id:
            self._generate_test_id()
            test_id = self.test_id_edit.text().strip()

        if not test_id:
            self.show_warning("Test ID Required", "Please enter or generate a test ID.")
            return False

        # Save to state
        self.state.test_id = test_id
        self.state.test_type = self.test_type_combo.currentData()
        self.state.validity_notes = self.notes_edit.toPlainText()

        # Handle override
        if self.override_check.isChecked():
            self.state.validity_override = True
            self.state.test_validity = self.override_combo.currentData()
            self.state.validity_override_reason = self.override_reason_edit.text()

        # Export test
        return self._export_test()

    def _generate_test_id(self) -> None:
        """Generate a unique test ID."""
        specimen_id = self.state.specimen_id or "UNKNOWN"
        date_str = self.state.test_date or datetime.now().strftime("%Y%m%d")
        date_str = date_str.replace("-", "")

        # Simple counter-based approach
        test_id = f"{specimen_id}_SHPB_{date_str}"

        self.test_id_edit.setText(test_id)
        self.state.test_id = test_id

        self._update_output_path()

    def _assess_validity(self) -> None:
        """Assess test validity from metrics."""
        metrics = self.state.equilibrium_metrics
        if not metrics:
            self.validity_label.setText("Cannot assess - no metrics")
            self.validity_label.setStyleSheet("color: gray; font-weight: bold;")
            return

        # Use SHPBTestMetadata's validity assessment
        try:
            # Create temporary metadata for assessment
            temp_metadata = SHPBTestMetadata(
                test_id="temp",
                specimen_uri=self.state.specimen_uri or "",
                test_date=self.state.test_date or datetime.now().strftime("%Y-%m-%d"),
                user=self.state.user_uri or "",
                striker_bar_uri=self.state.striker_bar_uri or "",
                incident_bar_uri=self.state.incident_bar_uri or "",
                transmission_bar_uri=self.state.transmission_bar_uri or "",
                incident_strain_gauge_uri=self.state.incident_gauge_uri or "",
                transmission_strain_gauge_uri=self.state.transmission_gauge_uri or ""
            )

            temp_metadata.assess_validity_from_metrics(metrics)

            self.state.test_validity = temp_metadata.test_validity
            self.state.validity_notes = temp_metadata.validity_notes
            self.state.validity_criteria = temp_metadata.validity_criteria

            # Update display
            validity = temp_metadata.test_validity
            if validity == "dyn:ValidTest":
                self.validity_label.setText("VALID")
                self.validity_label.setStyleSheet("color: green; font-weight: bold;")
            elif validity == "dyn:QuestionableTest":
                self.validity_label.setText("QUESTIONABLE")
                self.validity_label.setStyleSheet("color: orange; font-weight: bold;")
            else:
                self.validity_label.setText("INVALID")
                self.validity_label.setStyleSheet("color: red; font-weight: bold;")

            # Criteria
            criteria = temp_metadata.validity_criteria or []
            criteria_text = ", ".join([c.replace("dyn:", "") for c in criteria]) or "None"
            self.criteria_label.setText(criteria_text)

            # Notes
            self.notes_edit.setText(temp_metadata.validity_notes or "")

        except Exception as e:
            self.logger.error(f"Failed to assess validity: {e}")
            self.validity_label.setText("Assessment Error")
            self.validity_label.setStyleSheet("color: red; font-weight: bold;")

    def _on_override_changed(self, state: int) -> None:
        """Handle override checkbox change."""
        enabled = state == Qt.CheckState.Checked.value
        self.override_combo.setEnabled(enabled)
        self.override_reason_edit.setEnabled(enabled)

    def _update_summary(self) -> None:
        """Update test summary display."""
        # Specimen
        self.summary_labels['specimen'].setText(self.state.specimen_id or "--")

        # Date
        self.summary_labels['date'].setText(self.state.test_date or "--")

        # Equipment (simplified)
        if self.state.incident_bar_uri:
            bar_name = self.state.incident_bar_uri.split('#')[-1] if '#' in self.state.incident_bar_uri else self.state.incident_bar_uri
            self.summary_labels['equipment'].setText(bar_name)
        else:
            self.summary_labels['equipment'].setText("--")

        # Results
        results = self.state.calculation_results
        if results:
            import numpy as np
            stress_1w = results.get('stress_1w', [])
            strain_1w = results.get('strain_1w', [])

            if len(stress_1w) > 0:
                self.summary_labels['stress'].setText(f"{np.max(np.abs(stress_1w)):.1f} MPa")
            if len(strain_1w) > 0:
                self.summary_labels['strain'].setText(f"{np.max(np.abs(strain_1w)):.4f}")

        # FBC
        metrics = self.state.equilibrium_metrics
        if metrics:
            fbc = metrics.get('FBC', 0)
            self.summary_labels['fbc'].setText(f"{fbc:.4f}")

    def _update_output_path(self) -> None:
        """Update output path display."""
        test_id = self.test_id_edit.text().strip()
        specimen_id = self.state.specimen_id

        if test_id and specimen_id:
            output_path = config.SPECIMENS_DIR / specimen_id / f"{test_id}.ttl"
            self.output_label.setText(str(output_path))
        else:
            self.output_label.setText("(will be determined on export)")

    def _export_test(self) -> bool:
        """Export test to RDF/TTL.

        Returns:
            True if export successful
        """
        self.show_progress()
        self.set_status("Exporting test...")

        try:
            # Initialize test writer
            if self.test_writer is None:
                self.test_writer = SHPBTestWriter(
                    self.ontology_manager,
                    self.qudt_manager
                )

            # Build metadata from state
            kwargs = self.state.to_test_metadata_kwargs()
            metadata = SHPBTestMetadata(**kwargs)

            # Get raw DataFrame
            raw_df = self.state.raw_df
            if raw_df is None:
                raise ValueError("Raw data not available")

            # Rename columns to standard names
            column_mapping = self.state.column_mapping
            rename_map = {}
            for target, source in column_mapping.items():
                if source:
                    rename_map[source] = target

            export_df = raw_df.rename(columns=rename_map)

            # Ensure we have required columns
            required_cols = ['time', 'incident', 'transmitted']
            missing = [c for c in required_cols if c not in export_df.columns]
            if missing:
                raise ValueError(f"Missing columns for export: {missing}")

            # Export
            saved_path, validation_result = self.test_writer.ingest_test(
                test_metadata=metadata,
                raw_data_df=export_df,
                processed_results=self.state.calculation_results
            )

            if saved_path is None:
                # Validation failed
                error_msg = validation_result.get_summary() if validation_result else "Unknown validation error"
                self.show_error("Export Failed", f"Validation errors:\n\n{error_msg}")
                return False

            # Success
            self.state.exported_file_path = saved_path

            self.set_status(f"Exported successfully: {saved_path}")
            self.logger.info(f"Test exported to {saved_path}")

            # Show warnings if any
            if validation_result and validation_result.has_any_issues():
                self.show_warning(
                    "Export Complete with Warnings",
                    f"Test saved to:\n{saved_path}\n\n"
                    f"Warnings:\n{validation_result.get_summary()}"
                )
            else:
                from PyQt6.QtWidgets import QMessageBox
                QMessageBox.information(
                    self,
                    "Export Successful",
                    f"Test saved successfully!\n\n"
                    f"File: {saved_path}\n\n"
                    f"Test ID: {self.state.test_id}\n"
                    f"Validity: {self.state.test_validity}"
                )

            return True

        except Exception as e:
            self.logger.error(f"Export failed: {e}", exc_info=True)
            self.set_status(f"Export failed: {e}", is_error=True)
            self.show_error("Export Failed", str(e))
            return False

        finally:
            self.hide_progress()
