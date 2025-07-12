"""
DynaMat Platform Ribbon Menu Widget

Provides a modern ribbon-style interface for workflow selection and common actions.
The ribbon is organized into workflow categories with intuitive icons and groupings.
"""

import sys
from pathlib import Path
from typing import Dict, List, Callable, Optional

# Add the parent directory to Python path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QTabWidget, QToolBar, 
    QPushButton, QFrame, QLabel, QButtonGroup, QSizePolicy,
    QSpacerItem, QMenu, QActionGroup, QApplication
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize
from PyQt6.QtGui import (
    QFont, QPalette, QColor, QIcon, QAction, 
    QLinearGradient, QBrush, QPainter, QPen
)


class RibbonButton(QPushButton):
    """Custom button for ribbon interface with large icons and text below"""
    
    def __init__(self, text: str, icon_text: str = None, tooltip: str = None):
        super().__init__()
        
        self.setText(text)
        if tooltip:
            self.setToolTip(tooltip)
        
        # Set button styling
        self.setMinimumSize(60, 60)
        self.setMaximumSize(80, 60)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        
        # Style the button
        self.setStyleSheet("""
            QPushButton {
                border: 1px solid #c0c0c0;
                border-radius: 3px;
                background-color: #f0f0f0;
                font-size: 9px;
                text-align: center;
                padding: 2px;
            }
            QPushButton:hover {
                background-color: #e0e0e0;
                border: 1px solid #a0a0a0;
            }
            QPushButton:pressed {
                background-color: #d0d0d0;
                border: 1px solid #808080;
            }
            QPushButton:checked {
                background-color: #b0d4f1;
                border: 1px solid #3399ff;
            }
        """)


class RibbonTab(QWidget):
    """Individual tab in the ribbon containing related tools"""
    
    def __init__(self, tab_name: str):
        super().__init__()
        self.tab_name = tab_name
        
        # Main layout
        layout = QHBoxLayout()
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(10)
        self.setLayout(layout)
        
        # Groups within this tab
        self.groups = {}
    
    def add_group(self, group_name: str, buttons: List[Dict]) -> QFrame:
        """Add a group of related buttons to this tab"""
        
        # Create group frame
        group_frame = QFrame()
        group_frame.setFrameStyle(QFrame.Shape.StyledPanel)
        group_frame.setStyleSheet("""
            QFrame {
                border: 1px solid #c0c0c0;
                border-radius: 3px;
                margin: 2px;
            }
        """)
        
        # Group layout
        group_layout = QVBoxLayout()
        group_layout.setContentsMargins(5, 5, 5, 5)
        group_layout.setSpacing(2)
        group_frame.setLayout(group_layout)
        
        # Button container
        button_container = QWidget()
        button_layout = QHBoxLayout()
        button_layout.setContentsMargins(0, 0, 0, 0)
        button_layout.setSpacing(2)
        button_container.setLayout(button_layout)
        
        # Add buttons
        for button_info in buttons:
            btn = RibbonButton(
                text=button_info.get('text', ''),
                icon_text=button_info.get('icon', ''),
                tooltip=button_info.get('tooltip', '')
            )
            
            # Connect callback if provided
            if 'callback' in button_info:
                btn.clicked.connect(button_info['callback'])
            
            # Set checkable if it's a workflow selector
            if button_info.get('checkable', False):
                btn.setCheckable(True)
            
            button_layout.addWidget(btn)
            
            # Store button reference
            if 'name' in button_info:
                setattr(self, f"{button_info['name']}_button", btn)
        
        group_layout.addWidget(button_container)
        
        # Group label
        group_label = QLabel(group_name)
        group_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        group_label.setStyleSheet("font-size: 8px; color: #606060;")
        group_layout.addWidget(group_label)
        
        # Add to main layout
        self.layout().addWidget(group_frame)
        self.groups[group_name] = group_frame
        
        return group_frame


