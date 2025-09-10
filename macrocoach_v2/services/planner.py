# -*- coding: utf-8 -*-
from __future__ import annotations
from typing import Optional, List, Dict
import pandas as pd
from ..settings import EA_MIN_DEFAULT, EA_PREF_DEFAULT, TRAINING_LOAD_THRESHOLD, TRAINING_DAY_CARB_BUMP_G_PER_KG
from ..domain.models import UserProfile, ActivityBlock, PIDConfig
from ..domain.calcs import calc_bmr, ffm_from_bf, calc_daily_exercise_kcal, carb_periodize, clamp
from ..domain.pid import PID

KCAL_PER_KG_FAT = 7700.0

def weekly_loss_from_df(dm: pd.DataFrame) -> Optional[float]:
    if dm is None or len(dm) == 0 or 'weight' not in dm:
        return None
    df = dm[['date','weight']].dropna().sort_values('date')
    if len(df) < 8: return None
    last7 = df.tail(7)['weight'].mean()
    prev7 = df.tail(14).head(7)['weight'].mean()
    if pd.isna(last7) or pd.isna(prev7): return None
    return float(max(0.0, prev7 - last7))

def _ema(series: pd.Series, alpha: float=0.5) -> float:
    if series is None or len(series) == 0: return 0.0
    try:
        return float(series.ewm(alpha=alpha, adjust=False).mean().iloc[-1])
    except Exception:
        return float(series.mean())

def predict_next_day(tracker_df: Optional[pd.DataFrame]) -> Dict[str,str]:
    if tracker_df is None or len(tracker_df) == 0:
        return {'train_band':'medium','deficit_band':'medium','note':'无历史数据，使用默认中档。'}
    df = tracker_df.copy().sort_values('date').tail(14)
    f_ema = _ema(df.get('fatigue', pd.Series(dtype=float)), 0.3)
    s_ema = _ema(df.get('sleep_h', pd.Series(dtype=float)), 0.3)
    l_ema = _ema(df.get('load_index', pd.Series(dtype=float)), 0.3)
    p_ema = _ema(df.get('perf_pct', pd.Series(dtype=float)), 0.3)
    HIGH_FATIGUE, LOW_SLEEP, HIGH_LOAD, LOW_LOAD, POOR_PERF = 7.0, 6.5, 1600, 900, -5.0
    if f_ema >= HIGH_FATIGUE or s_ema < LOW_SLEEP or p_ema <= POOR_PERF:
        return {'train_band':'low','deficit_band':'low','note':'疲劳/睡眠/表现指示恢复日。'}
    if l_ema >= HIGH_LOAD:
        return {'train_band':'medium','deficit_band':'medium','note':'近期负荷较高，建议中强度与中等赤字。'}
    if l_ema <= LOW_LOAD and f_ema <= 4.0 and s_ema >= 7.5 and p_ema >= 0:
        return {'train_band':'high','deficit_band':'medium','note':'状态佳且负荷不高，可安排高强度日。'}
    return {'train_band':'medium','deficit_band':'medium','note':'整体中性，采用中档。'}

