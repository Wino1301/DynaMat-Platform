r"""pinn_model.py
========================================
Physics‑driven PINN for SHPB Johnson–Cook fitting.

ASCII‑only, no external frameworks other than PyTorch + Lightning.

* Predicts Johnson–Cook parameters θ = {A,B,C,n,m} that best fit the
  *one‑wave* experimental stress curve (low‑oscillation transmitted bar).
* Uses *explicit Euler* to evolve plastic strain and (optionally) temperature.
* Loss = MSE between predicted JC stress and experimental one‑wave stress,
  plus an L2 regulariser on the raw parameter deltas.

Batch dictionary expected from DataLoader
----------------------------------------
    {
        "time"       : (B,T)  ms,
        "incident_raw"    : (B,T)  –,  incident  strain   (aligned)
        "reflected_raw"    : (B,T)  –,  reflected strain   (aligned)
        "transmitted_raw"    : (B,T)  –,  transmitted strain (aligned)
        "length_mm"  : (B,)   mm, specimen length
        "area_mm2"   : (B,)   mm², specimen cross‑section
        # any other fields are ignored by the model
    }

User must supply bar constants at construction time.
"""

from __future__ import annotations

from typing import Dict, Tuple
import torch
import torch.nn as nn
import torch.nn.functional as F
import pytorch_lightning as pl

from pathlib import Path
import sys
nb_dir        = Path.cwd()                     # …/SHPB_Johnson_Cook/notebooks
proj_root     = nb_dir.parent                 # …/SHPB_Johnson_Cook
jc_scripts    = proj_root / "scripts"
sys.path.insert(0, str(jc_scripts))

from jc_layer import JCParameterLayer

# -----------------------------------------------------------------------------
# helper: simple rectangle cumulative integral (torch has no cumtrapz yet)
# -----------------------------------------------------------------------------

def cumulative_integral(y: torch.Tensor, time: torch.Tensor) -> torch.Tensor:
    """
    Forward-Euler cumulative integral ∫ y dt on an *uneven* grid.
    Works even when `time` has one extra point.
    Returns same length as `y`.
    """
    # dt_k  = t_{k+1} − t_k ; length = T-1
    dt = torch.diff(time, dim=1)            # (B, T-1)
    # align lengths: use y[:, :-1] so both mats multiply
    integral = torch.cumsum(y[:, :-1] * dt, dim=1)   # (B, T-1)
    pad = torch.zeros(y.size(0), 1, device=y.device, dtype=y.dtype)
    return torch.cat([pad, integral], dim=1)         # (B, T)

def assert_finite(tag, *tensors):
    for t in tensors:
        if not torch.isfinite(t).all():
            raise RuntimeError(f'Non-finite in {tag}')

# -----------------------------------------------------------------------------
# main model
# -----------------------------------------------------------------------------

