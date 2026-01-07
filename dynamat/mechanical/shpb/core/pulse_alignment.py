"""Pulse alignment for SHPB signals.

This module provides tools for aligning transmitted and reflected pulses
to the incident pulse by optimizing integer sample shifts that maximize
physical equilibrium criteria.

Classes
-------
PulseAligner : Configurable pulse alignment optimizer

References
----------
Gray, G. T. (2000). Classic Split-Hopkinson Pressure Bar Testing.
ASM Handbook, Vol. 8: Mechanical Testing and Evaluation.
"""
from __future__ import annotations
from typing import Tuple, Dict, Optional, Sequence
import numpy as np
from scipy.integrate import cumulative_trapezoid
from scipy.optimize import differential_evolution


class PulseAligner:
    """Align transmitted and reflected pulses using multi-criteria optimization.

    Optimizes integer sample shifts to maximize physical equilibrium between
    1-wave and 3-wave analysis methods:
    - Pulse correlation
    - Bar displacement equilibrium
    - Strain rate equilibrium
    - Strain equilibrium

    Parameters
    ----------
    bar_wave_speed : float
        Wave speed in the bar (mm/ms).
    specimen_length : float
        Initial specimen length (mm).
    k_linear : float, default 0.35
        Fraction of steepest slope to define linear region of incident pulse.
        Used for isolating equilibrium check region (0.25-0.40 typical).
    weights : dict, optional
        Fitness component weights. Keys: 'corr', 'u', 'sr', 'e'.
        Defaults to {'corr': 0.3, 'u': 0.3, 'sr': 0.3, 'e': 0.1}.

    Examples
    --------
    >>> aligner = PulseAligner(
    ...     bar_wave_speed=4953.3,
    ...     specimen_length=6.5,
    ...     k_linear=0.35
    ... )
    >>> inc, trs, ref, shift_t, shift_r = aligner.align(
    ...     incident=inc_seg,
    ...     transmitted=trs_seg,
    ...     reflected=ref_seg,
    ...     time_vector=time_seg,
    ...     search_bounds_t=(1200, 1800),
    ...     search_bounds_r=(-2800, -2400)
    ... )
    """

    def __init__(
        self,
        bar_wave_speed: float,
        specimen_length: float,
        k_linear: float = 0.35,
        weights: Dict[str, float] | None = None
    ):
        self.bar_wave_speed = bar_wave_speed
        self.specimen_length = specimen_length
        self.k_linear = k_linear
        self.weights = weights or {
            'corr': 0.3,
            'u': 0.3,
            'sr': 0.3,
            'e': 0.1
        }

        # Validate weights
        if not np.isclose(sum(self.weights.values()), 1.0, atol=0.01):
            import warnings
            warnings.warn(
                f"Weights sum to {sum(self.weights.values()):.3f}, not 1.0"
            )

    @staticmethod
    def _shift_signal(signal: np.ndarray, shift: int) -> np.ndarray:
        """Apply zero-padded shift to signal.

        Parameters
        ----------
        signal : np.ndarray
            Input signal.
        shift : int
            Shift amount (positive = right, negative = left).

        Returns
        -------
        np.ndarray
            Shifted signal (same length, zero-padded).
        """
        n = len(signal)
        s = int(round(shift))
        if s > 0:
            return np.concatenate((np.zeros(s), signal))[:n]
        elif s < 0:
            return np.concatenate((signal[-s:], np.zeros(-s)))[:n]
        else:
            return signal.copy()

    @staticmethod
    def _pulse_correlation(
        inc: np.ndarray,
        trs: np.ndarray,
        ref: np.ndarray,
        idx: np.ndarray
    ) -> float:
        """Pearson correlation between incident and (transmitted - reflected).

        Parameters
        ----------
        inc, trs, ref : np.ndarray
            Pulse arrays.
        idx : np.ndarray
            Indices to evaluate (linear region).

        Returns
        -------
        float
            Correlation coefficient [-1, 1].
        """
        base = inc[idx]
        cand = trs[idx] - ref[idx]
        if base.std() == 0 or cand.std() == 0:
            return -1.0
        return float(np.corrcoef(base, cand)[0, 1])

    @staticmethod
    def _bar_displacement_rmse(
        c: float,
        inc: np.ndarray,
        trs: np.ndarray,
        ref: np.ndarray,
        idx: np.ndarray
    ) -> float:
        """RMSE between 1-wave and 2-wave bar displacement.

        u_1W = c * ε_T
        u_2W = c * (ε_I + ε_R)

        Parameters
        ----------
        c : float
            Bar wave speed (mm/ms).
        inc, trs, ref : np.ndarray
            Pulse arrays.
        idx : np.ndarray
            Indices to evaluate.

        Returns
        -------
        float
            RMSE in displacement (mm).
        """
        u2 = c * (inc + ref)
        u1 = c * trs
        return float(np.sqrt(np.mean((u1[idx] - u2[idx]) ** 2)))

    @staticmethod
    def _strain_rate_rmse(
        c: float,
        L: float,
        inc: np.ndarray,
        trs: np.ndarray,
        ref: np.ndarray,
        idx: np.ndarray
    ) -> float:
        """RMSE between 1-wave and 3-wave strain rate.

        ε̇_3W = (c/L) * (ε_I - ε_R - ε_T)
        ε̇_1W = (2c/L) * ε_R

        Parameters
        ----------
        c : float
            Bar wave speed (mm/ms).
        L : float
            Specimen length (mm).
        inc, trs, ref : np.ndarray
            Pulse arrays.
        idx : np.ndarray
            Indices to evaluate.

        Returns
        -------
        float
            RMSE in strain rate (1/ms).
        """
        sr3 = (c / L) * (inc - ref - trs)
        sr1 = (2 * c * ref) / L
        return float(np.sqrt(np.mean((sr1[idx] - sr3[idx]) ** 2)))

    @staticmethod
    def _strain_rmse(
        c: float,
        L: float,
        inc: np.ndarray,
        trs: np.ndarray,
        ref: np.ndarray,
        time: np.ndarray,
        idx: np.ndarray
    ) -> float:
        """RMSE between 1-wave and 3-wave strain.

        ε_3W = (c/L) * ∫(ε_I - ε_R - ε_T) dt
        ε_1W = (2c/L) * ∫ε_R dt

        Parameters
        ----------
        c : float
            Bar wave speed (mm/ms).
        L : float
            Specimen length (mm).
        inc, trs, ref : np.ndarray
            Pulse arrays.
        time : np.ndarray
            Time vector (ms).
        idx : np.ndarray
            Indices to evaluate.

        Returns
        -------
        float
            RMSE in strain (unitless).
        """
        e3 = (c / L) * cumulative_trapezoid(inc - ref - trs, time, initial=0)
        e1 = (2 * c / L) * cumulative_trapezoid(ref, time, initial=0)
        return float(np.sqrt(np.mean((e1[idx] - e3[idx]) ** 2)))

    def _fitness_function(
        self,
        shifts: Sequence[float],
        inc: np.ndarray,
        trs: np.ndarray,
        ref: np.ndarray,
        idx: np.ndarray,
        time: np.ndarray
    ) -> float:
        """Negative fitness for minimization.

        Combines four equilibrium criteria with user-defined weights.

        Parameters
        ----------
        shifts : Sequence[float]
            [shift_transmitted, shift_reflected].
        inc, trs, ref : np.ndarray
            Pulse arrays.
        idx : np.ndarray
            Linear region indices.
        time : np.ndarray
            Time vector.

        Returns
        -------
        float
            Negative weighted fitness (lower is better).
        """
        shift_t, shift_r = shifts
        T = self._shift_signal(trs, shift_t)
        R = self._shift_signal(ref, shift_r)

        # Calculate metrics
        r = self._pulse_correlation(inc, T, R, idx)
        u_rmse = self._bar_displacement_rmse(self.bar_wave_speed, inc, T, R, idx)
        sr_rmse = self._strain_rate_rmse(
            self.bar_wave_speed, self.specimen_length, inc, T, R, idx
        )
        e_rmse = self._strain_rmse(
            self.bar_wave_speed, self.specimen_length, inc, T, R, time, idx
        )

        # Convert RMSEs to similarities (0 to 1)
        sim_u = 1.0 / (1.0 + u_rmse)
        sim_sr = 1.0 / (1.0 + sr_rmse)
        sim_e = 1.0 / (1.0 + e_rmse)

        # Weighted sum
        fitness = (
            self.weights['corr'] * r +
            self.weights['u'] * sim_u +
            self.weights['sr'] * sim_sr +
            self.weights['e'] * sim_e
        )

        return -fitness if not np.isnan(fitness) else 1e3

    def align(
        self,
        incident: np.ndarray,
        transmitted: np.ndarray,
        reflected: np.ndarray,
        time_vector: np.ndarray,
        search_bounds_t: Tuple[int, int] | None = None,
        search_bounds_r: Tuple[int, int] | None = None,
        debug: bool = False
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray, int, int]:
        """Align transmitted and reflected pulses to incident.

        Uses differential evolution to find optimal integer shifts that
        maximize physical equilibrium between 1-wave and 3-wave analysis.

        Parameters
        ----------
        incident : np.ndarray
            Incident pulse (reference, not shifted).
        transmitted : np.ndarray
            Transmitted pulse to align.
        reflected : np.ndarray
            Reflected pulse to align.
        time_vector : np.ndarray
            Time axis (ms), same length as pulses.
        search_bounds_t : Tuple[int, int], optional
            Search bounds for transmitted shift (min, max) in samples.
            Defaults to ±N/2 where N is pulse length.
        search_bounds_r : Tuple[int, int], optional
            Search bounds for reflected shift (min, max) in samples.
            Defaults to ±N/2.
        debug : bool
            Print optimization diagnostics.

        Returns
        -------
        inc_aligned : np.ndarray
            Incident pulse (unchanged).
        trs_aligned : np.ndarray
            Transmitted pulse shifted.
        ref_aligned : np.ndarray
            Reflected pulse shifted.
        shift_t : int
            Optimal transmitted shift (samples).
        shift_r : int
            Optimal reflected shift (samples).

        Raises
        ------
        ValueError
            If input arrays have different lengths.
        """
        # Validate inputs
        N = len(incident)
        if not (len(transmitted) == len(reflected) == len(time_vector) == N):
            raise ValueError(
                f"All inputs must have same length. Got: "
                f"incident={len(incident)}, transmitted={len(transmitted)}, "
                f"reflected={len(reflected)}, time={len(time_vector)}"
            )

        # Default search bounds
        if search_bounds_t is None:
            search_bounds_t = (-N // 2, N // 2)
        if search_bounds_r is None:
            search_bounds_r = (-N // 2, N // 2)

        # Find linear region of incident pulse
        grad_inc = np.gradient(incident)
        target_val = np.min(grad_inc) * self.k_linear
        min_idx = np.argmin(grad_inc)
        fall_start = np.where(grad_inc[:min_idx] >= target_val)[0][-1]
        fall_end = np.where(grad_inc[min_idx:] >= target_val)[0][0] + min_idx
        idx_linear = np.arange(fall_start, fall_end)

        if debug:
            print(f"[PulseAligner] Linear region: [{fall_start}, {fall_end}] "
                  f"({len(idx_linear)} points)")
            print(f"[PulseAligner] Search bounds: T={search_bounds_t}, "
                  f"R={search_bounds_r}")

        # Run differential evolution
        bounds = [search_bounds_t, search_bounds_r]
        result = differential_evolution(
            self._fitness_function,
            bounds,
            args=(incident, transmitted, reflected, idx_linear, time_vector),
            strategy="best2bin",
            popsize=50,
            maxiter=250,
            tol=5e-5,
            polish=True,
            disp=debug
        )

        # Extract optimal shifts
        shift_t, shift_r = map(lambda x: int(round(x)), result.x)

        if debug:
            print(f"[PulseAligner] Optimal shifts: T={shift_t:+d}, "
                  f"R={shift_r:+d} samples")
            print(f"[PulseAligner] Final fitness: {-result.fun:.6f}")

        # Apply shifts and return
        inc_aligned = incident.copy()
        trs_aligned = self._shift_signal(transmitted, shift_t)
        ref_aligned = self._shift_signal(reflected, shift_r)

        return inc_aligned, trs_aligned, ref_aligned, shift_t, shift_r
