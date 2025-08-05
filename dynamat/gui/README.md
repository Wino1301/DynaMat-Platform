# DynaMat GUI Module

This module contains the PyQt6-based desktop application for the DynaMat Platform.

## Structure

```
dynamat/gui/
├── __init__.py                    # Module initialization
├── app.py                         # Main QApplication class
├── main_window.py                 # Main window with ribbons and panels
├── form_builder.py                # Ontology-based form generation
├── widgets/                       # Custom widgets
│   ├── __init__.py
│   ├── specimen_form.py           # Specimen data entry form
│   ├── terminal_widget.py         # Live terminal/log display
│   └── action_panel.py            # Left panel with action buttons
├── models/                        # Data models (future)
├── views/                         # Additional views (future)
├── controllers/                   # Business logic controllers (future)
└── resources/                     # Static resources
    ├── styles.qss                 # Application stylesheet
    ├── icons/                     # Icon files (future)
    └── images/                    # Image resources (future)
```

## Key Features

### Main Window
- **Upper Ribbon**: Configuration, view mode, database status
- **Activity Tabs**: Specimen, Mechanical Test, Visualize
- **Left Panel (20%)**: Action buttons and live terminal
- **Main Content (80%)**: Dynamic forms and data views

### Form Builder
- Automatic form generation from ontology definitions
- Uses display names, form groups, and display orders
- Supports various widget types (text, combo, numeric, date)
- Built-in validation based on ontology constraints

### Specimen Form
- Complete specimen metadata entry
- Template loading and saving
- Real-time validation
- Data persistence (future)

## Usage

### Running the Application
```bash
# From project root
python main.py

# With debug logging
python main.py --debug

# Validate ontology only
python main.py --validate
```

### Extending the GUI

#### Adding New Activity Tabs
1. Create new widget in `widgets/`
2. Add to `MainWindow._show_*_activity()` methods
3. Update activity list in `MainWindow._create_activity_bar()`

#### Adding New Form Types
1. Use `OntologyFormBuilder.build_form(class_uri)`
2. Handle form data with `get_form_data()` and `populate_form()`
3. Add validation logic as needed

#### Custom Widgets
- Inherit from appropriate Qt widget classes
- Follow naming convention: `*Widget`
- Emit signals for communication with main window
- Include proper error handling and logging

## Dependencies

- PyQt6: GUI framework
- rdflib: Ontology handling (via ontology manager)
- Python 3.11+

## Future Enhancements

- Database integration for data persistence
- Advanced visualization widgets
- Plugin architecture for tools
- Export/import functionality
- Batch processing capabilities