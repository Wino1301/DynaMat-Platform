"""pinn_data.py
================
Dataset and helper utilities for the PINN project.

Each experiment lives in a **.npz** file whose keys were set in the
*Preprocessing Script for PINNs* discussion.  The only compulsory keys
for model training are

    time, incident_raw, reflected_raw, transmitted_raw,
    incident_weight, reflected_weight, transmitted_weight,
    L0_mm, A0_mm2, D0_mm

All string tags are kept in the sample dict but ignored by the model –
use them later for plotting / filtering.

The module exposes:

* `SHPBDataNPZ`   – `torch.utils.data.Dataset` implementation.
* `build_dataloaders` – convenience function that discovers files in a
  folder, splits them into train / val sets, and returns ready‑to‑use
  `DataLoader`s.

Logging is standard `logging`; set the level to `DEBUG` when you want to
watch every file load.
"""

from __future__ import annotations

import logging
import random
from pathlib import Path
from typing import List, Tuple

import numpy as np
import torch
from torch.utils.data import Dataset, DataLoader

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Dataset
# ---------------------------------------------------------------------------

class SHPBDataNPZ(Dataset):
    """Load individual **.npz** experiment files for PINN training.

    Parameters
    ----------
    files : list[pathlib.Path]
        List of **.npz** files.
    enable_debug : bool, default=False
        If *True* the constructor sets the module logger to DEBUG.
    """

    def __init__(self, files: List[Path], *, enable_debug: bool = False):
        super().__init__()
        self.files = list(files)
        if enable_debug:
            logging.basicConfig(level=logging.DEBUG)
        logger.info("SHPBDataNPZ loaded %d files", len(self.files))

    # ---------------------------------------------------------------------
    # Required by torch Dataset interface
    # ---------------------------------------------------------------------

    def __len__(self) -> int:
        return len(self.files)

    def __getitem__(self, idx: int):
        path = self.files[idx]
        data = np.load(path, allow_pickle=False)

        # --- Continuous signals ------------------------------------------------
        sig_keys = [
            "time",
            "incident_raw",
            "reflected_raw",
            "transmitted_raw",
            "incident_weight",
            "reflected_weight",
            "transmitted_weight",  
        ]
        sample = {k: torch.from_numpy(data[k]) for k in sig_keys if k in data}

        # --- Geometry  (keep as 0‑D float32 tensors) --------------------------
        geom_keys = ["L0_mm", "A0_mm2", "D0_mm"]
        for gk in geom_keys:
            if gk in data:
                sample[gk] = torch.tensor(data[gk], dtype=torch.float32)

        # --- Tags (strings) ----------------------------------------------------
        tag_keys = [
            "uid",
            "material",
            "processing",
            "test_mode",
            "test_date",
            "test_temperature",
            "test_id",
        ]
        sample["tags"] = {tk: str(data[tk]) for tk in tag_keys if tk in data}

        logger.debug("Loaded %s", path.name)
        return sample


# ---------------------------------------------------------------------------
# Helper to build DataLoaders                                                  
# ---------------------------------------------------------------------------

def build_dataloaders(
    root_dir: str | Path,
    *,
    batch_size: int = 1,
    val_ratio: float = 0.2,
    shuffle: bool = True,
    seed: int = 42,
    num_workers: int = 0,
    debug: bool = False,
    persistent_workers: bool = False,
) -> Tuple[DataLoader, DataLoader]:
    """Create train/validation DataLoaders from a directory of **.npz** files.

    Parameters
    ----------
    root_dir : str or pathlib.Path
        Folder containing experiment *.npz* files.
    batch_size : int, default 1
        Mini‑batch size.  For a PINN the data loader usually just returns
        one experiment (set of signals) at a time, but a higher batch can
        average gradients across experiments.
    val_ratio : float, default 0.2
        Fraction of files to reserve for validation.
    shuffle : bool, default True
        Whether to shuffle file order before splitting.
    seed : int, default 42
        RNG seed for reproducible splits.
    num_workers : int, default 0
        Passed through to PyTorch `DataLoader`.

    Returns
    -------
    (train_loader, val_loader)
        Tuple of PyTorch DataLoaders.
    """

    root = Path(root_dir)
    if not root.is_dir():
        raise FileNotFoundError(f"{root} is not a directory")

    files = sorted(root.glob("*.npz"))
    if not files:
        raise FileNotFoundError(f"No .npz files found in {root}")

    if shuffle:
        random.seed(seed)
        random.shuffle(files)

    split_idx = int(len(files) * (1 - val_ratio))
    train_files = files[:split_idx]
    val_files = files[split_idx:]

    train_ds = SHPBDataNPZ(train_files)
    val_ds = SHPBDataNPZ(val_files)

    if debug:
        logging.basicConfig(level=logging.DEBUG)
        logger.debug("Train files: %s", [f.name for f in train_ds.files])
        logger.debug("Val   files: %s", [f.name for f in val_ds.files])

    train_loader = DataLoader(
        train_ds,
        batch_size=batch_size,
        shuffle=shuffle,
        num_workers=num_workers,
        pin_memory=torch.cuda.is_available(),
        persistent_workers=persistent_workers and num_workers > 0, 
    )
    val_loader = DataLoader(
        val_ds,
        batch_size=batch_size,
        shuffle=False,
        num_workers=num_workers,
        pin_memory=torch.cuda.is_available(),
        persistent_workers=persistent_workers and num_workers > 0, 
    )

    return train_loader, val_loader
