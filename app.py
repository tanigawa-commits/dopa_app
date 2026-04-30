import streamlit as st
import pandas as pd
from datetime import datetime, date, timedelta
from streamlit_gsheets import GSheetsConnection
import hashlib
import time
import calendar

# --- 1. アプリ設定 ---
st.set_page_config(page_title="Dopamine Tracker", layout="wide")
conn = st.connection("gsheets", type=GSheetsConnection)

SECRET_AUTH_CODE = "feelist2026" 

# デザインCSS（ボタンを表のセルに見せかける魔法のCSS）
st.markdown("""
    <style>
    /* 記録画面のカード */
    .status-card {
        border: 1px solid #e6e9ef; border-radius: 15px; padding: 15px; text-align: center;
        background-color: white; margin-bottom: 10px;
    }
    .star-display { font-size: 24px; letter-spacing: 2px; margin: 5px 0; font-family: monospace; }

    /* 【核心】カレンダー行を250pxに固定して中央寄せ */
    div[data-testid="stHorizontalBlock"]:has(button[key*="calbtn_"]) {
        max-width: 250px !important;
        margin: 0 auto !important;
        gap: 0px !important; /* 隙間をゼロに */
    }

    /* 各セル（カラム）を35pxに固定 */
    div[data-testid="stHorizontalBlock"]:has(button[key*="calbtn_"]) div[data-testid="column"] {
        flex: 0 0 35px !important;
        min-width: 35px !important;
        padding: 0px !important;
    }

    /* ボタンを表のセルのように整形 */
    div[data-testid="stHorizontalBlock"] button[key*="calbtn_"] {
        padding: 0px !important;
        margin: 0px !important;
        font-size: 11px !important;
        min-height: 35px !important;
        height: 45px !important; /* 少し縦長にして青丸スペースを確保 */
        width: 35px !important;
        border-radius: 0px !important; /* 四角くする */
        border: 0.5px solid #eee !important;
        background-color: white !important;
        display: flex !important;
        flex-direction: column !important;
        justify-content: center !important;
        line-height: 1.2 !important;
    }

    /* 曜日ヘッダーも幅を合わせる */
    .cal-header-row {
        display: flex;
        justify-content: center;
        max-width: 250px;
        margin: 0 auto;
        border-bottom: 1px solid #eee;
    }
    .cal-header-cell {
        width: 35px;
        text-align: center;
        font-size: 12px;
        font-weight: bold;
        color: #666;
        padding: 5px 0;
    }
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
    if 'cal_sel_date' not in st.session_state: st.session_state.cal_sel_date = str(date.today())

    # --- 認証 ---
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

    tab1, tab2, tab3, tab4 = st.tabs(["記録登録", "ランキング", "履歴カレンダー", "設定"])

    # --- タブ1: 記録 ---
    with tab1:
        pts = pd.to_numeric(user_records['points'], errors='coerce').fillna(0).sum() if not user_records.empty else 0
        st.write(f"### 累計: {pts:g} pt")
        target_date = st.date_input("登録日", value=date.today())
        @st.fragment
        def record_ui():
            col1, col2 = st.columns(2)
            v = st.session_state.form_version
            with col1: sel_inv = [i for i in INVESTMENT_ITEMS if st.checkbox(i, key=f"inv_{i}_{v}")]
            with col2: sel_debt = [i for i in DEBT_ITEMS if st.checkbox(i, key=f"debt_{i}_{v}")]
            day_pts = len(sel_inv) - len(sel_debt)
            st.metric("本日のポイント", f"{day_pts:+d}")
            if st.button("登録する", type="primary", use_container_width=True):
                db = conn.read(worksheet="Records", ttl="0s").astype(str)
                new_row = pd.DataFrame([{"real_name": current_emp_id, "date": str(target_date), "points": str(day_pts), "investment_items": ", ".join(sel_inv), "debt_items": ", ".join(sel_debt)}])
                conn.update(worksheet="Records", data=pd.concat([db, new_row]).reset_index(drop=True).astype(str))
                st.session_state.form_version += 1
                st.cache_data.clear(); st.balloons(); st.rerun()
        record_ui()

    # --- タブ3: マイデータ（新・押せるコンパクトカレンダー） ---
    with tab3:
        st.subheader("🗓 履歴カレンダー")
        
        # 月の管理
        if 'cal_year' not in st.session_state:
            st.session_state.cal_year, st.session_state.cal_month = date.today().year, date.today().month
        
        # 前月・次月切り替え
        c1, c2, c3 = st.columns([1, 2, 1])
        with c1:
            if st.button("⬅️", key="prev_m"):
                st.session_state.cal_month -= 1
                if st.session_state.cal_month == 0: st.session_state.cal_month, st.session_state.cal_year = 12, st.session_state.cal_year - 1
                st.rerun()
        with c2: st.markdown(f"<p style='text-align:center; font-weight:bold; margin:0;'>{st.session_state.cal_year}年 {st.session_state.cal_month}月</p>", unsafe_allow_html=True)
        with c3:
            if st.button("➡️", key="next_m"):
                st.session_state.cal_month += 1
                if st.session_state.cal_month == 13: st.session_state.cal_month, st.session_state.cal_year = 1, st.session_state.cal_year + 1
                st.rerun()

        # 曜日ヘッダー
        st.markdown("""<div class='cal-header-row'>
            <div class='cal-header-cell'>月</div><div class='cal-header-cell'>火</div><div class='cal-header-cell'>水</div>
            <div class='cal-header-cell'>木</div><div class='cal-header-cell'>金</div><div class='cal-header-cell'>土</div><div class='cal-header-cell'>日</div>
            </div>""", unsafe_allow_html=True)
        
        # カレンダーボタンの生成
        cal = calendar.monthcalendar(st.session_state.cal_year, st.session_state.cal_month)
        recorded_dates = user_records['date'].unique().tolist() if not user_records.empty else []
        
        for week in cal:
            cols = st.columns(7)
            for i, day in enumerate(week):
                if day == 0:
                    cols[i].write("") # 空白
                else:
                    d_str = f"{st.session_state.cal_year}-{st.session_state.cal_month:02d}-{day:02d}"
                    has_data = d_str in recorded_dates
                    label = f"{day}\n🔵" if has_data else f"{day}"
                    
                    # セル（ボタン）を配置。クリックでその日の日付をセッションに保存
                    if cols[i].button(label, key=f"calbtn_{d_str}"):
                        st.session_state.cal_sel_date = d_str

        # 選択された日の詳細表示
        st.divider()
        sel_d = st.session_state.cal_sel_date
        det = user_records[user_records['date'] == sel_d]
        if not det.empty:
            d = det.iloc[0]
            st.info(f"📅 {sel_d} の記録\n\n🟢 投資: {display_format(d['investment_items'])}\n\n🔴 借金: {display_format(d['debt_items'])}")
        else:
            st.write(f"📅 {sel_d} の記録はありません。日付をクリックしてください。")

    with tab2: st.write("ランキングエリア")
    with tab4: st.button("ログアウト", on_click=lambda: st.session_state.update({"authenticated": False}))

if __name__ == "__main__":
    main()
