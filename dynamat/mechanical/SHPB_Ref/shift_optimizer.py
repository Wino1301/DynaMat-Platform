"""shift_optimizer.py
Align transmitted and reflected pulses to the incident pulse by
optimising integer sample shifts that maximise four physical criteria.

Usage (in notebook)
-------------------
```python
from shift_optimizer import shift_optimizer

inc_aligned, tran_aligned, refl_aligned, dT, dR = shift_optimizer(
    incident         = inc_seg,
    transmitted      = trs_seg,
    reflected        = ref_seg,
    time_vector      = time_seg,
    bar_wave_speed   = 4953.3,     # m/s
    specimen_length  = 6.50,       # mm
    k_linear         = 0.25,       # 25 % of steepest slope
    search_bounds    = None,       # default ±N/2
    weights          = dict(corr=0.4, u=0.25, sr=0.25, e=0.10),
    debug            = True,
)
```

Returns the three aligned traces **and** the integer shifts that were
found (ΔT, ΔR).
"""
from __future__ import annotations

from typing import Tuple, Dict
import numpy as np
from scipy.integrate import cumulative_trapezoid
from scipy.optimize  import differential_evolution

__all__ = ["shift_optimizer"]

# ------------------------------------------------------------------------- #
# 1.  LOW-LEVEL PHYSICAL METRICS                                            #
# ------------------------------------------------------------------------- #
def _pulse_corr(inc: np.ndarray, tra: np.ndarray, ref: np.ndarray,
                idx: np.ndarray) -> float:
    """Pearson r between *inc[idx]* and *(T-R)[idx]*."""
    base = inc[idx]
    cand = tra[idx] - ref[idx]
    if base.std() == 0 or cand.std() == 0:
        return -1.0
    return float(np.corrcoef(base, cand)[0, 1])


def _bar_u_rmse(c: float,
                inc: np.ndarray, tra: np.ndarray, ref: np.ndarray,
                idx: np.ndarray) -> float:
    """RMSE between one-wave and two-wave bar displacement."""
    u2 = c * (inc + ref)
    u1 = c * tra
    return float(np.sqrt(np.mean((u1[idx] - u2[idx]) ** 2)))


def _sr_rmse(c: float, L: float,
             inc: np.ndarray, tra: np.ndarray, ref: np.ndarray,
             idx: np.ndarray) -> float:
    sr3 = (c / L) * (inc - ref - tra)
    sr1 = (2 * c * ref) / L
    return float(np.sqrt(np.mean((sr1[idx] - sr3[idx]) ** 2)))


def _strain_rmse(c: float, L: float,
                 inc: np.ndarray, tra: np.ndarray, ref: np.ndarray,
                 time: np.ndarray, idx: np.ndarray) -> float:
    e3 = (c / L) * cumulative_trapezoid(inc - ref - tra, time, initial=0)
    e1 = ((2 * c) / L) * cumulative_trapezoid(ref, time, initial=0)
    return float(np.sqrt(np.mean((e1[idx] - e3[idx]) ** 2)))


# ------------------------------------------------------------------------- #
# 2.  SHIFT UTILITIES                                                       #
# ------------------------------------------------------------------------- #
def _shift_signal(sig: np.ndarray, shift: int) -> np.ndarray:
    """Zero-padded shift (positive → right)."""
    n = len(sig)
    s = int(round(shift))
    if s > 0:
        return np.concatenate((np.zeros(s), sig))[:n]
    if s < 0:
        return np.concatenate((sig[-s:], np.zeros(-s)))[:n]
    return sig.copy()


# -----------------------------------------------------------------------------
# 3.   FITNESS FUNCTION
# -----------------------------------------------------------------------------

def _neg_fitness(shifts: Sequence[float],
                     inc: np.ndarray,
                     tra: np.ndarray,
                     ref: np.ndarray,
                     idx: np.ndarray,
                     tvec: np.ndarray,
                     c: float, L: float,
                     w: Dict[str, float]) -> float:
        sh_t, sh_r = shifts
        T = _shift_signal(tra, sh_t)
        R = _shift_signal(ref, sh_r)

        r      = _pulse_corr(inc, T, R, idx)
        u_rmse = _bar_u_rmse(c, inc, T, R, idx)
        sr_rmse= _sr_rmse(c, L, inc, T, R, idx)
        e_rmse = _strain_rmse(c, L, inc, T, R, tvec, idx)

        sim_u  = 1.0 / (1.0 + u_rmse)
        sim_sr = 1.0 / (1.0 + sr_rmse)
        sim_e  = 1.0 / (1.0 + e_rmse)

        fitness = (w['corr'] * r +
                   w['u']    * sim_u +
                   w['sr']   * sim_sr +
                   w['e']    * sim_e)
        return -fitness if not np.isnan(fitness) else 1e3   # minimise negative


