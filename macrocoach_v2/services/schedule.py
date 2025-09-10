# -*- coding: utf-8 -*-
from __future__ import annotations
from typing import List, Dict
from datetime import date, timedelta
from ..domain.models import UserProfile
from ..domain.calcs import calc_bmr
from ..data.db import upsert_targets

def schedule(profile: UserProfile, start: date, days: int, mode: str, deficit: float, pal: float, protein_g: float, fat_g: float) -> List[Dict[str, str]]:
    out = []
    bmr = calc_bmr(profile)
    for i in range(days):
        d = start + timedelta(days=i)
        day_type = 'deficit'
        if mode == 'continuous':
            day_type = 'deficit'
        elif mode == '5+2':
            if (i % 7) >= 5:
                day_type = 'maintain'
        elif mode == 'matador_2+2':
            if (i % 28) >= 14:
                day_type = 'maintain'
        tdee = bmr * pal
        if day_type == 'deficit':
            target_kcal = tdee * (1 - deficit); def_used = deficit
        else:
            target_kcal = tdee; def_used = 0.0
        carb_kcal = max(0.0, target_kcal - (protein_g*4 + fat_g*9))
        carb_g = carb_kcal / 4.0
        upsert_targets(d.isoformat(), {
            'target_kcal': round(target_kcal,0), 'protein_g': round(protein_g,0),
            'fat_g': round(fat_g,0), 'carb_g': round(carb_g,0),
            'bmr': round(bmr,1), 'pal': round(pal,2), 'tdee_used': round(tdee,0),
            'deficit': round(def_used,3), 'ea': 0.0
        }, notes=f'预生成({mode})', ea_guard_applied=0, day_type=day_type)
        out.append({'date': d.isoformat(), 'day_type': day_type})
    return out
