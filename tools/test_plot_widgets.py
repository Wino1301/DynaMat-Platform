"""
DynaMat Platform - Plot Widget Integration Test
Tests the DataSeriesWidget, SeriesMetadataResolver, and plotting widgets.

Usage:
    python tools/test_plot_widgets.py
    python tools/test_plot_widgets.py --visual  # Show interactive plot window
    python tools/test_plot_widgets.py --verbose
    python tools/test_plot_widgets.py --backend plotly  # Test specific backend
    python tools/test_plot_widgets.py --backend matplotlib
"""

import sys
import argparse
from pathlib import Path
import numpy as np

# Add project root to Python path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def test_series_metadata_resolver(ontology_manager, qudt_manager, verbose: bool = False):
    """Test SeriesMetadataResolver functionality."""
    from dynamat.gui.widgets.base import SeriesMetadataResolver

    print("\n=== Testing SeriesMetadataResolver ===")
    resolver = SeriesMetadataResolver(ontology_manager, qudt_manager)

    # Test cases: (series_type_uri, expected_substring_in_label)
    test_cases = [
        ('dyn:Stress', 'Stress'),
        ('dyn:Strain', 'Strain'),
        ('dyn:Time', 'Time'),
        ('dyn:IncidentPulse', 'Incident'),
        ('https://dynamat.utep.edu/ontology#TrueStress', 'True Stress'),
    ]

    passed = 0
    failed = 0

    for series_uri, expected_substr in test_cases:
        try:
            # Test get_axis_label
            label = resolver.get_axis_label(series_uri)
            if expected_substr.lower() in label.lower():
                if verbose:
                    print(f"  [PASS] get_axis_label('{series_uri}') = '{label}'")
                passed += 1
            else:
                print(f"  [FAIL] get_axis_label('{series_uri}') = '{label}' (expected '{expected_substr}')")
                failed += 1

            # Test get_legend_text with analysis method
            legend = resolver.get_legend_text(series_uri, '1-wave')
            if verbose:
                print(f"         get_legend_text('{series_uri}', '1-wave') = '{legend}'")

        except Exception as e:
            print(f"  [FAIL] {series_uri}: {e}")
            failed += 1

    # Test unit symbol resolution
    print("\n  Testing unit symbol resolution:")
    unit_tests = [
        ('http://qudt.org/vocab/unit/MegaPA', 'MPa'),
        ('unit:MilliM', 'mm'),
        ('http://qudt.org/vocab/unit/V', 'V'),
    ]

    for unit_uri, expected_symbol in unit_tests:
        try:
            symbol = resolver.resolve_unit_symbol(unit_uri)
            if symbol.lower() == expected_symbol.lower():
                if verbose:
                    print(f"  [PASS] resolve_unit_symbol('{unit_uri}') = '{symbol}'")
                passed += 1
            else:
                print(f"  [FAIL] resolve_unit_symbol('{unit_uri}') = '{symbol}' (expected '{expected_symbol}')")
                failed += 1
        except Exception as e:
            print(f"  [FAIL] {unit_uri}: {e}")
            failed += 1

    print(f"\n  SeriesMetadataResolver: {passed} passed, {failed} failed")
    return failed == 0


