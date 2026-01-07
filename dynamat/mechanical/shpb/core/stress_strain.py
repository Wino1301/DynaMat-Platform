"""Stress-strain calculation for SHPB analysis.

This module provides tools for converting aligned SHPB pulses into
engineering stress-strain curves using 1-wave, 2-wave, or 3-wave analysis
methods.

Classes
-------
StressStrainCalculator : Configurable stress-strain computation engine

References
----------
Gray, G. T. (2000). Classic Split-Hopkinson Pressure Bar Testing.
ASM Handbook, Vol. 8: Mechanical Testing and Evaluation.

Kolsky, H. (1949). An Investigation of the Mechanical Properties of
Materials at very High Rates of Loading. Proceedings of the Physical
Society. Section B, 62(11), 676.
"""
from __future__ import annotations
from typing import Tuple, Dict, Literal
import numpy as np
from scipy.integrate import cumulative_trapezoid


class StressStrainCalculator:
    """Calculate stress-strain curves from aligned SHPB pulses.

    Computes engineering stress, strain, and strain rate from incident,
    transmitted, and reflected pulses using standard SHPB equations.
    Supports 1-wave, 2-wave, and 3-wave analysis methods.

    All results are returned as absolute values following the compressive
    loading convention (positive stress, strain, and strain rate).

    Parameters
    ----------
    bar_diameter : float
        Bar diameter (mm).
    bar_wave_speed : float
        Elastic wave speed in bar material (mm/ms).
    bar_elastic_modulus : float
        Elastic / Young's modulus of bar material (GPa).
    specimen_diameter : float
        Specimen diameter (mm).
    specimen_length : float
        Initial specimen length (mm).
    strain_scale_factor : float, default 1e4
        Scale factor to convert input strain signals to dimensionless strain.
        Default 1e4 assumes input strains are in units where 10000 = 1.0 strain
        (common for SHPB gauge data). Set to 1.0 if inputs are already dimensionless.

    Examples
    --------
    >>> calculator = StressStrainCalculator(
    ...     bar_diameter=19.0,
    ...     bar_wave_speed=4953.3,
    ...     bar_elastic_modulus=200.0,  # GPa
    ...     specimen_diameter=12.7,
    ...     specimen_length=6.5,
    ...     strain_scale_factor=1e4  # Convert scaled gauge data to dimensionless
    ... )
    >>> results = calculator.calculate(
    ...     incident=inc_aligned,
    ...     transmitted=trs_aligned,
    ...     reflected=ref_aligned,
    ...     time_vector=time,
    ...     method='1-wave'
    ... )
    >>> stress = results['stress']
    >>> strain = results['strain']
    >>> strain_rate = results['strain_rate']
    """

    def __init__(
        self,
        bar_diameter: float,
        bar_wave_speed: float,
        bar_elastic_modulus: float,
        specimen_diameter: float,
        specimen_length: float,
        strain_scale_factor: float = 1e4
    ):
        self.bar_diameter = bar_diameter
        self.bar_wave_speed = bar_wave_speed
        self.bar_elastic_modulus = bar_elastic_modulus
        self.specimen_diameter = specimen_diameter
        self.specimen_length = specimen_length
        self.strain_scale_factor = strain_scale_factor

        # Derived quantities
        self.bar_area = np.pi * (bar_diameter / 2) ** 2
        self.specimen_area = np.pi * (specimen_diameter / 2) ** 2
        self.area_ratio = self.bar_area / self.specimen_area

    def calculate(
        self,
        incident: np.ndarray,
        transmitted: np.ndarray,
        reflected: np.ndarray,
        time_vector: np.ndarray,
        method: Literal['1-wave', '2-wave', '3-wave'] = '1-wave'
    ) -> Dict[str, np.ndarray]:
        """Calculate stress-strain curve from aligned pulses.

        Input strains are automatically converted to dimensionless using
        the strain_scale_factor.

        Parameters
        ----------
        incident : np.ndarray
            Incident pulse strain (in units defined by strain_scale_factor).
        transmitted : np.ndarray
            Transmitted pulse strain (in units defined by strain_scale_factor).
        reflected : np.ndarray
            Reflected pulse strain (in units defined by strain_scale_factor).
        time_vector : np.ndarray
            Time axis (ms), same length as pulses.
        method : {'1-wave', '2-wave', '3-wave'}, default '1-wave'
            Analysis method:
            - '1-wave': Uses only reflected/transmitted pulses (assumes equilibrium)
            - '2-wave': Uses incident and reflected pulses
            - '3-wave': Uses all three pulses (most complete, checks equilibrium)

        Returns
        -------
        Dict[str, np.ndarray]
            Dictionary containing:
            - 'stress' : Engineering stress (MPa, absolute value)
            - 'strain' : Engineering strain (unitless, absolute value)
            - 'strain_rate' : Strain rate (1/s, absolute value)
            - 'time' : Time vector (ms)

        Raises
        ------
        ValueError
            If input arrays have different lengths.
        """
        # Validate inputs
        N = len(time_vector)
        if not (len(incident) == len(transmitted) == len(reflected) == N):
            raise ValueError(
                f"All inputs must have same length. Got: "
                f"time={N}, incident={len(incident)}, "
                f"transmitted={len(transmitted)}, reflected={len(reflected)}"
            )

        # Calculate based on method
        if method == '1-wave':
            return self._calculate_1wave(
                transmitted, reflected, time_vector
            )
        elif method == '2-wave':
            return self._calculate_2wave(
                incident, reflected, time_vector
            )
        elif method == '3-wave':
            return self._calculate_3wave(
                incident, transmitted, reflected, time_vector
            )
        else:
            raise ValueError(
                f"Unknown method '{method}'. "
                f"Use '1-wave', '2-wave', or '3-wave'."
            )

    def _calculate_1wave(
        self,
        transmitted: np.ndarray,
        reflected: np.ndarray,
        time: np.ndarray
    ) -> Dict[str, np.ndarray]:
        """1-wave analysis (assumes stress equilibrium).

        Uses:
        - Stress from transmitted pulse
        - Strain rate from reflected pulse
        - Strain from integrating strain rate

        Input strains are automatically converted to dimensionless using
        the strain_scale_factor. Returns absolute values (compressive loading convention).

        Parameters
        ----------
        transmitted : np.ndarray
            Transmitted pulse strain (in units defined by strain_scale_factor).
        reflected : np.ndarray
            Reflected pulse strain (in units defined by strain_scale_factor).
        time : np.ndarray
            Time vector (ms).

        Returns
        -------
        Dict[str, np.ndarray]
            Stress-strain data.
        """
        c = self.bar_wave_speed
        L = self.specimen_length
        E_bar = self.bar_elastic_modulus  # GPa (outputs MPa when multiplied by dimensionless strain)

        # Convert input strains to dimensionless
        transmitted_norm = transmitted / self.strain_scale_factor
        reflected_norm = reflected / self.strain_scale_factor

        # Stress from transmitted pulse (MPa)
        # E_bar is in GPa, so multiply by 1000 to convert to MPa
        stress = self.area_ratio * E_bar * transmitted_norm * 1000.0

        # Strain rate from reflected pulse (1/ms)
        strain_rate_ms = -(2 * c / L) * reflected_norm

        # Integrate to get strain
        strain = cumulative_trapezoid(strain_rate_ms, time, initial=0)

        # Convert strain rate to 1/s for output
        strain_rate_s = strain_rate_ms * 1000.0

        # Return absolute values (compressive loading convention)
        return {
            'stress': np.abs(stress),
            'strain': np.abs(strain),
            'strain_rate': np.abs(strain_rate_s),
            'time': time
        }

    def _calculate_2wave(
        self,
        incident: np.ndarray,
        reflected: np.ndarray,
        time: np.ndarray
    ) -> Dict[str, np.ndarray]:
        """2-wave analysis (uses incident and reflected bars).

        Uses:
        - Stress from (incident + reflected)
        - Strain rate from reflected pulse
        - Strain from integrating strain rate

        Input strains are automatically converted to dimensionless using
        the strain_scale_factor. Returns absolute values (compressive loading convention).

        Parameters
        ----------
        incident : np.ndarray
            Incident pulse strain (in units defined by strain_scale_factor).
        reflected : np.ndarray
            Reflected pulse strain (in units defined by strain_scale_factor).
        time : np.ndarray
            Time vector (ms).

        Returns
        -------
        Dict[str, np.ndarray]
            Stress-strain data.
        """
        c = self.bar_wave_speed
        L = self.specimen_length
        E_bar = self.bar_elastic_modulus  # GPa (outputs MPa when multiplied by dimensionless strain)

        # Convert input strains to dimensionless
        incident_norm = incident / self.strain_scale_factor
        reflected_norm = reflected / self.strain_scale_factor

        # Stress from incident + reflected (MPa)
        # E_bar is in GPa, so multiply by 1000 to convert to MPa
        stress = self.area_ratio * E_bar * (incident_norm + reflected_norm) * 1000.0

        # Strain rate from reflected pulse (1/ms)
        strain_rate_ms = -(2 * c / L) * reflected_norm

        # Integrate to get strain
        strain = cumulative_trapezoid(strain_rate_ms, time, initial=0)

        # Convert strain rate to 1/s
        strain_rate_s = strain_rate_ms * 1000.0

        # Return absolute values (compressive loading convention)
        return {
            'stress': np.abs(stress),
            'strain': np.abs(strain),
            'strain_rate': np.abs(strain_rate_s),
            'time': time
        }

    def _calculate_3wave(
        self,
        incident: np.ndarray,
        transmitted: np.ndarray,
        reflected: np.ndarray,
        time: np.ndarray
    ) -> Dict[str, np.ndarray]:
        """3-wave analysis (uses all three pulses).

        Uses:
        - Stress from transmitted pulse (or average of 1-wave and 2-wave)
        - Strain rate from all three pulses
        - Strain from integrating strain rate

        This is the most complete method and allows checking equilibrium.

        Input strains are automatically converted to dimensionless using
        the strain_scale_factor. Returns absolute values (compressive loading convention).

        Parameters
        ----------
        incident : np.ndarray
            Incident pulse strain (in units defined by strain_scale_factor).
        transmitted : np.ndarray
            Transmitted pulse strain (in units defined by strain_scale_factor).
        reflected : np.ndarray
            Reflected pulse strain (in units defined by strain_scale_factor).
        time : np.ndarray
            Time vector (ms).

        Returns
        -------
        Dict[str, np.ndarray]
            Stress-strain data.
        """
        c = self.bar_wave_speed
        L = self.specimen_length
        E_bar = self.bar_elastic_modulus  # GPa (outputs MPa when multiplied by dimensionless strain)

        # Convert input strains to dimensionless
        incident_norm = incident / self.strain_scale_factor
        transmitted_norm = transmitted / self.strain_scale_factor
        reflected_norm = reflected / self.strain_scale_factor

        # Stress from transmitted pulse (traditional 1-wave, MPa)
        # E_bar is in GPa, so multiply by 1000 to convert to MPa
        stress = self.area_ratio * E_bar * transmitted_norm * 1000.0

        # Strain rate from 3-wave formula (1/ms)
        strain_rate_ms = (c / L) * (incident_norm - reflected_norm - transmitted_norm)

        # Integrate to get strain
        strain = cumulative_trapezoid(strain_rate_ms, time, initial=0)

        # Convert strain rate to 1/s
        strain_rate_s = strain_rate_ms * 1000.0

        # Return absolute values (compressive loading convention)
        return {
            'stress': np.abs(stress),
            'strain': np.abs(strain),
            'strain_rate': np.abs(strain_rate_s),
            'time': time
        }

    def calculate_all_methods(
        self,
        incident: np.ndarray,
        transmitted: np.ndarray,
        reflected: np.ndarray,
        time_vector: np.ndarray
    ) -> Dict[str, Dict[str, np.ndarray]]:
        """Calculate stress-strain using all three methods for comparison.

        Useful for validating equilibrium assumptions and understanding
        differences between methods.

        Input strains are automatically converted to dimensionless using
        the strain_scale_factor. All results are returned as absolute values
        (compressive loading convention).

        Parameters
        ----------
        incident : np.ndarray
            Incident pulse strain (in units defined by strain_scale_factor).
        transmitted : np.ndarray
            Transmitted pulse strain (in units defined by strain_scale_factor).
        reflected : np.ndarray
            Reflected pulse strain (in units defined by strain_scale_factor).
        time_vector : np.ndarray
            Time axis (ms).

        Returns
        -------
        Dict[str, Dict[str, np.ndarray]]
            Dictionary with keys '1-wave', '2-wave', '3-wave', each containing
            the stress-strain results for that method.

        Examples
        --------
        >>> all_results = calculator.calculate_all_methods(inc, trs, ref, time)
        >>> stress_1w = all_results['1-wave']['stress']
        >>> stress_3w = all_results['3-wave']['stress']
        >>> equilibrium_error = np.mean(np.abs(stress_1w - stress_3w))
        """
        return {
            '1-wave': self.calculate(
                incident, transmitted, reflected, time_vector, method='1-wave'
            ),
            '2-wave': self.calculate(
                incident, transmitted, reflected, time_vector, method='2-wave'
            ),
            '3-wave': self.calculate(
                incident, transmitted, reflected, time_vector, method='3-wave'
            )
        }
