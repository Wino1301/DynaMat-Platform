"""
DynaMat Platform - Calculation Engine
Mathematical calculations for form dependencies
"""

import logging
import math
from typing import Dict, Any, Optional, List
from enum import Enum

logger = logging.getLogger(__name__)


class CalculationType(Enum):
    """Types of calculations supported by the engine."""
    AREA = "area"
    VOLUME = "volume"
    DENSITY = "density"
    MASS = "mass"
    STRAIN_RATE = "strain_rate"
    STRESS = "stress"
    CUSTOM = "custom"


class CalculationEngine:
    """
    Handles mathematical calculations for form dependencies.
    
    Provides a centralized location for all calculation logic,
    making it easier to maintain and test.
    """
    
    def __init__(self):
        """Initialize the calculation engine."""
        self.logger = logging.getLogger(__name__)
        
        # Registry of calculation functions
        self.calculation_functions = {
            # Area calculations
            'circular_area_from_diameter': self._calc_circular_area_from_diameter,
            'circular_area_from_radius': self._calc_circular_area_from_radius,
            'rectangular_area': self._calc_rectangular_area,
            'square_area': self._calc_square_area,
            
            # Volume calculations
            'volume_cube': self._calc_volume_cube,
            'volume_cylinder': self._calc_volume_cylinder,
            'volume_rectangular': self._calc_volume_rectangular,
            'volume_sphere': self._calc_volume_sphere,
            
            # Density and mass calculations
            'density_from_mass_volume': self._calc_density_from_mass_volume,
            'mass_from_density_volume': self._calc_mass_from_density_volume,
            'volume_from_mass_density': self._calc_volume_from_mass_density,
            
            # Engineering calculations
            'strain_rate_from_velocity_length': self._calc_strain_rate_from_velocity_length,
            'stress_from_force_area': self._calc_stress_from_force_area,
            'force_from_stress_area': self._calc_force_from_stress_area,
            
            # Unit conversions
            'convert_units': self._convert_units,
        }
        
        # Unit conversion factors (to SI base units)
        self.unit_conversions = {
            # Length conversions to meters
            'mm': 0.001,
            'cm': 0.01,
            'm': 1.0,
            'in': 0.0254,
            'ft': 0.3048,
            
            # Area conversions to m²
            'mm²': 1e-6,
            'cm²': 1e-4,
            'm²': 1.0,
            'in²': 0.00064516,
            
            # Volume conversions to m³
            'mm³': 1e-9,
            'cm³': 1e-6,
            'm³': 1.0,
            'in³': 1.6387e-5,
            
            # Mass conversions to kg
            'g': 0.001,
            'kg': 1.0,
            'lb': 0.453592,
            
            # Force conversions to N
            'N': 1.0,
            'kN': 1000.0,
            'lbf': 4.44822,
            
            # Pressure/Stress conversions to Pa
            'Pa': 1.0,
            'kPa': 1000.0,
            'MPa': 1e6,
            'GPa': 1e9,
            'psi': 6894.76,
            'ksi': 6.89476e6,
        }
    
    def calculate(self, function_name: str, **kwargs) -> Optional[float]:
        """
        Perform a calculation.
        
        Args:
            function_name: Name of the calculation function
            **kwargs: Arguments for the calculation
            
        Returns:
            Calculation result or None if failed
        """
        try:
            if function_name not in self.calculation_functions:
                self.logger.error(f"Unknown calculation function: {function_name}")
                return None
            
            calc_func = self.calculation_functions[function_name]
            result = calc_func(**kwargs)
            
            self.logger.debug(f"Calculation {function_name} with {kwargs} = {result}")
            return result
            
        except Exception as e:
            self.logger.error(f"Calculation failed for {function_name}: {e}")
            return None
    
    def get_available_calculations(self) -> List[str]:
        """Get list of available calculation functions."""
        return list(self.calculation_functions.keys())
    
    def validate_calculation_inputs(self, function_name: str, **kwargs) -> List[str]:
        """
        Validate inputs for a calculation.
        
        Args:
            function_name: Name of the calculation function
            **kwargs: Arguments to validate
            
        Returns:
            List of validation error messages
        """
        errors = []
        
        try:
            if function_name not in self.calculation_functions:
                errors.append(f"Unknown calculation: {function_name}")
                return errors
            
            # Get function and check required parameters
            calc_func = self.calculation_functions[function_name]
            
            # Basic validation for common parameters
            for param, value in kwargs.items():
                if value is None:
                    errors.append(f"Parameter {param} cannot be None")
                elif isinstance(value, (int, float)) and value < 0:
                    if param in ['diameter', 'radius', 'length', 'width', 'height', 'mass', 'volume', 'area']:
                        errors.append(f"Parameter {param} cannot be negative")
            
            return errors
            
        except Exception as e:
            errors.append(f"Validation error: {str(e)}")
            return errors
    
    # ============================================================================
    # AREA CALCULATION METHODS
    # ============================================================================
    
    def _calc_circular_area_from_diameter(self, **kwargs) -> float:
        """
        Calculate circular area from diameter: A = π × (d/2)²

        Accepts diameter from any property URI that contains 'Diameter' in the key.
        """
        # Extract diameter value from kwargs (could be any property URI)
        diameter = None
        for key, value in kwargs.items():
            if 'Diameter' in key or 'diameter' in key:
                diameter = value
                break

        if diameter is None:
            raise ValueError("No diameter value provided in inputs")

        if diameter <= 0:
            raise ValueError("Diameter must be positive")

        radius = diameter / 2.0
        return math.pi * radius * radius
    
    def _calc_circular_area_from_radius(self, radius: float, **kwargs) -> float:
        """Calculate circular area from radius: A = π × r²"""
        if radius <= 0:
            raise ValueError("Radius must be positive")
        return math.pi * radius * radius
    
    def _calc_rectangular_area(self, **kwargs) -> float:
        """
        Calculate rectangular area: A = width × thickness (or length × width)

        Accepts dimensions from any property URIs that contain 'Width' and 'Thickness' (or 'Length').
        """
        # Extract width and thickness/length values from kwargs
        width = None
        thickness = None

        for key, value in kwargs.items():
            if 'Width' in key or 'width' in key:
                width = value
            elif 'Thickness' in key or 'thickness' in key:
                thickness = value
            elif thickness is None and ('Length' in key or 'length' in key):
                # Use length as second dimension if thickness not found
                thickness = value

        if width is None or thickness is None:
            raise ValueError("Need both width and thickness (or length) values for rectangular area calculation")

        if width <= 0 or thickness <= 0:
            raise ValueError("Width and thickness must be positive")

        return width * thickness
    
    def _calc_square_area(self, **kwargs) -> float:
        """
        Calculate square area: A = side²

        Accepts side length from any property URI that contains 'Length' or 'Side' in the key.
        """
        # Extract side/length value from kwargs (could be any property URI)
        side = None
        for key, value in kwargs.items():
            if 'Length' in key or 'length' in key:
                side = value
                break

        if side is None:
            raise ValueError("No side/length value provided in inputs")

        if side <= 0:
            raise ValueError("Side length must be positive")

        return side * side
    
    # ============================================================================
    # VOLUME CALCULATION METHODS
    # ============================================================================
    
    def _calc_volume_cylinder(self, diameter: float, length: float, **kwargs) -> float:
        """Calculate cylinder volume: V = π × (d/2)² × L"""
        if diameter <= 0 or length <= 0:
            raise ValueError("Diameter and length must be positive")
        radius = diameter / 2.0
        return math.pi * radius * radius * length
    
    def _calc_volume_cube(self, side: float, **kwargs) -> float:
        """Calculate cube volume: V = side³"""
        if side <= 0:
            raise ValueError("Side length must be positive")
        return side * side * side
    
    def _calc_volume_rectangular(self, length: float, width: float, height: float, **kwargs) -> float:
        """Calculate rectangular volume: V = L × W × H"""
        if length <= 0 or width <= 0 or height <= 0:
            raise ValueError("All dimensions must be positive")
        return length * width * height
    
    def _calc_volume_sphere(self, radius: float, **kwargs) -> float:
        """Calculate sphere volume: V = (4/3) × π × r³"""
        if radius <= 0:
            raise ValueError("Radius must be positive")
        return (4.0 / 3.0) * math.pi * radius * radius * radius
    
    # ============================================================================
    # DENSITY AND MASS CALCULATION METHODS
    # ============================================================================
    
    def _calc_density_from_mass_volume(self, mass: float, volume: float, **kwargs) -> float:
        """Calculate density: ρ = m / V"""
        if mass <= 0 or volume <= 0:
            raise ValueError("Mass and volume must be positive")
        return mass / volume
    
    def _calc_mass_from_density_volume(self, density: float, volume: float, **kwargs) -> float:
        """Calculate mass: m = ρ × V"""
        if density <= 0 or volume <= 0:
            raise ValueError("Density and volume must be positive")
        return density * volume
    
    def _calc_volume_from_mass_density(self, mass: float, density: float, **kwargs) -> float:
        """Calculate volume: V = m / ρ"""
        if mass <= 0 or density <= 0:
            raise ValueError("Mass and density must be positive")
        return mass / density
    
    # ============================================================================
    # ENGINEERING CALCULATION METHODS
    # ============================================================================
    
    def _calc_strain_rate_from_velocity_length(self, velocity: float, length: float, **kwargs) -> float:
        """Calculate strain rate: ε̇ = v / L"""
        if length <= 0:
            raise ValueError("Length must be positive")
        return velocity / length
    
    def _calc_stress_from_force_area(self, force: float, area: float, **kwargs) -> float:
        """Calculate stress: σ = F / A"""
        if area <= 0:
            raise ValueError("Area must be positive")
        return force / area
    
    def _calc_force_from_stress_area(self, stress: float, area: float, **kwargs) -> float:
        """Calculate force: F = σ × A"""
        if area <= 0:
            raise ValueError("Area must be positive")
        return stress * area
    
    # ============================================================================
    # UNIT CONVERSION METHODS
    # ============================================================================
    
    def _convert_units(self, value: float, from_unit: str, to_unit: str, **kwargs) -> float:
        """
        Convert between units.
        
        Args:
            value: Value to convert
            from_unit: Source unit
            to_unit: Target unit
            
        Returns:
            Converted value
        """
        if from_unit == to_unit:
            return value
        
        # Get conversion factors
        from_factor = self.unit_conversions.get(from_unit)
        to_factor = self.unit_conversions.get(to_unit)
        
        if from_factor is None:
            raise ValueError(f"Unknown unit: {from_unit}")
        if to_factor is None:
            raise ValueError(f"Unknown unit: {to_unit}")
        
        # Convert to SI base unit, then to target unit
        si_value = value * from_factor
        result = si_value / to_factor
        
        return result
    
    def get_supported_units(self) -> Dict[str, List[str]]:
        """
        Get dictionary of supported units by category.
        
        Returns:
            Dictionary mapping categories to unit lists
        """
        return {
            'length': ['mm', 'cm', 'm', 'in', 'ft'],
            'area': ['mm²', 'cm²', 'm²', 'in²'],
            'volume': ['mm³', 'cm³', 'm³', 'in³'],
            'mass': ['g', 'kg', 'lb'],
            'force': ['N', 'kN', 'lbf'],
            'pressure': ['Pa', 'kPa', 'MPa', 'GPa', 'psi', 'ksi']
        }
    
    def is_unit_compatible(self, unit1: str, unit2: str) -> bool:
        """
        Check if two units are compatible for conversion.
        
        Args:
            unit1: First unit
            unit2: Second unit
            
        Returns:
            True if units are compatible
        """
        # Get unit categories
        categories = self.get_supported_units()
        
        unit1_category = None
        unit2_category = None
        
        for category, units in categories.items():
            if unit1 in units:
                unit1_category = category
            if unit2 in units:
                unit2_category = category
        
        return unit1_category is not None and unit1_category == unit2_category
    
    # ============================================================================
    # UTILITY METHODS
    # ============================================================================
    
    def format_result(self, value: float, decimal_places: int = 6) -> str:
        """
        Format calculation result for display.
        
        Args:
            value: Value to format
            decimal_places: Number of decimal places
            
        Returns:
            Formatted string
        """
        if value is None:
            return "N/A"
        
        # Use scientific notation for very large or small numbers
        if abs(value) >= 1e6 or (abs(value) < 1e-3 and value != 0):
            return f"{value:.{decimal_places}e}"
        else:
            return f"{value:.{decimal_places}f}".rstrip('0').rstrip('.')
    
    def get_calculation_info(self, function_name: str) -> Dict[str, Any]:
        """
        Get information about a calculation function.
        
        Args:
            function_name: Name of the calculation function
            
        Returns:
            Dictionary with function information
        """
        if function_name not in self.calculation_functions:
            return {}
        
        # Get function object
        func = self.calculation_functions[function_name]
        
        return {
            'name': function_name,
            'description': func.__doc__ or "No description available",
            'category': self._get_calculation_category(function_name)
        }
    
    def _get_calculation_category(self, function_name: str) -> str:
        """Get category for a calculation function."""
        if 'area' in function_name:
            return 'Area'
        elif 'volume' in function_name:
            return 'Volume'
        elif 'density' in function_name or 'mass' in function_name:
            return 'Mass/Density'
        elif 'strain' in function_name or 'stress' in function_name or 'force' in function_name:
            return 'Engineering'
        elif 'convert' in function_name:
            return 'Unit Conversion'
        else:
            return 'General'