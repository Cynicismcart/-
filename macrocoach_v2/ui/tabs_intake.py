# -*- coding: utf-8 -*-
from __future__ import annotations
from datetime import date, datetime
import streamlit as st
from ..domain.models import UserProfile
from ..domain.calcs import calc_bmr, ffm_from_bf
from ..data.db import df_from_sql, upsert_targets, intake_sums, fetch_intake_today, add_intake_row, delete_last_intake_today
from .keys import key

def render_tab_intake(side: dict) -> None:
    # === Calendar (start) [forced] ===
    import datetime as _dt
    if "selected_date" not in st.session_state:
        st.session_state["selected_date"] = _dt.date.today()
    cur_date = st.session_state["selected_date"]
    cur_date_str = cur_date.isoformat()
    today_str = cur_date_str  # backward-compat
    with st.container(border=True):
        c1, c2 = st.columns([3,1])
        st.session_state["selected_date"] = c1.date_input("选择日期", value=cur_date, key=key("tabs_intake","date"))
        c2.button("今天", key=key("tabs_intake","today_btn"), on_click=lambda: st.session_state.update(selected_date=_dt.date.today()))
    cur_date = st.session_state["selected_date"]
    cur_date_str = cur_date.isoformat()
    today_str = cur_date_str
    # === Calendar (end) ===

    today_str = cur_date_str
    st.subheader('今日摄入 · 实时记录', anchor=False)

    dt_today = df_from_sql('SELECT * FROM daily_targets WHERE date = ?', (today_str,))
    if len(dt_today)==0:
        st.warning('今天还没有目标。建议先在“今日计划”生成；或点击下面按钮快速生成“基线目标”（按侧栏参数，暂不含运动）。')
        if st.button('⚡ 一键生成今日基线目标（按侧栏参数，无运动）', key=key('intake','quick_target'), help='仅按 PAL，不含运动。当日用“今日计划”计算后会覆盖得更精确。'):
            profile = UserProfile(
                sex=str(side['sex']), age=int(side['age']), height_cm=float(side['height_cm']), weight_kg=float(side['weight_kg']),
                body_fat_pct=float(side['body_fat_pct']) if side['body_fat_pct'] is not None else None, baseline_pal=float(side['baseline_pal']),
                protein_g_per_kg_bw=float(side['protein_per_kg_bw']), fat_g_per_kg_bw=float(side['fat_per_kg_bw']),
                deficit=float(side['deficit']), min_deficit=float(side['min_def']), max_deficit=float(side['max_def']),
            )
            bmr = calc_bmr(profile)
            ffm = ffm_from_bf(profile.weight_kg, profile.body_fat_pct)
            tdee_no_ex = bmr * float(side['baseline_pal'])
            target_kcal = tdee_no_ex * (1 - float(side['deficit']))
            protein_g = float(side['protein_per_kg_bw']) * profile.weight_kg
            fat_g = float(side['fat_per_kg_bw']) * profile.weight_kg
            carb_g = max(0.0, (target_kcal - (protein_g*4 + fat_g*9)) / 4.0)
            ea = (target_kcal - 0.0) / max(ffm,1e-6)
            upsert_targets(today_str, {
                'target_kcal': round(target_kcal,0), 'protein_g': round(protein_g,0), 'fat_g': round(fat_g,0), 'carb_g': round(carb_g,0),
                'bmr': round(bmr,1), 'pal': round(float(side['baseline_pal']),2), 'tdee_used': round(tdee_no_ex,0), 'deficit': round(float(side['deficit']),3), 'ea': round(ea,1)
            }, notes='基线目标（Intake页快速生成，未包含运动）', ea_guard_applied=0, day_type='deficit')
            st.success('已生成今日基线目标！回到“今日计划”用完整运动数据再次计算覆盖。')
            dt_today = df_from_sql('SELECT * FROM daily_targets WHERE date = ?', (today_str,))

    totals = intake_sums(today_str)
    st.write('---')
    colA, colB, colC = st.columns(3)
    with colA:
        st.metric('今日已摄入(kcal)', int(totals['kcal']))
        st.caption(f"P {int(totals['protein_g'])}g · F {int(totals['fat_g'])}g · C {int(totals['carb_g'])}g")
    with colB:
        if len(dt_today)>0:
            tgt = dt_today.iloc[0]
            remain_k = max(0, int(float(tgt['target_kcal']) - totals['kcal']))
            remain_p = max(0, int(float(tgt['protein_g']) - totals['protein_g']))
            remain_f = max(0, int(float(tgt['fat_g']) - totals['fat_g']))
            remain_c = max(0, int(float(tgt['carb_g']) - totals['carb_g']))
            st.metric('剩余目标(kcal)', remain_k)
            st.caption(f"剩余：P {remain_p}g · F {remain_f}g · C {remain_c}g")
        else:
            st.info('尚无今日目标，剩余无法计算。')
    with colC:
        dm_today = df_from_sql('SELECT * FROM daily_metrics WHERE date = ?', (today_str,))
        if len(dm_today)>0 and 'load_index' in dm_today:
            li = float(dm_today.iloc[-1]['load_index'] or 0.0)
            ex_est = 3.5 * float(side['weight_kg']) * li / 200.0
            ffm = ffm_from_bf(float(side['weight_kg']), float(side['body_fat_pct']) if side['body_fat_pct'] is not None else None)
            ea_est = (totals['kcal'] - ex_est) / max(ffm,1e-6)
            st.metric('EA 估算 (kcal/kg FFM)', f"{ea_est:.1f}")
            st.caption('基于负荷指数的粗估：白天前期可能偏低，晚间进食后会上升。')
        else:
            st.caption('无今日负荷数据，EA 估算暂缺。')

    st.write('---')
    st.subheader('添加一条摄入', anchor=False)
    with st.form(key('intake','form')):
        now_h = datetime.now().hour
        default_tag = '早餐' if now_h<11 else ('午餐' if now_h<16 else ('晚餐' if now_h<22 else '加餐'))
        meal_tag = st.selectbox('餐别', ['早餐','午餐','晚餐','加餐','训练前','训练后','其他'], index=['早餐','午餐','晚餐','加餐','训练前','训练后','其他'].index(default_tag), key=key('intake','tag'), help='用于回顾餐次。')
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            kcal_in = st.number_input('热量(kcal)', 0.0, 3000.0, 0.0, 10.0, key=key('intake','k'))
        with c2:
            p_in = st.number_input('蛋白(g)', 0.0, 200.0, 0.0, 1.0, key=key('intake','p'))
        with c3:
            f_in = st.number_input('脂肪(g)', 0.0, 150.0, 0.0, 1.0, key=key('intake','f'))
        with c4:
            c_in = st.number_input('碳水(g)', 0.0, 500.0, 0.0, 1.0, key=key('intake','c'))
        note_in = st.text_input('备注(可选)', key=key('intake','note'), help='如“米饭+鸡胸+西兰花”。')
        col_btn_add, col_btn_undo = st.columns(2)
        add_ok = col_btn_add.form_submit_button('添加记录', type='primary', help='保存到数据库。')
        undo_ok = col_btn_undo.form_submit_button('撤销上一条', help='删除今天最新一条。')

        if add_ok:
            kcal_final = float(kcal_in)
            kcal_from_macros = float(p_in)*4 + float(f_in)*9 + float(c_in)*4
            if kcal_final <= 0 and kcal_from_macros>0:
                kcal_final = kcal_from_macros
            if kcal_final>0 and kcal_from_macros>0 and abs(kcal_final - kcal_from_macros) > 80:
                note_in = (note_in + ' | kcal与宏不一致(已按kcal记录)').strip()
            add_intake_row(today_str, str(meal_tag), kcal_final, float(p_in), float(f_in), float(c_in), str(note_in))
            st.success('已添加！')
        if undo_ok:
            ok = delete_last_intake_today(today_str)
            st.success('已撤销上一条。' if ok else '今天还没有可撤销的记录。')

    logs = fetch_intake_today(today_str)
    if len(logs)>0:
        st.dataframe(logs, width='stretch')
    else:
        st.caption('今天还没有记录。')

    if len(dt_today)>0:
        st.write('---')
        st.subheader('下一餐建议', anchor=False)
        mode = st.selectbox('建议模式', ['均衡补齐','训练前/后高碳'], index=0, key=key('intake','mode'), help='训练日前后可选高碳。')
        tgt = dt_today.iloc[0]
        remain_p = max(0.0, float(tgt['protein_g']) - totals['protein_g'])
        remain_f = max(0.0, float(tgt['fat_g']) - totals['fat_g'])
        remain_c = max(0.0, float(tgt['carb_g']) - totals['carb_g'])
        if mode=='均衡补齐':
            rec_p = max(min(remain_p, 50.0), 25.0)
            rec_f = max(min(remain_f, 25.0), 10.0)
            rec_c = max(min(remain_c*0.5, 150.0), 40.0)
        else:
            rec_p = max(min(remain_p, 40.0), 25.0)
            rec_f = max(min(remain_f, 15.0), 5.0)
            rec_c = max(min(max(remain_c*0.6, 0.8*float(side['weight_kg'])), 200.0), 60.0)
        rec_k = rec_p*4 + rec_f*9 + rec_c*4
        colx, coly, colz, colw = st.columns(4)
        colx.metric('建议蛋白(g)', int(rec_p))
        coly.metric('建议脂肪(g)', int(rec_f))
        colz.metric('建议碳水(g)', int(rec_c))
        colw.metric('建议热量(kcal)', int(rec_k))

