# -*- coding: utf-8 -*-
from __future__ import annotations
from typing import List, Tuple
from .models import ActivityBlock, UserProfile
from ..settings import MET_TABLE, CARB_FLOOR_HIGH_INT, CARB_FLOOR_MOD_INT

def mifflin_bmr(sex: str, age: int, height_cm: float, weight_kg: float) -> float:
    return float(10*weight_kg + 6.25*height_cm - 5*age + (5 if sex.lower()=='male' else -161))

def katch_bmr(weight_kg: float, body_fat_pct: float) -> float:
    ffm = weight_kg * (1 - body_fat_pct/100.0)
    return float(370 + 21.6*ffm)

def ffm_from_bf(weight_kg: float, body_fat_pct: float | None) -> float:
    if body_fat_pct is None:
        return float(weight_kg * 0.75)
    return float(weight_kg * (1 - body_fat_pct/100.0))

def calc_bmr(profile: UserProfile) -> float:
    if profile.body_fat_pct is not None:
        return katch_bmr(profile.weight_kg, profile.body_fat_pct)
    return mifflin_bmr(profile.sex, profile.age, profile.height_cm, profile.weight_kg)

def resolve_met(name: str, intensity: str) -> float:
    if name not in MET_TABLE or intensity not in MET_TABLE[name]:
        raise ValueError(f"Unknown MET for {name}-{intensity}")
    return float(MET_TABLE[name][intensity])

def met_kcal(met: float, weight_kg: float, minutes: float) -> float:
    return float(met * 3.5 * weight_kg / 200.0 * minutes)

def calc_daily_exercise_kcal(weight_kg: float, acts: List[ActivityBlock]) -> Tuple[float, float]:
    total, load = 0.0, 0.0
    for a in acts:
        if a.minutes <= 0: 
            continue
        m = resolve_met(a.name, a.intensity)
        total += met_kcal(m, weight_kg, a.minutes)
        load  += m * a.minutes
    return float(total), float(load)

def carb_periodize(base_carb_g: float, load_index: float, weight_kg: float) -> float:
    adj = base_carb_g + 50.0 * max(0.0, (load_index - 1200.0))/1000.0
    if load_index >= 1600: return float(max(adj, CARB_FLOOR_HIGH_INT*weight_kg))
    if load_index >= 1200: return float(max(adj, CARB_FLOOR_MOD_INT*weight_kg))
    return float(adj)

def clamp(v: float, lo: float, hi: float) -> float:
    return float(max(lo, min(hi, v)))
