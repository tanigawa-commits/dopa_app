import streamlit as st
import pandas as pd
from datetime import datetime, date, timedelta
from streamlit_gsheets import GSheetsConnection
import hashlib
import time
import calendar

# --- 1. アプリ設定 ---
st.set_page_config(page_title="Dopamine Tracker", layout="centered")
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
    .status-label { font-size: 16px; font-weight: bold; margin-bottom: 5px; }
    /* New CSS class for the selected count text */
    .status-count { font-size: 14px; color: #5e6064; }
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
INVESTMENT_ITEMS = ["料理", "掃除", "睡眠が8時間以上", "湯舟に入浴、サウナ", "朝10分前に出社", "身体を動かした", "健康的な食生活", "洗濯", "ニュースをみる", "学習", "読書", "創作", "音楽", "挨拶", "感謝", "家族との時間を過ごす", "植物を育てる", "ペットと触れ合う", "普段やらない事を挑戦"]
DEBT_ITEMS = ["外食オンリー", "掃除なし", "睡眠不足", "シャワーのみ", "朝ギリギリ", "1日ゴロゴロ", "ギルティ食", "アルコール", "タバコ", "スマホ2h以上", "映像2h以上", "SNS2h以上", "ゲーム2h以上", "ソシャゲ起動", "ゲーム課金", "ギャンブル", "無駄な出費", "独り言", "倫理欠如"]

# --- 2. メイン認証 ---
def main():
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
        st.session_state.current_user = None
    if 'last_logged_id' not in st.session_state:
        st.session_state.last_logged_id = ""
    if 'form_version' not in st.session_state:
        st.session_state.form_version = 0

    if not st.session_state.authenticated:
        st.title("🔒 Dopamine Tracker")
        target_id = st.text_input("社員番号(4桁)", value=st.session_state.last_logged_id, max_chars=4, key="login_id_input")
        if target_id:
            master = load_data_cached("UserMaster")
            target_id_norm = normalize_id_strictly(target_id)
            user_row = master[master['emp_id'] == target_id_norm] if not master.empty else pd.DataFrame()
            if user_row.empty:
                st.error("許可されていません。")
            else:
                val = user_row.iloc[0].get('password_hash', "")
                stored_hash = str(val) if pd.notna(val) and str(val).lower() != "nan" and str(val).strip() != "" else None
                if not stored_hash:
                    st.warning("⚠️ パスワード設定")
                    with st.form("reg"):
                        ac = st.text_input("合言葉", type="password")
                        np = st.text_input("パスワード", type="password")
                        npc = st.text_input("確認", type="password")
                        if st.form_submit_button("登録"):
                            if ac != SECRET_AUTH_CODE or np != npc: st.error("エラー")
                            else:
                                cm = conn.read(worksheet="UserMaster", ttl="0s").astype(str)
                                cm['emp_id'] = cm['emp_id'].apply(normalize_id_strictly)
                                idx = cm[cm['emp_id'] == target_id_norm].index[0]
                                cm.at[idx, 'password_hash'] = str(make_hash(np))
                                cm.at[idx, 'nickname'] = target_id_norm
                                conn.update(worksheet="UserMaster", data=cm.astype(str))
                                st.session_state.authenticated, st.session_state.current_user = True, target_id_norm
                                st.cache_data.clear(); st.rerun()
                else:
                    with st.form("login"):
                        ip = st.text_input("パスワード", type="password")
                        if st.form_submit_button("ログイン"):
                            if make_hash(ip) == stored_hash:
                                st.session_state.authenticated, st.session_state.current_user = True, target_id_norm
                                st.cache_data.clear(); st.rerun()
        st.stop()

    current_emp_id = st.session_state.current_user
    master_data = load_data_cached("UserMaster")
    user_info = master_data[master_data['emp_id'] == current_emp_id].iloc[0]
    current_nickname = clean_string_strictly(user_info['nickname']) if pd.notna(user_info['nickname']) and str(user_info['nickname']) != "" else current_emp_id

    all_records = load_data_cached("Records")
    user_records = all_records[all_records['real_name'] == current_emp_id].copy() if not all_records.empty else pd.DataFrame()

    tab1, tab2, tab3, tab4 = st.tabs(["今日の記録", "ランキング", "マイデータ", "設定"])

    # --- タブ1: 今日の記録 ---
    with tab1:
        pts = pd.to_numeric(user_records['points'], errors='coerce').fillna(0).sum() if not user_records.empty else 0
        st.write(f"### 累計ポイント: {pts:g}")
        target_date = st.date_input("対象日", value=date.today(), min_value=date.today()-timedelta(days=7), max_value=date.today())
        
        # Fragment to optimize re-rendering within the UI
        @st.fragment
        def record_ui():
            st.divider()
            
            # Top placeholder for star display. declare first to place above main columns.
            top_stars_p = st.empty()
            
            # Columns for category titles and checklists
            col_inv, col_debt = st.columns(2)
            v = st.session_state.form_version
            
            # Title & Checklist of checkboxes for Investment Side
            with col_inv:
                st.markdown("#### 🟢 投資型")
                sel_inv = [i for i in INVESTMENT_ITEMS if st.checkbox(i, key=f"inv_{i}_{v}")]
            
            # Title & Checklist of checkboxes for Debt Side
            with col_debt:
                st.markdown("#### 🔴 借金型")
                sel_debt = [i for i in DEBT_ITEMS if st.checkbox(i, key=f"debt_{i}_{v}")]
            
            # Recalculate status, apply conditional logic from counts to fill stars
            n_inv, n_debt = len(sel_inv), len(sel_debt)
            inv_s, debt_s = "★" * min(n_inv, 10) + "☆" * max(0, 10 - n_inv), "★" * min(n_debt, 10) + "☆" * max(0, 10 - n_debt)
            
            # Conditional Text Logic based on counts
            # No text for 0. Count for 1-10. "10 or more" for 11+.
            inv_txt = ""
            debt_txt = ""
            
            if n_inv > 0:
                if n_inv <= 10: inv_txt = f"{n_inv}個実施！"
                else: inv_txt = "10個以上実施！"
                
            if n_debt > 0:
                if n_debt <= 10: debt_txt = f"{n_debt}個実施！"
                else: debt_txt = "10個以上実施！"

            # Place the full star rating UI into the placeholder ABOVE the titles using containers. 
            # Re-calculates state based on checkbox results but visually places it first.
            with top_stars_p.container():
                # A new row of columns for the star rating UI, placed ABOVE the checklists.
                sc1, sc2 = st.columns(2)
                
                # Apply the text conditions within the HTML templates
                with sc1: st.markdown(f"""<div class="status-card"><div class="status-label" style="color:#0066cc;">投資型</div><div class="star-display" style="color:#00cc99;">{inv_s}</div><div class="status-count">{inv_txt}</div></div>""", unsafe_allow_html=True)
                with sc2: st.markdown(f"""<div class="status-card"><div class="status-label" style="color:#cc3333;">借金型</div><div class="star-display" style="color:#ff4b4b;">{debt_s}</div><div class="status-count">{debt_txt}</div></div>""", unsafe_allow_html=True)
            
            day_pts = n_inv - n_debt
            st.metric("本日のポイント", f"{day_pts:+d}")
            if st.button("登録する", type="primary", use_container_width=True):
                # Save the new record, avoiding duplicates for the same day/user
                db = conn.read(worksheet="Records", ttl="0s").astype(str)
                new_row = pd.DataFrame([{"real_name": current_emp_id, "date": str(target_date), "points": str(day_pts), "investment_items": ", ".join(sel_inv), "debt_items": ", ".join(sel_debt)}])
                others = db[~((db['real_name'] == current_emp_id) & (db['date'] == str(target_date)))]
                conn.update(worksheet="Records", data=pd.concat([others, new_row]).reset_index(drop=True).astype(str))
                # Update state to force fragment re-rendering
                st.session_state.form_version += 1
                st.cache_data.clear(); st.balloons(); st.rerun()
        record_ui()

    # --- タブ2: ランキング ---
    with tab2: st.write("ランキングエリア")

    # --- タブ3: マイデータ ---
    with tab3: st.write("マイデータエリア")

    # --- タブ4: 設定 ---
    with tab4: st.button("ログアウト", on_click=lambda: st.session_state.update({"authenticated": False}))

if __name__ == "__main__":
    main()
