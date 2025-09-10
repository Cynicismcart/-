# -*- coding: utf-8 -*-
from __future__ import annotations
from datetime import date
import streamlit as st
from ..data.db import upsert_metrics, add_weekly_volume
from .keys import key

def render_tab_manual(side: dict) -> None:
    # === Calendar (start) [forced] ===
    import datetime as _dt
    if "selected_date" not in st.session_state:
        st.session_state["selected_date"] = _dt.date.today()
    cur_date = st.session_state["selected_date"]
    cur_date_str = cur_date.isoformat()
    today_str = cur_date_str
    with st.container(border=True):
        c1, c2 = st.columns([3,1])
        st.session_state["selected_date"] = c1.date_input("选择日期", value=cur_date, key=key("tabs_manual","date"))
        c2.button("今天", key=key("tabs_manual","today_btn"), on_click=lambda: st.session_state.update(selected_date=_dt.date.today()))
    cur_date = st.session_state["selected_date"]
    cur_date_str = cur_date.isoformat()
    today_str = cur_date_str
    # === Calendar (end) ===

    st.subheader('每日关键指标（手动输入即可）', anchor=False)
    d = st.date_input('日期', value=date.today(), key=key('t2','date'), help='选择要录入的日期。')
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        w_in = st.number_input('晨重(kg)', 0.0, 250.0, float(st.session_state.get('t2_w', float(side['weight_kg']))), 0.1, key=key('t2','w'), help='起床后称重。')
        steps_in = st.number_input('步数', 0, 200000, int(st.session_state.get('t2_steps', 8000)), 500, key=key('t2','steps'), help='当天总步数。')
    with col2:
        ex_min = st.number_input('当日运动总分钟', 0, 600, int(st.session_state.get('t2_ex', 120)), 5, key=key('t2','ex'), help='力量+有氧总时长。')
        sleep_in = st.number_input('睡眠(h)', 0.0, 16.0, float(st.session_state.get('t2_sleep', 7.5)), 0.1, key=key('t2','sleep'), help='昨夜睡眠小时数。')
    with col3:
        fat_in = st.slider('疲劳(1-10)', 1, 10, int(st.session_state.get('t2_fatigue', 4)), key=key('t2','fatigue'), help='1=精力满满；8–10=非常疲惫。')
        perf_in = st.slider('表现变化(%)', -20.0, 20.0, float(st.session_state.get('t2_perf', 0.0)), step=1.0, key=key('t2','perf'), help='0=正常；正数=更好；负数=更差。可不每天填。')
    with col4:
        load_in = st.number_input('训练负荷指数(MET*min)', 0, 5000, int(st.session_state.get('t2_load', 1400)), 50, key=key('t2','load'), help='在“今日计划”可一键同步到这里。')

    if st.button('保存到数据库', key=key('t2','save'), help='写入/覆盖该日期数据。'):
        upsert_metrics(d.isoformat(), {
            'weight': float(w_in), 'steps': int(steps_in), 'exercise_min': int(ex_min),
            'sleep_h': float(sleep_in), 'fatigue': int(fat_in), 'perf_pct': float(perf_in),
            'avg_hr': None, 'max_hr': None, 'load_index': float(load_in),
        })
        st.success('已保存！可前往“报告与曲线”查看趋势。')

    st.write('---')
    st.subheader('（可选）记录每肌群周组数', anchor=False)
    vcol1, vcol2, vcol3 = st.columns([2,2,1])
    with vcol1:
        m = st.selectbox('肌群', ['胸','背','腿','肩','臂','臀','核心','小腿'], index=0, key=key('vol','mg'), help='用于训练量监控。')
    with vcol2:
        sets = st.number_input('本次增加组数', 0, 30, 6, 1, key=key('vol','sets'), help='把一次训练的组数记下来。')
    with vcol3:
        if st.button('记一笔', key=key('vol','save'), help='追加到 weekly_volume 表。'):
            add_weekly_volume(d.isoformat(), m, int(sets))
            st.success('已记录。')

