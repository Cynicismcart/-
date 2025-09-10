# -*- coding: utf-8 -*-
from __future__ import annotations
import streamlit as st
from ..settings import DEFAULTS, PID_DEFAULT, EA_MIN_DEFAULT, EA_PREF_DEFAULT, TRAINING_DAY_CARB_BUMP_G_PER_KG, TRAINING_LOAD_THRESHOLD

def render_sidebar() -> dict:
    with st.sidebar:
        st.header('基础资料', anchor=False)
        sex = st.selectbox('性别', ['male','female'], index=0, key='sb_sex', help='用于 BMR 计算。')
        age = st.number_input('年龄', 12, 80, DEFAULTS['age'], key='sb_age', help='用于 BMR 计算。')
        height_cm = st.number_input('身高(cm)', 120.0, 230.0, DEFAULTS['height_cm'], 0.5, key='sb_h', help='用于 BMR 计算。')
        weight_kg = st.number_input('（当前）体重(kg)', 30.0, 250.0, DEFAULTS['weight_kg'], 0.1, key='sb_w', help='用于所有按体重的计算。')
        bf_in = st.number_input('体脂率%(可选)', 0.0, 60.0, DEFAULTS['body_fat_pct'], 0.1, key='sb_bf', help='用于估算瘦体重(FFM)。留空亦可。')
        body_fat_pct = bf_in if bf_in>0 else None

        st.subheader('活动与模式', anchor=False)
        baseline_pal = st.slider('PAL(非运动日)', 1.1, 1.8, DEFAULTS['baseline_pal'], 0.01, key='sb_pal', help='1.2=久坐；1.35=轻度(推荐)；1.5–1.6=中等；>1.7=体力劳动。')
        steps = st.number_input('当日步数(可选)', 0, 150000, 8000, 500, key='sb_steps', help='用于微调 PAL（步数↑→PAL 略增）。')
        auto_mode = st.toggle('启用 Auto', value=True, key='sb_auto', help='开启后：用最近 7–14 天体重趋势自动微调赤字。若历史不足，将直接按“目标%体重/周”估算赤字。')

        st.subheader('下降速度（按体重百分比）', anchor=False)
        loss_rate_pct = st.slider('目标每周下降(%体重/周)', 0.5, 1.2, DEFAULTS['loss_rate_pct'], 0.1, key='sb_loss_pct', help='历史不足时“立即生效”，有历史后由 PID 围绕该速度微调。')

        st.subheader('蛋白与脂肪', anchor=False)
        protein_basis = st.selectbox('蛋白依据', ['按FFM','按体重'], index=0, key='sb_pbasis', help='按 FFM 计更能在缺口期保肌。')
        protein_per_kg_ffm = st.slider('蛋白(g/kg FFM)', 2.3, 3.1, 2.6, 0.1, key='sb_p_ffm', help='缺口期推荐 2.3–3.1 g/kg FFM。')
        protein_per_kg_bw = st.slider('蛋白(g/kg 体重)', 1.6, 3.0, DEFAULTS['protein_g_per_kg_bw'], 0.1, key='sb_p_bw', help='若选择按体重计时生效。')
        fat_per_kg_bw = st.slider('脂肪(g/kg 体重)', 0.5, 1.0, DEFAULTS['fat_g_per_kg_bw'], 0.05, key='sb_f_bw', help='低于 0.5 g/kg 不建议长期。')

        st.subheader('能量可用性（EA）', anchor=False)
        ea_min = st.slider('EA 下限(硬护栏)', 30.0, 40.0, EA_MIN_DEFAULT, 1.0, key='sb_ea_min', help='低于该值时系统会优先保障健康，自动提高摄入。')
        ea_pref = st.slider('EA 偏好线(报告提醒)', 30.0, 40.0, EA_PREF_DEFAULT, 1.0, key='sb_ea_pref', help='报告中以 7 天均值对比，长期低于该线会提示回补。')

        st.subheader('训练日判定与加碳', anchor=False)
        training_threshold = st.slider('训练日负荷阈值(MET·min)', 400, 2000, int(TRAINING_LOAD_THRESHOLD), 50, key='sb_tload', help='当日负荷≥此值视为训练日。')
        training_bump = st.slider('训练日额外碳水(g/kg)', 0.0, 1.5, TRAINING_DAY_CARB_BUMP_G_PER_KG, 0.1, key='sb_tbump', help='训练日额外碳水基线（在周期化之前应用）。')

        st.subheader('赤字上下限 & PID', anchor=False)
        deficit = st.slider('赤字(手动上/下限)', 0.05, 0.35, DEFAULTS['deficit'], 0.01, key='sb_def', help='用于限定赤字范围；默认按“目标%体重/周”计算的赤字会被夹在上下限之间。')
        min_def = st.slider('赤字下限', 0.05, 0.25, DEFAULTS['min_deficit'], 0.01, key='sb_min', help='最小赤字，防止系统推得过低。')
        max_def = st.slider('赤字上限', 0.10, 0.40, DEFAULTS['max_deficit'], 0.01, key='sb_max', help='最大赤字，防止系统推得过高。')
        Kp = st.number_input('Kp', 0.0, 1.0, PID_DEFAULT['Kp'], 0.01, key='sb_kp', help='比例项：差距越大，调整越多。')
        Ki = st.number_input('Ki', 0.0, 0.5, PID_DEFAULT['Ki'], 0.01, key='sb_ki', help='积分项：持续落后时逐步累积。')
        Kd = st.number_input('Kd', 0.0, 0.5, PID_DEFAULT['Kd'], 0.01, key='sb_kd', help='微分项：抑制对突发波动过度反应。')
        Icap = st.number_input('积分上限', 0.0, 0.5, PID_DEFAULT['integral_cap'], 0.01, key='sb_icap', help='限制积分累计幅度，避免失控。')

    return dict(
        sex=sex, age=age, height_cm=height_cm, weight_kg=weight_kg, body_fat_pct=body_fat_pct,
        baseline_pal=baseline_pal, steps=steps, auto_mode=auto_mode,
        loss_rate_pct=loss_rate_pct,
        protein_basis=protein_basis, protein_per_kg_ffm=protein_per_kg_ffm, protein_per_kg_bw=protein_per_kg_bw, fat_per_kg_bw=fat_per_kg_bw,
        ea_min=ea_min, ea_pref=ea_pref,
        training_threshold=training_threshold, training_bump=training_bump,
        deficit=deficit, min_def=min_def, max_def=max_def,
        Kp=Kp, Ki=Ki, Kd=Kd, Icap=Icap
    )