class RibbonMenu(QWidget):
    """
    Main ribbon menu widget providing workflow navigation and common actions.
    Emits signals when workflow buttons are clicked.
    """
    
    # Signals for workflow selection
    workflow_selected = pyqtSignal(str)  # workflow_name
    action_triggered = pyqtSignal(str)   # action_name
    
    def __init__(self):
        super().__init__()
        
        # Current workflow tracking
        self.current_workflow = None
        self.workflow_buttons = {}
        
        self._setup_ui()
        self._create_tabs()
        self._setup_button_groups()
    
    def _setup_ui(self):
        """Setup the main ribbon UI structure"""
        
        # Main layout
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        self.setLayout(main_layout)
        
        # Ribbon background
        self.setStyleSheet("""
            RibbonMenu {
                background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 #f8f8f8, stop: 1 #e8e8e8);
                border-bottom: 1px solid #c0c0c0;
            }
        """)
        
        # Tab widget for different workflow categories
        self.tab_widget = QTabWidget()
        self.tab_widget.setStyleSheet("""
            QTabWidget::pane {
                border: none;
                background-color: transparent;
            }
            QTabBar::tab {
                background-color: #e8e8e8;
                border: 1px solid #c0c0c0;
                border-bottom: none;
                border-radius: 4px 4px 0px 0px;
                padding: 4px 12px;
                margin-right: 2px;
            }
            QTabBar::tab:selected {
                background-color: #f8f8f8;
                border-bottom: 1px solid #f8f8f8;
            }
            QTabBar::tab:hover {
                background-color: #f0f0f0;
            }
        """)
        
        main_layout.addWidget(self.tab_widget)
        
        # Set fixed height for ribbon
        self.setFixedHeight(120)
    
    def _create_tabs(self):
        """Create the main workflow tabs"""
        
        # Specimen Tab
        self.specimen_tab = self._create_specimen_tab()
        self.tab_widget.addTab(self.specimen_tab, "Specimen")
        
        # Mechanical Tab
        self.mechanical_tab = self._create_mechanical_tab()
        self.tab_widget.addTab(self.mechanical_tab, "Mechanical")
        
        # Characterization Tab
        self.characterization_tab = self._create_characterization_tab()
        self.tab_widget.addTab(self.characterization_tab, "Characterization")
        
        # Database Tab
        self.database_tab = self._create_database_tab()
        self.tab_widget.addTab(self.database_tab, "Database")
        
        # Help Tab
        self.help_tab = self._create_help_tab()
        self.tab_widget.addTab(self.help_tab, "Help")
    
    def _create_specimen_tab(self) -> RibbonTab:
        """Create the specimen workflow tab"""
        tab = RibbonTab("Specimen")
        
        # Specimen Operations Group
        specimen_ops = [
            {
                'name': 'new_specimen',
                'text': 'New\nSpecimen',
                'tooltip': 'Create a new specimen entry',
                'callback': lambda: self.workflow_selected.emit('specimen_new'),
                'checkable': True
            },
            {
                'name': 'edit_specimen',
                'text': 'Edit\nSpecimen',
                'tooltip': 'Edit existing specimen',
                'callback': lambda: self.workflow_selected.emit('specimen_edit'),
                'checkable': True
            }
        ]
        tab.add_group("Specimen", specimen_ops)
        
        # File Operations Group
        file_ops = [
            {
                'name': 'save',
                'text': 'Save',
                'tooltip': 'Save current specimen data',
                'callback': lambda: self.action_triggered.emit('save')
            },
            {
                'name': 'load',
                'text': 'Load',
                'tooltip': 'Load specimen from file',
                'callback': lambda: self.action_triggered.emit('load')
            }
        ]
        tab.add_group("File", file_ops)
        
        return tab
    
    def _create_mechanical_tab(self) -> RibbonTab:
        """Create the mechanical testing workflow tab"""
        tab = RibbonTab("Mechanical")
        
        # Test Type Group
        test_types = [
            {
                'name': 'shpb_test',
                'text': 'SHPB\nTest',
                'tooltip': 'Split Hopkinson Pressure Bar testing',
                'callback': lambda: self.workflow_selected.emit('mechanical_shpb'),
                'checkable': True
            },
            {
                'name': 'quasi_static',
                'text': 'Quasi\nStatic',
                'tooltip': 'Quasi-static mechanical testing',
                'callback': lambda: self.workflow_selected.emit('mechanical_qs'),
                'checkable': True
            },
            {
                'name': 'tensile_test',
                'text': 'Tensile\nTest',
                'tooltip': 'Tensile testing',
                'callback': lambda: self.workflow_selected.emit('mechanical_tensile'),
                'checkable': True
            }
        ]
        tab.add_group("Test Type", test_types)
        
        # Templates Group
        template_ops = [
            {
                'name': 'save_template',
                'text': 'Save\nTemplate',
                'tooltip': 'Save current setup as template',
                'callback': lambda: self.action_triggered.emit('save_template')
            },
            {
                'name': 'load_template',
                'text': 'Load\nTemplate',
                'tooltip': 'Load saved template',
                'callback': lambda: self.action_triggered.emit('load_template')
            }
        ]
        tab.add_group("Templates", template_ops)
        
        # Actions Group
        actions = [
            {
                'name': 'validate',
                'text': 'Validate',
                'tooltip': 'Validate current test setup',
                'callback': lambda: self.action_triggered.emit('validate')
            },
            {
                'name': 'export',
                'text': 'Export',
                'tooltip': 'Export test data to TTL',
                'callback': lambda: self.action_triggered.emit('export')
            }
        ]
        tab.add_group("Actions", actions)
        
        return tab
    
    def _create_characterization_tab(self) -> RibbonTab:
        """Create the characterization workflow tab"""
        tab = RibbonTab("Characterization")
        
        # Imaging Group
        imaging_ops = [
            {
                'name': 'sem_analysis',
                'text': 'SEM\nAnalysis',
                'tooltip': 'Scanning Electron Microscopy analysis',
                'callback': lambda: self.workflow_selected.emit('characterization_sem'),
                'checkable': True
            },
            {
                'name': 'optical_analysis',
                'text': 'Optical\nAnalysis',
                'tooltip': 'Optical microscopy analysis',
                'callback': lambda: self.workflow_selected.emit('characterization_optical'),
                'checkable': True
            }
        ]
        tab.add_group("Imaging", imaging_ops)
        
        return tab
    
    def _create_database_tab(self) -> RibbonTab:
        """Create the database workflow tab"""
        tab = RibbonTab("Database")
        
        # Search Group
        search_ops = [
            {
                'name': 'search',
                'text': 'Search\nData',
                'tooltip': 'Search experimental database',
                'callback': lambda: self.workflow_selected.emit('database_search'),
                'checkable': True
            },
            {
                'name': 'visualize',
                'text': 'Visualize\nData',
                'tooltip': 'Create data visualizations',
                'callback': lambda: self.workflow_selected.emit('database_visualize'),
                'checkable': True
            }
        ]
        tab.add_group("Analysis", search_ops)
        
        return tab
    
    def _create_help_tab(self) -> RibbonTab:
        """Create the help tab"""
        tab = RibbonTab("Help")
        
        # Help Group
        help_ops = [
            {
                'name': 'documentation',
                'text': 'Docs',
                'tooltip': 'Open documentation',
                'callback': lambda: self.action_triggered.emit('documentation')
            },
            {
                'name': 'about',
                'text': 'About',
                'tooltip': 'About DynaMat Platform',
                'callback': lambda: self.action_triggered.emit('about')
            }
        ]
        tab.add_group("Help", help_ops)
        
        return tab
    
    def _setup_button_groups(self):
        """Setup button groups for exclusive workflow selection"""
        
        # Create button group for workflow buttons (mutually exclusive)
        self.workflow_group = QButtonGroup()
        self.workflow_group.setExclusive(True)
        
        # Add workflow buttons to group
        workflow_buttons = [
            self.specimen_tab.new_specimen_button,
            self.specimen_tab.edit_specimen_button,
            self.mechanical_tab.shpb_test_button,
            self.mechanical_tab.quasi_static_button,
            self.mechanical_tab.tensile_test_button,
            self.characterization_tab.sem_analysis_button,
            self.characterization_tab.optical_analysis_button,
            self.database_tab.search_button,
            self.database_tab.visualize_button
        ]
        
        for button in workflow_buttons:
            self.workflow_group.addButton(button)
    
    def set_active_workflow(self, workflow_name: str):
        """Set the active workflow and update button states"""
        self.current_workflow = workflow_name
        
        # Update button states based on workflow
        workflow_button_map = {
            'specimen_new': self.specimen_tab.new_specimen_button,
            'specimen_edit': self.specimen_tab.edit_specimen_button,
            'mechanical_shpb': self.mechanical_tab.shpb_test_button,
            'mechanical_qs': self.mechanical_tab.quasi_static_button,
            'mechanical_tensile': self.mechanical_tab.tensile_test_button,
            'characterization_sem': self.characterization_tab.sem_analysis_button,
            'characterization_optical': self.characterization_tab.optical_analysis_button,
            'database_search': self.database_tab.search_button,
            'database_visualize': self.database_tab.visualize_button
        }
        
        if workflow_name in workflow_button_map:
            workflow_button_map[workflow_name].setChecked(True)
    
    def get_current_workflow(self) -> Optional[str]:
        """Get the currently active workflow"""
        return self.current_workflow


# =============================================================================
# EXAMPLE USAGE AND TESTING
# =============================================================================

def main():
    """Example usage of the ribbon menu"""
    app = QApplication(sys.argv)
    
    # Create ribbon menu
    ribbon = RibbonMenu()
    
    # Connect signals
    ribbon.workflow_selected.connect(
        lambda workflow: print(f"Workflow selected: {workflow}")
    )
    ribbon.action_triggered.connect(
        lambda action: print(f"Action triggered: {action}")
    )
    
    # Show ribbon
    ribbon.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()