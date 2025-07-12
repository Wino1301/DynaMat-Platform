"""
DynaMat Platform Main GUI Application

File location: dynamat/gui/app.py

This module provides the main desktop application interface for managing
dynamic materials testing data with ontology-based forms and workflows.

Key Features:
1. Tabbed interface for different workflow stages
2. Integration with ontology system
3. Data validation and error handling
4. Template management
5. Export capabilities for TTL generation
"""

import sys
import os
from pathlib import Path
from typing import Dict, List, Any, Optional

# Add the parent directory to Python path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QTabWidget, QWidget, QVBoxLayout, 
    QHBoxLayout, QMenuBar, QMenu, QStatusBar, QToolBar, QSplitter,
    QPushButton, QLabel, QComboBox, QMessageBox, QFileDialog,
    QProgressDialog, QTextEdit, QGroupBox, QFrame
)
from PyQt6.QtCore import Qt, pyqtSignal, QThread, QTimer
from PyQt6.QtGui import QAction, QIcon, QFont

try:
    from dynamat.gui.forms import OntologyFormGenerator, OntologyForm, FormData, FormTemplate
    from dynamat.gui.widgets import WidgetData, WidgetState
    from dynamat.ontology.manager import get_ontology_manager
except ImportError:
    # Fallback for direct execution
    from forms import OntologyFormGenerator, OntologyForm, FormData, FormTemplate
    from widgets import WidgetData, WidgetState
    from dynamat.ontology.manager import get_ontology_manager


# =============================================================================
# MAIN APPLICATION CLASS
# =============================================================================

