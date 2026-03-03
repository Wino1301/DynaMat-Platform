r"""jc_layer.py
====================================
Johnson–Cook parameter layer with hard bounds and optional L2 regularisation.

*   **ASCII‑only names** – no Unicode symbols.
*   Works in **kg‑mm‑ms** or **SI**; bounds are given in the same units you
    want to optimise in (e.g. GPa).
*   The module itself does **not** add the L2 term to the loss; the parent
    model should call   `layer.l2_penalty()` and add it with a weight
    `lambda_reg` of its choice.
"""

from __future__ import annotations

import math
from typing import Dict, Tuple, List
import torch
import torch.nn as nn

# -----------------------------------------------------------------------------
# Helper: inverse‑sigmoid to initialise delta so that the mapped value equals a
# user‑provided theta_init.
# -----------------------------------------------------------------------------

def _inv_sigmoid(x: float, low: float, high: float) -> float:
    """Given *x* in (low, high), return *z* such that sigmoid(z) maps to x."""
    # Map x from (low, high) → (0,1)
    r = (x - low) / (high - low)
    # Avoid infinities
    r = min(max(r, 1e-6), 1 - 1e-6)
    return math.log(r / (1 - r))

# -----------------------------------------------------------------------------
# Main layer
# -----------------------------------------------------------------------------

class JCParameterLayer(nn.Module):
    """Johnson–Cook parameters with hard bounds via a sigmoid mapping.

    Parameters
    ----------
    bounds : dict[str, tuple[float, float]]
        Keys are parameter names (e.g. ``"A"``) and values are *(low, high)*
        bounds in **physical units**.
    theta_init : dict[str, float] | None, default None
        Optional initial values for θ.  If omitted, midpoint of each interval
        is used.
    """

    def __init__(self, bounds: Dict[str, Tuple[float, float]],
                 theta_init: Dict[str, float] | None = None):
        super().__init__()
        self._names: List[str] = list(bounds.keys())

        lows  = []
        highs = []
        deltas = []

        for name in self._names:
            low, high = bounds[name]
            lows.append(low)
            highs.append(high)
            if theta_init and name in theta_init:
                z0 = _inv_sigmoid(theta_init[name], low, high)
            else:
                z0 = 0.0  # midpoint
            deltas.append(z0)

        # register as buffers so they move with .to(device)
        self.register_buffer("_low",  torch.tensor(lows, dtype=torch.float32))
        self.register_buffer("_high", torch.tensor(highs, dtype=torch.float32))
        # trainable raw parameters
        self.delta = nn.Parameter(torch.tensor(deltas, dtype=torch.float32))

    # ------------------------------------------------------------------ api --

    def forward(self) -> torch.Tensor:
        """Return a 1‑D tensor **θ_pred** with values in their physical bounds."""
        # --- new: hard-clip the raw deltas ------------------------------
        self.delta.data.nan_to_num_(nan=0.0, posinf=20.0, neginf=-20.0)
        self.delta.data.clamp_(-20.0, 20.0)          # ±20 ⇒ sigmoid ≈ 2 e-9 … 0.999 999 998
        # ----------------------------------------------------------------
        sigma = torch.sigmoid(self.delta)            # (0,1)
        return self._low + (self._high - self._low) * sigma

    # ------------------------------------------------------------------ utils --

    def as_dict(self) -> Dict[str, float]:
        """Return θ as an ``OrderedDict`` {name: value} on CPU for logging."""
        return {k: float(v) for k, v in zip(self._names, self().detach().cpu())}

    def l2_penalty(self) -> torch.Tensor:
        """Return ‖delta‖² so caller can add ``lambda_reg * layer.l2_penalty()``."""
        return torch.sum(self.delta ** 2)
