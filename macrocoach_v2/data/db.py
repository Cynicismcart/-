# -*- coding: utf-8 -*-
from __future__ import annotations
from typing import Iterable, List, Optional, Dict
import sqlite3
import pandas as pd
import streamlit as st
from ..settings import DB_PATH

SCHEMA = {
    'daily_metrics': """
    CREATE TABLE IF NOT EXISTS daily_metrics(
      date TEXT PRIMARY KEY,
      weight REAL, steps INTEGER, exercise_min REAL,
      sleep_h REAL, fatigue INTEGER, perf_pct REAL,
      avg_hr REAL, max_hr REAL, load_index REAL
    )
    """,
    'daily_targets': """
    CREATE TABLE IF NOT EXISTS daily_targets(
      date TEXT PRIMARY KEY,
      target_kcal REAL, protein_g REAL, fat_g REAL, carb_g REAL,
      bmr REAL, pal REAL, tdee_used REAL, deficit REAL, ea REAL,
      ea_guard_applied INTEGER, notes TEXT,
      day_type TEXT
    )
    """,
    'intake_logs': """
    CREATE TABLE IF NOT EXISTS intake_logs(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      ts TEXT,
      date TEXT,
      meal_tag TEXT,
      kcal REAL,
      protein_g REAL,
      fat_g REAL,
      carb_g REAL,
      note TEXT
    )
    """,
    'weekly_volume': """
    CREATE TABLE IF NOT EXISTS weekly_volume(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      date TEXT,
      muscle_group TEXT,
      sets INTEGER
    )
    """
}

@st.cache_resource(show_spinner=False)
def get_conn() -> sqlite3.Connection:
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def init_db() -> None:
    conn = get_conn(); cur = conn.cursor()
    for sql in SCHEMA.values():
        cur.execute(sql)
    conn.commit()
    migrate_db()

def migrate_db() -> None:
    conn = get_conn(); cur = conn.cursor()
    def existing_cols(table: str) -> Iterable[str]:
        cur.execute(f"PRAGMA table_info({table})")
        return [row[1] for row in cur.fetchall()]
    need = {
        'daily_metrics': {
            'weight': 'REAL', 'steps': 'INTEGER', 'exercise_min': 'REAL',
            'sleep_h': 'REAL', 'fatigue': 'INTEGER', 'perf_pct': 'REAL',
            'avg_hr': 'REAL', 'max_hr': 'REAL', 'load_index': 'REAL',
        },
        'daily_targets': {
            'ea': 'REAL', 'ea_guard_applied': 'INTEGER', 'notes': 'TEXT', 'day_type':'TEXT',
        },
    }
    for table, cols in need.items():
        try:
            have = set(existing_cols(table))
        except Exception:
            continue
        for col, coltype in cols.items():
            if col not in have:
                try:
                    cur.execute(f"ALTER TABLE {table} ADD COLUMN {col} {coltype}")
                except Exception:
                    pass
    conn.commit()

def df_from_sql(query: str, params: tuple = ()) -> pd.DataFrame:
    try:
        return pd.read_sql_query(query, get_conn(), params=params)
    except Exception:
        return pd.DataFrame()

def execute(sql: str, params: tuple = ()) -> None:
    conn = get_conn(); cur = conn.cursor(); cur.execute(sql, params); conn.commit()

def executemany(sql: str, rows: List[tuple]) -> None:
    conn = get_conn(); cur = conn.cursor(); cur.executemany(sql, rows); conn.commit()

def upsert_metrics(d: str, data: Dict[str, Optional[float]]):
    execute("""
        INSERT OR REPLACE INTO daily_metrics
        (date,weight,steps,exercise_min,sleep_h,fatigue,perf_pct,avg_hr,max_hr,load_index)
        VALUES(?,?,?,?,?,?,?,?,?,?)
    """, (
        d, data.get('weight'), data.get('steps'), data.get('exercise_min'),
        data.get('sleep_h'), data.get('fatigue'), data.get('perf_pct'),
        data.get('avg_hr'), data.get('max_hr'), data.get('load_index'),
    ))