# -----------------------------------------------------------------------------
# 4.   PUBLIC OPTIMISER
# -----------------------------------------------------------------------------

def shift_optimizer(
        *,
        incident: np.ndarray,
        transmitted: np.ndarray,
        reflected: np.ndarray,
        time_vector: np.ndarray,
        bar_wave_speed: float,
        specimen_length: float,
        k_linear: float = 0.25,
        search_bounds: Optional[Tuple[int, int]] = None,
        search_bounds_t: Optional[Tuple[int, int]] = None,
        search_bounds_r: Optional[Tuple[int, int]] = None,
        weights: Dict[str, float] | None = None,
        debug: bool = False
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, int, int]:
    """Align *transmitted* and *reflected* pulses to *incident* by optimising
    integer sample shifts.

    Parameters
    ----------
    incident, transmitted, reflected : 1‑D np.ndarray
        Pulse vectors of equal length N.
    time_vector : 1‑D np.ndarray length N
        Physical time axis (s).  Used for strain integration.
    bar_wave_speed : float
        Wave speed in the bar (m/s).
    specimen_length : float
        Initial specimen length (mm).
    k_linear : float, default 0.25
        Fraction of the steepest negative slope used to isolate the linear
        section of the incident pulse.
    search_bounds : (lo, hi), optional
        Global bounds applied to *both* shifts when specific bounds are not
        supplied.
    search_bounds_t, search_bounds_r : (lo, hi), optional
        Independent bounds for transmitted and reflected shifts.  If *None*,
        fallback to *search_bounds*; if that is also *None*, bounds default
        to ±len(incident)//2.
    weights : dict, default ``{"corr":0.4,"u":0.25,"sr":0.25,"e":0.10}``
        Non‑negative weights for the four fitness components.
    debug : bool
        Print diagnostics.

    Returns
    -------
    inc_aligned, tran_aligned, refl_aligned : np.ndarray
        Shifted pulses (length N).
    best_shift_signal_t, best_shift_signal_r : int
        Integer sample shifts applied to transmitted, reflected.
    """
    # --- sanity check 
    N = len(incident)
    if len({len(transmitted), len(reflected), len(time_vector)}) != 1:
        raise ValueError("All input vectors must share the same length")
    if weights is None:
        weights = dict(corr=0.4, u=0.25, sr=0.25, e=0.10)
    if search_bounds is None:
        half = N // 2
        search_bounds = (-half, half)
    if search_bounds_t is None:
        search_bounds_t = search_bounds
    if search_bounds_r is None:
        search_bounds_r = search_bounds

    # ------------------------------------------------------------------
    # 1.  isolate linear‑region indices on incident pulse
    # ------------------------------------------------------------------
    grad_inc   = np.gradient(incident)
    targetval  = np.min(grad_inc) * k_linear
    minidx     = np.argmin(grad_inc)
    fall_start = np.where(grad_inc[:minidx] >= targetval)[0][-1]
    fall_end   = np.where(grad_inc[minidx:] >= targetval)[0][0] + minidx
    idx_lin    = np.arange(fall_start, fall_end)

    if debug:
        print(f"[shift_opt] linear idx = [{fall_start}, {fall_end}] len={len(idx_lin)}")
        print(f"[shift_opt] bounds T={search_bounds_t}  R={search_bounds_r}")

    
    # ------------------------------------------------------------------
    # 2.  differential evolution optimisation
    # ------------------------------------------------------------------
    bounds = [search_bounds_t, search_bounds_r]
        
    result = differential_evolution(
        _neg_fitness, bounds,
        args=(incident, transmitted, reflected, idx_lin, time_vector,
              bar_wave_speed, specimen_length, weights),
        strategy="best2bin", popsize=50, maxiter=250, tol=5e-5,
        polish=True, disp=debug
    )

    best_shift_signal_t, best_shift_signal_r = map(lambda x: int(round(x)), result.x)
    if debug:
        print(f"[shift_optimizer] ΔT={best_shift_signal_t:+d}  ΔR={best_shift_signal_r:+d}  [samples]")

    # ------------------------------------------------------------------
    # 3.  apply shifts and return
    # ------------------------------------------------------------------
    inc_aligned  = incident.copy()
    tran_aligned = _shift_signal(transmitted, best_shift_signal_t)
    refl_aligned = _shift_signal(reflected,   best_shift_signal_r)

    return inc_aligned, tran_aligned, refl_aligned, best_shift_signal_t, best_shift_signal_r
