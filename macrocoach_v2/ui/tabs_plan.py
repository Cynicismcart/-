# -*- coding: utf-8 -*-
from __future__ import annotations
from datetime import date
from typing import List
import streamlit as st
from ..domain.models import UserProfile, ActivityBlock, PIDConfig
from ..services.planner import plan_day, predict_next_day
from ..data.db import df_from_sql, upsert_metrics, upsert_targets
from .keys import key

def render_tab_plan(side: dict) -> None:
    # === Calendar (start) [forced] ===
    import datetime as _dt
    if "selected_date" not in st.session_state:
        st.session_state["selected_date"] = _dt.date.today()
    cur_date = st.session_state["selected_date"]
    cur_date_str = cur_date.isoformat()
    today_str = cur_date_str
    with st.container(border=True):
        c1, c2 = st.columns([3,1])
        st.session_state["selected_date"] = c1.date_input("选择日期", value=cur_date, key=key("tabs_plan","date"))
        c2.button("今天", key=key("tabs_plan","today_btn"), on_click=lambda: st.session_state.update(selected_date=_dt.date.today()))
    cur_date = st.session_state["selected_date"]
    cur_date_str = cur_date.isoformat()
    today_str = cur_date_str
    # === Calendar (end) ===

    with st.form(key('t1','form')):
        st.subheader('当日运动量', anchor=False)
        c1, c2, c3 = st.columns(3)
        with c1:
            bad_min = st.number_input('羽毛球(分钟)', 0, 300, 60, 10, key=key('t1','bad_min'), help='今天打了多长时间羽毛球。')
            bad_int = st.selectbox('羽毛球强度', ['low','moderate','high'], index=1, key=key('t1','bad_int'), help='主观强度。')
        with c2:
            lift_min = st.number_input('力量(分钟)', 0, 240, 55, 5, key=key('t1','lift_min'), help='包含热身与正式训练时间。')
            lift_int = st.selectbox('力量强度', ['low','moderate','high'], index=1, key=key('t1','lift_int'), help='按主观费力程度选择。')
        with c3:
            car_min = st.number_input('有氧(分钟)', 0, 240, 0, 5, key=key('t1','car_min'), help='跑步/骑行等。')
            car_int = st.selectbox('有氧强度', ['low','moderate','high'], index=1, key=key('t1','car_int'), help='主观强度。')

        st.subheader('主观/睡眠/晨重', anchor=False)
        c4, c5, c6, c7 = st.columns(4)
        with c4:
            fatigue = st.slider('疲劳(1-10)', 1, 10, 4, key=key('t1','fatigue'), help='1=精力满满；8–10=非常疲惫。')
        with c5:
            sleep_h = st.slider('昨夜睡眠(h)', 3.0, 10.0, 7.5, 0.5, key=key('t1','sleep'), help='<6.5 小时会触发“降赤字/加碳”保护。')
        with c6:
            perf_pct = st.slider('近期表现变化(%)', -20, 20, 0, key=key('t1','perf'), help='建议填 -10%~+10%。-5≈比平时差一点；0=正常；+5≈比平时好一点。不确定就 0。')
        with c7:
            today_w = st.number_input('今日晨重(kg，可选)', 0.0, 250.0, float(side['weight_kg']), 0.1, key=key('t1','w'), help='起床后称重，用于趋势与自动调赤字。')

        apply_sug = st.checkbox('一键应用智能建议（降赤字/加碳）', value=False, key=key('t1','apply'), help='根据疲劳/睡眠/表现快速调整。')

        col_btn1, col_btn2 = st.columns(2)
        submit_sync = col_btn1.form_submit_button('仅同步负荷到“手动录入”', help='把根据分钟+强度估算的负荷同步到“手动录入”页。')
        submit_calc = col_btn2.form_submit_button('计算 / 保存今日计划', type='primary', help='立刻计算当日目标并保存到数据库。')

        if submit_sync:
            acts_tmp: List[ActivityBlock] = []
            if bad_min>0: acts_tmp.append(ActivityBlock('badminton', bad_min, bad_int))
            if lift_min>0: acts_tmp.append(ActivityBlock('strength',  lift_min, lift_int))
            if car_min>0: acts_tmp.append(ActivityBlock('cardio',    car_min, car_int))
            from ..domain.calcs import calc_daily_exercise_kcal
            _, load_tmp = calc_daily_exercise_kcal(float(side['weight_kg']), acts_tmp)
            st.session_state['t2_load'] = round(load_tmp,0)
            st.success(f'已同步训练负荷到“手动录入”：{round(load_tmp,0)}')

        if submit_calc:
            dm_hist = df_from_sql('SELECT * FROM daily_metrics ORDER BY date ASC')
            profile = UserProfile(
                sex=str(side['sex']), age=int(side['age']), height_cm=float(side['height_cm']), weight_kg=float(side['weight_kg']),
                body_fat_pct=float(side['body_fat_pct']) if side['body_fat_pct'] is not None else None, baseline_pal=float(side['baseline_pal']),
                protein_g_per_kg_bw=float(side['protein_per_kg_bw']), fat_g_per_kg_bw=float(side['fat_per_kg_bw']),
                deficit=float(side['deficit']), min_deficit=float(side['min_def']), max_deficit=float(side['max_def']),
                carb_periodization=True,
            )
            acts: List[ActivityBlock] = []
            if bad_min>0: acts.append(ActivityBlock('badminton', bad_min, bad_int))
            if lift_min>0: acts.append(ActivityBlock('strength',  lift_min, lift_int))
            if car_min>0: acts.append(ActivityBlock('cardio',    car_min, car_int))

            current_w = float(today_w) if float(today_w) > 0 else float(side['weight_kg'])
            target_loss_week_kg = current_w * (float(side['loss_rate_pct'])/100.0)

            res = plan_day(
                profile, acts, int(side['steps']) if side['steps']>0 else None,
                bool(side['auto_mode']), float(target_loss_week_kg),
                PIDConfig(Kp=float(side['Kp']), Ki=float(side['Ki']), Kd=float(side['Kd']), integral_cap=float(side['Icap'])),
                int(fatigue), float(sleep_h), float(perf_pct),
                bool(apply_sug), dm_hist, float(today_w) if today_w>0 else None,
                protein_basis='FFM' if side['protein_basis']=='按FFM' else 'BW',
                protein_per_kg_ffm=float(side['protein_per_kg_ffm']),
                ea_min=float(side['ea_min']), ea_pref=float(side['ea_pref']),
                training_day_carb_bump_g_per_kg=float(side['training_bump']),
                training_load_threshold=float(side['training_threshold'])
            )

            st.session_state['t2_load']    = res['load_index']
            st.session_state['t2_w']       = float(today_w) if today_w>0 else float(side['weight_kg'])
            st.session_state['t2_steps']   = int(side['steps'])
            st.session_state['t2_ex']      = int(bad_min + lift_min + car_min)
            st.session_state['t2_sleep']   = float(sleep_h)
            st.session_state['t2_fatigue'] = int(fatigue)
            st.session_state['t2_perf']    = float(perf_pct)

            st.success('已计算今日目标，并写入数据库！')
            colA, colB, colC = st.columns(3)
            with colA:
                st.subheader('📊 今日目标')
                st.metric('目标热量 (kcal)', res['target_kcal'])
                st.write(f"蛋白: **{res['protein_g']} g**  |  脂肪: **{res['fat_g']} g**  |  碳水: **{res['carb_g']} g**")
            with colB:
                st.subheader('🧮 代谢/负荷')
                st.write(f"BMR: {res['bmr']}  |  PAL: {res['pal']}")
                st.write(f"运动消耗: {res['exercise_kcal']} kcal  |  训练负荷: {res['load_index']}")
                st.write(f"TDEE: **{res['tdee_used']}**  |  赤字: **{res['deficit']}**")
                st.caption(f"按赤字摄入(未应用EA)：{res['intended_kcal']} kcal | EA最低摄入：{res['ea_floor_kcal']} kcal | 最终目标：{res['target_kcal']} kcal（取两者较高≤TDEE）")
            with colC:
                st.subheader('🛡️ 安全护栏')
                st.write(f"FFM: {res['ffm']} kg  |  EA: **{res['ea']}** kcal/kg FFM")
                st.write('训练日：' + ('是 ✅' if res['is_training_day'] else '否'))
                if res['ea'] < float(side['ea_min']):
                    st.error(f'EA 低于 {int(side["ea_min"])}：已自动提高摄入/降低赤字')
                else:
                    st.success(f'EA ≥ {int(side["ea_min"])}')

            st.subheader('🧠 智能建议 & 动作')
            if len(res['suggestions'])==0:
                st.caption('暂无建议')
            else:
                for s in res['suggestions']:
                    st.write('- ', s)

            today_str = cur_date_str
            upsert_metrics(today_str, {
                'weight': float(today_w) if today_w>0 else float(side['weight_kg']), 'steps': int(side['steps']), 'exercise_min': int(bad_min+lift_min+car_min),
                'sleep_h': float(sleep_h), 'fatigue': int(fatigue), 'perf_pct': float(perf_pct),
                'avg_hr': None, 'max_hr': None, 'load_index': float(res['load_index']),
            })
            upsert_targets(today_str, {
                **{k:res[k] for k in ['target_kcal','protein_g','fat_g','carb_g','bmr','pal','tdee_used','deficit','ea']}
            }, notes=('；'.join([str(x) for x in res['notes']]) if len(res['notes']) else ''), ea_guard_applied=1 if res['ea']<float(side['ea_min']) else 0, day_type=('deficit' if res['deficit']>0 else 'maintain'))

            dm_hist2 = df_from_sql('SELECT * FROM daily_metrics ORDER BY date ASC')
            if len(dm_hist2)>0:
                pred = predict_next_day(dm_hist2)
                st.subheader('🔮 明日预测')
                st.write(f"训练建议：**{pred['train_band']}** 强度  |  赤字建议：**{pred['deficit_band']}** 档")
                st.caption(pred['note'])

