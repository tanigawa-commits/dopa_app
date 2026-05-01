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

    /* 【履歴テーブル専用CSS】自動折り返しを実現 */
    .history-table {
        width: 100%;
        border-collapse: collapse;
        font-size: 14px;
        table-layout: fixed;
        background-color: white;
    }
    .history-table th, .history-table td {
        border: 1px solid #f0f0f0;
        padding: 10px 8px;
        text-align: left;
        vertical-align: top;
        word-wrap: break-word;
        white-space: normal;
        overflow-wrap: break-word;
    }
    .history-table th {
        background-color: #f8f9fb;
        color: #666;
        font-weight: bold;
    }
    .col-date { width: 100px; }
    .col-pts { width: 80px; text-align: right !important; }
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
    """ IDを4桁のきれいな文字列にする（.0を徹底排除） """
    s = str(x).strip()
    if s.endswith('.0'): s = s[:-2]
    if not s or s.lower() in ["nan", "none"]: return ""
    try:
        # 一度数値にしてから再度整数として文字列化することで.0を消す
        return str(int(float(s))).zfill(4)
    except:
        return s.zfill(4)

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

# 項目定義
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
                    tid_norm = normalize_id(target_id)
                    user_row = master[master['emp_id_norm'] == tid_norm] if not master.empty else pd.DataFrame()
                    if user_row.empty: id_msg.error("この社員番号は使用できません")
                    else:
                        id_msg.empty()
                        raw_hash = user_row.iloc[0].get('password_hash', "")
                        stored_hash = str(raw_hash).strip() if pd.notna(raw_hash) and str(raw_hash).lower() not in ["nan", "none", ""] else None
                        if not stored_hash:
                            with st.form("init_reg"):
                                st.info("初回登録：パスワードを設定してください（４文字以上）")
                                reg_msg = st.empty()
                                ac, np, npc = st.text_input("秘密の合言葉", type="password"), st.text_input("PW", type="password"), st.text_input("確認", type="password")
                                if st.form_submit_button("登録してログイン"):
                                    if ac != SECRET_AUTH_CODE: reg_msg.error("秘密の合言葉が違います")
                                    elif len(np) < 4: reg_msg.error("パスワードは４文字以上")
                                    elif np != npc: reg_msg.error("不一致")
                                    else:
                                        reg_msg.empty()
                                        cm = conn.read(worksheet="UserMaster", ttl="0s").astype(str)
                                        # DB書き込み前にIDから.0を排除して4桁固定にする
                                        cm['emp_id'] = cm['emp_id'].apply(normalize_id)
                                        idx = cm[cm['emp_id'] == tid_norm].index[0]
                                        cm.at[idx, 'password_hash'], cm.at[idx, 'nickname'] = str(make_hash(np)), tid_norm
                                        conn.update(worksheet="UserMaster", data=cm)
                                        st.session_state.update({"authenticated":True, "current_user":tid_norm})
                                        st.cache_data.clear(); st.rerun()
                        else:
                            with st.form("login_f"):
                                login_msg = st.empty()
                                ip = st.text_input("パスワード", type="password")
                                if st.form_submit_button("ログイン"):
                                    if make_hash(ip) == stored_hash:
                                        login_msg.empty()
                                        st.session_state.update({"authenticated":True, "current_user":tid_norm})
                                        st.cache_data.clear(); st.rerun()
                                    else: login_msg.error("パスワードが違います")
        st.stop()

    current_emp_id = st.session_state.current_user
    master_data = load_data_cached("UserMaster")
    user_info = master_data[master_data['emp_id_norm'] == current_emp_id].iloc[0]
    nickname_raw = user_info.get('nickname', current_emp_id)
    current_nickname = str(nickname_raw) if pd.notna(nickname_raw) and str(nickname_raw).lower() not in ["nan", "none", ""] else current_emp_id
    
    all_recs = load_data_cached("Records")
    user_recs = all_recs[all_recs['real_name_norm'] == current_emp_id] if not all_recs.empty else pd.DataFrame()

    st.title("📊 Dopamine Tracker")
    with st.sidebar:
        st.write(f"ログイン: **{current_nickname}**")
        if st.button("ログアウト"): st.session_state.authenticated = False; st.rerun()

    tab1, tab2, tab3, tab4 = st.tabs(["今日の記録", "ランキング", "マイデータ", "設定"])

    # --- タブ1: 今日の記録 ---
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
                    # 書き込み前に社員番号をきれいにする
                    db['real_name'] = db['real_name'].apply(normalize_id)
                    new_row = pd.DataFrame([{"real_name": current_emp_id, "date": str(target_date), "points": str(n_inv - n_debt), "entry_date": str(datetime.now()), "investment_items": ", ".join(sel_inv), "debt_items": ", ".join(sel_debt)}])
                    others = db[~((db['real_name'] == current_emp_id) & (db['date'] == str(target_date)))]
                    conn.update(worksheet="Records", data=pd.concat([others, new_row]).reset_index(drop=True))
                    st.balloons(); time.sleep(2); st.session_state.form_version += 1; st.cache_data.clear(); st.rerun()
        record_ui()

    # --- タブ2: ランキング（pt表示追加） ---
    with tab2:
        st.subheader("🏆 累計ポイントランキング")
        if not all_recs.empty:
            rdf = all_recs.copy(); rdf["points"] = pd.to_numeric(rdf["points"], errors='coerce').fillna(0)
            summary = rdf.groupby("real_name_norm")["points"].sum().reset_index()
            mini = master_data[['emp_id_norm', 'nickname']].drop_duplicates()
            summary = summary.merge(mini, left_on='real_name_norm', right_on='emp_id_norm', how='left')
            summary['ニックネーム'] = summary['nickname'].apply(lambda x: x if pd.notna(x) and str(x).lower() not in ["nan", "none", ""] else "－")
            summary["順位"] = summary["points"].rank(ascending=False, method='min').astype(int)
            summary = summary.rename(columns={"points": "累計"})
            # ポイント数に pt を付ける設定
            st.dataframe(
                summary.sort_values("順位")[["順位", "ニックネーム", "累計"]],
                use_container_width=True,
                hide_index=True,
                column_config={
                    "順位": st.column_config.NumberColumn(alignment="left"),
                    "累計": st.column_config.NumberColumn(format="%d pt", alignment="left")
                }
            )

    # --- タブ3: マイデータ（HTMLテーブル・自動折り返し） ---
    with tab3:
        st.subheader("📋 全履歴の一覧")
        if not user_recs.empty:
            df_view = user_recs[['date', 'points', 'investment_items', 'debt_items']].copy()
            df_view = df_view.sort_values('date', ascending=False)
            table_html = '<table class="history-table"><tr><th class="col-date">日付</th><th class="col-pts">ポイント</th><th>投資</th><th>借金</th></tr>'
            for _, row in df_view.iterrows():
                d = row['date'].replace('-', '/')
                p = f"{int(float(row['points']))} pt"
                inv, dbt = clean_val_for_display(row['investment_items']), clean_val_for_display(row['debt_items'])
                table_html += f'<tr><td>{d}</td><td style="text-align:right;">{p}</td><td>{inv}</td><td>{dbt}</td></tr>'
            table_html += '</table>'
            st.markdown(table_html, unsafe_allow_html=True)
            st.caption("※ 項目が多い場合は自動的に折り返されます。")
        else: st.warning("記録がありません。")

    # --- タブ4: 設定 ---
    with tab4:
        st.subheader("⚙️ 設定")
        new_nick = st.text_input("ニックネーム変更", value=current_nickname)
        st.markdown("---")
        st.write("🔒 パスワードの変更")
        new_pw, new_pw_c = st.text_input("新PW", type="password"), st.text_input("確認", type="password")
        if st.button("設定を更新する"):
            m_db = conn.read(worksheet="UserMaster", ttl="0s").astype(str)
            # 書き込み前に全ての社員番号から.0を排除
            m_db['emp_id'] = m_db['emp_id'].apply(normalize_id)
            idx = m_db[m_db['emp_id'] == current_emp_id].index[0]
            m_db.at[idx, 'nickname'] = new_nick
            if new_pw:
                if len(new_pw) < 4: st.error("4文字以上必要です"); st.stop()
                if new_pw == new_pw_c: m_db.at[idx, 'password_hash'] = str(make_hash(new_pw))
                else: st.error("不一致です"); st.stop()
            conn.update(worksheet="UserMaster", data=m_db)
            st.cache_data.clear(); st.success("保存しました"); time.sleep(1); st.rerun()

if __name__ == "__main__":
    main()
