# -*- coding: utf-8 -*-
from __future__ import annotations
from datetime import date, timedelta
import streamlit as st
from ..services.schedule import schedule
from ..domain.models import UserProfile
from ..data.db import df_from_sql
from .keys import key

def render_tab_scheduler(side: dict) -> None:

    st.subheader('📆 饮食周期化调度器（预生成未来 N 天）', anchor=False)
    mode = st.selectbox('模式', ['continuous','5+2','matador_2+2'], index=1, key=key('sched','mode'), help='连续缺口/每周5缺口+2维持/MATADOR 2缺口+2维持。')
    days = st.number_input('生成天数', 7, 56, 14, 1, key=key('sched','days'), help='建议 14 天为一轮。')
    start = st.date_input('开始日期', value=date.today(), key=key('sched','start'), help='从哪天开始生成。')
    st.caption('说明：按当前侧栏参数生成“日目标”（不含运动）。当天进入“今日计划”会用当日负荷/睡眠覆盖为更精准的值。')
    if st.button('生成未来计划并写入数据库', type='primary', key=key('sched','run'), help='写入 daily_targets（day_type 会标注缺口/维持）。'):
        profile = UserProfile(
            sex=str(side['sex']), age=int(side['age']), height_cm=float(side['height_cm']), weight_kg=float(side['weight_kg']),
            body_fat_pct=float(side['body_fat_pct']) if side['body_fat_pct'] is not None else None, baseline_pal=float(side['baseline_pal']),
            protein_g_per_kg_bw=float(side['protein_per_kg_bw']), fat_g_per_kg_bw=float(side['fat_per_kg_bw']),
            deficit=float(side['deficit']), min_deficit=float(side['min_def']), max_deficit=float(side['max_def']),
        )
        if side['protein_basis']=='按FFM' and side['body_fat_pct'] is not None:
            ffm = float(side['weight_kg']) * (1 - float(side['body_fat_pct'])/100.0)
            protein_g = float(side['protein_per_kg_ffm']) * ffm
        else:
            protein_g = float(side['protein_per_kg_bw']) * float(side['weight_kg'])
        fat_g = float(side['fat_per_kg_bw']) * float(side['weight_kg'])
        out = schedule(profile, start, int(days), str(mode), float(side['deficit']), float(side['baseline_pal']), float(protein_g), float(fat_g))
        st.success(f'已写入 {len(out)} 天。下方显示预览。切到“📈 报告与曲线”可查看全局。')
        # 预览区间
        end = start + timedelta(days=int(days)-1)
        dfp = df_from_sql('SELECT date, target_kcal, protein_g, fat_g, carb_g, day_type FROM daily_targets WHERE date>=? AND date<=? ORDER BY date ASC', (start.isoformat(), end.isoformat()))
        if len(dfp)>0:
            st.dataframe(dfp, width='stretch', height=320)

