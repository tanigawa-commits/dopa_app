import streamlit as st
import pandas as pd
from datetime import datetime, date, timedelta
from streamlit_gsheets import GSheetsConnection
import hashlib
import time

# --- 1. アプリ設定 ---
st.set_page_config(page_title="Dopamine Tracker", layout="wide")
conn = st.connection("gsheets", type=GSheetsConnection)

SECRET_AUTH_CODE = "2026" 

# デザインCSS
st.markdown("""
    <style>
    /* 記録カード */
    .status-card {
        border: 1px solid #e6e9ef; border-radius: 15px; padding: 15px; text-align: center;
        background-color: white; margin-bottom: 10px; box-shadow: 0 4px 6px rgba(0, 0, 0, 0.05);
    }
    .star-display { font-size: 26px; letter-spacing: 2px; margin: 5px 0; font-family: monospace; }
    .status-label { font-size: 16px; font-weight: bold; margin-bottom: 5px; }
    .status-count { font-size: 15px; color: #333; font-weight: bold; height: 22px; }

    /* 【履歴テーブル専用CSS】折り返しと列幅固定を実現 */
    .history-table {
        width: 100%;
        border-collapse: collapse;
        font-size: 14px;
        table-layout: fixed; /* 列幅を固定 */
        background-color: white;
    }
    .history-table th, .history-table td {
        border: 1px solid #f0f0f0;
        padding: 10px 8px;
        text-align: left;
        vertical-align: top;
        word-wrap: break-word;      /* 折り返し設定 */
        white-space: normal;        /* 複数行表示を許可 */
        overflow-wrap: break-word;
    }
    .history-table th {
        background-color: #f8f9fb;
        color: #666;
        font-weight: bold;
    }
    /* 列ごとの幅指定 */
    .col-date { width: 100px; }
    .col-pts { width: 70px; text-align: right !important; }
    .col-main { width: auto; } /* 投資と借金で残りを分ける */
    </style>
    """, unsafe_allow_html=True)

# --- 2. ヘルパー関数 ---

def make_hash(password): return hashlib.sha256(str.encode(password)).hexdigest()

def clean_val_for_display(x):
    """ 表の表示用：空の値やNoneを全角ハイフンにする """
    if pd.isna(x): return "－"
    s = str(x).strip()
    if s.lower() in ["nan", "none", "", "null"]: return "－"
    return s

def normalize_id(x):
    s = str(x).strip()
    if s.endswith('.0'): s = s[:-2]
    if not s or s.lower() in ["nan", "none"]: return ""
    try: return str(int(float(s))).zfill(4)
    except: return s.zfill(4)

@st.cache_data(ttl=60)
def load_data_cached(sheet_name):
    try:
        df = conn.read(worksheet=sheet_name, ttl="1m")
        if df is None or df.empty: return pd.DataFrame()
        df = df.astype(str)
        if "emp_id" in df.columns:
            df["emp_id_norm"] = df["emp_id"].apply(normalize_id)
        if "real_name" in df.columns:
            df["real_name_norm"] = df["real_name"].apply(normalize_id)
        return df
    except Exception:
        return pd.DataFrame()

INVESTMENT_ITEMS = ["料理", "掃除", "睡眠が8時間以上", "湯舟に入浴、サウナ", "朝10分前に出社", "身体を動かした", "健康的な食生活", "洗濯", "ニュースをみる", "学習", "読書", "創作", "音楽", "挨拶", "感謝", "家族との時間", "植物", "ペット", "新しい挑戦"]
DEBT_ITEMS = ["外食オンリー", "掃除なし", "睡眠不足", "シャワーのみ", "朝ギリギリ", "1日ゴロゴロ", "ギルティ食", "アルコール", "タバコ", "スマホ2h以上", "映像2h以上", "SNS2h以上", "ゲーム2h以上", "ソシャゲ起動", "ゲーム課金", "ギャンブル", "無駄な出費", "独り言", "倫理欠如"]

