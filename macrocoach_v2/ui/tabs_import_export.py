# -*- coding: utf-8 -*-
from __future__ import annotations
import os
import pandas as pd
import streamlit as st
from ..data.db import df_from_sql, executemany, execute
from ..utils.safe_cast import to_float, to_int
from .keys import key

def render_tab_import_export(db_path: str) -> None:

    st.subheader('导出 CSV / 数据库', anchor=False)
    if st.button('导出全部 CSV（metrics/targets/intake/volume）', key=key('t4','export_csv'), help='下载四张表的 CSV。'):
        dm = df_from_sql('SELECT * FROM daily_metrics ORDER BY date ASC')
        dt = df_from_sql('SELECT * FROM daily_targets ORDER BY date ASC')
        il = df_from_sql('SELECT * FROM intake_logs ORDER BY ts ASC')
        wl = df_from_sql('SELECT * FROM weekly_volume ORDER BY date ASC')
        st.download_button('下载 daily_metrics.csv', dm.to_csv(index=False).encode('utf-8'), file_name='daily_metrics.csv')
        st.download_button('下载 daily_targets.csv', dt.to_csv(index=False).encode('utf-8'), file_name='daily_targets.csv')
        st.download_button('下载 intake_logs.csv', il.to_csv(index=False).encode('utf-8'), file_name='intake_logs.csv')
        st.download_button('下载 weekly_volume.csv', wl.to_csv(index=False).encode('utf-8'), file_name='weekly_volume.csv')

    try:
        with open(db_path, 'rb') as f:
            db_bytes = f.read()
        st.download_button('下载数据库备份（.db）', db_bytes, file_name=os.path.basename(db_path))
    except Exception:
        st.caption('数据库尚未创建或无法访问备份。')

    st.write('---')
    st.subheader('导入 CSV（覆盖/补充到当前数据库）', anchor=False)
    uploaded_dm = st.file_uploader('选择 daily_metrics.csv', type=['csv'], key=key('imp','dm'), help='导入日指标。')
    uploaded_dt = st.file_uploader('选择 daily_targets.csv', type=['csv'], key=key('imp','dt'), help='导入日目标。')
    uploaded_il = st.file_uploader('选择 intake_logs.csv', type=['csv'], key=key('imp','il'), help='导入摄入记录。')
    uploaded_wl = st.file_uploader('选择 weekly_volume.csv', type=['csv'], key=key('imp','wl'), help='导入训练量记录。')
    if st.button('开始导入', type='primary', key=key('imp','run'), help='将 CSV 数据写入数据库。'):
        imported = []
        try:
            if uploaded_dm is not None:
                df = pd.read_csv(uploaded_dm)
                req_cols = {'date','weight','steps','exercise_min','sleep_h','fatigue','perf_pct','avg_hr','max_hr','load_index'}
                for m in (req_cols - set(df.columns)): df[m] = None
                rows = [(
                    str(row.get('date')), to_float(row.get('weight')), to_int(row.get('steps')), to_float(row.get('exercise_min')),
                    to_float(row.get('sleep_h')), to_int(row.get('fatigue')), to_float(row.get('perf_pct')), to_float(row.get('avg_hr')),
                    to_float(row.get('max_hr')), to_float(row.get('load_index'))
                ) for _, row in df.iterrows()]
                executemany(
                    'INSERT OR REPLACE INTO daily_metrics(date,weight,steps,exercise_min,sleep_h,fatigue,perf_pct,avg_hr,max_hr,load_index) VALUES(?,?,?,?,?,?,?,?,?,?)',
                    rows
                )
                imported.append(f'daily_metrics: {len(rows)} 行')
            if uploaded_dt is not None:
                df = pd.read_csv(uploaded_dt)
                req_cols = {'date','target_kcal','protein_g','fat_g','carb_g','bmr','pal','tdee_used','deficit','ea','ea_guard_applied','notes','day_type'}
                for m in (req_cols - set(df.columns)): df[m] = None
                rows = [(
                    str(row.get('date')), to_float(row.get('target_kcal')), to_float(row.get('protein_g')), to_float(row.get('fat_g')),
                    to_float(row.get('carb_g')), to_float(row.get('bmr')), to_float(row.get('pal')), to_float(row.get('tdee_used')),
                    to_float(row.get('deficit')), to_float(row.get('ea')), to_int(row.get('ea_guard_applied')), str(row.get('notes') or ''), str(row.get('day_type') or None)
                ) for _, row in df.iterrows()]
                executemany(
                    'INSERT OR REPLACE INTO daily_targets(date,target_kcal,protein_g,fat_g,carb_g,bmr,pal,tdee_used,deficit,ea,ea_guard_applied,notes,day_type) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',
                    rows
                )
                imported.append(f'daily_targets: {len(rows)} 行')
            if uploaded_il is not None:
                df = pd.read_csv(uploaded_il)
                req_cols = {'ts','date','meal_tag','kcal','protein_g','fat_g','carb_g','note'}
                for m in (req_cols - set(df.columns)): df[m] = None
                rows = [(
                    str(row.get('ts')), str(row.get('date')), str(row.get('meal_tag') or ''), to_float(row.get('kcal')),
                    to_float(row.get('protein_g')), to_float(row.get('fat_g')), to_float(row.get('carb_g')), str(row.get('note') or '')
                ) for _, row in df.iterrows()]
                executemany(
                    'INSERT INTO intake_logs(ts,date,meal_tag,kcal,protein_g,fat_g,carb_g,note) VALUES(?,?,?,?,?,?,?,?)',
                    rows
                )
                imported.append(f'intake_logs: {len(rows)} 行')
            if uploaded_wl is not None:
                df = pd.read_csv(uploaded_wl)
                req_cols = {'date','muscle_group','sets'}
                for m in (req_cols - set(df.columns)): df[m] = None
                rows = [(
                    str(row.get('date')), str(row.get('muscle_group') or ''), to_int(row.get('sets'))
                ) for _, row in df.iterrows()]
                executemany(
                    'INSERT INTO weekly_volume(date,muscle_group,sets) VALUES(?,?,?)',
                    rows
                )
                imported.append(f'weekly_volume: {len(rows)} 行')
            if imported:
                st.success('导入完成：' + '；'.join(imported))
            else:
                st.info('没有选择任何文件。')
        except Exception as e:
            st.error(f'导入失败：{e}')