def test_data_series_widget(verbose: bool = False):
    """Test DataSeriesWidget functionality."""
    from dynamat.gui.widgets.base import DataSeriesWidget
    from rdflib import URIRef

    print("\n=== Testing DataSeriesWidget ===")

    # Need QApplication for signal handling
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])

    container = DataSeriesWidget()

    passed = 0
    failed = 0

    # Test 1: Add series
    test_array = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
    success = container.add_series(
        uri='dyn:TestSeries',
        array=test_array,
        unit='http://qudt.org/vocab/unit/MegaPA',
        legend='Test Series',
        metadata={'series_type': 'dyn:Stress'}
    )

    if success:
        if verbose:
            print("  [PASS] add_series() succeeded")
        passed += 1
    else:
        print("  [FAIL] add_series() failed")
        failed += 1

    # Test 2: Get series
    series = container.get_series('dyn:TestSeries')
    if series and np.array_equal(series['array'], test_array):
        if verbose:
            print("  [PASS] get_series() returned correct data")
        passed += 1
    else:
        print("  [FAIL] get_series() returned incorrect data")
        failed += 1

    # Test 3: Get array directly
    arr = container.get_array('dyn:TestSeries')
    if arr is not None and np.array_equal(arr, test_array):
        if verbose:
            print("  [PASS] get_array() returned correct array")
        passed += 1
    else:
        print("  [FAIL] get_array() failed")
        failed += 1

    # Test 4: Check has_series
    if container.has_series('dyn:TestSeries') and not container.has_series('dyn:NonExistent'):
        if verbose:
            print("  [PASS] has_series() works correctly")
        passed += 1
    else:
        print("  [FAIL] has_series() incorrect")
        failed += 1

    # Test 5: Get all URIs
    uris = container.get_all_uris()
    if len(uris) == 1:
        if verbose:
            print("  [PASS] get_all_uris() returned 1 URI")
        passed += 1
    else:
        print(f"  [FAIL] get_all_uris() returned {len(uris)} URIs (expected 1)")
        failed += 1

    # Test 6: Capture from results (simulating SHPB output)
    mock_results = {
        'stress_1w': np.array([100.0, 200.0, 300.0]),
        'strain_1w': np.array([0.01, 0.02, 0.03]),
    }
    mock_metadata = {
        'stress_1w': {
            'series_type': 'https://dynamat.utep.edu/ontology#Stress',
            'unit': 'http://qudt.org/vocab/unit/MegaPA',
            'legend_name': 'Engineering Stress (1-wave)',
        },
        'strain_1w': {
            'series_type': 'https://dynamat.utep.edu/ontology#Strain',
            'unit': 'http://qudt.org/vocab/unit/UNITLESS',
            'legend_name': 'Engineering Strain (1-wave)',
        },
    }

    container2 = DataSeriesWidget()
    count = container2.capture_from_results(mock_results, mock_metadata)

    if count == 2:
        if verbose:
            print(f"  [PASS] capture_from_results() captured {count} series")
        passed += 1
    else:
        print(f"  [FAIL] capture_from_results() captured {count} series (expected 2)")
        failed += 1

    # Test 7: getData/setData roundtrip
    data = container2.getData()
    container3 = DataSeriesWidget()
    container3.setData(data)

    if container3.get_series_count() == 2:
        if verbose:
            print("  [PASS] getData/setData roundtrip preserved data")
        passed += 1
    else:
        print("  [FAIL] getData/setData roundtrip failed")
        failed += 1

    # Test 8: Remove series
    removed = container.remove_series('dyn:TestSeries')
    if removed and container.get_series_count() == 0:
        if verbose:
            print("  [PASS] remove_series() worked")
        passed += 1
    else:
        print("  [FAIL] remove_series() failed")
        failed += 1

    # Test 9: Clear
    container2.clear()
    if container2.get_series_count() == 0:
        if verbose:
            print("  [PASS] clear() removed all series")
        passed += 1
    else:
        print("  [FAIL] clear() didn't remove all series")
        failed += 1

    print(f"\n  DataSeriesWidget: {passed} passed, {failed} failed")
    return failed == 0


def test_plot_widget_factory(verbose: bool = False):
    """Test the plot widget factory and backend detection."""
    from dynamat.gui.widgets.base import (
        create_plot_widget, get_available_backends, is_backend_available,
        BasePlotWidget, MatplotlibPlotWidget
    )

    print("\n=== Testing Plot Widget Factory ===")

    passed = 0
    failed = 0

    # Test get_available_backends
    backends = get_available_backends()
    if 'matplotlib' in backends:
        if verbose:
            print(f"  [PASS] get_available_backends() = {backends}")
        passed += 1
    else:
        print(f"  [FAIL] matplotlib not in available backends: {backends}")
        failed += 1

    # Test is_backend_available
    if is_backend_available('matplotlib'):
        if verbose:
            print("  [PASS] is_backend_available('matplotlib') = True")
        passed += 1
    else:
        print("  [FAIL] is_backend_available('matplotlib') should be True")
        failed += 1

    # Test Plotly availability check
    plotly_available = is_backend_available('plotly')
    if verbose:
        print(f"  [INFO] is_backend_available('plotly') = {plotly_available}")

    print(f"\n  Plot Widget Factory: {passed} passed, {failed} failed")
    return failed == 0