class JCPINN(pl.LightningModule):
    def __init__(self, *,
        bar_const: Dict[str, float],            # bar material constants
        spec_E: float,                          # specimen elastic modulus
        bounds: Dict[str, Tuple[float,float]],  # Johnson-Cook parameter bounds
        theta_init: Dict[str, float],           # Initial Johnson-Cook parameters
        rho_s: float,                           # Specimen density
        Cp_s:  float,                           # Specimen Specific Heat capacity
        T_room: float = 293.0,                  # Room Temperature (kelvin)
        T_melt: float = 1673.0,                 # Specimen melting temperature (kelvin)
        beta: float = 0.9,                      # Specimen Adiabatic Factor
        lambda_sig: float = 20.0,               # Weight for Stress component
        lambda_reg: float = 1e-3,               # Weight for regression component (JC-Paramater fitness)
        lr_adam: float = 5e-5):                 # Adaptive Moment Estimation (Adam) optimizer learning rate
        super().__init__()

        # physical constants
        self.E_bar  = torch.tensor(bar_const["E_bar"], dtype=torch.float32)
        self.c_bar  = torch.tensor(bar_const["c_bar"], dtype=torch.float32)
        self.bar_cross = torch.tensor(bar_const["bar_cross"], dtype=torch.float32)
        self.register_buffer("rho_s", torch.tensor(rho_s, dtype=torch.float32))
        self.register_buffer("Cp_s",  torch.tensor(Cp_s,  dtype=torch.float32))
        self.T_room = T_room
        self.T_melt = T_melt
        self.beta   = beta
        self.E_spec = torch.tensor(spec_E, dtype=torch.float32)

        # learnable JC parameters
        self.jc = JCParameterLayer(bounds, theta_init)

        # loss weights & optimiser param
        self.lambda_sig = lambda_sig
        self.lambda_reg = lambda_reg
        self.lr_adam    = lr_adam

    # ---------------------------------------------------------------- training
    def _forward_physics(
        self,
        batch: Dict[str, torch.Tensor],
        return_all: bool = False
        ) -> Union[
        Tuple[torch.Tensor, torch.Tensor],      # (sig_jc_pred, sig_1w_exp)
        Tuple[torch.Tensor, torch.Tensor,       # eps_dot_exp, eps_exp
              torch.Tensor, torch.Tensor,       # sig_1w_exp, eps_pl_exp
              torch.Tensor, torch.Tensor,       # eps_pl_dot_exp, T_star_exp
              torch.Tensor]                     # sig_jc_pred
        ]:
        
        """Returns (sig_jc_pred, sig_1w_exp) both shape (B,T)"""
        time              = batch["time"]                  # (B,T)
        incident_raw      = batch["incident_raw"]          # (B,T)
        reflected_raw     = batch["reflected_raw"]         # (B,T)
        transmitted_raw   = batch["transmitted_raw"]       # (B,T)
        transmitted_w     = batch["transmitted_weight"]
        length_mm         = batch["L0_mm"].unsqueeze(1)    # (B,1)
        area_mm2          = batch["A0_mm2"].unsqueeze(1)   # (B,1)

        assert incident_raw.shape[1] == time.shape[1] - 1 or \
           incident_raw.shape[1] == time.shape[1], \
           "time and pulse lengths inconsistent"

        # time step dt per sample (rectangle rule assumes uniform dt)
        dt_scalar = torch.median(time[:, 1:] - time[:, :-1], dim=1).values  # (B,)
        dt = dt_scalar.unsqueeze(1).expand_as(time)                         # (B,T)

        # ------------------------- experimental derived curves ----------------
        eps_dot_exp = (self.c_bar/length_mm) * (incident_raw - reflected_raw - transmitted_raw)
        eps_exp     = (self.c_bar/length_mm) * cumulative_integral(incident_raw - reflected_raw - transmitted_raw, time)
        sig_1w_exp  = self.E_bar * (self.bar_cross/area_mm2) * transmitted_raw

        # plastic strain rate - strain
        eps_pl_dot_exp = 2.0 * self.c_bar / length_mm * reflected_raw            
        eps_pl_exp     = cumulative_integral(torch.abs(eps_pl_dot_exp), time)

        # log term for JC
        # 1. normalise |ε̇_pl| and |ε̇_tot| by their own maxima so both ∈ [0, 1]
        num = eps_pl_dot_exp.abs()
        den = eps_dot_exp.abs()
        
        # avoid division by zero for batches with all-zero rates
        num_norm = num / num.amax(dim=1, keepdim=True) + 1e-6
        den_norm = den / den.amax(dim=1, keepdim=True) + 1e-6
        
        # 2. ratio & log  (add small ε to keep >0)        
        ratio = (num_norm / den_norm).clamp(1e-12, 1e12)
        log_term = torch.log(ratio)
        
        # 3. replace any remaining NaN / Inf by 0
        eps_log_term = torch.nan_to_num(log_term, nan=0.0, posinf=0.0, neginf=0.0)
        eps_log_term = eps_log_term * transmitted_w

        if not torch.isfinite(eps_log_term).all():
            print(f"Non-finite log_term for ID: {batch['tags']['test_id']}")
            #raise RuntimeError("Non-finite log_term detected")

        # ---------- adiabatic heating term ----------------------------------------
        alpha = self.beta / (self.rho_s * self.Cp_s * (self.T_melt - self.T_room))  
        t_star_raw = alpha * cumulative_integral(sig_1w_exp * eps_pl_dot_exp, time)

        # add ε to avoid exactly zero, then clamp to (0, 0.999)
        eps_T = 1e-6
        t_star = torch.clamp(t_star_raw + eps_T, min=eps_T, max=0.999)
        """
        with torch.no_grad():
            print('ranges:',
                  eps_exp.abs().max().item(),    # should be ≤ ~0.3–0.4
                  eps_pl_exp.abs().max().item(), # same scale
                  t_star_raw.abs().max().item()) # << 1
        """
        # ---------- JC stress prediction ------------------------------------------
        A, B, n, C, m = self.jc()  # tensor of shape (5,)
        #sig_jc_pred = (A + B * eps_pl_exp**n) * (1 + C * eps_log_term) * (1 - t_star)**m
        eps_pl64   = eps_pl_exp.double()         # (B,T)
        eps_term64 = A.double() + B.double() * eps_pl64.pow(n.double())
        
        # Clamp to a physically plausible window 0 → 10 GPa
        eps_term   = eps_term64.clamp(0.0, 1e10).float()
        
        # ---- ②  strain-rate term  ----------------------------------------------
        #  |log_term| ≤ ln(1e12) ≈ 27.6 after your ratio-clamp,
        #  so  C up to 1e3 would still fit in float32.  Guard anyway:
        strain_rate_factor = (1.0 + C * eps_log_term).clamp(-1e4, 1e4)
        
        # ---- ③  temperature term  ----------------------------------------------
        # t_star already ∈ (1e-6 , 0.999); just convert to double for Pow
        temp_factor = (1.0 - t_star.double()).pow(m.double()).float()
        
        # ---- final JC stress  ----------------------------------------------------
        sig_jc_pred = eps_term * strain_rate_factor * temp_factor
        
        """
        with torch.no_grad():
            print('max |eps_term|           :', eps_term.abs().max().item())
            print('max |strain_rate_factor|:', strain_rate_factor.abs().max().item())
            print('min temp_factor         :', temp_factor.min().item())
        """
            
        assert_finite('sig_jc_pred', sig_jc_pred)

        if not torch.isfinite(sig_jc_pred).all():
            bad = sig_jc_pred[~torch.isfinite(sig_jc_pred)]
            #raise RuntimeError(f"Non-finite sig_jc_pred: {bad[:5]}")
            print(f"Non-finite sig_jc_pred: {batch['tags']['test_id']}")

        if return_all:
            return (time,
                    sig_1w_exp,  sig_jc_pred, eps_exp,
                    eps_pl_exp, eps_pl_dot_exp, t_star)
            
        return sig_jc_pred, sig_1w_exp

    # ---------------------------------------------------------------- loss
    def _loss(self,
              sig_pred: torch.Tensor,
              sig_exp:  torch.Tensor,
              batch:    Dict[str, torch.Tensor]) -> torch.Tensor:
        """
        Tukey-weighted RMSE between predicted JC stress and experimental
        one-wave stress.  Returns a tensor of shape (B,).
        """
        w_raw = batch["transmitted_weight"]                         # (B,T)
        mask  = w_raw / w_raw.abs().amax(dim=1, keepdim=True)#.clamp_min(1e-6)
    
        resid2 = mask * (-sig_pred - sig_exp).square()               # (B,T)
        rmse   = torch.sqrt(resid2.sum(dim=1) /
                            mask.sum(dim=1))
        #.clamp_min(1e-6))        # (B,)
        #rmse = torch.nan_to_num(rmse, nan=1e6, posinf=1e6, neginf=1e6)
    
        return rmse

    # ---------------------------------------------------------------- training step
    def training_step(self, batch, _):
        # move tensors? Lightning will via transfer hook; still assert
        assert batch["incident_raw"].is_cuda, "batch not on GPU"

        with torch.autocast(device_type='cuda', dtype=torch.float64, enabled=True):
            sig_pred, sig_exp = self._forward_physics(batch)
        bs = sig_pred.size(0)
        L_sig = self._loss(sig_pred, sig_exp, batch).mean()
        L_reg = self.lambda_reg * self.jc.l2_penalty()
        loss  = self.lambda_sig * L_sig + L_reg

        # logging
        self.log("train_L_sig", L_sig, prog_bar=False, batch_size=bs)
        self.log("train_loss",   loss,  prog_bar=False, batch_size=bs)
        return loss

    # ---------------------------------------------------------------- validation
    def validation_step(self, batch, _):
        sig_pred, sig_exp = self._forward_physics(batch)
        bs = sig_pred.size(0)
        L_sig = self._loss(sig_pred, sig_exp, batch).mean()
        L_reg = self.lambda_reg * self.jc.l2_penalty()
        loss  = self.lambda_sig * L_sig + L_reg
        self.log("val_L_sig", L_sig, prog_bar=False, on_epoch=True, batch_size=bs)
        self.log("val_loss",   loss,  prog_bar=False, on_epoch=True, batch_size=bs)
        return lossF

    # ---------------------------------------------------------------- epoch end (LR sched)
    def on_validation_epoch_end(self):
        #print(f"[DEBUG] keys in callback_metrics: {list(trainer.callback_metrics.keys())[:10]}")
        sch = self.lr_schedulers()
        sch.step(self.trainer.callback_metrics["val_loss"])
        pass

    # ---------------------------------------------------------------- optim
    def configure_optimizers(self):
        opt = torch.optim.Adam(self.parameters(), lr=self.lr_adam, betas=(0.9, 0.99))
        sch = torch.optim.lr_scheduler.ReduceLROnPlateau(opt, factor=0.5, patience=100, verbose=True)
        return {"optimizer": opt, "lr_scheduler": sch, "monitor": "val_loss"}

    # ---------------------------------------------------------------- custom batch transfer
    def transfer_batch_to_device(self, batch, device, dataloader_idx):
        return {k: (v.to(device) if torch.is_tensor(v) else v) for k, v in batch.items()}

    def compute_loss(self, batch):
        """Convenience wrapper for quick smoke-tests (no grad, no logging)."""
        sig_1w_exp, sig_jc_pred = self._forward_physics(batch)
        loss_sig = torch.mean((sig_jc_pred - sig_1w_exp) ** 2)
        return loss_sig