# --- 3. メイン処理 ---
def main():
    if 'authenticated' not in st.session_state: st.session_state.authenticated = False
    if 'last_logged_id' not in st.session_state: st.session_state.last_logged_id = ""
    if 'form_version' not in st.session_state: st.session_state.form_version = 0

    # 認証
    if not st.session_state.authenticated:
        st.title("🔒 Dopamine Tracker - 認証")
        id_msg = st.empty()
        target_id = st.text_input("社員番号(4桁)", value=st.session_state.last_logged_id, max_chars=4)
        if target_id:
            if len(target_id) != 4: id_msg.error("社員番号は4桁で入力してください")
            else:
                with st.spinner("認証中..."):
                    master = load_data_cached("UserMaster")
                    target_id_norm = normalize_id(target_id)
                    user_row = master[master['emp_id_norm'] == target_id_norm] if not master.empty else pd.DataFrame()
                    if user_row.empty: id_msg.error("この社員番号は使用できません")
                    else:
                        id_msg.empty()
                        raw_hash = user_row.iloc[0].get('password_hash', "")
                        stored_hash = str(raw_hash).strip() if pd.notna(raw_hash) and str(raw_hash).lower() not in ["nan", "none", ""] else None
                        if not stored_hash:
                            with st.form("init_reg"):
                                st.info("初回登録：パスワードを設定してください（４文字以上）")
                                ac, np, npc = st.text_input("合言葉", type="password"), st.text_input("PW", type="password"), st.text_input("確認", type="password")
                                if st.form_submit_button("登録"):
                                    if ac == SECRET_AUTH_CODE and np == npc and len(np) >= 4:
                                        cm = conn.read(worksheet="UserMaster", ttl="0s").astype(str)
                                        cm['tmp'] = cm['emp_id'].apply(normalize_id)
                                        idx = cm[cm['tmp'] == target_id_norm].index[0]
                                        cm.at[idx, 'password_hash'], cm.at[idx, 'nickname'] = str(make_hash(np)), target_id_norm
                                        conn.update(worksheet="UserMaster", data=cm.drop(columns=['tmp']))
                                        st.session_state.update({"authenticated":True, "current_user":target_id_norm})
                                        st.cache_data.clear(); st.rerun()
                        else:
                            with st.form("login_f"):
                                ip = st.text_input("パスワード", type="password")
                                if st.form_submit_button("ログイン"):
                                    if make_hash(ip) == stored_hash:
                                        st.session_state.update({"authenticated":True, "current_user":target_id_norm})
                                        st.cache_data.clear(); st.rerun()
                                    else: st.error("パスワードが違います")
        st.stop()

    current_emp_id = st.session_state.current_user
    master_data = load_data_cached("UserMaster")
    user_info = master_data[master_data['emp_id_norm'] == current_emp_id].iloc[0]
    current_nickname = user_info.get('nickname', current_emp_id)
    
    all_recs = load_data_cached("Records")
    user_recs = all_recs[all_recs['real_name_norm'] == current_emp_id] if not all_recs.empty else pd.DataFrame()

    st.title("📊 Dopamine Tracker")
    tab1, tab2, tab3, tab4 = st.tabs(["今日の記録", "ランキング", "マイデータ", "設定"])

    # --- タブ1: 今日の記録（安定版） ---
    with tab1:
        valid_pts = pd.to_numeric(user_recs['points'], errors='coerce').fillna(0)
        st.write(f"### {current_nickname}さんの累計ポイントは {int(valid_pts.sum())} ptです")
        target_date = st.date_input("対象日（７日前まで遡って登録、修正が出来ます）", value=date.today(), min_value=date.today()-timedelta(days=7), max_value=date.today())

        @st.fragment
        def record_ui():
            st.divider()
            top_stars_p = st.empty()
            v = st.session_state.form_version
            c1, c2 = st.columns(2)
            with c1:
                st.markdown("#### 🟢 投資型")
                sel_inv = [i for i in INVESTMENT_ITEMS if st.checkbox(i, key=f"inv_{i}_{v}")]
            with c2:
                st.markdown("#### 🔴 借金型")
                sel_debt = [i for i in DEBT_ITEMS if st.checkbox(i, key=f"debt_{i}_{v}")]
            
            n_inv, n_debt = len(sel_inv), len(sel_debt)
            inv_s, debt_s = "★" * min(n_inv, 10) + "☆" * max(0, 10 - n_inv), "★" * min(n_debt, 10) + "☆" * max(0, 10 - n_debt)
            inv_txt = f"{n_inv}個実施！" if 0 < n_inv <= 10 else ("10個以上実施！" if n_inv > 10 else "")
            debt_txt = f"{n_debt}個実施！" if 0 < n_debt <= 10 else ("10個以上実施！" if n_debt > 10 else "")

            with top_stars_p.container():
                sc1, sc2 = st.columns(2)
                with sc1: st.markdown(f'<div class="status-card"><div class="status-label" style="color:#0066cc;">投資型</div><div class="star-display" style="color:#00cc99;">{inv_s}</div><div class="status-count">{inv_txt}</div></div>', unsafe_allow_html=True)
                with sc2: st.markdown(f'<div class="status-card"><div class="status-label" style="color:#cc3333;">借金型</div><div class="star-display" style="color:#ff4b4b;">{debt_s}</div><div class="status-count">{debt_txt}</div></div>', unsafe_allow_html=True)
            
            st.metric("本日のポイント", f"{n_inv - n_debt:+d}")
            if st.button("登録する", type="primary", use_container_width=True):
                with st.spinner("保存中..."):
                    db = conn.read(worksheet="Records", ttl="0s").astype(str)
                    new_row = pd.DataFrame([{"real_name": current_emp_id, "date": str(target_date), "points": str(n_inv - n_debt), "entry_date": str(datetime.now()), "investment_items": ", ".join(sel_inv), "debt_items": ", ".join(sel_debt)}])
                    db['tmp'] = db['real_name'].apply(normalize_id)
                    others = db[~((db['tmp'] == current_emp_id) & (db['date'] == str(target_date)))]
                    conn.update(worksheet="Records", data=pd.concat([others, new_row]).drop(columns=['tmp']).reset_index(drop=True))
                    st.balloons(); time.sleep(2); st.session_state.form_version += 1; st.cache_data.clear(); st.rerun()
        record_ui()

    # --- タブ3: マイデータ（新・自動折り返しHTMLテーブル版） ---
    with tab3:
        st.subheader("📋 全履歴の一覧")
        if not user_recs.empty:
            df_view = user_recs[['date', 'points', 'investment_items', 'debt_items']].copy()
            df_view = df_view.sort_values('date', ascending=False)
            
            # HTMLテーブルの組み立て
            table_html = '<table class="history-table">'
            table_html += '<tr><th class="col-date">日付</th><th class="col-pts">ポイント</th><th class="col-main">投資</th><th class="col-main">借金</th></tr>'
            
            for _, row in df_view.iterrows():
                d = row['date'].replace('-', '/')
                p = f"{int(float(row['points']))} pt"
                inv = clean_val_for_display(row['investment_items'])
                dbt = clean_val_for_display(row['debt_items'])
                table_html += f'<tr><td>{d}</td><td style="text-align:right;">{p}</td><td>{inv}</td><td>{dbt}</td></tr>'
            
            table_html += '</table>'
            
            st.markdown(table_html, unsafe_allow_html=True)
            st.caption("※ 項目が多い場合は自動的に折り返して表示されます。")
        else:
            st.warning("記録がありません。")

    # --- 他タブ ---
    with tab2: st.subheader("🏆 ランキング") # 以前のランキングコードをここへ
    with tab4: st.subheader("⚙️ 設定") # 以前の設定コードをここへ

if __name__ == "__main__":
    main()