def test_matplotlib_plot_widget(ontology_manager, qudt_manager, visual: bool = False, verbose: bool = False):
    """Test MatplotlibPlotWidget functionality."""
    from dynamat.gui.widgets.base import MatplotlibPlotWidget, DataSeriesWidget

    print("\n=== Testing MatplotlibPlotWidget ===")

    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])

    passed = 0
    failed = 0

    # Create plot widget
    try:
        plot = MatplotlibPlotWidget(ontology_manager, qudt_manager, show_toolbar=visual)
        if verbose:
            print("  [PASS] MatplotlibPlotWidget created successfully")
        passed += 1
    except Exception as e:
        print(f"  [FAIL] MatplotlibPlotWidget creation failed: {e}")
        failed += 1
        return False

    # Test set_axis_series
    try:
        plot.set_axis_series('dyn:Strain', 'dyn:Stress')
        ax = plot.get_axes()
        xlabel = ax.get_xlabel()
        ylabel = ax.get_ylabel()

        if 'Strain' in xlabel and 'Stress' in ylabel:
            if verbose:
                print(f"  [PASS] set_axis_series: x='{xlabel}', y='{ylabel}'")
            passed += 1
        else:
            print(f"  [FAIL] set_axis_series produced unexpected labels: x='{xlabel}', y='{ylabel}'")
            failed += 1
    except Exception as e:
        print(f"  [FAIL] set_axis_series failed: {e}")
        failed += 1

    # Test add_trace
    try:
        x = np.linspace(0, 0.3, 100)
        y = 500 * x  # Simple stress-strain curve

        trace_id = plot.add_trace(x, y, label="Test Data", color="blue")
        if trace_id:
            if verbose:
                print(f"  [PASS] add_trace returned id: {trace_id}")
            passed += 1
        else:
            print("  [FAIL] add_trace returned None")
            failed += 1
    except Exception as e:
        print(f"  [FAIL] add_trace failed: {e}")
        failed += 1

    # Test add_reference_line
    try:
        plot.add_reference_line('h', 100, color='r', linestyle='--', label="Yield")
        plot.add_reference_line('v', 0.1, color='g', linestyle=':', label="0.1 strain")
        if verbose:
            print("  [PASS] add_reference_line succeeded")
        passed += 1
    except Exception as e:
        print(f"  [FAIL] add_reference_line failed: {e}")
        failed += 1

    # Test styling
    try:
        plot.set_title("Stress-Strain Curve")
        plot.enable_legend()
        plot.enable_grid()
        if verbose:
            print("  [PASS] Styling methods succeeded")
        passed += 1
    except Exception as e:
        print(f"  [FAIL] Styling methods failed: {e}")
        failed += 1

    # Test subplot configuration
    try:
        plot.configure_subplot(1, 2)
        plot.set_active_subplot(0)
        plot.set_axis_series('dyn:Time', 'dyn:IncidentPulse')
        plot.add_trace(np.linspace(0, 1, 50), np.random.randn(50), label="Panel 1")

        plot.set_active_subplot(1)
        plot.set_axis_series('dyn:Strain', 'dyn:Stress')
        plot.add_trace(np.linspace(0, 0.2, 50), np.linspace(0, 400, 50), label="Panel 2")

        if plot.get_subplot_count() == 2:
            if verbose:
                print("  [PASS] Multi-panel configuration worked")
            passed += 1
        else:
            print(f"  [FAIL] Expected 2 subplots, got {plot.get_subplot_count()}")
            failed += 1
    except Exception as e:
        print(f"  [FAIL] Subplot configuration failed: {e}")
        failed += 1

    # Test refresh
    try:
        plot.refresh()
        if verbose:
            print("  [PASS] refresh() succeeded")
        passed += 1
    except Exception as e:
        print(f"  [FAIL] refresh() failed: {e}")
        failed += 1

    # Test with DataSeriesWidget integration
    try:
        container = DataSeriesWidget()
        container.add_series(
            'dyn:Strain',
            np.linspace(0, 0.25, 100),
            unit='http://qudt.org/vocab/unit/UNITLESS',
            legend='Test Strain'
        )
        container.add_series(
            'dyn:Stress',
            np.linspace(0, 500, 100),
            unit='http://qudt.org/vocab/unit/MegaPA',
            legend='Test Stress'
        )

        # Reset to single panel for this test
        plot.configure_subplot(1, 1)
        plot.set_axis_series('dyn:Strain', 'dyn:Stress')

        trace_id = plot.add_trace_from_container(
            container,
            x_uri='dyn:Strain',
            y_uri='dyn:Stress',
            color='purple',
            linewidth=2.0
        )

        if trace_id:
            if verbose:
                print(f"  [PASS] add_trace_from_container returned id: {trace_id}")
            passed += 1
        else:
            print("  [FAIL] add_trace_from_container returned None")
            failed += 1
    except Exception as e:
        print(f"  [FAIL] DataSeriesWidget integration failed: {e}")
        failed += 1

    plot.enable_legend()
    plot.enable_grid()
    plot.set_title("Integration Test: Stress-Strain")
    plot.refresh()

    # Show visual window if requested
    if visual:
        print("\n  Showing Matplotlib visual test window (close to continue)...")
        plot.setWindowTitle("MatplotlibPlotWidget Visual Test")
        plot.resize(800, 600)
        plot.show()
        app.exec()

    print(f"\n  MatplotlibPlotWidget: {passed} passed, {failed} failed")
    return failed == 0