def plan_day(profile: UserProfile,
             acts: List[ActivityBlock],
             steps: Optional[int],
             auto_mode: bool,
             target_loss_week_kg: float,
             pid_cfg: PIDConfig,
             fatigue: int, sleep_h: float, perf_change_pct: float,
             apply_suggestions: bool,
             dm_hist: pd.DataFrame,
             today_weight: Optional[float],
             protein_basis: str = 'FFM',
             protein_per_kg_ffm: float = 2.6,
             ea_min: float = EA_MIN_DEFAULT,
             ea_pref: float = EA_PREF_DEFAULT,
             training_day_carb_bump_g_per_kg: float = TRAINING_DAY_CARB_BUMP_G_PER_KG,
             training_load_threshold: float = TRAINING_LOAD_THRESHOLD
             ) -> Dict[str, object]:

    if today_weight is not None and today_weight > 0:
        profile.weight_kg = float(today_weight)

    ffm = ffm_from_bf(profile.weight_kg, profile.body_fat_pct)

    pal = float(profile.baseline_pal)
    if steps is not None:
        pal += max(0, (steps - 7000)) / 2000.0 * 0.05

    bmr = calc_bmr(profile)
    ex_kcal, load_index = calc_daily_exercise_kcal(profile.weight_kg, acts)
    tdee = bmr * pal + ex_kcal

    # —— 关键改动：基于“目标每周下降”即刻反推赤字（历史不足时也生效） ——
    deficit_from_rate = 0.0
    if tdee > 0:
        daily_deficit_kcal = (target_loss_week_kg * KCAL_PER_KG_FAT) / 7.0
        deficit_from_rate = daily_deficit_kcal / tdee
    deficit = float(clamp(deficit_from_rate if deficit_from_rate>0 else profile.deficit, profile.min_deficit, profile.max_deficit))
    notes: List[str] = [f'按目标下降直接估算赤字={deficit_from_rate:.3f}（已夹在上下限内）']

    # 有历史 → 使用 PID 围绕目标周下降微调（基于实际趋势）
    if auto_mode:
        loss_obs = weekly_loss_from_df(dm_hist)
        if loss_obs is not None:
            err = target_loss_week_kg - loss_obs
            pid = PID(pid_cfg)
            delta = pid.step(err)
            before = deficit
            deficit = clamp(deficit + delta, profile.min_deficit, profile.max_deficit)
            if abs(deficit - before) > 1e-6:
                notes.append(f'PID: 基于趋势调整赤字 {before:.2f} → {deficit:.2f} (目标{target_loss_week_kg:.2f}kg/周, 实际{loss_obs:.2f})')
        else:
            notes.append('趋势不足：最近体重记录不足，已直接按“目标每周下降”计算赤字')

    suggestions: List[Dict[str, float | str]] = []
    if fatigue >= 7:
        suggestions += [{'type':'deficit','delta':-0.03,'desc':'疲劳高→赤字-0.03'},
                        {'type':'carb','g_per_kg':+0.8,'desc':'疲劳高→碳水+0.8 g/kg'}]
    if sleep_h < 6.5:
        suggestions += [{'type':'deficit','delta':-0.02,'desc':'睡眠不足→赤字-0.02'}]
    if perf_change_pct <= -5:
        suggestions += [{'type':'deficit_to','value':0.10,'desc':'表现下降→赤字≤0.10'},
                        {'type':'carb','g_per_kg':+1.0,'desc':'表现下降→碳水+1.0 g/kg'}]

    if dm_hist is not None and len(dm_hist)>0 and 'sleep_h' in dm_hist:
        df_sorted = dm_hist.sort_values('date').tail(7)
        if len(df_sorted)>0 and df_sorted['sleep_h'].notna().any():
            sleep_ema3 = _ema(df_sorted['sleep_h'].dropna(), 0.5)
            if sleep_ema3 < 6.5:
                before = deficit
                deficit = clamp(min(deficit, 0.10), profile.min_deficit, profile.max_deficit)
                if deficit < before:
                    notes.append('短期睡眠偏低(EMA)：将赤字限制到 ≤0.10')

    target_kcal = tdee * (1 - deficit)

    if protein_basis.upper() == 'FFM':
        protein_g = float(protein_per_kg_ffm * ffm)
    else:
        protein_g = float(profile.protein_g_per_kg_bw * profile.weight_kg)
    fat_g = float(profile.fat_g_per_kg_bw * profile.weight_kg)

    kcal_pf = protein_g*4 + fat_g*9
    carb_kcal = max(0.0, target_kcal - kcal_pf)
    carb_g = carb_kcal/4.0

    if apply_suggestions and len(suggestions)>0:
        carb_g += sum(float(s.get('g_per_kg',0))*profile.weight_kg for s in suggestions if s['type']=='carb')

    is_training_day = (load_index >= float(training_load_threshold))
    if is_training_day and training_day_carb_bump_g_per_kg > 0:
        carb_g += float(training_day_carb_bump_g_per_kg) * profile.weight_kg
        notes.append(f'训练日加成：+{training_day_carb_bump_g_per_kg:.1f} g/kg 碳水')

    if profile.carb_periodization:
        carb_g = carb_periodize(carb_g, load_index, profile.weight_kg)

    final_kcal = protein_g*4 + fat_g*9 + carb_g*4

    # —— 诊断：纯按赤字时的摄入与 EA 下限要求 ——
    intended_kcal = tdee * (1 - deficit)
    ea_floor_kcal = ex_kcal + float(ea_min) * ffm

    ea_kcal_per_kg = (final_kcal - ex_kcal) / max(1e-6, ffm)
    ea_guard_applied = 0
    if ea_kcal_per_kg < float(ea_min):
        need_intake = ex_kcal + float(ea_min) * ffm
        new_kcal = min(need_intake, tdee)
        if new_kcal > final_kcal + 1e-6:
            ea_guard_applied = 1
            notes.append(f'EA 守门：为满足 EA≥{ea_min:.0f}，摄入 {final_kcal:.0f} → {new_kcal:.0f} kcal（以碳水填充）')
            final_kcal = new_kcal
            carb_g = max(0.0, (final_kcal - (protein_g*4 + fat_g*9)) / 4.0)
            ea_kcal_per_kg = (final_kcal - ex_kcal) / max(1e-6, ffm)

    loss_obs = weekly_loss_from_df(dm_hist) if dm_hist is not None else None
    weekly_loss_pct = None
    target_loss_pct = None
    if loss_obs is not None:
        current_w = float(profile.weight_kg)
        weekly_loss_pct = (loss_obs / max(1e-6, current_w)) * 100.0
        target_loss_pct = (target_loss_week_kg / max(1e-6, current_w)) * 100.0

    return {
        'bmr': round(bmr,1), 'pal': round(pal,2),
        'exercise_kcal': round(ex_kcal,0), 'tdee_used': round(tdee,0),
        'deficit': round(deficit,3),
        'target_kcal': round(final_kcal,0),
        'protein_g': round(protein_g,0), 'fat_g': round(fat_g,0), 'carb_g': round(carb_g,0),
        'load_index': round(load_index,0),
        'ea': round(ea_kcal_per_kg,1),
        'notes': notes,
        'apply_log': [],
        'suggestions': [str(s['desc']) for s in suggestions],
        'ffm': round(ffm,1),
        'ea_guard_applied': int(ea_guard_applied),
        'is_training_day': bool(is_training_day),
        'weekly_loss_pct': None if weekly_loss_pct is None else round(weekly_loss_pct,2),
        'target_loss_pct': None if target_loss_pct is None else round(target_loss_pct,2),
        'intended_kcal': round(intended_kcal,0),
        'ea_floor_kcal': round(ea_floor_kcal,0)
    }
