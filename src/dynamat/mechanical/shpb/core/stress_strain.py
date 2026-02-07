"""Stress-strain calculation for SHPB analysis.

This module provides tools for converting aligned SHPB pulses into
engineering stress-strain curves using 1-wave and 3-wave analysis methods.
All results include bar displacement, bar force, engineering quantities,
and true stress-strain calculations.

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

Chen, W. W., & Song, B. (2011). Split Hopkinson (Kolsky) Bar: Design,
Testing and Applications. Springer.
"""
from __future__ import annotations

import logging
from typing import Dict

import numpy as np
from scipy.integrate import cumulative_trapezoid
from scipy.stats import pearsonr

logger = logging.getLogger(__name__)


class StressStrainCalculator:
    """Calculate stress-strain curves from aligned SHPB pulses.

    Computes engineering stress, strain, and strain rate from incident,
    transmitted, and reflected pulses using standard SHPB equations.
    Calculates two analysis methods (1-wave and 2/3-wave) simultaneously
    along with derived quantities (bar displacement, bar force, true stress,
    true strain, and true strain rate).

    Results include both engineering and true quantities following the
    compressive loading convention.

    Parameters
    ----------
    bar_area : float
        Bar cross-sectional area (mm²).
    bar_wave_speed : float
        Elastic wave speed in bar material (mm/ms).
    bar_elastic_modulus : float
        Elastic / Young's modulus of bar material (GPa).
    specimen_area : float
        Specimen cross-sectional area (mm²).
    specimen_height : float
        Initial specimen height (mm).
    strain_scale_factor : float, default 1e4
        Scale factor to convert input strain signals to dimensionless strain.
        Default 1e4 assumes input strains are in units where 10000 = 1.0 strain
        (common for SHPB gauge data). Set to 1.0 if inputs are already dimensionless.
    use_voltage_input : bool, default False
        If True, input arrays are treated as voltages and converted to strain
        using gauge parameters before analysis.
    incident_reflected_gauge_params : dict, optional
        Gauge parameters for incident/reflected bars. Required if use_voltage_input=True.
        Must contain keys: 'gauge_res', 'gauge_factor', 'cal_voltage', 'cal_resistance'.
    transmitted_gauge_params : dict, optional
        Gauge parameters for transmitted bar. Required if use_voltage_input=True.
        Must contain keys: 'gauge_res', 'gauge_factor', 'cal_voltage', 'cal_resistance'.

    Examples
    --------
    >>> # Example 1: Using strain inputs
    >>> calculator = StressStrainCalculator(
    ...     bar_area=283.53,
    ...     bar_wave_speed=4953.3,
    ...     bar_elastic_modulus=199.99,
    ...     specimen_area=126.68,
    ...     specimen_height=6.5,
    ...     strain_scale_factor=1e4
    ... )
    >>> results = calculator.calculate(inc_aligned, trs_aligned, ref_aligned, time)
    >>> stress_1w = results['stress_1w']
    >>> force_1w = results['bar_force_1w']
    >>> true_strain_3w = results['true_strain_3w']
    >>>
    >>> # Example 2: Using voltage inputs
    >>> calculator = StressStrainCalculator(
    ...     bar_area=283.53,
    ...     bar_wave_speed=4953.3,
    ...     bar_elastic_modulus=199.99,
    ...     specimen_area=126.68,
    ...     specimen_height=6.5,
    ...     use_voltage_input=True,
    ...     incident_reflected_gauge_params={
    ...         'gauge_res': 350, 'gauge_factor': 2.1,
    ...         'cal_voltage': 5.0, 'cal_resistance': 100000
    ...     },
    ...     transmitted_gauge_params={
    ...         'gauge_res': 350, 'gauge_factor': 2.1,
    ...         'cal_voltage': 5.0, 'cal_resistance': 100000
    ...     }
    ... )
    >>> results = calculator.calculate(inc_voltage, trs_voltage, ref_voltage, time)
    >>> stress_3w = results['stress_3w']
    >>> displacement_3w = results['bar_displacement_3w']
    """

    def __init__(
        self,
        bar_area: float,
        bar_wave_speed: float,
        bar_elastic_modulus: float,
        specimen_area: float,
        specimen_height: float,
        strain_scale_factor: float = 1e4,
        use_voltage_input: bool = False,
        incident_reflected_gauge_params: dict = None,
        transmitted_gauge_params: dict = None
    ):

        self.bar_wave_speed = bar_wave_speed
        self.bar_elastic_modulus = bar_elastic_modulus
        self.specimen_height = specimen_height
        self.strain_scale_factor = strain_scale_factor
        self.use_voltage_input = use_voltage_input

        # Derived quantities
        self.bar_area = bar_area
        self.specimen_area = specimen_area
        self.area_ratio = self.bar_area / self.specimen_area

        # Voltage-to-strain conversion parameters
        self.incident_reflected_gauge_params = incident_reflected_gauge_params
        self.transmitted_gauge_params = transmitted_gauge_params

        # Validate gauge parameters if voltage input is enabled
        if use_voltage_input:
            required_keys = ['gauge_res', 'gauge_factor', 'cal_voltage', 'cal_resistance']

            if incident_reflected_gauge_params is None:
                msg = "incident_reflected_gauge_params must be provided when use_voltage_input=True"
                logger.error(msg)
                raise ValueError(msg)
            if transmitted_gauge_params is None:
                msg = "transmitted_gauge_params must be provided when use_voltage_input=True"
                logger.error(msg)
                raise ValueError(msg)

            # Check incident/reflected parameters
            missing_ir = [k for k in required_keys if k not in incident_reflected_gauge_params]
            if missing_ir:
                msg = f"incident_reflected_gauge_params missing required keys: {missing_ir}"
                logger.error(msg)
                raise ValueError(msg)

            # Check transmitted parameters
            missing_t = [k for k in required_keys if k not in transmitted_gauge_params]
            if missing_t:
                msg = f"transmitted_gauge_params missing required keys: {missing_t}"
                logger.error(msg)
                raise ValueError(msg)

    def calculate(
        self,
        incident: np.ndarray,
        transmitted: np.ndarray,
        reflected: np.ndarray,
        time_vector: np.ndarray
    ) -> Dict[str, np.ndarray]:
        """Calculate stress-strain curves from aligned pulses using two methods.

        Computes 1-wave and 3-wave analysis simultaneously with all derived
        quantities including bar displacements, forces, and true stress-strain.
        All results are returned in a single flat dictionary with suffixes
        _1w (1-wave) and _3w (3-wave).

        Input strains/voltages are automatically converted to dimensionless strain
        using the strain_scale_factor (and voltage_to_strain if enabled).

        Parameters
        ----------
        incident : np.ndarray
            Incident pulse (voltage if use_voltage_input=True, else strain).
        transmitted : np.ndarray
            Transmitted pulse (voltage if use_voltage_input=True, else strain).
        reflected : np.ndarray
            Reflected pulse (voltage if use_voltage_input=True, else strain).
        time_vector : np.ndarray
            Time axis (ms), same height as pulses.

        Returns
        -------
        Dict[str, np.ndarray]
            Dictionary containing all calculated series with suffixes:
            - 'time' : Time vector (ms)
            - 'incident' : Incident pulse (dimensionless strain)
            - 'transmitted' : Transmitted pulse (dimensionless strain)
            - 'reflected' : Reflected pulse (dimensionless strain)
            - 'bar_displacement_1w' : Bar displacement (mm) - 1-wave
            - 'bar_force_1w' : Bar force (N) - 1-wave
            - 'strain_rate_1w' : Engineering strain rate (1/ms) - 1-wave
            - 'strain_1w' : Engineering strain (unitless) - 1-wave
            - 'stress_1w' : Engineering stress (MPa) - 1-wave
            - 'true_strain_rate_1w' : True strain rate (1/ms) - 1-wave
            - 'true_strain_1w' : True strain (unitless) - 1-wave
            - 'true_stress_1w' : True stress (MPa) - 1-wave
            - 'bar_displacement_3w' : Bar displacement (mm) - 3-wave
            - 'bar_force_3w' : Bar force (N) - 3-wave
            - 'strain_rate_3w' : Engineering strain rate (1/ms) - 3-wave
            - 'strain_3w' : Engineering strain (unitless) - 3-wave
            - 'stress_3w' : Engineering stress (MPa) - 3-wave
            - 'true_strain_rate_3w' : True strain rate (1/ms) - 3-wave
            - 'true_strain_3w' : True strain (unitless) - 3-wave
            - 'true_stress_3w' : True stress (MPa) - 3-wave

        Raises
        ------
        ValueError
            If input arrays have different heights.

        Examples
        --------
        >>> calculator = StressStrainCalculator(...)
        >>> results = calculator.calculate(inc, trs, ref, time)
        >>> stress_1w = results['stress_1w']
        >>> true_strain_3w = results['true_strain_3w']
        >>> force_1w = results['bar_force_1w']
        """
        # Validate inputs
        N = len(time_vector)
        if not (len(incident) == len(transmitted) == len(reflected) == N):
            msg = (
                f"All inputs must have same length. Got: "
                f"time={N}, incident={len(incident)}, "
                f"transmitted={len(transmitted)}, reflected={len(reflected)}"
            )
            logger.error(msg)
            raise ValueError(msg)

        # Convert voltage to strain if needed
        if self.use_voltage_input:
            incident = self.voltage_to_strain(incident, self.incident_reflected_gauge_params)
            transmitted = self.voltage_to_strain(transmitted, self.transmitted_gauge_params)
            reflected = self.voltage_to_strain(reflected, self.incident_reflected_gauge_params)

        # Convert to dimensionless strain
        incident_norm = incident / self.strain_scale_factor
        transmitted_norm = transmitted / self.strain_scale_factor
        reflected_norm = reflected / self.strain_scale_factor

        # Common parameters
        c = self.bar_wave_speed
        L = self.specimen_height
        E_bar = self.bar_elastic_modulus  # GPa
        A_bar = self.bar_area
        A_spec = self.specimen_area

        # ===== 1-WAVE ANALYSIS =====
        # Bar displacement (mm)
        bar_displacement_1w = c * transmitted_norm

        # Bar force (N)
        bar_force_1w = A_bar * E_bar  * transmitted_norm

        # Engineering strain rate (1/ms)
        strain_rate_1w = (2 * c * reflected_norm) / L

        # True strain rate (1/ms)
        true_strain_rate_1w = np.log(1 + strain_rate_1w)

        # Engineering strain (integrate strain rate)
        strain_1w = ((2 * c) / L) * cumulative_trapezoid(reflected_norm, time_vector, initial=0)

        # Engineering stress (MPa)
        stress_1w = E_bar  * (A_bar / A_spec) * transmitted_norm

        # True strain
        true_strain_1w = np.log(1 + strain_1w)

        # True stress (MPa) - uses strain_1w
        true_stress_1w = stress_1w * (1 + strain_1w)

        # ===== 3-WAVE ANALYSIS =====
        # Bar displacement (mm)
        bar_displacement_3w = c * (incident_norm + reflected_norm)

        # Bar force (N)
        bar_force_3w = A_bar * E_bar  * (incident_norm + reflected_norm)

        # Engineering strain rate (1/ms)
        strain_rate_3w = (c / L) * (incident_norm - reflected_norm - transmitted_norm)

        # True strain rate (1/ms)
        true_strain_rate_3w = np.log(1 - strain_rate_3w)

        # Engineering strain (integrate strain rate)
        strain_3w = (c / L) * cumulative_trapezoid(
            (incident_norm - reflected_norm - transmitted_norm),
            time_vector,
            initial=0
        )

        # Engineering stress (MPa)
        stress_3w = E_bar  * (A_bar / A_spec) * (incident_norm + reflected_norm)

        # True strain
        true_strain_3w = np.log(1 + strain_3w)

        # True stress (MPa) - uses strain_3w
        true_stress_3w = stress_3w * (1 + strain_3w)

        # Return all results in a single flat dictionary with absolute values
        # First four columns: time, incident, transmitted, reflected (pulse windows)
        # Then all processed quantities for 1-wave and 3-wave analyses
        return {
            'time': time_vector,
            'incident': incident_norm,
            'transmitted': transmitted_norm,
            'reflected': reflected_norm,
            'bar_displacement_1w': np.abs(bar_displacement_1w),
            'bar_force_1w': np.abs(bar_force_1w),
            'strain_rate_1w': np.abs(strain_rate_1w) * 1000,
            'strain_1w': np.abs(strain_1w),
            'stress_1w': np.abs(stress_1w),
            'true_strain_rate_1w': np.abs(true_strain_rate_1w) *1000,
            'true_strain_1w': np.abs(true_strain_1w),
            'true_stress_1w': np.abs(true_stress_1w),
            'bar_displacement_3w': np.abs(bar_displacement_3w),
            'bar_force_3w': np.abs(bar_force_3w),
            'strain_rate_3w': np.abs(strain_rate_3w) * 1000,
            'strain_3w': np.abs(strain_3w),
            'stress_3w': np.abs(stress_3w),
            'true_strain_rate_3w': np.abs(true_strain_rate_3w) * 1000,
            'true_strain_3w': np.abs(true_strain_3w),
            'true_stress_3w': np.abs(true_stress_3w)
        }

    def _normalize_inputs(
        self,
        incident: np.ndarray,
        transmitted: np.ndarray,
        reflected: np.ndarray
    ):
        """Convert voltage to strain if needed, then normalize by scale factor.

        Returns
        -------
        tuple of np.ndarray
            (incident_norm, transmitted_norm, reflected_norm) as dimensionless strain.
        """
        if self.use_voltage_input:
            incident = self.voltage_to_strain(incident, self.incident_reflected_gauge_params)
            transmitted = self.voltage_to_strain(transmitted, self.transmitted_gauge_params)
            reflected = self.voltage_to_strain(reflected, self.incident_reflected_gauge_params)

        return (
            incident / self.strain_scale_factor,
            transmitted / self.strain_scale_factor,
            reflected / self.strain_scale_factor,
        )

    # ==================== INDIVIDUAL 1-WAVE METHODS ====================

    def bar_displacement_1w(self, transmitted_norm: np.ndarray) -> np.ndarray:
        """Bar displacement from transmitted pulse. Unit: mm."""
        return np.abs(self.bar_wave_speed * transmitted_norm)

    def bar_force_1w(self, transmitted_norm: np.ndarray) -> np.ndarray:
        """Bar force from transmitted pulse. Unit: N."""
        return np.abs(self.bar_area * self.bar_elastic_modulus * transmitted_norm)

    def strain_rate_1w(self, reflected_norm: np.ndarray) -> np.ndarray:
        """Engineering strain rate (1-wave). Unit: 1/s."""
        return np.abs((2 * self.bar_wave_speed * reflected_norm) / self.specimen_height) * 1000

    def strain_1w(self, reflected_norm: np.ndarray, time: np.ndarray) -> np.ndarray:
        """Engineering strain (1-wave). Unit: unitless."""
        return np.abs(
            (2 * self.bar_wave_speed / self.specimen_height)
            * cumulative_trapezoid(reflected_norm, time, initial=0)
        )

    def stress_1w(self, transmitted_norm: np.ndarray) -> np.ndarray:
        """Engineering stress (1-wave). Unit: MPa."""
        return np.abs(self.bar_elastic_modulus * self.area_ratio * transmitted_norm)

    def true_strain_1w(self, strain_1w_arr: np.ndarray) -> np.ndarray:
        """True strain from engineering strain. Unit: unitless."""
        return np.abs(np.log(1 + strain_1w_arr))

    def true_stress_1w(self, stress_1w_arr: np.ndarray, strain_1w_arr: np.ndarray) -> np.ndarray:
        """True stress from engineering stress and strain. Unit: MPa."""
        return np.abs(stress_1w_arr * (1 + strain_1w_arr))

    def true_strain_rate_1w(self, reflected_norm: np.ndarray) -> np.ndarray:
        """True strain rate (1-wave). Unit: 1/s."""
        raw_rate = (2 * self.bar_wave_speed * reflected_norm) / self.specimen_height
        return np.abs(np.log(1 + raw_rate)) * 1000

    # ==================== INDIVIDUAL 3-WAVE METHODS ====================

    def bar_displacement_3w(self, incident_norm: np.ndarray, reflected_norm: np.ndarray) -> np.ndarray:
        """Bar displacement (3-wave). Unit: mm."""
        return np.abs(self.bar_wave_speed * (incident_norm + reflected_norm))

    def bar_force_3w(self, incident_norm: np.ndarray, reflected_norm: np.ndarray) -> np.ndarray:
        """Bar force (3-wave). Unit: N."""
        return np.abs(self.bar_area * self.bar_elastic_modulus * (incident_norm + reflected_norm))

    def strain_rate_3w(self, incident_norm: np.ndarray, reflected_norm: np.ndarray, transmitted_norm: np.ndarray) -> np.ndarray:
        """Engineering strain rate (3-wave). Unit: 1/s."""
        return np.abs(
            (self.bar_wave_speed / self.specimen_height)
            * (incident_norm - reflected_norm - transmitted_norm)
        ) * 1000

    def strain_3w(self, incident_norm: np.ndarray, reflected_norm: np.ndarray, transmitted_norm: np.ndarray, time: np.ndarray) -> np.ndarray:
        """Engineering strain (3-wave). Unit: unitless."""
        return np.abs(
            (self.bar_wave_speed / self.specimen_height)
            * cumulative_trapezoid(
                incident_norm - reflected_norm - transmitted_norm,
                time, initial=0
            )
        )

    def stress_3w(self, incident_norm: np.ndarray, reflected_norm: np.ndarray) -> np.ndarray:
        """Engineering stress (3-wave). Unit: MPa."""
        return np.abs(self.bar_elastic_modulus * self.area_ratio * (incident_norm + reflected_norm))

    def true_strain_3w(self, strain_3w_arr: np.ndarray) -> np.ndarray:
        """True strain (3-wave). Unit: unitless."""
        return np.abs(np.log(1 + strain_3w_arr))

    def true_stress_3w(self, stress_3w_arr: np.ndarray, strain_3w_arr: np.ndarray) -> np.ndarray:
        """True stress (3-wave). Unit: MPa."""
        return np.abs(stress_3w_arr * (1 + strain_3w_arr))

    def true_strain_rate_3w(self, incident_norm: np.ndarray, reflected_norm: np.ndarray, transmitted_norm: np.ndarray) -> np.ndarray:
        """True strain rate (3-wave). Unit: 1/s."""
        raw_rate = (self.bar_wave_speed / self.specimen_height) * (incident_norm - reflected_norm - transmitted_norm)
        return np.abs(np.log(1 - raw_rate)) * 1000

    # ==================== ENRICHED CALCULATION ====================

    def calculate_enriched(
        self,
        incident: np.ndarray,
        transmitted: np.ndarray,
        reflected: np.ndarray,
        time_vector: np.ndarray,
        incident_uri: str = None,
        transmitted_uri: str = None,
        reflected_uri: str = None,
        time_uri: str = None,
        test_id: str = None,
    ) -> Dict[str, Dict]:
        """Calculate all series with provenance metadata per series.

        Provenance is inherent from function signatures - each ``enrich()`` call
        explicitly passes the URIs of its inputs. No external derivation map needed.

        Parameters
        ----------
        incident, transmitted, reflected : np.ndarray
            Input pulse arrays.
        time_vector : np.ndarray
            Time axis (ms).
        incident_uri, transmitted_uri, reflected_uri, time_uri : str, optional
            URIs of windowed input series for provenance tracking.
        test_id : str, optional
            Test ID for generating intermediate series URIs.

        Returns
        -------
        Dict[str, Dict]
            Enriched results: ``{key: {'data': array, 'series_type': uri,
            'unit': uri, 'derived_from': [uris], ...}}``.
        """
        from ..io.series_config import SERIES_METADATA

        N = len(time_vector)
        if not (len(incident) == len(transmitted) == len(reflected) == N):
            raise ValueError(
                f"All inputs must have same length. Got: time={N}, "
                f"incident={len(incident)}, transmitted={len(transmitted)}, "
                f"reflected={len(reflected)}"
            )

        inc_n, trs_n, ref_n = self._normalize_inputs(incident, transmitted, reflected)

        results = {}

        def enrich(key, data, derived_from_uris):
            meta = SERIES_METADATA.get(key, {})
            results[key] = {
                'data': data,
                'series_type': meta.get('series_type'),
                'unit': meta.get('unit'),
                'quantity_kind': meta.get('quantity_kind'),
                'analysis_method': meta.get('analysis_method'),
                'legend_name': meta.get('legend_name'),
                'derived_from': [u for u in derived_from_uris if u],
                'class_uri': meta.get('class_uri', 'https://dynamat.utep.edu/ontology#ProcessedData'),
            }

        # Windowed pulses (direct from inputs)
        enrich('time', time_vector, [time_uri])
        enrich('incident', inc_n, [incident_uri])
        enrich('transmitted', trs_n, [transmitted_uri])
        enrich('reflected', ref_n, [reflected_uri])

        # 1-wave: provenance from function arguments
        _bd1 = self.bar_displacement_1w(trs_n)
        enrich('bar_displacement_1w', _bd1, [transmitted_uri])

        _bf1 = self.bar_force_1w(trs_n)
        enrich('bar_force_1w', _bf1, [transmitted_uri])

        _sr1 = self.strain_rate_1w(ref_n)
        enrich('strain_rate_1w', _sr1, [reflected_uri])

        _s1 = self.strain_1w(ref_n, time_vector)
        enrich('strain_1w', _s1, [reflected_uri])

        _sig1 = self.stress_1w(trs_n)
        enrich('stress_1w', _sig1, [transmitted_uri])

        # True quantities derive from intermediate series
        _ts1 = self.true_strain_1w(_s1)
        enrich('true_strain_1w', _ts1, [f"dyn:{test_id}_strain_1w"] if test_id else [])

        _tsig1 = self.true_stress_1w(_sig1, _s1)
        enrich('true_stress_1w', _tsig1,
               [f"dyn:{test_id}_stress_1w", f"dyn:{test_id}_strain_1w"] if test_id else [])

        _tsr1 = self.true_strain_rate_1w(ref_n)
        enrich('true_strain_rate_1w', _tsr1, [f"dyn:{test_id}_strain_rate_1w"] if test_id else [])

        # 3-wave: multi-input provenance
        _bd3 = self.bar_displacement_3w(inc_n, ref_n)
        enrich('bar_displacement_3w', _bd3, [incident_uri, reflected_uri])

        _bf3 = self.bar_force_3w(inc_n, ref_n)
        enrich('bar_force_3w', _bf3, [incident_uri, reflected_uri])

        _sr3 = self.strain_rate_3w(inc_n, ref_n, trs_n)
        enrich('strain_rate_3w', _sr3, [incident_uri, reflected_uri, transmitted_uri])

        _s3 = self.strain_3w(inc_n, ref_n, trs_n, time_vector)
        enrich('strain_3w', _s3, [incident_uri, reflected_uri, transmitted_uri])

        _sig3 = self.stress_3w(inc_n, ref_n)
        enrich('stress_3w', _sig3, [incident_uri, reflected_uri])

        _ts3 = self.true_strain_3w(_s3)
        enrich('true_strain_3w', _ts3, [f"dyn:{test_id}_strain_3w"] if test_id else [])

        _tsig3 = self.true_stress_3w(_sig3, _s3)
        enrich('true_stress_3w', _tsig3,
               [f"dyn:{test_id}_stress_3w", f"dyn:{test_id}_strain_3w"] if test_id else [])

        _tsr3 = self.true_strain_rate_3w(inc_n, ref_n, trs_n)
        enrich('true_strain_rate_3w', _tsr3, [f"dyn:{test_id}_strain_rate_3w"] if test_id else [])

        return results

    def voltage_to_strain(self, voltage_array: np.ndarray, gauge_params: dict) -> np.ndarray:
        """
        Converts measured voltage from a strain gauge into strain.

        Parameters
        ----------
        voltage_array : np.ndarray
            Voltage measurements from the strain gauge (in volts).
        gauge_params : dict
            Dictionary containing gauge parameters with keys:
            - 'gauge_res' : float - Gauge resistance (ohms)
            - 'gauge_factor' : float - Gauge sensitivity coefficient (unitless)
            - 'cal_voltage' : float - Calibration voltage (volts)
            - 'cal_resistance' : float - Calibration resistor resistance (ohms)

        Returns
        -------
        np.ndarray
            Calculated strain values (unitless, dimensionless).

        Notes
        -----
        The conversion uses the formula:
        strain = voltage * (gauge_res / (cal_voltage * gauge_factor * (gauge_res + cal_resistance)))
        """
        gauge_res = gauge_params['gauge_res']
        gauge_factor = gauge_params['gauge_factor']
        cal_voltage = gauge_params['cal_voltage']
        cal_resistance = gauge_params['cal_resistance']

        conversion_factor = gauge_res / (cal_voltage * gauge_factor * (gauge_res + cal_resistance))
        strain = voltage_array * conversion_factor

        return strain

    def calculate_equilibrium_metrics(self, results: Dict[str, np.ndarray]) -> Dict[str, float]:
        """Calculate equilibrium assessment metrics between 1-wave and 3-wave analyses.

        Computes five metrics to assess the quality of stress equilibrium:
        1. Force Balance Coefficient (FBC) - measures force equilibrium
        2. Stress Equilibrium Quality Index (SEQI) - normalized RMSE metric
        3. Time-Windowed Analysis - metrics during loading, plateau, and unloading
        4. Stress Oscillation Index (SOI) - stress uniformity during plateau
        5. Dynamic Stress Uniformity Factor (DSUF) - R² correlation

        Parameters
        ----------
        results : Dict[str, np.ndarray]
            Dictionary returned by calculate() containing stress-strain data
            for both 1-wave and 3-wave analyses.

        Returns
        -------
        Dict[str, float]
            Dictionary containing equilibrium metrics:
            - 'FBC' : Force Balance Coefficient (0-1, higher is better)
            - 'SEQI' : Stress Equilibrium Quality Index (0-1, higher is better)
            - 'SOI' : Stress Oscillation Index (lower is better)
            - 'DSUF' : Dynamic Stress Uniformity Factor / R² (0-1, higher is better)
            - 'windowed_FBC_loading' : FBC during loading phase (0-50% peak)
            - 'windowed_FBC_plateau' : FBC during plateau phase (50-100% peak)
            - 'windowed_FBC_unloading' : FBC during unloading phase
            - 'windowed_DSUF_loading' : R² during loading phase
            - 'windowed_DSUF_plateau' : R² during plateau phase
            - 'windowed_DSUF_unloading' : R² during unloading phase

        Examples
        --------
        >>> results = calculator.calculate(inc, trs, ref, time)
        >>> metrics = calculator.calculate_equilibrium_metrics(results)
        >>> print(f"Force Balance: {metrics['FBC']:.3f}")
        >>> print(f"Overall R²: {metrics['DSUF']:.3f}")
        >>> print(f"Plateau R²: {metrics['windowed_DSUF_plateau']:.3f}")

        Notes
        -----
        - FBC and DSUF values close to 1.0 indicate good equilibrium
        - SEQI values > 0.9 typically indicate acceptable equilibrium
        - SOI values < 0.05 (5%) suggest good stress uniformity
        - Windowed metrics help identify where equilibrium breaks down
        - All metrics use absolute values to handle compressive convention

        References
        ----------
        Chen, W. W., & Song, B. (2011). Split Hopkinson (Kolsky) Bar: Design,
        Testing and Applications. Springer.
        """
        # Extract required data
        stress_1w = results['stress_1w']
        stress_3w = results['stress_3w']
        bar_force_1w = results['bar_force_1w']
        bar_force_3w = results['bar_force_3w']

        # Find valid region (where stress is non-negligible)
        stress_threshold = 0.01 * np.max(stress_3w)  # 1% of peak
        valid_mask = (stress_3w > stress_threshold) & (stress_1w > stress_threshold)

        if not valid_mask.any():
            # Return NaN metrics if no valid data
            return {
                'FBC': np.nan,
                'SEQI': np.nan,
                'SOI': np.nan,
                'DSUF': np.nan,
                'windowed_FBC_loading': np.nan,
                'windowed_FBC_plateau': np.nan,
                'windowed_FBC_unloading': np.nan,
                'windowed_DSUF_loading': np.nan,
                'windowed_DSUF_plateau': np.nan,
                'windowed_DSUF_unloading': np.nan,
            }

        # ===== METRIC 1: Force Balance Coefficient (FBC) =====
        force_diff = np.abs(bar_force_3w - bar_force_1w)
        force_max = np.maximum(bar_force_3w, bar_force_1w)
        force_ratio = force_diff / (force_max + 1e-10)  # Avoid division by zero
        FBC = float(1.0 - np.mean(force_ratio[valid_mask]))

        # ===== METRIC 2: Stress Equilibrium Quality Index (SEQI) =====
        stress_diff = stress_3w[valid_mask] - stress_1w[valid_mask]
        rmse = np.sqrt(np.mean(stress_diff**2))
        stress_range = np.max(stress_3w[valid_mask]) - np.min(stress_3w[valid_mask])
        nrmse = rmse / (stress_range + 1e-10)
        SEQI = float(np.exp(-nrmse))

        # ===== METRIC 3: Time-Windowed Analysis =====
        peak_stress = np.max(stress_3w)
        peak_idx = np.argmax(stress_3w)

        # Define phase masks
        loading_mask = (stress_3w < 0.5 * peak_stress) & valid_mask
        plateau_mask = (stress_3w >= 0.5 * peak_stress) & valid_mask
        unloading_mask = (np.arange(len(stress_3w)) > peak_idx) & valid_mask

        def compute_phase_metrics(mask):
            """Compute FBC and DSUF for a given phase."""
            if not mask.any() or mask.sum() < 3:
                return np.nan, np.nan

            # Phase FBC
            phase_force_diff = np.abs(bar_force_3w[mask] - bar_force_1w[mask])
            phase_force_max = np.maximum(bar_force_3w[mask], bar_force_1w[mask])
            phase_force_ratio = phase_force_diff / (phase_force_max + 1e-10)
            phase_fbc = 1.0 - np.mean(phase_force_ratio)

            # Phase DSUF (R²)
            try:
                r, _ = pearsonr(stress_1w[mask], stress_3w[mask])
                phase_dsuf = r**2
            except:
                phase_dsuf = np.nan

            return float(phase_fbc), float(phase_dsuf)

        windowed_FBC_loading, windowed_DSUF_loading = compute_phase_metrics(loading_mask)
        windowed_FBC_plateau, windowed_DSUF_plateau = compute_phase_metrics(plateau_mask)
        windowed_FBC_unloading, windowed_DSUF_unloading = compute_phase_metrics(unloading_mask)

        # ===== METRIC 4: Stress Oscillation Index (SOI) =====
        # Use plateau region (80-100% of peak stress)
        plateau_high_mask = (stress_3w >= 0.8 * peak_stress) & valid_mask
        if plateau_high_mask.any() and plateau_high_mask.sum() > 2:
            plateau_stress = stress_3w[plateau_high_mask]
            SOI = float(np.std(plateau_stress) / (np.mean(plateau_stress) + 1e-10))
        else:
            SOI = np.nan

        # ===== METRIC 5: Dynamic Stress Uniformity Factor (DSUF) =====
        # Overall R² between 1-wave and 3-wave stress
        try:
            r, _ = pearsonr(stress_1w[valid_mask], stress_3w[valid_mask])
            DSUF = float(r**2)
        except:
            DSUF = np.nan

        return {
            'FBC': FBC,
            'SEQI': SEQI,
            'SOI': SOI,
            'DSUF': DSUF,
            'windowed_FBC_loading': windowed_FBC_loading,
            'windowed_FBC_plateau': windowed_FBC_plateau,
            'windowed_FBC_unloading': windowed_FBC_unloading,
            'windowed_DSUF_loading': windowed_DSUF_loading,
            'windowed_DSUF_plateau': windowed_DSUF_plateau,
            'windowed_DSUF_unloading': windowed_DSUF_unloading,
        }



