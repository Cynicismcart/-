# -*- coding: utf-8 -*-
from __future__ import annotations
import streamlit as st
from .keys import key
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from ..data.db import df_from_sql, intake_aggregate_by_day, volume_last_n_days
from ..services.planner import weekly_loss_from_df
from ..domain.calcs import ffm_from_bf
from ..settings import EA_MIN_DEFAULT, EA_PREF_DEFAULT

def _ts(df, xcol, ycols, title, yaxis_title):
    fig = go.Figure()
    for y in ycols:
        if y in df.columns:
            fig.add_trace(go.Scatter(x=pd.to_datetime(df[xcol]), y=df[y], name=y, mode='lines'))
    fig.update_layout(title=title, hovermode='x unified', legend_orientation='h', margin=dict(l=10,r=10,t=40,b=10))
    fig.update_xaxes(rangeslider_visible=True)
    fig.update_yaxes(title_text=yaxis_title)
    return fig

def render_tab_report(side: dict) -> None:

    st.subheader('历史趋势（支持缩放/悬停/导出）', anchor=False)
    st.caption('图表可拖动缩放、框选区域、悬停查看数值，并可从右上角菜单导出图像。')

    dm = df_from_sql('SELECT * FROM daily_metrics ORDER BY date ASC')
    dt = df_from_sql('SELECT * FROM daily_targets ORDER BY date ASC')

    if len(dm)==0 and len(dt)==0:
        st.info('暂无历史数据。先在“今日计划”或“手动录入”保存一些记录吧。')
        return

    if len(dm)>0:
        st.markdown('**体重/睡眠/负荷**')
        cols = ['weight','sleep_h','load_index']
        fig1 = _ts(dm, 'date', [c for c in cols if c in dm], '体重/睡眠/负荷', '值')
        st.plotly_chart(fig1, width='stretch')

    if len(dt)>0:
        st.markdown('**TDEE 与目标热量**')
        cols2 = ['tdee_used','target_kcal']
        fig2 = _ts(dt, 'date', [c for c in cols2 if c in dt], 'TDEE & 目标热量', 'kcal')
        st.plotly_chart(fig2, width='stretch')

    st.write('---')
    st.subheader('%BW/week 轨道图', help='后7 vs 前7 的滚动周降幅，建议落在 0.5–1.0%/周之间。')
    if len(dm)>7 and 'weight' in dm:
        dfw = dm[['date','weight']].dropna().copy()
        dfw['date'] = pd.to_datetime(dfw['date']).sort_values()
        dfw = dfw.sort_values('date')
        x, y = [], []
        for i in range(13, len(dfw)):
            prev7 = dfw['weight'].iloc[i-13:i-6].mean()
            last7 = dfw['weight'].iloc[i-6:i+1].mean()
            loss_kg = max(0.0, prev7 - last7)
            current_w = dfw['weight'].iloc[i]
            x.append(dfw['date'].iloc[i]); y.append((loss_kg/max(1e-6,current_w))*100.0)
        if y:
            fig3 = go.Figure()
            fig3.add_trace(go.Scatter(x=x, y=y, mode='lines', name='%BW/week'))
            fig3.add_hline(y=0.5, line_dash='dash'); fig3.add_hline(y=1.0, line_dash='dash')
            fig3.update_layout(title='每周下降速度（%体重/周）', hovermode='x unified', legend_orientation='h', margin=dict(l=10,r=10,t=40,b=10))
            fig3.update_xaxes(rangeslider_visible=True); fig3.update_yaxes(title_text='%BW/week')
            st.plotly_chart(fig3, width='stretch')
        else:
            st.caption('数据不足，无法绘制。')
    else:
        st.caption('数据不足，无法计算 %BW/week。')

    st.write('---')
    st.subheader('EA（日值与7天均值）', help='EA=(摄入-运动)/FFM；展示 7 天滚动均值和阈值线。')
    ia = intake_aggregate_by_day()
    if len(ia)>0 and len(dm)>0:
        df_ea = pd.merge(dm[['date','weight','load_index']], ia, on='date', how='left')
        df_ea['kcal'] = pd.to_numeric(df_ea['kcal'], errors='coerce')
        df_ea['weight'] = pd.to_numeric(df_ea['weight'], errors='coerce')
        df_ea['load_index'] = pd.to_numeric(df_ea['load_index'], errors='coerce')
        df_ea = df_ea.fillna({'kcal':0.0}).copy()

        def est_ea_row(r):
            w = float(r.get('weight') or 0.0)
            bf = float(side['body_fat_pct']) if side['body_fat_pct'] is not None else 24.0
            ffm = ffm_from_bf(w if w>0 else float(side['weight_kg']), bf)
            ex = 3.5 * (w if w>0 else float(side['weight_kg'])) * float(r.get('load_index') or 0.0) / 200.0
            return (float(r.get('kcal') or 0.0) - ex) / max(ffm,1e-6)

        df_ea['EA'] = df_ea.apply(est_ea_row, axis=1)
        df_ea['EA_7d'] = df_ea['EA'].rolling(window=7, min_periods=1).mean()

        fig4 = go.Figure()
        fig4.add_trace(go.Scatter(x=pd.to_datetime(df_ea['date']), y=df_ea['EA'], name='EA 日值', mode='lines'))
        fig4.add_trace(go.Scatter(x=pd.to_datetime(df_ea['date']), y=df_ea['EA_7d'], name='EA 7天均值', mode='lines'))
        fig4.add_hline(y=float(side.get('ea_min', EA_MIN_DEFAULT)), line_dash='dash')
        fig4.add_hline(y=float(side.get('ea_pref', EA_PREF_DEFAULT)), line_dash='dot')
        fig4.update_layout(title='能量可用性', hovermode='x unified', legend_orientation='h', margin=dict(l=10,r=10,t=40,b=10))
        fig4.update_xaxes(rangeslider_visible=True); fig4.update_yaxes(title_text='EA (kcal/kg FFM)')
        st.plotly_chart(fig4, width='stretch')
    else:
        st.caption('EA 图缺少摄入或指标数据。')

    st.write('---')
    st.subheader('蛋白达成率（摄入/目标）', help='每日摄入蛋白 / 当日目标蛋白。')
    if len(dt)>0:
        protein_target = dt[['date','protein_g']].copy()
        protein_target['protein_g'] = pd.to_numeric(protein_target['protein_g'], errors='coerce')

        ia2 = intake_aggregate_by_day()[['date','protein_g']].rename(columns={'protein_g':'protein_intake'})
        ia2['protein_intake'] = pd.to_numeric(ia2['protein_intake'], errors='coerce')

        dfp = pd.merge(protein_target, ia2, on='date', how='left')
        dfp['protein_intake'] = dfp['protein_intake'].fillna(0.0)

        dfp['rate'] = (dfp['protein_intake'] / dfp['protein_g']).clip(upper=2.0) * 100.0
        fig5 = go.Figure()
        fig5.add_trace(go.Scatter(x=pd.to_datetime(dfp['date']), y=dfp['rate'], mode='lines', name='蛋白达成率(%)'))
        fig5.add_hline(y=100.0, line_dash='dash')
        fig5.update_layout(title='蛋白达成率', hovermode='x unified', legend_orientation='h', margin=dict(l=10,r=10,t=40,b=10))
        fig5.update_xaxes(rangeslider_visible=True); fig5.update_yaxes(title_text='%', range=[0, 200])
        st.plotly_chart(fig5, width='stretch')
    else:
        st.caption('尚无目标，无法计算蛋白达成率。')

    st.write('---')
    st.subheader('近7天每肌群组数', help='用于监控训练量是否处于合理区间（10–20 组/周/肌群）。')
    vol = volume_last_n_days(7)
    if len(vol)>0:
        dfv = vol.groupby('muscle_group', as_index=False)['sets'].sum()
        fig6 = px.bar(dfv, x='muscle_group', y='sets', title='7天总组数', labels={'muscle_group':'肌群','sets':'组数'})
        st.plotly_chart(fig6, width='stretch')
        tips = []
        for _, r in dfv.iterrows():
            if r['sets'] < 10:
                tips.append(f"{r['muscle_group']} < 10 组/周：考虑增加。")
            elif r['sets'] > 20:
                tips.append(f"{r['muscle_group']} > 20 组/周：若疲劳高/睡眠差，考虑降量一周。")
        if tips:
            st.info('；'.join(tips))
    else:
        st.caption('尚无训练量记录。')

