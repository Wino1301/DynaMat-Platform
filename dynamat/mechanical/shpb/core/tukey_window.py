"""Tukey window generation for SHPB signal processing.

This module provides Tukey (tapered cosine) window functions for tapering
SHPB signals before frequency-domain operations or machine learning feature
extraction. Tapering reduces edge effects and Gibbs phenomena.

Classes
-------
TukeyWindow : Tukey window generator for signal tapering

References
----------
Harris, F. J. (1978). On the use of windows for harmonic analysis with the
discrete Fourier transform. Proceedings of the IEEE, 66(1), 51-83.
"""
from __future__ import annotations
import numpy as np


class TukeyWindow:
    """Generate Tukey (tapered cosine) windows for signal processing.

    The Tukey window is a rectangular window with cosine-tapered edges,
    useful for reducing edge effects in frequency-domain operations and
    preparing signals for machine learning analysis. It's parameterized
    by α ∈ [0, 1]:

    - α = 0: Rectangular window (no taper)
    - α = 1: Hann window (full taper)
    - α = 0.5: Half tapered, half flat (common for SHPB)

    Parameters
    ----------
    alpha : float, default 0.5
        Taper fraction. Must be in [0, 1].
        - 0.0 = rectangular window (no tapering)
        - 0.5 = half-tapered (recommended for SHPB)
        - 1.0 = Hann window (full tapering)

    Examples
    --------
    >>> window_gen = TukeyWindow(alpha=0.5)
    >>> weights = window_gen.generate(length=10000)
    >>> tapered_signal = signal * weights

    >>> # Apply to SHPB pulses for ML feature extraction
    >>> tukey = TukeyWindow(alpha=0.3)
    >>> inc_tapered = incident * tukey.generate(len(incident))
    >>> trs_tapered = transmitted * tukey.generate(len(transmitted))
    """

    def __init__(self, alpha: float = 0.5):
        if not 0.0 <= alpha <= 1.0:
            raise ValueError(
                f"alpha must be in [0, 1], got {alpha}"
            )
        self.alpha = alpha

    def generate(self, length: int) -> np.ndarray:
        """Generate Tukey window of specified length.

        Parameters
        ----------
        length : int
            Window length in samples.

        Returns
        -------
        np.ndarray
            Tukey window weights in range [0, 1].

        Notes
        -----
        The Tukey window is defined as:

        w[n] = 0.5 * (1 + cos(π * (2n/αN - 1)))        for 0 ≤ n < αN/2
        w[n] = 1                                        for αN/2 ≤ n < N(1-α/2)
        w[n] = 0.5 * (1 + cos(π * (2n/αN - 2/α + 1)))  for N(1-α/2) ≤ n < N

        where N is the window length and α is the taper fraction.
        """
        if length <= 0:
            raise ValueError(f"length must be positive, got {length}")

        # Special cases for efficiency
        if self.alpha == 0.0:
            return np.ones(length)
        elif self.alpha == 1.0:
            return np.hanning(length)

        # General Tukey window
        n = np.arange(length)
        w = np.ones(length)

        # Taper length (number of samples in each taper)
        taper_samples = int(np.floor(self.alpha * length / 2.0))

        if taper_samples > 0:
            # Left taper (rising edge)
            left_idx = n < taper_samples
            w[left_idx] = 0.5 * (
                1.0 + np.cos(np.pi * (2.0 * n[left_idx] / (self.alpha * length) - 1.0))
            )

            # Right taper (falling edge)
            right_idx = n >= (length - taper_samples)
            w[right_idx] = 0.5 * (
                1.0 + np.cos(np.pi * (
                    2.0 * n[right_idx] / (self.alpha * length)
                    - 2.0 / self.alpha + 1.0
                ))
            )

        return w

    def apply(self, signal: np.ndarray) -> np.ndarray:
        """Apply Tukey window to a signal.

        Convenience method that generates the window and applies it
        in one step.

        Parameters
        ----------
        signal : np.ndarray
            Input signal to taper.

        Returns
        -------
        np.ndarray
            Tapered signal (same length as input).

        Examples
        --------
        >>> tukey = TukeyWindow(alpha=0.5)
        >>> tapered = tukey.apply(raw_signal)
        """
        weights = self.generate(len(signal))
        return signal * weights

    @staticmethod
    def compare_alphas(
        length: int,
        alphas: list[float] | None = None
    ) -> dict[float, np.ndarray]:
        """Generate multiple Tukey windows with different alpha values.

        Useful for visualizing the effect of different taper fractions
        or experimenting with different tapering strategies for ML input.

        Parameters
        ----------
        length : int
            Window length in samples.
        alphas : list[float], optional
            List of alpha values to generate.
            Defaults to [0.0, 0.25, 0.5, 0.75, 1.0].

        Returns
        -------
        dict[float, np.ndarray]
            Dictionary mapping alpha values to window arrays.

        Examples
        --------
        >>> windows = TukeyWindow.compare_alphas(length=1000)
        >>> import matplotlib.pyplot as plt
        >>> for alpha, window in windows.items():
        ...     plt.plot(window, label=f'α={alpha}')
        >>> plt.legend()
        >>> plt.xlabel('Sample')
        >>> plt.ylabel('Window weight')
        >>> plt.title('Tukey windows with different α values')
        >>> plt.show()
        """
        if alphas is None:
            alphas = [0.0, 0.25, 0.5, 0.75, 1.0]

        return {
            alpha: TukeyWindow(alpha).generate(length)
            for alpha in alphas
        }

    def __repr__(self) -> str:
        return f"TukeyWindow(alpha={self.alpha})"
