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

# 【秘密の合言葉】
SECRET_AUTH_CODE = "feelist2026" 

# デザインCSS（カレンダーの「列」そのものを強制的に32pxに固定する）
st.markdown("""
    <style>
    /* 1. 記録画面のステータスカード（PCで2列、星表示を保護） */
    .status-card {
        border: 1px solid #e6e9ef; border-radius: 15px; padding: 15px; text-align: center;
        background-color: white; margin-bottom: 10px;
    }
    .star-display { font-size: 26px; letter-spacing: 2px; margin: 5px 0; font-family: monospace; }
    .status-label { font-size: 16px; font-weight: bold; margin-bottom: 5px; }

    /* 2. 【核心】7列並んでいる行（曜日・日付ボタン）だけを強制的に縮小して中央寄せ */
    /* 曜日ヘッダーと日付ボタン行の両方に適用 */
    div[data-testid="stHorizontalBlock"]:has(div[data-testid="column"]:nth-child(7)) {
        display: flex !important;
        flex-direction: row !important;
        justify-content: center !important; /* 中央寄せ */
        max-width: 250px !important;       /* 行全体の最大幅を250pxに制限 */
        margin: 0 auto !important;         /* 画面中央に配置 */
        gap: 2px !important;               /* 列同士の隙間を2pxに */
    }

    /* 7列ある行の中の各「列(Column)」を強制的に32px幅にする */
    div[data-testid="stHorizontalBlock"]:has(div[data-testid="column"]:nth-child(7)) div[data-testid="column"] {
        flex: 0 0 32px !important;
        width: 32px !important;
        min-width: 32px !important;
        max-width: 32px !important;
        padding: 0px !important;
        margin: 0px !important;
    }

    /* ボタン要素自体のサイズを32pxに固定し、余白を削り取る */
    div[data-testid="stHorizontalBlock"]:has(div:nth-child(7)) button {
        padding: 0px !important;
        margin: 0px !important;
        font-size: 10px !important;
        min-height: 32px !important;
        height: 32px !important;
        width: 32px !important;
        border-radius: 4px !important;
        display: flex !important;
        justify-content: center !important;
        align-items: center !important;
    }

    .cal-day-header { text-align: center; font-weight: bold; font-size: 10px; color: #666; width: 32px; }
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
DEBT_ITEMS = ["外食オンリー", "掃除なし", "睡眠不足", "シャワーのみ", "朝ギリギリ", "1日ゴロゴロ", "ギルティ食", "アルコール", "タバコ", "スマホ2h+", "映像2h+", "SNS2h+", "ゲーム2h+", "ソシャゲ", "課金", "ギャンブル", "無駄遣い", "独り言", "倫理欠如"]

# --- 2. メイン処理 ---
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
    master_data = load_data_cached("UserMaster")
    user_records = load_data_cached("Records")
    if not user_records.empty:
        user_records = user_records[user_records['real_name'] == current_emp_id]
    
    tab1, tab2, tab3, tab4 = st.tabs(["今日の記録", "ランキング", "マイデータ", "設定"])

    # --- 今日の記録 ---
    with tab1:
        pts = pd.to_numeric(user_records['points'], errors='coerce').fillna(0).sum() if not user_records.empty else 0
        st.write(f"### 累計ポイント: {pts:g}")
        target_date = st.date_input("対象日", value=date.today())
        
        @st.fragment
        def record_ui():
            col_inv, col_debt = st.columns(2)
            v = st.session_state.form_version
            with col_inv:
                sel_inv = [i for i in INVESTMENT_ITEMS if st.checkbox(i, key=f"inv_{i}_{v}")]
            with col_debt:
                sel_debt = [i for i in DEBT_ITEMS if st.checkbox(i, key=f"debt_{i}_{v}")]
            
            n_inv, n_debt = len(sel_inv), len(sel_debt)
            inv_s, debt_s = "★" * min(n_inv, 10) + "☆" * max(0, 10 - n_inv), "★" * min(n_debt, 10) + "☆" * max(0, 10 - n_debt)
            
            sc1, sc2 = st.columns(2)
            with sc1: st.markdown(f"""<div class="status-card"><div class="status-label">投資型</div><div class="star-display" style="color:#00cc99;">{inv_s}</div><div>{n_inv}個</div></div>""", unsafe_allow_html=True)
            with sc2: st.markdown(f"""<div class="status-card"><div class="status-label">借金型</div><div class="star-display" style="color:#ff4b4b;">{debt_s}</div><div>{n_debt}個</div></div>""", unsafe_allow_html=True)
            
            if st.button("登録する", type="primary", use_container_width=True):
                db = conn.read(worksheet="Records", ttl="0s").astype(str)
                new_row = pd.DataFrame([{"real_name": current_emp_id, "date": str(target_date), "points": str(n_inv - n_debt), "investment_items": ", ".join(sel_inv), "debt_items": ", ".join(sel_debt)}])
                conn.update(worksheet="Records", data=pd.concat([db, new_row]).reset_index(drop=True).astype(str))
                st.session_state.form_version += 1
                st.cache_data.clear(); st.balloons(); st.rerun()
        record_ui()

    # --- マイデータ ---
    with tab3:
        st.subheader("🗓 カレンダー履歴")
        if 'cal_y' not in st.session_state: st.session_state.cal_y, st.session_state.cal_m = date.today().year, date.today().month
        
        c1, c2, c3 = st.columns([1, 2, 1])
        with c1: 
            if st.button("⬅️", key="prev"):
                st.session_state.cal_m -= 1
                if st.session_state.cal_m == 0: st.session_state.cal_m, st.session_state.cal_y = 12, st.session_state.cal_y - 1
                st.rerun()
        with c2: st.markdown(f"<p style='text-align:center; font-weight:bold; margin:0;'>{st.session_state.cal_y}年 {st.session_state.cal_m}月</p>", unsafe_allow_html=True)
        with c3:
            if st.button("➡️", key="next"):
                st.session_state.cal_m += 1
                if st.session_state.cal_m == 13: st.session_state.cal_m, st.session_state.cal_y = 1, st.session_state.cal_y + 1
                st.rerun()
        
        # 曜日ヘッダー
        days = ["月", "火", "水", "木", "金", "土", "日"]
        cols_h = st.columns(7)
        for i, d in enumerate(days): cols_h[i].markdown(f"<div class='cal-day-header'>{d}</div>", unsafe_allow_html=True)
        
        # 日付ボタン行
        cal = calendar.monthcalendar(st.session_state.cal_y, st.session_state.cal_m)
        recorded_dates = user_records['date'].unique().tolist() if not user_records.empty else []
        for week in cal:
            cols = st.columns(7)
            for i, day in enumerate(week):
                if day != 0:
                    t_str = f"{st.session_state.cal_y}-{st.session_state.cal_m:02d}-{day:02d}"
                    has_d = t_str in recorded_dates
                    if cols[i].button(f"{day}🔵" if has_d else f"{day}", key=f"btn_{t_str}", disabled=not has_d):
                        st.session_state.sel_d = t_str
        
        if st.session_state.get('sel_d'):
            det = user_records[user_records['date'] == st.session_state.sel_d].iloc[0]
            st.info(f"📅 {st.session_state.sel_d}\n\n🟢 投資: {display_format(det['investment_items'])}\n\n🔴 借金: {display_format(det['debt_items'])}")

    # --- 設定 / ランキング ---
    with tab2: st.write("ランキング表示エリア")
    with tab4: st.button("ログアウト", on_click=lambda: st.session_state.update({"authenticated": False}))

if __name__ == "__main__":
    main()