def test_plotly_plot_widget(ontology_manager, qudt_manager, visual: bool = False, verbose: bool = False):
    """Test PlotlyPlotWidget functionality."""
    from dynamat.gui.widgets.base import is_backend_available

    print("\n=== Testing PlotlyPlotWidget ===")

    if not is_backend_available('plotly'):
        print("  [SKIP] Plotly backend not available (install plotly and PyQtWebEngine)")
        return True  # Not a failure, just skipped

    from dynamat.gui.widgets.base import PlotlyPlotWidget, DataSeriesWidget

    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])

    passed = 0
    failed = 0

    # Create plot widget
    try:
        plot = PlotlyPlotWidget(ontology_manager, qudt_manager, show_toolbar=visual)
        if verbose:
            print("  [PASS] PlotlyPlotWidget created successfully")
        passed += 1
    except Exception as e:
        print(f"  [FAIL] PlotlyPlotWidget creation failed: {e}")
        failed += 1
        return False

    # Test set_axis_series
    try:
        plot.set_axis_series('dyn:Strain', 'dyn:Stress')
        if verbose:
            print("  [PASS] set_axis_series succeeded")
        passed += 1
    except Exception as e:
        print(f"  [FAIL] set_axis_series failed: {e}")
        failed += 1

    # Test add_trace
    try:
        x = np.linspace(0, 0.3, 100)
        y = 500 * x  # Simple stress-strain curve

        trace_id = plot.add_trace(x, y, label="Test Data", color="blue")
        if trace_id:
            if verbose:
                print(f"  [PASS] add_trace returned id: {trace_id}")
            passed += 1
        else:
            print("  [FAIL] add_trace returned None")
            failed += 1
    except Exception as e:
        print(f"  [FAIL] add_trace failed: {e}")
        failed += 1

    # Test add_reference_line
    try:
        plot.add_reference_line('h', 100, color='red', linestyle='--', label="Yield")
        plot.add_reference_line('v', 0.1, color='green', linestyle=':', label="0.1 strain")
        if verbose:
            print("  [PASS] add_reference_line succeeded")
        passed += 1
    except Exception as e:
        print(f"  [FAIL] add_reference_line failed: {e}")
        failed += 1

    # Test styling
    try:
        plot.set_title("Stress-Strain Curve (Plotly)")
        plot.enable_legend()
        plot.enable_grid()
        if verbose:
            print("  [PASS] Styling methods succeeded")
        passed += 1
    except Exception as e:
        print(f"  [FAIL] Styling methods failed: {e}")
        failed += 1

    # Test subplot configuration
    try:
        plot.configure_subplot(1, 2)
        plot.set_active_subplot(0)
        plot.set_axis_series('dyn:Time', 'dyn:IncidentPulse')
        plot.add_trace(np.linspace(0, 1, 50), np.random.randn(50), label="Panel 1")

        plot.set_active_subplot(1)
        plot.set_axis_series('dyn:Strain', 'dyn:Stress')
        plot.add_trace(np.linspace(0, 0.2, 50), np.linspace(0, 400, 50), label="Panel 2")

        if plot.get_subplot_count() == 2:
            if verbose:
                print("  [PASS] Multi-panel configuration worked")
            passed += 1
        else:
            print(f"  [FAIL] Expected 2 subplots, got {plot.get_subplot_count()}")
            failed += 1
    except Exception as e:
        print(f"  [FAIL] Subplot configuration failed: {e}")
        failed += 1

    # Test refresh
    try:
        plot.refresh()
        if verbose:
            print("  [PASS] refresh() succeeded")
        passed += 1
    except Exception as e:
        print(f"  [FAIL] refresh() failed: {e}")
        failed += 1

    # Test with DataSeriesWidget integration
    try:
        container = DataSeriesWidget()
        container.add_series(
            'dyn:Strain',
            np.linspace(0, 0.25, 100),
            unit='http://qudt.org/vocab/unit/UNITLESS',
            legend='Test Strain'
        )
        container.add_series(
            'dyn:Stress',
            np.linspace(0, 500, 100),
            unit='http://qudt.org/vocab/unit/MegaPA',
            legend='Test Stress'
        )

        # Reset to single panel for this test
        plot.configure_subplot(1, 1)
        plot.set_axis_series('dyn:Strain', 'dyn:Stress')

        trace_id = plot.add_trace_from_container(
            container,
            x_uri='dyn:Strain',
            y_uri='dyn:Stress',
            color='purple',
            linewidth=2.0
        )

        if trace_id:
            if verbose:
                print(f"  [PASS] add_trace_from_container returned id: {trace_id}")
            passed += 1
        else:
            print("  [FAIL] add_trace_from_container returned None")
            failed += 1
    except Exception as e:
        print(f"  [FAIL] DataSeriesWidget integration failed: {e}")
        failed += 1

    plot.enable_legend()
    plot.enable_grid()
    plot.set_title("Integration Test: Stress-Strain (Plotly)")
    plot.refresh()

    # Show visual window if requested
    if visual:
        print("\n  Showing Plotly visual test window (close to continue)...")
        plot.setWindowTitle("PlotlyPlotWidget Visual Test")
        plot.resize(900, 600)
        plot.show()
        app.exec()

    print(f"\n  PlotlyPlotWidget: {passed} passed, {failed} failed")
    return failed == 0


