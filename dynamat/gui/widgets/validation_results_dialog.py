"""
DynaMat Platform - Validation Results Dialog
Displays SHACL validation results with severity-based UI
"""

import logging
from typing import List

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QScrollArea, QWidget, QFrame, QTextEdit,
    QGroupBox, QSizePolicy
)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QFont, QColor, QPalette

from ..core.form_validator import ValidationResult, ValidationIssue, ValidationSeverity

logger = logging.getLogger(__name__)


class ValidationResultsDialog(QDialog):
    """
    Dialog to display SHACL validation results.

    Features:
    - Color-coded severity levels (red=Violation, yellow=Warning, blue=Info)
    - Expandable sections for each severity
    - Copy to clipboard functionality
    - "Save Anyway" button (only if no violations)
    """

    def __init__(self, validation_result: ValidationResult, parent=None):
        super().__init__(parent)

        self.validation_result = validation_result
        self.logger = logging.getLogger(__name__)

        self._setup_ui()
        self._populate_results()

    def _setup_ui(self):
        """Setup the dialog UI"""
        self.setWindowTitle("Validation Results")
        self.setMinimumSize(600, 400)
        self.resize(700, 500)

        # Main layout
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # Title
        title_label = QLabel("SHACL Validation Results")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)

        # Summary
        summary_label = QLabel(self._get_summary_text())
        summary_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        summary_label.setWordWrap(True)
        layout.addWidget(summary_label)

        # Scroll area for issues
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.StyledPanel)

        scroll_content = QWidget()
        self.scroll_layout = QVBoxLayout(scroll_content)
        self.scroll_layout.setSpacing(10)

        scroll.setWidget(scroll_content)
        layout.addWidget(scroll)

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        # Copy button
        copy_btn = QPushButton("Copy All")
        copy_btn.clicked.connect(self._copy_to_clipboard)
        button_layout.addWidget(copy_btn)

        # Close button
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.reject)
        button_layout.addWidget(close_btn)

        # Save Anyway button (only if no violations)
        if not self.validation_result.has_blocking_issues():
            save_anyway_btn = QPushButton("Save Anyway")
            save_anyway_btn.setDefault(True)
            save_anyway_btn.clicked.connect(self.accept)
            button_layout.addWidget(save_anyway_btn)
        else:
            # Set Close as default if violations exist
            close_btn.setDefault(True)

        layout.addLayout(button_layout)

    def _get_summary_text(self) -> str:
        """Get summary text for the dialog"""
        if self.validation_result.conforms and not self.validation_result.has_any_issues():
            return "✓ Validation passed - no issues found"

        parts = []

        if self.validation_result.violations:
            parts.append(f"⛔ {len(self.validation_result.violations)} Violation(s) - Save Blocked")

        if self.validation_result.warnings:
            parts.append(f"⚠️ {len(self.validation_result.warnings)} Warning(s) - Can Proceed")

        if self.validation_result.infos:
            parts.append(f"ℹ️ {len(self.validation_result.infos)} Info")

        return "\n".join(parts)

    def _populate_results(self):
        """Populate the results sections"""
        # Violations section
        if self.validation_result.violations:
            self._add_severity_section(
                "Violations (Save Blocked)",
                self.validation_result.violations,
                "#ff4444",  # Red
                "⛔"
            )

        # Warnings section
        if self.validation_result.warnings:
            self._add_severity_section(
                "Warnings (Can Proceed)",
                self.validation_result.warnings,
                "#ffbb33",  # Yellow/Orange
                "⚠️"
            )

        # Info section
        if self.validation_result.infos:
            self._add_severity_section(
                "Information",
                self.validation_result.infos,
                "#33b5e5",  # Blue
                "ℹ️"
            )

        # Add stretch at the end
        self.scroll_layout.addStretch()

    def _add_severity_section(self, title: str, issues: List[ValidationIssue],
                              color: str, icon: str):
        """
        Add a section for a specific severity level.

        Args:
            title: Section title
            issues: List of validation issues
            color: Background color for the section
            icon: Emoji icon for the severity
        """
        # Create group box
        group = QGroupBox(f"{icon} {title} ({len(issues)})")
        group.setStyleSheet(f"""
            QGroupBox {{
                font-weight: bold;
                border: 2px solid {color};
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }}
        """)

        group_layout = QVBoxLayout()

        # Add each issue
        for i, issue in enumerate(issues, 1):
            issue_widget = self._create_issue_widget(issue, i, color)
            group_layout.addWidget(issue_widget)

        group.setLayout(group_layout)
        self.scroll_layout.addWidget(group)

    def _create_issue_widget(self, issue: ValidationIssue, number: int, color: str) -> QWidget:
        """
        Create widget for a single validation issue.

        Args:
            issue: Validation issue
            number: Issue number in the list
            color: Color for the issue

        Returns:
            QWidget containing the issue details
        """
        widget = QFrame()
        widget.setFrameShape(QFrame.Shape.StyledPanel)
        widget.setStyleSheet(f"""
            QFrame {{
                background-color: {color}20;
                border-left: 3px solid {color};
                border-radius: 3px;
                padding: 5px;
            }}
        """)

        layout = QVBoxLayout()
        layout.setContentsMargins(5, 5, 5, 5)

        # Issue number and message
        message_label = QLabel(f"{number}. {issue.message}")
        message_label.setWordWrap(True)
        message_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(message_label)

        # Property path (if available)
        if issue.result_path:
            prop_name = self._extract_uri_fragment(issue.result_path)
            prop_label = QLabel(f"   Property: <b>{prop_name}</b>")
            prop_label.setStyleSheet("color: #555; font-size: 9pt;")
            prop_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            layout.addWidget(prop_label)

        # Value (if available)
        if issue.value:
            value_label = QLabel(f"   Value: <code>{issue.value}</code>")
            value_label.setStyleSheet("color: #555; font-size: 9pt;")
            value_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            layout.addWidget(value_label)

        widget.setLayout(layout)
        return widget

    def _extract_uri_fragment(self, uri: str) -> str:
        """Extract the fragment/name from a URI"""
        if "#" in uri:
            return uri.split("#")[-1]
        elif "/" in uri:
            return uri.split("/")[-1]
        return uri

    def _copy_to_clipboard(self):
        """Copy all validation results to clipboard"""
        try:
            from PyQt6.QtGui import QGuiApplication

            # Build text report
            report_lines = ["SHACL Validation Results", "=" * 50, ""]

            if self.validation_result.violations:
                report_lines.append(f"VIOLATIONS ({len(self.validation_result.violations)}) - Save Blocked:")
                report_lines.append("-" * 50)
                for i, issue in enumerate(self.validation_result.violations, 1):
                    report_lines.append(f"{i}. {issue.message}")
                    if issue.result_path:
                        report_lines.append(f"   Property: {issue.result_path}")
                    if issue.value:
                        report_lines.append(f"   Value: {issue.value}")
                    report_lines.append("")

            if self.validation_result.warnings:
                report_lines.append(f"WARNINGS ({len(self.validation_result.warnings)}) - Can Proceed:")
                report_lines.append("-" * 50)
                for i, issue in enumerate(self.validation_result.warnings, 1):
                    report_lines.append(f"{i}. {issue.message}")
                    if issue.result_path:
                        report_lines.append(f"   Property: {issue.result_path}")
                    if issue.value:
                        report_lines.append(f"   Value: {issue.value}")
                    report_lines.append("")

            if self.validation_result.infos:
                report_lines.append(f"INFORMATION ({len(self.validation_result.infos)}):")
                report_lines.append("-" * 50)
                for i, issue in enumerate(self.validation_result.infos, 1):
                    report_lines.append(f"{i}. {issue.message}")
                    if issue.result_path:
                        report_lines.append(f"   Property: {issue.result_path}")
                    if issue.value:
                        report_lines.append(f"   Value: {issue.value}")
                    report_lines.append("")

            report_text = "\n".join(report_lines)

            # Copy to clipboard
            clipboard = QGuiApplication.clipboard()
            clipboard.setText(report_text)

            self.logger.info("Validation results copied to clipboard")

        except Exception as e:
            self.logger.error(f"Failed to copy to clipboard: {e}")

    def sizeHint(self) -> QSize:
        """Suggested size for the dialog"""
        return QSize(700, 500)