def upsert_targets(d: str, res: Dict[str, float], notes: str, ea_guard_applied: int, day_type: Optional[str] = None):
    execute("""
        INSERT OR REPLACE INTO daily_targets
        (date,target_kcal,protein_g,fat_g,carb_g,bmr,pal,tdee_used,deficit,ea,ea_guard_applied,notes,day_type)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (
        d, res['target_kcal'], res['protein_g'], res['fat_g'], res['carb_g'],
        res['bmr'], res['pal'], res['tdee_used'], res['deficit'], res['ea'],
        ea_guard_applied, notes, day_type
    ))

def ensure_intake_table():
    execute(SCHEMA['intake_logs'])

def add_intake_row(d: str, meal_tag: str, kcal: float, protein_g: float, fat_g: float, carb_g: float, note: str=''):
    import datetime as _dt
    ts = _dt.datetime.now().isoformat(timespec='seconds')
    execute("""
        INSERT INTO intake_logs(ts,date,meal_tag,kcal,protein_g,fat_g,carb_g,note)
        VALUES(?,?,?,?,?,?,?,?)
    """, (ts, d, meal_tag, float(kcal or 0.0), float(protein_g or 0.0), float(fat_g or 0.0), float(carb_g or 0.0), note or ''))
    # 记录活动日志用于撤销
    try:
        log_activity('add_intake', {'date': d})
    except Exception:
        pass

def fetch_intake_today(d: str) -> pd.DataFrame:
    return df_from_sql('SELECT * FROM intake_logs WHERE date=? ORDER BY ts ASC', (d,))

def intake_sums(d: str) -> Dict[str, float]:
    conn = get_conn(); cur = conn.cursor()
    cur.execute('SELECT COALESCE(SUM(kcal),0), COALESCE(SUM(protein_g),0), COALESCE(SUM(fat_g),0), COALESCE(SUM(carb_g),0) FROM intake_logs WHERE date=?', (d,))
    k,p,f,c = cur.fetchone()
    return {'kcal': float(k or 0.0), 'protein_g': float(p or 0.0), 'fat_g': float(f or 0.0), 'carb_g': float(c or 0.0)}

def delete_last_intake_today(d: str) -> bool:
    conn = get_conn(); cur = conn.cursor()
    cur.execute('SELECT id FROM intake_logs WHERE date=? ORDER BY ts DESC LIMIT 1', (d,))
    row = cur.fetchone()
    if not row: return False
    cur.execute('DELETE FROM intake_logs WHERE id=?', (row[0],))
    conn.commit()
    return True

def add_weekly_volume(d: str, group: str, sets: int):
    execute('INSERT INTO weekly_volume(date,muscle_group,sets) VALUES(?,?,?)', (d, group, int(sets)))

def volume_last_n_days(n: int = 7) -> pd.DataFrame:
    return df_from_sql('SELECT date,muscle_group,sets FROM weekly_volume WHERE date>=date("now", ?)', (f'-{n} day',))

def intake_aggregate_by_day() -> pd.DataFrame:
    df = df_from_sql('SELECT date, COALESCE(SUM(kcal),0) AS kcal, COALESCE(SUM(protein_g),0) AS protein_g FROM intake_logs GROUP BY date ORDER BY date')
    for col in ['kcal','protein_g']:
        if col in df:
            df[col] = pd.to_numeric(df[col], errors='coerce')
    return df


# === Added: activity_logs table (sqlite) ===
SCHEMA['activity_logs'] = """
CREATE TABLE IF NOT EXISTS activity_logs(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts TEXT DEFAULT (strftime('%Y-%m-%d %H:%M:%S','now')),
  action TEXT NOT NULL,
  payload TEXT NOT NULL
)
"""


# === Added: activity log helpers (sqlite) ===
import json as _json

def ensure_activity_table():
    execute(SCHEMA['activity_logs'])

def log_activity(action: str, payload: dict):
    ensure_activity_table()
    execute("INSERT INTO activity_logs(action,payload) VALUES(?,?)", (action, _json.dumps(payload, ensure_ascii=False)))

def fetch_activity_logs(limit: int = 50) -> pd.DataFrame:
    ensure_activity_table()
    return df_from_sql("SELECT id,ts,action,payload FROM activity_logs ORDER BY id DESC LIMIT ?", (int(limit),))

def undo_last(date_hint: Optional[str] = None) -> str:
    ensure_activity_table()
    conn = get_conn(); cur = conn.cursor()
    cur.execute("SELECT id, action, payload FROM activity_logs ORDER BY id DESC LIMIT 1")
    row = cur.fetchone()
    if not row:
        return "无可撤销的操作"
    log_id, action, payload = row[0], row[1], row[2]
    try:
        payload_obj = _json.loads(payload) if isinstance(payload, str) else (payload or {})
    except Exception:
        payload_obj = {}
    msg = ""
    if action == "add_intake":
        # 删除该日期的最近一条摄入记录
        d = payload_obj.get("date") or date_hint
        if d:
            ok = delete_last_intake_today(d)
            msg = "撤销成功：删除刚保存的摄入记录" if ok else "未找到可删除的摄入记录"
        else:
            msg = "缺少日期信息，无法撤销"
    else:
        msg = f"暂不支持撤销的操作类型：{action}"
    # 删除这条活动日志
    cur.execute("DELETE FROM activity_logs WHERE id=?", (log_id,))
    conn.commit()
    return msg
