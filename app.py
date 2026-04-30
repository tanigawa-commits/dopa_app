import streamlit as st
import pandas as pd
from datetime import datetime, date, timedelta
from streamlit_gsheets import GSheetsConnection
import hashlib
import time
import calendar

# --- 1. アプリ設定 ---
st.set_page_config(page_title="Dopamine Tracker", layout="centered") # 画面を中央寄せに固定
conn = st.connection("gsheets", type=GSheetsConnection)

SECRET_AUTH_CODE = "feelist2026" 

# デザインCSS
st.markdown("""
    <style>
    .status-card {
        border: 1px solid #e6e9ef; border-radius: 15px; padding: 15px; text-align: center;
        background-color: white; margin-bottom: 10px;
    }
    .star-display { font-size: 26px; letter-spacing: 2px; margin: 5px 0; font-family: monospace; }
    /* 記録マップ（カレンダー表）のスタイル */
    .cal-map { font-family: monospace; font-size: 14px; border-collapse: collapse; margin: 0 auto; }
    .cal-map td { padding: 5px 8px; text-align: center; border: 1px solid #eee; }
    .has-data { color: #0066cc; font-weight: bold; }
    .no-data { color: #ccc; }
    </style>
    """, unsafe_allow_html=True)

# ヘルパー関数
def make_hash(password): return hashlib.sha256(str.encode(password)).hexdigest()
def clean_string_strictly(x):
    s = str(x).strip()
    if '.' in s: s = s.split('.')[0]
    if s.lower() in ["nan", "none", "", "null"]: return ""
    return s
def display_format(val):
    s = clean_string_strictly(val)
    return s if s != "" else "－"
def normalize_id_strictly(x):
    s = clean_string_strictly(x)
    if s == "": return ""
    try: return str(int(float(s))).zfill(4)
    except: return s.zfill(4)

@st.cache_data(ttl=60)
def load_data_cached(sheet_name):
    try:
        df = conn.read(worksheet=sheet_name, ttl="1m")
        if df.empty: return pd.DataFrame()
        df = df.astype(str)
        if sheet_name == "UserMaster":
            df["emp_id"] = df["emp_id"].apply(normalize_id_strictly)
            df["nickname"] = df["nickname"].apply(clean_string_strictly)
        else:
            df["real_name"] = df["real_name"].apply(normalize_id_strictly)
            if "points" in df.columns: df["points"] = df["points"].apply(clean_string_strictly)
        return df
    except: return pd.DataFrame()

# 項目リスト
INVESTMENT_ITEMS = ["料理", "掃除", "睡眠が8時間以上", "湯舟に入浴、サウナ", "朝10分前に出社", "身体を動かした", "健康的な食生活", "洗濯", "ニュースをみる", "学習", "読書", "創作", "音楽", "挨拶", "感謝", "家族との時間", "植物", "ペット", "挑戦"]
DEBT_ITEMS = ["外食オンリー", "掃除なし", "睡眠不足", "シャワーのみ", "朝ギリギリ", "1日ゴロゴロ", "ギルティ食", "アルコール", "タバコ", "スマホ2h+", "映像2h+", "SNS2h+", "ゲーム2h+", "ソシャゲ起動", "ゲーム課金", "ギャンブル", "無駄遣い", "独り言", "倫理欠如"]

