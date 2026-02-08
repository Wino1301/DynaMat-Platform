import pytest
import numpy as np
from dynamat.ontology.qudt.qudt_manager import QUDTUnit

class TestQUDTManager:
    """Tests for QUDTManager and unit conversions."""

    def test_unit_lookup(self, qudt_manager):
        """Test looking up units by URI."""
        # Test a common unit: Millimeter
        unit = qudt_manager.get_unit_by_uri("http://qudt.org/vocab/unit/MilliM")
        assert unit is not None
        assert unit.symbol == "mm"
        assert unit.label.lower() == "millimetre"
        assert "http://qudt.org/vocab/quantitykind/Length" in unit.quantity_kinds

    def test_prefixed_unit_lookup(self, qudt_manager):
        """Test looking up units using prefixed URIs."""
        unit = qudt_manager.get_unit_by_uri("unit:MilliM")
        assert unit is not None
        assert unit.symbol == "mm"

    def test_get_units_for_quantity_kind(self, qudt_manager):
        """Test retrieving all units for a specific quantity kind."""
        units = qudt_manager.get_units_for_quantity_kind("http://qudt.org/vocab/quantitykind/Length")
        assert len(units) > 0
        symbols = [u.symbol for u in units]
        assert "m" in symbols
        assert "mm" in symbols
        assert "cm" in symbols

    def test_ratio_scale_conversion(self, qudt_manager):
        """Test conversion for ratio scales (offset = 0)."""
        # 10 inches to millimeters
        # 1 inch = 25.4 mm
        # 10 inches = 254 mm
        value = 10.0
        result = qudt_manager.convert_value(value, "unit:IN", "unit:MilliM")
        assert pytest.approx(result, rel=1e-5) == 254.0

    def test_interval_scale_conversion(self, qudt_manager):
        """Test conversion for interval scales (offset != 0)."""
        # 100 Celsius to Kelvin
        # 100 + 273.15 = 373.15
        value = 100.0
        result = qudt_manager.convert_value(value, "unit:DEG_C", "unit:K")
        assert pytest.approx(result, rel=1e-5) == 373.15

        # 32 Fahrenheit to Celsius
        # 32 °F = 0 °C
        value = 32.0
        result = qudt_manager.convert_value(value, "unit:DEG_F", "unit:DEG_C")
        assert pytest.approx(result, abs=1e-5) == 0.0

    def test_incompatible_units_warning(self, qudt_manager, caplog):
        """Test that conversion between incompatible units logs a warning."""
        # Length to Mass conversion (should log warning but still calculate if possible)
        # Note: QUDT conversion logic works as long as multipliers/offsets exist
        value = 10.0
        qudt_manager.convert_value(value, "unit:MilliM", "unit:KiloGM")
        assert "Unit conversion between different quantity kinds" in caplog.text

    def test_invalid_unit_raises_error(self, qudt_manager):
        """Test that non-existent units raise ValueError."""
        with pytest.raises(ValueError, match="Source unit not found"):
            qudt_manager.convert_value(10.0, "unit:NonExistentUnit", "unit:MilliM")