def test_factory_creates_correct_widget(ontology_manager, qudt_manager, verbose: bool = False):
    """Test that the factory creates the correct widget based on backend."""
    from dynamat.gui.widgets.base import (
        create_plot_widget, MatplotlibPlotWidget, is_backend_available
    )
    from dynamat.config import Config

    print("\n=== Testing Factory Widget Creation ===")

    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])

    passed = 0
    failed = 0

    # Test explicit matplotlib backend
    try:
        plot = create_plot_widget(ontology_manager, qudt_manager, backend='matplotlib')
        if isinstance(plot, MatplotlibPlotWidget):
            if verbose:
                print("  [PASS] backend='matplotlib' creates MatplotlibPlotWidget")
            passed += 1
        else:
            print(f"  [FAIL] Expected MatplotlibPlotWidget, got {type(plot).__name__}")
            failed += 1
    except Exception as e:
        print(f"  [FAIL] Factory with backend='matplotlib' failed: {e}")
        failed += 1

    # Test explicit plotly backend (if available)
    if is_backend_available('plotly'):
        try:
            from dynamat.gui.widgets.base import PlotlyPlotWidget
            plot = create_plot_widget(ontology_manager, qudt_manager, backend='plotly')
            if isinstance(plot, PlotlyPlotWidget):
                if verbose:
                    print("  [PASS] backend='plotly' creates PlotlyPlotWidget")
                passed += 1
            else:
                print(f"  [FAIL] Expected PlotlyPlotWidget, got {type(plot).__name__}")
                failed += 1
        except Exception as e:
            print(f"  [FAIL] Factory with backend='plotly' failed: {e}")
            failed += 1
    else:
        # Should fallback to matplotlib when plotly not available
        try:
            plot = create_plot_widget(ontology_manager, qudt_manager, backend='plotly')
            if isinstance(plot, MatplotlibPlotWidget):
                if verbose:
                    print("  [PASS] backend='plotly' falls back to MatplotlibPlotWidget (plotly not installed)")
                passed += 1
            else:
                print(f"  [FAIL] Expected fallback to MatplotlibPlotWidget, got {type(plot).__name__}")
                failed += 1
        except Exception as e:
            print(f"  [FAIL] Factory fallback failed: {e}")
            failed += 1

    # Test config-based backend selection
    original_backend = Config.PLOT_BACKEND
    try:
        Config.PLOT_BACKEND = 'matplotlib'
        plot = create_plot_widget(ontology_manager, qudt_manager)
        if isinstance(plot, MatplotlibPlotWidget):
            if verbose:
                print("  [PASS] Config.PLOT_BACKEND='matplotlib' works")
            passed += 1
        else:
            print(f"  [FAIL] Config.PLOT_BACKEND='matplotlib' created wrong type")
            failed += 1
    except Exception as e:
        print(f"  [FAIL] Config-based backend selection failed: {e}")
        failed += 1
    finally:
        Config.PLOT_BACKEND = original_backend

    print(f"\n  Factory Widget Creation: {passed} passed, {failed} failed")
    return failed == 0