def main():
    if 'authenticated' not in st.session_state: st.session_state.authenticated = False
    if 'last_logged_id' not in st.session_state: st.session_state.last_logged_id = ""
    if 'form_version' not in st.session_state: st.session_state.form_version = 0

    if not st.session_state.authenticated:
        st.title("🔒 Dopamine Tracker")
        target_id = st.text_input("社員番号(4桁)", value=st.session_state.last_logged_id, max_chars=4)
        if target_id:
            master = load_data_cached("UserMaster")
            target_id_norm = normalize_id_strictly(target_id)
            user_row = master[master['emp_id'] == target_id_norm] if not master.empty else pd.DataFrame()
            if not user_row.empty:
                stored_hash = user_row.iloc[0].get('password_hash', "")
                if not stored_hash or str(stored_hash).lower() == "nan":
                    with st.form("reg"):
                        ac, np, npc = st.text_input("合言葉", type="password"), st.text_input("PW", type="password"), st.text_input("確認", type="password")
                        if st.form_submit_button("登録"):
                            if ac == SECRET_AUTH_CODE and np == npc:
                                cm = conn.read(worksheet="UserMaster", ttl="0s").astype(str)
                                idx = cm[cm['emp_id'].apply(normalize_id_strictly) == target_id_norm].index[0]
                                cm.at[idx, 'password_hash'], cm.at[idx, 'nickname'] = str(make_hash(np)), target_id_norm
                                conn.update(worksheet="UserMaster", data=cm.astype(str))
                                st.session_state.authenticated, st.session_state.current_user, st.session_state.last_logged_id = True, target_id_norm, target_id_norm
                                st.cache_data.clear(); st.rerun()
                else:
                    with st.form("login"):
                        ip = st.text_input("パスワード", type="password")
                        if st.form_submit_button("ログイン"):
                            if make_hash(ip) == stored_hash:
                                st.session_state.authenticated, st.session_state.current_user, st.session_state.last_logged_id = True, target_id_norm, target_id_norm
                                st.cache_data.clear(); st.rerun()
        st.stop()

    current_emp_id = st.session_state.current_user
    all_records = load_data_cached("Records")
    user_records = all_records[all_records['real_name'] == current_emp_id] if not all_records.empty else pd.DataFrame()

    tab1, tab2, tab3, tab4 = st.tabs(["今日の記録", "ランキング", "マイデータ", "設定"])

    # --- タブ1: 今日の記録 ---
    with tab1:
        pts = pd.to_numeric(user_records['points'], errors='coerce').fillna(0).sum() if not user_records.empty else 0
        st.write(f"### 累計ポイント: {pts:g}")
        target_date = st.date_input("対象日（７日前まで遡れます）", value=date.today())
        
        @st.fragment
        def record_ui():
            col1, col2 = st.columns(2)
            v = st.session_state.form_version
            with col1:
                st.markdown("#### 🟢 投資型")
                sel_inv = [i for i in INVESTMENT_ITEMS if st.checkbox(i, key=f"inv_{i}_{v}")]
            with col2:
                st.markdown("#### 🔴 借金型")
                sel_debt = [i for i in DEBT_ITEMS if st.checkbox(i, key=f"debt_{i}_{v}")]
            
            n_inv, n_debt = len(sel_inv), len(sel_debt)
            inv_s, debt_s = "★" * min(n_inv, 10) + "☆" * max(0, 10 - n_inv), "★" * min(n_debt, 10) + "☆" * max(0, 10 - n_debt)
            
            c1, c2 = st.columns(2)
            c1.markdown(f"""<div class="status-card"><div class="status-label">投資型</div><div class="star-display" style="color:#00cc99;">{inv_s}</div><div>{n_inv}個</div></div>""", unsafe_allow_html=True)
            c2.markdown(f"""<div class="status-card"><div class="status-label">借金型</div><div class="star-display" style="color:#ff4b4b;">{debt_s}</div><div>{n_debt}個</div></div>""", unsafe_allow_html=True)
            
            if st.button("登録する", type="primary", use_container_width=True):
                db = conn.read(worksheet="Records", ttl="0s").astype(str)
                new_row = pd.DataFrame([{"real_name": current_emp_id, "date": str(target_date), "points": str(n_inv - n_debt), "investment_items": ", ".join(sel_inv), "debt_items": ", ".join(sel_debt)}])
                conn.update(worksheet="Records", data=pd.concat([db, new_row]).reset_index(drop=True).astype(str))
                st.session_state.form_version += 1
                st.cache_data.clear(); st.balloons(); st.rerun()
        record_ui()

    # --- タブ3: マイデータ（新カレンダー方式） ---
    with tab3:
        st.subheader("🗓 履歴の確認")
        
        # 1. 閲覧する日を専用パーツで選択（これが「別のパーツ」）
        sel_date = st.date_input("確認したい日を選択してください", value=date.today())
        
        # 2. 記録状況の視覚化（今月のどこに記録があるかを表で表示）
        st.write("▼ 今月の記録状況（🔵＝記録あり）")
        year, month = sel_date.year, sel_date.month
        cal = calendar.monthcalendar(year, month)
        recorded_dates = user_records['date'].unique().tolist() if not user_records.empty else []
        
        html = "<table class='cal-map'><tr><td>月</td><td>火</td><td>水</td><td>木</td><td>金</td><td>土</td><td>日</td></tr>"
        for week in cal:
            html += "<tr>"
            for day in week:
                if day == 0:
                    html += "<td></td>"
                else:
                    d_str = f"{year}-{month:02d}-{day:02d}"
                    dot = "🔵" if d_str in recorded_dates else ""
                    html += f"<td>{day}<br>{dot}</td>"
            html += "</tr>"
        html += "</table>"
        st.markdown(html, unsafe_allow_html=True)
        
        # 3. 選択された日の詳細を表示
        st.divider()
        det = user_records[user_records['date'] == str(sel_date)]
        if not det.empty:
            d = det.iloc[0]
            st.info(f"📅 {sel_date} の詳細\n\n🟢 投資: {display_format(d['investment_items'])}\n\n🔴 借金: {display_format(d['debt_items'])}")
        else:
            st.warning(f"📅 {sel_date} の記録はありません。")

    with tab2: st.write("ランキング表示エリア")
    with tab4: st.button("ログアウト", on_click=lambda: st.session_state.update({"authenticated": False}))

if __name__ == "__main__":
    main()
