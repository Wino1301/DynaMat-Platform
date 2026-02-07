# SHPB Wizard Pages

## Overview

The SHPB analysis wizard guides users through a multi-step signal processing pipeline. Each page is a `QWizardPage` subclass (via `BaseSHPBPage`) that shares state through `SHPBAnalysisState`.

All parameter forms are **ontology-driven**: the GUI reads property definitions from the RDF ontology and generates appropriate widgets automatically via `CustomizableFormBuilder`.

## Ontology-Driven Pages

| Page | Ontology Class | Form Groups | TTL File |
|------|---------------|-------------|----------|
| `pulse_detection_page.py` | `dyn:PulseDetectionParams` | DetectionConfig, SearchBounds | `shpb_processing_class.ttl` |
| `segmentation_page.py` | `dyn:SegmentationParams` | SegmentationConfig | `shpb_processing_class.ttl` |
| `alignment_page.py` | `dyn:AlignmentParams` | AlignmentConfig, FitnessWeights, ShiftSearchBounds, AlignmentResults | `shpb_processing_class.ttl` |
| `tukey_window_page.py` | `dyn:TukeyWindowParams` | WindowConfig | `shpb_processing_class.ttl` |
| `results_page.py` | `dyn:EquilibriumMetrics` | OverallMetrics, PhaseMetrics | `shpb_processing_class.ttl` |

## Form URI to State Mapping Pattern

Each page implements `_restore_params()` and `_save_params()` to bridge the ontology form and `SHPBAnalysisState`:

```python
def _restore_params(self):
    """State -> Form: populate form widgets from state."""
    form_data = {
        f"{DYN_NS}hasPropertyName": self.state.field_name,
    }
    self.form_builder.set_form_data(self._form_widget, form_data)

def _save_params(self):
    """Form -> State: extract widget values back to state."""
    form_data = self.form_builder.get_form_data(self._form_widget)
    self.state.field_name = form_data.get(f"{DYN_NS}hasPropertyName", default)
```

## Page Lifecycle

```
initializePage()          # Called when page becomes current
  -> _restore_params()    # Populate form from state
  -> _update_plot()       # Show existing results if any

[User interacts with form, clicks action button]
  -> _action_method()     # Run computation (e.g., _segment_pulses)
  -> state.xxx = result   # Store results in state
  -> _update_display()    # Update results labels / plots

validatePage()            # Called when user clicks Next
  -> _save_params()       # Save form values to state
  -> return True/False    # Gate progression
```

## Non-Form UI Elements

Each page may include elements outside the ontology form:
- **Action buttons**: "Segment All Pulses", "Run Alignment", "Calculate Results", "Apply Window"
- **Results displays**: Status labels, segmentation stats, centering shifts
- **Plots**: Matplotlib/Plotly widgets showing signals, stress-strain curves, equilibrium checks
- **Info text**: Static help text explaining parameters

These are created manually in `_setup_ui()` alongside the ontology form.

## Adding a New Page

1. Define the ontology class and properties in `shpb_processing_class.ttl` with GUI annotations
2. Create page class extending `BaseSHPBPage`
3. In `__init__`, create `CustomizableFormBuilder` and store as `self.form_builder`
4. In `_setup_ui`, call `self.form_builder.build_form(CLASS_URI)` to generate the form
5. Implement `_restore_params()` / `_save_params()` for state bridging
6. Add any non-form UI (buttons, plots, results labels)
7. Register the page in the wizard's page sequence