class DynaMatApp(QMainWindow):
    """
    Main DynaMat Platform GUI Application.
    Provides a complete interface for materials testing data management.
    """
    
    def __init__(self):
        super().__init__()
        
        # Core components
        self.ontology_manager = get_ontology_manager()
        self.form_generator = OntologyFormGenerator(self.ontology_manager)
        
        # Data tracking
        self.current_experiment_data = {}
        self.active_forms: Dict[str, OntologyForm] = {}
        
        # Setup UI
        self._setup_ui()
        self._setup_menus()
        self._setup_toolbars()
        self._setup_status_bar()
        self._connect_signals()
        
        # Initialize application state
        self._initialize_app()
    
    def _setup_ui(self):
        """Setup the main UI structure"""
        self.setWindowTitle("DynaMat Platform - Materials Testing Data Management")
        self.setGeometry(100, 100, 1400, 900)
        
        # Central widget with splitter
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QHBoxLayout()
        central_widget.setLayout(main_layout)
        
        # Create splitter for sidebar and main content
        splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout.addWidget(splitter)
        
        # Left sidebar for navigation and templates
        self._create_sidebar(splitter)
        
        # Main content area with tabs
        self._create_main_content(splitter)
        
        # Set splitter proportions
        splitter.setSizes([300, 1100])
    
    def _create_sidebar(self, parent):
        """Create left sidebar with navigation and templates"""
        sidebar = QFrame()
        sidebar.setFrameStyle(QFrame.Shape.StyledPanel)
        sidebar.setMaximumWidth(350)
        sidebar.setMinimumWidth(250)
        
        sidebar_layout = QVBoxLayout()
        sidebar.setLayout(sidebar_layout)
        
        # Experiment info section
        exp_group = QGroupBox("Current Experiment")
        exp_layout = QVBoxLayout()
        
        self.experiment_label = QLabel("No experiment loaded")
        self.experiment_label.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        exp_layout.addWidget(self.experiment_label)
        
        # New experiment button
        new_exp_btn = QPushButton("New Experiment")
        new_exp_btn.clicked.connect(self._new_experiment)
        exp_layout.addWidget(new_exp_btn)
        
        # Load experiment button
        load_exp_btn = QPushButton("Load Experiment")
        load_exp_btn.clicked.connect(self._load_experiment)
        exp_layout.addWidget(load_exp_btn)
        
        exp_group.setLayout(exp_layout)
        sidebar_layout.addWidget(exp_group)
        
        # Templates section
        template_group = QGroupBox("Form Templates")
        template_layout = QVBoxLayout()
        
        self.template_selector = QComboBox()
        self.template_selector.addItem("Default", None)
        self._populate_templates()
        template_layout.addWidget(self.template_selector)
        
        apply_template_btn = QPushButton("Apply Template")
        apply_template_btn.clicked.connect(self._apply_selected_template)
        template_layout.addWidget(apply_template_btn)
        
        template_group.setLayout(template_layout)
        sidebar_layout.addWidget(template_group)
        
        # Quick actions section
        actions_group = QGroupBox("Quick Actions")
        actions_layout = QVBoxLayout()
        
        validate_btn = QPushButton("Validate All Forms")
        validate_btn.clicked.connect(self._validate_all_forms)
        actions_layout.addWidget(validate_btn)
        
        export_btn = QPushButton("Export to TTL")
        export_btn.clicked.connect(self._export_experiment)
        actions_layout.addWidget(export_btn)
        
        clear_btn = QPushButton("Clear All Forms")
        clear_btn.clicked.connect(self._clear_all_forms)
        actions_layout.addWidget(clear_btn)
        
        actions_group.setLayout(actions_layout)
        sidebar_layout.addWidget(actions_group)
        
        # Status section
        status_group = QGroupBox("Status")
        status_layout = QVBoxLayout()
        
        self.validation_status = QLabel("Ready")
        status_layout.addWidget(self.validation_status)
        
        self.data_completeness = QLabel("Data: 0%")
        status_layout.addWidget(self.data_completeness)
        
        status_group.setLayout(status_layout)
        sidebar_layout.addWidget(status_group)
        
        sidebar_layout.addStretch()
        parent.addWidget(sidebar)
    
    def _create_main_content(self, parent):
        """Create main content area with tabbed interface"""
        self.tab_widget = QTabWidget()
        self.tab_widget.setTabPosition(QTabWidget.TabPosition.North)
        self.tab_widget.setTabsClosable(False)  # Keep core tabs always open
        
        # Create core workflow tabs
        self._create_specimen_tab()
        self._create_test_setup_tab()
        self._create_test_execution_tab()
        self._create_analysis_tab()
        self._create_export_tab()
        
        parent.addWidget(self.tab_widget)
    
    def _create_specimen_tab(self):
        """Create specimen definition tab"""
        specimen_widget = QWidget()
        layout = QVBoxLayout()
        
        # Header
        header = QLabel("Specimen Definition")
        header.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        layout.addWidget(header)
        
        # Create specimen form
        self.specimen_form = self.form_generator.create_class_form(
            "Specimen",
            on_change_callback=self._on_specimen_changed,
            validation_callback=self._on_specimen_validation_changed
        )
        
        layout.addWidget(self.specimen_form)
        self.active_forms["specimen"] = self.specimen_form
        
        specimen_widget.setLayout(layout)
        self.tab_widget.addTab(specimen_widget, "1. Specimen")
    
    def _create_test_setup_tab(self):
        """Create test setup configuration tab"""
        setup_widget = QWidget()
        layout = QVBoxLayout()
        
        # Header
        header = QLabel("Test Setup Configuration")
        header.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        layout.addWidget(header)
        
        # Test type selector
        type_layout = QHBoxLayout()
        type_layout.addWidget(QLabel("Test Type:"))
        
        self.test_type_selector = QComboBox()
        self.test_type_selector.addItems(["SHPBTest", "QuasiStaticTest", "TensileTest"])
        self.test_type_selector.currentTextChanged.connect(self._on_test_type_changed)
        type_layout.addWidget(self.test_type_selector)
        
        type_layout.addStretch()
        layout.addLayout(type_layout)
        
        # Form area (will be populated based on test type)
        self.test_setup_form_area = QVBoxLayout()
        layout.addLayout(self.test_setup_form_area)
        
        # Initialize with default test type
        self._on_test_type_changed("SHPBTest")
        
        setup_widget.setLayout(layout)
        self.tab_widget.addTab(setup_widget, "2. Test Setup")
    
    def _create_test_execution_tab(self):
        """Create test execution tab"""
        execution_widget = QWidget()
        layout = QVBoxLayout()
        
        # Header
        header = QLabel("Test Execution")
        header.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        layout.addWidget(header)
        
        # Execution controls
        controls_layout = QHBoxLayout()
        
        start_test_btn = QPushButton("Start Test")
        start_test_btn.clicked.connect(self._start_test)
        controls_layout.addWidget(start_test_btn)
        
        stop_test_btn = QPushButton("Stop Test")
        stop_test_btn.clicked.connect(self._stop_test)
        controls_layout.addWidget(stop_test_btn)
        
        controls_layout.addStretch()
        layout.addLayout(controls_layout)
        
        # Test status area
        self.test_status_area = QTextEdit()
        self.test_status_area.setMaximumHeight(200)
        self.test_status_area.setPlainText("Test status: Ready\n")
        layout.addWidget(self.test_status_area)
        
        # Real-time data display area
        data_group = QGroupBox("Real-time Data")
        data_layout = QVBoxLayout()
        
        # Placeholder for real-time plots and data
        self.realtime_data_label = QLabel("No test running")
        self.realtime_data_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.realtime_data_label.setMinimumHeight(300)
        self.realtime_data_label.setStyleSheet("border: 1px dashed #ccc;")
        data_layout.addWidget(self.realtime_data_label)
        
        data_group.setLayout(data_layout)
        layout.addWidget(data_group)
        
        execution_widget.setLayout(layout)
        self.tab_widget.addTab(execution_widget, "3. Test Execution")
    
    def _create_analysis_tab(self):
        """Create analysis and results tab"""
        analysis_widget = QWidget()
        layout = QVBoxLayout()
        
        # Header
        header = QLabel("Analysis & Results")
        header.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        layout.addWidget(header)
        
        # Analysis controls
        controls_layout = QHBoxLayout()
        
        analyze_btn = QPushButton("Run Analysis")
        analyze_btn.clicked.connect(self._run_analysis)
        controls_layout.addWidget(analyze_btn)
        
        export_results_btn = QPushButton("Export Results")
        export_results_btn.clicked.connect(self._export_results)
        controls_layout.addWidget(export_results_btn)
        
        controls_layout.addStretch()
        layout.addLayout(controls_layout)
        
        # Results area
        results_group = QGroupBox("Analysis Results")
        results_layout = QVBoxLayout()
        
        # Placeholder for analysis results
        self.results_area = QTextEdit()
        self.results_area.setPlainText("No analysis results yet")
        results_layout.addWidget(self.results_area)
        
        results_group.setLayout(results_layout)
        layout.addWidget(results_group)
        
        analysis_widget.setLayout(layout)
        self.tab_widget.addTab(analysis_widget, "4. Analysis")
    
    def _create_export_tab(self):
        """Create data export tab"""
        export_widget = QWidget()
        layout = QVBoxLayout()
        
        # Header
        header = QLabel("Data Export")
        header.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        layout.addWidget(header)
        
        # Export options
        options_group = QGroupBox("Export Options")
        options_layout = QVBoxLayout()
        
        # Format selection
        format_layout = QHBoxLayout()
        format_layout.addWidget(QLabel("Export Format:"))
        
        self.export_format_selector = QComboBox()
        self.export_format_selector.addItems(["TTL/RDF", "CSV", "JSON", "Excel"])
        format_layout.addWidget(self.export_format_selector)
        
        format_layout.addStretch()
        options_layout.addLayout(format_layout)
        
        # Export content selection
        content_layout = QVBoxLayout()
        content_layout.addWidget(QLabel("Include:"))
        
        # Checkboxes for different data types
        # Note: In a real implementation, these would be actual checkboxes
        content_layout.addWidget(QLabel("✓ Specimen metadata"))
        content_layout.addWidget(QLabel("✓ Test configuration"))
        content_layout.addWidget(QLabel("✓ Raw data"))
        content_layout.addWidget(QLabel("✓ Analysis results"))
        
        options_layout.addLayout(content_layout)
        options_group.setLayout(options_layout)
        layout.addWidget(options_group)
        
        # Export controls
        export_controls_layout = QHBoxLayout()
        
        preview_btn = QPushButton("Preview Export")
        preview_btn.clicked.connect(self._preview_export)
        export_controls_layout.addWidget(preview_btn)
        
        export_final_btn = QPushButton("Export to File")
        export_final_btn.clicked.connect(self._export_to_file)
        export_controls_layout.addWidget(export_final_btn)
        
        export_controls_layout.addStretch()
        layout.addLayout(export_controls_layout)
        
        # Preview area
        preview_group = QGroupBox("Export Preview")
        preview_layout = QVBoxLayout()
        
        self.export_preview = QTextEdit()
        self.export_preview.setPlainText("Export preview will appear here")
        preview_layout.addWidget(self.export_preview)
        
        preview_group.setLayout(preview_layout)
        layout.addWidget(preview_group)
        
        export_widget.setLayout(layout)
        self.tab_widget.addTab(export_widget, "5. Export")
    
    def _setup_menus(self):
        """Setup application menus"""
        menubar = self.menuBar()
        
        # File menu
        file_menu = menubar.addMenu("File")
        
        new_action = QAction("New Experiment", self)
        new_action.setShortcut("Ctrl+N")
        new_action.triggered.connect(self._new_experiment)
        file_menu.addAction(new_action)
        
        open_action = QAction("Open Experiment", self)
        open_action.setShortcut("Ctrl+O")
        open_action.triggered.connect(self._load_experiment)
        file_menu.addAction(open_action)
        
        save_action = QAction("Save Experiment", self)
        save_action.setShortcut("Ctrl+S")
        save_action.triggered.connect(self._save_experiment)
        file_menu.addAction(save_action)
        
        file_menu.addSeparator()
        
        exit_action = QAction("Exit", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # Tools menu
        tools_menu = menubar.addMenu("Tools")
        
        validate_action = QAction("Validate All Forms", self)
        validate_action.triggered.connect(self._validate_all_forms)
        tools_menu.addAction(validate_action)
        
        refresh_ontology_action = QAction("Refresh Ontology", self)
        refresh_ontology_action.triggered.connect(self._refresh_ontology)
        tools_menu.addAction(refresh_ontology_action)
        
        # Help menu
        help_menu = menubar.addMenu("Help")
        
        about_action = QAction("About", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)
    
    def _setup_toolbars(self):
        """Setup application toolbars"""
        toolbar = self.addToolBar("Main")
        toolbar.setMovable(False)
        
        # Quick action buttons
        new_btn = QPushButton("New")
        new_btn.clicked.connect(self._new_experiment)
        toolbar.addWidget(new_btn)
        
        save_btn = QPushButton("Save")
        save_btn.clicked.connect(self._save_experiment)
        toolbar.addWidget(save_btn)
        
        validate_btn = QPushButton("Validate")
        validate_btn.clicked.connect(self._validate_all_forms)
        toolbar.addWidget(validate_btn)
        
        export_btn = QPushButton("Export")
        export_btn.clicked.connect(self._export_experiment)
        toolbar.addWidget(export_btn)
    
    def _setup_status_bar(self):
        """Setup status bar"""
        self.status_bar = self.statusBar()
        self.status_bar.showMessage("Ready")
        
        # Add permanent widgets to status bar
        self.status_validation = QLabel("Validation: OK")
        self.status_bar.addPermanentWidget(self.status_validation)
        
        self.status_ontology = QLabel("Ontology: Loaded")
        self.status_bar.addPermanentWidget(self.status_ontology)
    
    def _connect_signals(self):
        """Connect application-level signals"""
        self.tab_widget.currentChanged.connect(self._on_tab_changed)
    
    def _initialize_app(self):
        """Initialize application state"""
        self.status_bar.showMessage("DynaMat Platform initialized successfully")
        
        # Start with specimen tab
        self.tab_widget.setCurrentIndex(0)
        
        # Update validation status
        self._update_validation_status()
    
    # =============================================================================
    # EVENT HANDLERS
    # =============================================================================
    
    def _new_experiment(self):
        """Create a new experiment"""
        # Clear all forms
        self._clear_all_forms()
        
        # Update experiment info
        self.experiment_label.setText("New Experiment")
        self.current_experiment_data = {}
        
        self.status_bar.showMessage("New experiment created")
    
    def _load_experiment(self):
        """Load an existing experiment"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Load Experiment", "", "TTL Files (*.ttl);;All Files (*)"
        )
        
        if file_path:
            try:
                # Here you would load the experiment data
                # For now, just show a message
                self.experiment_label.setText(f"Loaded: {Path(file_path).name}")
                self.status_bar.showMessage(f"Experiment loaded from {file_path}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to load experiment: {str(e)}")
    
    def _save_experiment(self):
        """Save current experiment"""
        if not self.current_experiment_data:
            QMessageBox.information(self, "Info", "No experiment data to save")
            return
        
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save Experiment", "", "TTL Files (*.ttl);;All Files (*)"
        )
        
        if file_path:
            try:
                # Here you would save the experiment data
                self.status_bar.showMessage(f"Experiment saved to {file_path}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to save experiment: {str(e)}")
    
    def _on_specimen_changed(self, form_data: FormData):
        """Handle specimen form changes"""
        self.current_experiment_data["specimen"] = form_data.export_data()
        self._update_data_completeness()
    
    def _on_specimen_validation_changed(self, is_valid: bool, errors: List[str]):
        """Handle specimen validation changes"""
        if not is_valid:
            self.validation_status.setText(f"Specimen: {len(errors)} error(s)")
        else:
            self.validation_status.setText("Specimen: Valid")
        
        self._update_validation_status()
    
    def _on_test_type_changed(self, test_type: str):
        """Handle test type selection change"""
        # Clear existing test form
        while self.test_setup_form_area.count():
            child = self.test_setup_form_area.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        
        # Create new form for selected test type
        test_form = self.form_generator.create_class_form(
            test_type,
            on_change_callback=self._on_test_setup_changed,
            validation_callback=self._on_test_setup_validation_changed
        )
        
        self.test_setup_form_area.addWidget(test_form)
        self.active_forms["test_setup"] = test_form
    
    def _on_test_setup_changed(self, form_data: FormData):
        """Handle test setup form changes"""
        self.current_experiment_data["test_setup"] = form_data.export_data()
        self._update_data_completeness()
    
    def _on_test_setup_validation_changed(self, is_valid: bool, errors: List[str]):
        """Handle test setup validation changes"""
        # Update status based on validation
        self._update_validation_status()
    
    def _on_tab_changed(self, index: int):
        """Handle tab change"""
        tab_names = ["Specimen", "Test Setup", "Test Execution", "Analysis", "Export"]
        if index < len(tab_names):
            self.status_bar.showMessage(f"Current tab: {tab_names[index]}")
    
    def _populate_templates(self):
        """Populate template selector with available templates"""
        # Clear existing templates
        self.template_selector.clear()
        self.template_selector.addItem("No Template", None)
        
        # Add auto-generated templates for common classes
        common_classes = ["Specimen", "SHPBTest", "Material"]
        for class_name in common_classes:
            try:
                # Check if class exists in ontology
                manager = get_ontology_manager()
                test_result = manager.test_measurement_detection(class_name)
                
                if test_result['class_exists']:
                    template_name = f"Auto: {class_name}"
                    self.template_selector.addItem(template_name, class_name)
            except Exception as e:
                print(f"Could not check class {class_name}: {e}")
        
        # In the future, this will also load templates from TTL files
        try:
            loaded_templates = self.form_generator.get_available_templates()
            for template_name in loaded_templates:
                display_name = template_name.replace("_", " ").title()
                self.template_selector.addItem(f"Saved: {display_name}", template_name)
        except Exception as e:
            print(f"Could not load saved templates: {e}")
    
    def _apply_selected_template(self):
        """Apply selected template to current form"""
        template_data = self.template_selector.currentData()
        
        if not template_data:
            return
        
        try:
            # If it's a class name, create auto-template
            if isinstance(template_data, str) and template_data in ["Specimen", "SHPBTest", "Material"]:
                template = self.form_generator.create_template_from_ontology(template_data)
                print(f"Created auto-template for {template_data}")
                
                # Apply to current specimen form if it's a Specimen template
                if template_data == "Specimen" and hasattr(self, 'specimen_form'):
                    self.specimen_form.apply_template(template)
                    self.status_bar.showMessage(f"Applied auto-template for {template_data}")
                
            # If it's a saved template name, load it
            elif template_data in self.form_generator.templates:
                template = self.form_generator.templates[template_data]
                
                # Apply to appropriate form based on class name
                if template.class_name == "Specimen" and hasattr(self, 'specimen_form'):
                    self.specimen_form.apply_template(template)
                    self.status_bar.showMessage(f"Applied template: {template.name}")
            
        except Exception as e:
            QMessageBox.warning(self, "Template Error", f"Could not apply template: {str(e)}")
            print(f"Template application error: {e}")
    
    def _validate_all_forms(self):
        """Validate all active forms"""
        all_valid = True
        error_count = 0
        
        for form_name, form in self.active_forms.items():
            is_valid, errors = form._get_current_validation()
            if not is_valid:
                all_valid = False
                error_count += len(errors)
        
        if all_valid:
            QMessageBox.information(self, "Validation", "All forms are valid!")
        else:
            QMessageBox.warning(self, "Validation", f"Found {error_count} validation error(s)")
        
        self._update_validation_status()
    
    def _clear_all_forms(self):
        """Clear all forms"""
        for form in self.active_forms.values():
            form.reset_form()
        
        self.current_experiment_data = {}
        self._update_data_completeness()
    
    def _export_experiment(self):
        """Export experiment to TTL"""
        if not self.current_experiment_data:
            QMessageBox.information(self, "Info", "No experiment data to export")
            return
        
        # Switch to export tab
        self.tab_widget.setCurrentIndex(4)
        
        # Generate preview
        self._preview_export()
    
    def _start_test(self):
        """Start test execution"""
        self.test_status_area.append("Test started...")
        self.realtime_data_label.setText("Test running... (real-time data would appear here)")
    
    def _stop_test(self):
        """Stop test execution"""
        self.test_status_area.append("Test stopped.")
        self.realtime_data_label.setText("Test completed")
    
    def _run_analysis(self):
        """Run data analysis"""
        self.results_area.setPlainText("Running analysis...\n(Analysis results would appear here)")
    
    def _export_results(self):
        """Export analysis results"""
        QMessageBox.information(self, "Info", "Results export functionality would be implemented here")
    
    def _preview_export(self):
        """Preview export data"""
        export_format = self.export_format_selector.currentText()
        
        preview_text = f"Export Preview - {export_format}\n"
        preview_text += "=" * 40 + "\n\n"
        
        for data_type, data in self.current_experiment_data.items():
            preview_text += f"{data_type.title()}:\n"
            preview_text += str(data) + "\n\n"
        
        self.export_preview.setPlainText(preview_text)
    
    def _export_to_file(self):
        """Export data to file"""
        if not self.current_experiment_data:
            QMessageBox.information(self, "Info", "No data to export")
            return
        
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Export Data", "", "TTL Files (*.ttl);;CSV Files (*.csv);;JSON Files (*.json);;All Files (*)"
        )
        
        if file_path:
            try:
                # Here you would implement the actual export logic
                QMessageBox.information(self, "Success", f"Data exported to {file_path}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Export failed: {str(e)}")
    
    def _refresh_ontology(self):
        """Refresh ontology data"""
        # Reload ontology and refresh form options
        try:
            # Here you would reload the ontology
            self.status_ontology.setText("Ontology: Reloaded")
            self.status_bar.showMessage("Ontology refreshed successfully")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to refresh ontology: {str(e)}")
    
    def _show_about(self):
        """Show about dialog"""
        QMessageBox.about(
            self, 
            "About DynaMat Platform",
            "DynaMat Platform v1.0\n\n"
            "Ontology-based desktop application for managing\n"
            "dynamic materials testing data.\n\n"
            "Developed at UTEP Dynamic Materials Laboratory"
        )
    
    def _update_validation_status(self):
        """Update overall validation status"""
        # Check validation status of all forms
        all_valid = True
        for form in self.active_forms.values():
            is_valid, _ = form._get_current_validation()
            if not is_valid:
                all_valid = False
                break
        
        if all_valid:
            self.status_validation.setText("Validation: ✓ OK")
            self.status_validation.setStyleSheet("color: green;")
        else:
            self.status_validation.setText("Validation: ✗ Errors")
            self.status_validation.setStyleSheet("color: red;")
    
    def _update_data_completeness(self):
        """Update data completeness indicator"""
        total_sections = 5  # Specimen, Test Setup, Execution, Analysis, Export
        completed_sections = len(self.current_experiment_data)
        
        percentage = (completed_sections / total_sections) * 100
        self.data_completeness.setText(f"Data: {percentage:.0f}%")


# =============================================================================
# APPLICATION ENTRY POINT
# =============================================================================

def main():
    """Main application entry point"""
    app = QApplication(sys.argv)
    
    # Set application properties
    app.setApplicationName("DynaMat Platform")
    app.setApplicationVersion("1.0")
    app.setOrganizationName("UTEP Dynamic Materials Laboratory")
    
    # Create and show main window
    main_window = DynaMatApp()
    main_window.show()
    
    # Start event loop
    sys.exit(app.exec())


if __name__ == "__main__":
    main()