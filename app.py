import streamlit as st
import pandas as pd
from datetime import datetime, date, timedelta
from streamlit_gsheets import GSheetsConnection
import hashlib
import time
import calendar

# --- 1. アプリ設定 ---
# 画面全体を中央寄せにすることで、カレンダーだけでなくアプリ全体が「イケてる」感じになります。
st.set_page_config(page_title="Dopamine Tracker", layout="centered") 
conn = st.connection("gsheets", type=GSheetsConnection)

SECRET_AUTH_CODE = "feelist2026" 

# デザインCSS
st.markdown("""
    <style>
    /* 他のタブで使用するカードスタイル（登録、ランキング） */
    .status-card {
        border: 1px solid #e6e9ef; border-radius: 15px; padding: 15px; text-align: center;
        background-color: white; margin-bottom: 10px;
    }
    .star-display { font-size: 26px; letter-spacing: 2px; margin: 5px 0; font-family: monospace; }
    
    /* 【秘密の狙い撃ちCSS】カレンダーグリッドを中央寄せにし、スマフォでも1列にならないようにする */
    /* 曜日見出しと日付ボタン行の両方に適用 */
    div[data-testid="stHorizontalBlock"]:has(div:nth-child(7)) {
        display: flex !important;
        flex-direction: row !important;
        justify-content: center !important; /* 中央寄せ */
        width: 270px !important;            /* PC/スマフォの両方で崩れない固定幅 */
        margin: 0 auto !important;         /* 中央寄せ */
        gap: 0px !important;               /* ボタン同士の隙間を消す */
    }

    /* 7列あるブロックの各列（Column）の幅を38pxに固定する */
    div[data-testid="stHorizontalBlock"]:has(div:nth-child(7)) div[data-testid="column"] {
        flex: 0 0 38px !important;
        min-width: 38px !important;
        padding: 0px !important;
        margin: 0px !important;
    }

    /* ボタン要素自体のサイズを38pxに固定し、余白を削り取る。これで「イケてる」グリッドになる */
    div[data-testid="stHorizontalBlock"]:has(div:nth-child(7)) button {
        padding: 0px !important;
        margin: 0px !important;
        font-size: 11px !important;
        min-height: 38px !important;
        height: 38px !important;
        width: 38px !important;
        border-radius: 0px !important; /* グリッドにするために四角くする */
        display: flex !important;
        justify-content: center !important;
        align-items: center !important;
    }

    /* 曜日ヘッダーのテキスト用スタイル。ボタンと幅を合わせる */
    .cal-day-header { text-align: center; font-weight: bold; font-size: 12px; color: #666; width: 38px; }
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
                        st.info("初回登録が必要です")
                        ac, np, npc = st.text_input("秘密の合言葉", type="password"), st.text_input("PW", type="password"), st.text_input("確認", type="password")
                        if st.form_submit_button("登録"):
                            if ac == SECRET_AUTH_CODE and np == npc:
                                cm = conn.read(worksheet="UserMaster", ttl="0s").astype(str)
                                cm['emp_id_t'] = cm['emp_id'].apply(normalize_id_strictly)
                                idx = cm[cm['emp_id_t'] == target_id_norm].index[0]
                                cm.at[idx, 'password_hash'], cm.at[idx, 'nickname'] = str(make_hash(np)), target_id_norm
                                conn.update(worksheet="UserMaster", data=cm.drop(columns=['emp_id_t']).astype(str))
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
    all_records = load_data_cached("Records")
    user_records = all_records[all_records['real_name'] == current_emp_id] if not all_records.empty else pd.DataFrame()

    tab1, tab2, tab3, tab4 = st.tabs(["今日の記録", "ランキング", "マイデータ", "設定"])

    # --- タブ1: 今日の記録（星も風船も文言も、以前のまま死守） ---
    with tab1:
        pts = pd.to_numeric(user_records['points'], errors='coerce').fillna(0).sum()
        st.write(f"### {current_emp_id}さんのこれまでのポイントは {pts:g} ptです") # pt文言死守
        target_date = st.date_input("対象日（７日前まで遡って登録、修正が出来ます）", value=date.today(), min_value=date.today()-timedelta(days=7), max_value=date.today()) # 日付ラベル死守
        
        @st.fragment
        def record_ui():
            st.divider()
            
            # 星表示のプレースホルダー（チェックボックスの上に表示）
            top_stars_p = st.empty()
            
            # チェックボックス
            col_inv, col_debt = st.columns(2)
            v = st.session_state.form_version
            with col_inv:
                st.markdown("#### 🟢 投資型")
                sel_inv = [i for i in INVESTMENT_ITEMS if st.checkbox(i, key=f"inv_{i}_{v}")]
            with col2 if 'col2' in locals() else col_debt:
                st.markdown("#### 🔴 借金型")
                sel_debt = [i for i in DEBT_ITEMS if st.checkbox(i, key=f"debt_{i}_{v}")]
            
            # 計算ロジック（0個なら非表示、11個以上なら「10個以上」）
            n_inv, n_debt = len(sel_inv), len(sel_debt)
            inv_s, debt_s = "★" * min(n_inv, 10) + "☆" * max(0, 10 - n_inv), "★" * min(n_debt, 10) + "☆" * max(0, 10 - n_debt)
            inv_txt = f"{n_inv}個実施！" if 0 < n_inv <= 10 else ("10個以上実施！" if n_inv > 10 else "")
            debt_txt = f"{n_debt}個実施！" if 0 < n_debt <= 10 else ("10個以上実施！" if n_debt > 10 else "")

            # プレースホルダーに星カードを流し込む
            with top_stars_p.container():
                sc1, sc2 = st.columns(2)
                with sc1: st.markdown(f'<div class="status-card"><div class="status-label" style="color:#0066cc;">投資型</div><div class="star-display" style="color:#00cc99;">{inv_s}</div><div class="status-count">{inv_txt}
