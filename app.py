# -*- coding: utf-8 -*-
from __future__ import annotations
import pandas as pd
import streamlit as st
from macrocoach_v2.settings import APP_TITLE, APP_ICON, configure_matplotlib_fonts, DB_PATH
from macrocoach_v2.data.db import init_db, ensure_intake_table
from macrocoach_v2.ui.sidebar import render_sidebar
from macrocoach_v2.ui.tabs_plan import render_tab_plan
from macrocoach_v2.ui.tabs_intake import render_tab_intake
from macrocoach_v2.ui.tabs_manual import render_tab_manual
from macrocoach_v2.ui.tabs_report import render_tab_report
from macrocoach_v2.ui.tabs_import_export import render_tab_import_export
from macrocoach_v2.ui.tabs_scheduler import render_tab_scheduler

def _init_session_defaults():
    ss = st.session_state
    ss.setdefault('t2_load', 1400)
    ss.setdefault('t2_w', 88.2)
    ss.setdefault('t2_steps', 8000)
    ss.setdefault('t2_ex', 120)
    ss.setdefault('t2_sleep', 7.5)
    ss.setdefault('t2_fatigue', 4)
    ss.setdefault('t2_perf', 0.0)

def main():
    st.set_page_config(page_title=APP_TITLE, page_icon=APP_ICON, layout='wide')
    configure_matplotlib_fonts()
    pd.set_option('future.no_silent_downcasting', True)
    st.title(APP_TITLE)
    init_db(); ensure_intake_table(); _init_session_defaults()
    side = render_sidebar()
    T1, T5, T2, T3, T6, T4 = st.tabs(['📅 今日计划', '🍽️ 实时摄入', '📝 手动录入（日常指标）', '📈 报告与曲线（交互）', '📆 周期调度', '📤 导入/导出'])
    with T1: render_tab_plan(side)
    with T5: render_tab_intake(side)
    with T2: render_tab_manual(side)
    with T3: render_tab_report(side)
    with T6: render_tab_scheduler(side)
    with T4: render_tab_import_export(DB_PATH)
    st.caption('提示：若按 1% BW/week 调速，但因 EA 守门而不变，说明当日运动+FFM 要求的最低摄入更高——已在“🧮 代谢/负荷”区域列出对比。')

if __name__ == '__main__':
    main()
