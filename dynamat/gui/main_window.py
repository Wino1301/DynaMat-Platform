"""
DynaMat Platform - Main Window
Main application window with ribbon interface and activity tabs
"""

import logging
from typing import Optional, Dict, Any

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QSplitter, QTabWidget, QMenuBar, QStatusBar,
    QTextEdit, QPushButton, QLabel, QFrame,
    QToolBar, QComboBox
)
from PyQt6.QtGui import QAction, QActionGroup
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QIcon, QFont

from ..ontology.manager import OntologyManager
from .widgets.forms.specimen_form import SpecimenFormWidget
from .widgets.terminal_widget import TerminalWidget
from .widgets.action_panel import ActionPanelWidget

logger = logging.getLogger(__name__)

class MainWindow(QMainWindow):
    """
    Main application window for DynaMat Platform.
    
    Features:
    - Upper ribbon with common dropdowns
    - Activity tabs (specimen, mechanical test, visualize)
    - Left panel with action buttons (20% width)
    - Bottom left terminal panel
    - Main content area for forms/actions
    """
    
    # Signals
    status_message = pyqtSignal(str)
    activity_changed = pyqtSignal(str)
    
    def __init__(self, ontology_manager: OntologyManager, parent=None):
        super().__init__(parent)

        try:
            self.ontology_manager = OntologyManager()
            print(f"OntologyManager created: {self.ontology_manager}")
            print(f"Has get_class_metadata_for_form: {hasattr(self.ontology_manager, 'get_class_metadata_for_form')}")
        except Exception as e:
            print(f"OntologyManager creation failed: {e}")
            self.ontology_manager = None
        
        self.current_activity = None
        self.activity_widgets = {}
        self.content_widget = None
        
        # Setup window
        self._setup_window()
        
        # Create interface
        self._create_menu_bar()
        self._create_ribbon_bar()
        self._create_activity_bar()
        self._create_central_widget()
        self._create_status_bar()
        
        # Connect signals
        self._connect_signals()
        
        # Initialize with specimen activity (create immediately)
        self._switch_activity("specimen")
        
        logger.info("Main window initialized")
    
    def _setup_window(self):
        """Setup main window properties"""
        self.setWindowTitle("DynaMat Platform - Dynamic Materials Testing")
        self.setMinimumSize(1200, 800)
        self.resize(1400, 900)
        
        # Center window on screen
        self.move(100, 100)
    
    def _create_menu_bar(self):
        """Create main menu bar"""
        menubar = self.menuBar()
        
        # File menu
        file_menu = menubar.addMenu("&File")
        
        new_action = QAction("&New", self)
        new_action.setShortcut("Ctrl+N")
        file_menu.addAction(new_action)
        
        open_action = QAction("&Open", self)
        open_action.setShortcut("Ctrl+O")
        file_menu.addAction(open_action)
        
        save_action = QAction("&Save", self)
        save_action.setShortcut("Ctrl+S")
        file_menu.addAction(save_action)
        
        file_menu.addSeparator()
        
        exit_action = QAction("E&xit", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # Edit menu
        edit_menu = menubar.addMenu("&Edit")
        edit_menu.addAction("&Preferences")
        
        # View menu
        view_menu = menubar.addMenu("&View")
        view_menu.addAction("&Refresh")
        view_menu.addAction("&Full Screen")
        
        # Help menu
        help_menu = menubar.addMenu("&Help")
        help_menu.addAction("&About")
        help_menu.addAction("&Documentation")
    
    def _create_ribbon_bar(self):
        """Create upper ribbon bar with common dropdowns"""
        self.ribbon_toolbar = QToolBar("Ribbon")
        self.ribbon_toolbar.setMovable(False)
        self.ribbon_toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        
        # Configuration dropdown
        config_combo = QComboBox()
        config_combo.addItems(["Default Configuration", "SHPB Setup", "Quasi-Static Setup"])
        config_combo.setMinimumWidth(150)
        self.ribbon_toolbar.addWidget(QLabel("Configuration:"))
        self.ribbon_toolbar.addWidget(config_combo)
        
        self.ribbon_toolbar.addSeparator()
        
        # View dropdown
        view_combo = QComboBox()
        view_combo.addItems(["Standard View", "Compact View", "Expert View"])
        view_combo.setMinimumWidth(120)
        self.ribbon_toolbar.addWidget(QLabel("View:"))
        self.ribbon_toolbar.addWidget(view_combo)
        
        self.ribbon_toolbar.addSeparator()
        
        # Database connection status
        db_status = QLabel("Database: Connected")
        db_status.setStyleSheet("color: green; font-weight: bold;")
        self.ribbon_toolbar.addWidget(db_status)
        
        self.addToolBar(self.ribbon_toolbar)
    
    def _create_activity_bar(self):
        """Create activity selection bar"""
        self.activity_toolbar = QToolBar("Activities")
        self.activity_toolbar.setMovable(False)
        self.activity_toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        
        # Activity action group for exclusive selection
        self.activity_group = QActionGroup(self)
        
        # Activity buttons
        activities = [
            ("specimen", "Specimen", "Manage specimen metadata and properties"),
            ("mechanical", "Mechanical Test", "Configure and run mechanical tests"),
            ("visualize", "Visualize", "View and analyze test data")
        ]
        
        for activity_id, name, tooltip in activities:
            action = QAction(name, self)
            action.setCheckable(True)
            action.setToolTip(tooltip)
            action.setData(activity_id)
            action.triggered.connect(lambda checked, aid=activity_id: self._switch_activity(aid))
            
            self.activity_group.addAction(action)
            self.activity_toolbar.addAction(action)
            
            if activity_id == "specimen":
                action.setChecked(True)
        
        self.addToolBar(self.activity_toolbar)
    
    def _create_central_widget(self):
        """Create main central widget with panels"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Main horizontal layout
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(5, 5, 5, 5)
        
        # Create horizontal splitter
        self.main_splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Left panel (20% width)
        self._create_left_panel()
        
        # Main content area (80% width)
        self._create_main_content()
        
        # Set splitter proportions
        self.main_splitter.setSizes([250, 1000])  # Approximately 20% / 80%
        self.main_splitter.setChildrenCollapsible(False)
        
        main_layout.addWidget(self.main_splitter)
    
    def _create_left_panel(self):
        """Create left panel with actions and terminal"""
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(5, 5, 5, 5)
        
        # Create vertical splitter for action panel and terminal
        left_splitter = QSplitter(Qt.Orientation.Vertical)
        
        # Action panel (top part of left panel)
        self.action_panel = ActionPanelWidget(self.ontology_manager)
        left_splitter.addWidget(self.action_panel)
        
        # Terminal widget (bottom part of left panel)
        self.terminal = TerminalWidget()
        left_splitter.addWidget(self.terminal)
        
        # Set splitter proportions (60% actions, 40% terminal)
        left_splitter.setSizes([300, 200])
        
        left_layout.addWidget(left_splitter)
        self.main_splitter.addWidget(left_panel)
    
    def _create_main_content(self):
        """Create main content area"""
        self.content_frame = QFrame()
        self.content_frame.setFrameStyle(QFrame.Shape.StyledPanel)
        self.content_layout = QVBoxLayout(self.content_frame)
        self.content_layout.setContentsMargins(10, 10, 10, 10)
        
        # Title label
        self.content_title = QLabel("Specimen Management")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        self.content_title.setFont(title_font)
        self.content_layout.addWidget(self.content_title)
        
        # Content widget placeholder (will be replaced based on activity)
        self.content_widget = QWidget()
        self.content_layout.addWidget(self.content_widget)
        
        self.main_splitter.addWidget(self.content_frame)
    
    def _create_status_bar(self):
        """Create status bar"""
        self.status_bar = self.statusBar()
        self.status_bar.showMessage("Ready")
        
        # Add permanent widgets
        self.activity_status = QLabel("Activity: Specimen")
        self.status_bar.addPermanentWidget(self.activity_status)
    
    def _connect_signals(self):
        """Connect internal signals"""
        self.status_message.connect(self.status_bar.showMessage)
        self.activity_changed.connect(self._update_activity_status)
        
        # Connect action panel signals
        self.action_panel.template_loaded.connect(self._on_template_loaded)
        self.action_panel.new_instance.connect(self._on_new_instance)
    
    def _initialize_specimen_activity(self):
        """Initialize specimen activity widget immediately"""
        try:
            logger.info("Initializing specimen activity widget")
            self.activity_widgets["specimen"] = SpecimenFormWidget(self.ontology_manager)
            self.log_message("Specimen form widget created and cached")
        except Exception as e:
            logger.error(f"Failed to initialize specimen form: {e}", exc_info=True)
            self.log_message(f"Failed to create specimen form: {e}", "error")
            # Create error widget as fallback
            error_widget = QLabel(f"Failed to create specimen form:\n{str(e)}")
            error_widget.setStyleSheet("color: red; padding: 20px;")
            error_widget.setWordWrap(True)
            self.activity_widgets["specimen"] = error_widget
    
    def _switch_activity(self, activity_id: str):
        """Switch to a different activity with proper widget management"""
        if activity_id == self.current_activity:
            return
        
        try:
            logger.info(f"Switching from {self.current_activity} to {activity_id}")
            
            # Remove current content widget safely
            if self.content_widget:
                self.content_layout.removeWidget(self.content_widget)
                # Don't delete cached widgets, just hide them
                if not self._is_cached_widget(self.content_widget):
                    self.content_widget.deleteLater()
                else:
                    self.content_widget.hide()
                self.content_widget = None
            
            self.current_activity = activity_id
            
            # Update content based on activity
            if activity_id == "specimen":
                self._show_specimen_activity()
            elif activity_id == "mechanical":
                self._show_mechanical_activity()
            elif activity_id == "visualize":
                self._show_visualize_activity()
            
            # Emit signals
            self.activity_changed.emit(activity_id)
            self.log_message(f"Switched to {activity_id} activity")
            
        except Exception as e:
            logger.error(f"Failed to switch to {activity_id}: {e}", exc_info=True)
            self.log_message(f"Error switching to {activity_id}: {e}", "error")
    
    def _is_cached_widget(self, widget: QWidget) -> bool:
        """Check if widget is cached in activity_widgets"""
        return widget in self.activity_widgets.values()
    
    def _show_specimen_activity(self):
        """Show specimen management interface"""
        self.content_title.setText("Specimen Management")
        
        # Use cached specimen widget
        if "specimen" in self.activity_widgets:
            self.content_widget = self.activity_widgets["specimen"]
            self.content_widget.show()  # Make sure it's visible
            self.content_layout.addWidget(self.content_widget)
            logger.info("Specimen form widget restored from cache")
        else:
            # This shouldn't happen since we initialize in __init__, but handle gracefully
            logger.warning("Specimen widget not cached, creating new one")
            self._initialize_specimen_activity()
            if "specimen" in self.activity_widgets:
                self.content_widget = self.activity_widgets["specimen"]
                self.content_layout.addWidget(self.content_widget)
    
    def _show_mechanical_activity(self):
        """Show mechanical test interface"""
        self.content_title.setText("Mechanical Testing")
        
        # Create or reuse mechanical test widget
        if "mechanical" not in self.activity_widgets:
            # Placeholder for mechanical test widget
            self.activity_widgets["mechanical"] = QLabel("Mechanical Testing Interface\n(Coming Soon)")
            self.activity_widgets["mechanical"].setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.activity_widgets["mechanical"].setStyleSheet("font-size: 16px; color: gray;")
        
        self.content_widget = self.activity_widgets["mechanical"]
        self.content_widget.show()
        self.content_layout.addWidget(self.content_widget)
    
    def _show_visualize_activity(self):
        """Show visualization interface"""
        self.content_title.setText("Data Visualization")
        
        # Create or reuse visualization widget
        if "visualize" not in self.activity_widgets:
            # Placeholder for visualization widget
            self.activity_widgets["visualize"] = QLabel("Data Visualization Interface\n(Coming Soon)")
            self.activity_widgets["visualize"].setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.activity_widgets["visualize"].setStyleSheet("font-size: 16px; color: gray;")
        
        self.content_widget = self.activity_widgets["visualize"]
        self.content_widget.show()
        self.content_layout.addWidget(self.content_widget)
    
    def _update_activity_status(self, activity_id: str):
        """Update activity status in status bar"""
        activity_names = {
            "specimen": "Specimen",
            "mechanical": "Mechanical Test",
            "visualize": "Visualize"
        }
        name = activity_names.get(activity_id, activity_id.title())
        self.activity_status.setText(f"Activity: {name}")
    
    def _on_template_loaded(self, template_data: Dict[str, Any]):
        """Handle template loaded signal"""
        self.log_message(f"Template loaded: {template_data.get('name', 'Unknown')}")
        
        # If we're in specimen activity, populate the form
        if self.current_activity == "specimen" and "specimen" in self.activity_widgets:
            specimen_widget = self.activity_widgets["specimen"]
            if hasattr(specimen_widget, 'populate_form'):
                specimen_widget.populate_form(template_data)
    
    def _on_new_instance(self, class_uri: str):
        """Handle new instance creation request"""
        if class_uri == "https://dynamat.utep.edu/ontology#Specimen":
            # Switch to specimen activity if not already there
            if self.current_activity != "specimen":
                self._switch_activity("specimen")
            
            # Create new specimen
            if "specimen" in self.activity_widgets:
                specimen_widget = self.activity_widgets["specimen"]
                if hasattr(specimen_widget, 'create_new_specimen'):
                    specimen_widget.create_new_specimen()
        else:
            logger.warning(f"Cannot create instance of {class_uri} in current interface")
    
    def log_message(self, message: str, level: str = "info"):
        """Log message to terminal and logger"""
        # Log to Python logger
        if level == "error":
            logger.error(message)
        elif level == "warning":
            logger.warning(message)
        else:
            logger.info(message)
        
        # Log to terminal widget
        if hasattr(self, 'terminal'):
            self.terminal.add_message(message, level)
    
    def closeEvent(self, event):
        """Handle window close event"""
        try:
            # Clean up cached widgets properly
            for activity_id, widget in self.activity_widgets.items():
                if widget and not widget.isHidden():
                    widget.hide()
            
            # Accept the close event
            event.accept()
            logger.info("Main window closed")
            
        except Exception as e:
            logger.error(f"Error during window close: {e}")
            event.accept()  # Close anyway