def main():
    parser = argparse.ArgumentParser(description="Test plot widgets")
    parser.add_argument('--verbose', '-v', action='store_true', help="Show detailed output")
    parser.add_argument('--visual', action='store_true', help="Show interactive plot window")
    parser.add_argument('--backend', choices=['matplotlib', 'plotly', 'all'], default='all',
                       help="Which backend to test visually (default: all)")
    args = parser.parse_args()

    print("=" * 60)
    print("DynaMat Platform - Plot Widget Integration Test")
    print("=" * 60)

    # Initialize managers
    print("\nInitializing OntologyManager and QUDTManager...")
    try:
        from dynamat.ontology import OntologyManager
        from dynamat.ontology.qudt import QUDTManager

        ontology_manager = OntologyManager()
        qudt_manager = QUDTManager()
        qudt_manager.load()

        print("  Managers initialized successfully")
    except Exception as e:
        print(f"  [ERROR] Failed to initialize managers: {e}")
        sys.exit(1)

    # Run tests
    results = []

    results.append(("SeriesMetadataResolver", test_series_metadata_resolver(ontology_manager, qudt_manager, args.verbose)))
    results.append(("DataSeriesWidget", test_data_series_widget(args.verbose)))
    results.append(("PlotWidgetFactory", test_plot_widget_factory(args.verbose)))

    # Test Matplotlib widget
    show_matplotlib = args.visual and args.backend in ('matplotlib', 'all')
    results.append(("MatplotlibPlotWidget", test_matplotlib_plot_widget(
        ontology_manager, qudt_manager, show_matplotlib, args.verbose)))

    # Test Plotly widget
    show_plotly = args.visual and args.backend in ('plotly', 'all')
    results.append(("PlotlyPlotWidget", test_plotly_plot_widget(
        ontology_manager, qudt_manager, show_plotly, args.verbose)))

    # Test factory widget creation
    results.append(("FactoryWidgetCreation", test_factory_creates_correct_widget(
        ontology_manager, qudt_manager, args.verbose)))

    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)

    all_passed = True
    for name, passed in results:
        status = "PASS" if passed else "FAIL"
        print(f"  {name}: {status}")
        if not passed:
            all_passed = False

    print()
    if all_passed:
        print("All tests PASSED!")
        sys.exit(0)
    else:
        print("Some tests FAILED.")
        sys.exit(1)


if __name__ == "__main__":
    main()
