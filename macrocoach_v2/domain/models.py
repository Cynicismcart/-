# -*- coding: utf-8 -*-
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional

@dataclass
class UserProfile:
    sex: str; age: int; height_cm: float; weight_kg: float
    body_fat_pct: Optional[float] = None
    baseline_pal: float = 1.35
    protein_g_per_kg_bw: float = 2.2
    fat_g_per_kg_bw: float = 0.7
    deficit: float = 0.20
    min_deficit: float = 0.10
    max_deficit: float = 0.30
    carb_periodization: bool = True

@dataclass
class ActivityBlock:
    name: str; minutes: float; intensity: str  # 'low'/'moderate'/'high'

@dataclass
class PIDConfig:
    Kp: float; Ki: float; Kd: float; integral_cap: float = 0.2
