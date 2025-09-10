# -*- coding: utf-8 -*-
from __future__ import annotations
import os

APP_TITLE = '🧠 MacroCoach v2（互动+稳健热修复）'
APP_ICON = '🧠'

DEFAULTS = {
    'sex': 'male', 'age': 21, 'height_cm': 181.0, 'weight_kg': 88.2, 'body_fat_pct': 24.0,
    'baseline_pal': 1.35,
    'protein_g_per_kg_bw': 2.2, 'fat_g_per_kg_bw': 0.7,
    'deficit': 0.20, 'min_deficit': 0.10, 'max_deficit': 0.30,
    'loss_rate_pct': 0.7,
}

MET_TABLE = {
    'badminton': {'low': 4.5, 'moderate': 6.0, 'high': 7.0},
    'strength':  {'low': 3.5, 'moderate': 5.0, 'high': 6.0},
    'cardio':    {'low': 5.0, 'moderate': 7.0, 'high': 10.0},
}

CARB_FLOOR_HIGH_INT = 4.0
CARB_FLOOR_MOD_INT  = 3.0

EA_MIN_DEFAULT  = 30.0
EA_PREF_DEFAULT = 35.0

TRAINING_LOAD_THRESHOLD = 900.0
TRAINING_DAY_CARB_BUMP_G_PER_KG = 1.0

PID_DEFAULT = {'Kp': 0.35, 'Ki': 0.05, 'Kd': 0.00, 'integral_cap': 0.15}

DB_PATH = os.getenv('MACRO_COACH_DB_PATH', 'macrocoach.db')

def configure_matplotlib_fonts() -> None:
    import matplotlib
    matplotlib.rcParams['font.sans-serif'] = [
        'Microsoft YaHei', 'SimHei', 'Noto Sans CJK SC', 'WenQuanYi Zen Hei',
        'Arial Unicode MS', 'DejaVu Sans'
    ]
    matplotlib.rcParams['axes.unicode_minus'] = False
