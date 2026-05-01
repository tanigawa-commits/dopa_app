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

# デザインCSS（他画面に干渉しないようクラスを限定）
st.markdown("""
    <style>
    .status-card {
        border: 1px solid #e6e9ef; border-radius: 15px; padding: 15px; text-align: center;
        background-color: white; margin-bottom: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.05);
    }
    .star-display { font-size: 26px; letter-spacing: 2px; margin: 5px 0; font-family: monospace; }
    .status-label { font-size: 16px; font-weight: bold; margin-bottom: 5px; }
    .status-count { font-size: 14px; color: #5e6064; height: 20px; } /* テキスト用の高さを確保 */
    </style>
    """, unsafe_allow_html=True)

# --- 2. データクリーニング・ヘルパー関数 ---
def make_hash(password): return hashlib.sha256(str.encode(password)).hexdigest()

def clean_val(x):
    if pd.isna(x): return ""
    s = str(x).strip()
    if s.endswith('.0'): s = s[:-2]
    if s.lower() in ["nan", "none", "", "null"]: return ""
    return s

def display_format(val):
    s = clean_val(val)
    return s if s != "" else "－"

def normalize_id(x):
    s = clean_val(x)
    if s == "": return ""
    try: return str(int(float(s))).zfill(4)
    except: return s.zfill(4)

@st.cache_data(ttl=60)
def load_data_cached(sheet_name):
    try:
        df = conn.read(worksheet=sheet_name, ttl="1m")
        return df.astype(str) if not df.empty else pd.DataFrame()
    except: return pd.DataFrame()

# 項目定義
INVESTMENT_ITEMS = ["料理", "掃除", "睡眠が8時間以上", "湯舟に入浴、サウナ", "朝10分前に出社", "身体を動かした", "健康的な食生活", "洗濯", "ニュースをみる", "学習", "読書", "創作", "音楽", "挨拶", "感謝", "家族との時間", "植物", "ペット", "新しい挑戦"]
DEBT_ITEMS = ["外食オンリー", "掃除なし", "睡眠不足", "シャワーのみ", "朝ギリギリ", "1日ゴロゴロ", "ギルティ食", "アルコール", "タバコ", "スマホ2h以上", "映像2h以上", "SNS2h以上", "ゲーム2h以上", "ソシャゲ起動", "ゲーム課金", "ギャンブル", "無駄な出費", "独り言", "倫理欠如"]

# --- 3. メイン処理 ---
def main():
    if 'authenticated' not in st.session_state: st.session_state.authenticated = False
    if 'last_logged_id' not in st.session_state: st.session_state.last_logged_id = ""
    if 'form_version' not in st.session_state: st.session_state.form_version = 0

    # 認証セクション
    if not st.session_state.authenticated:
        st.title("🔒 Dopamine Tracker - 認証")
        target_id = st.text_input("社員番号(4桁)", value=st.session_state.last_logged_id, max_chars=4)
        if target_id:
            master = load_data_cached("UserMaster")
            target_id_norm = normalize_id(target_id)
            user_row = master[master['emp_id'].apply(normalize_id) == target_id_norm] if not master.empty else pd.DataFrame()
            if not user_row.empty:
                stored_hash = clean_val(user_row.iloc[0].get('password_hash', ""))
                if stored_hash == "":
                    with st.form("initial_reg"):
                        ac, np, npc = st.text_input("合言葉", type="password"), st.text_input("PW", type="password"), st.text_input("確認", type="password")
                        if st.form_submit_button("登録"):
                            if ac == SECRET_AUTH_CODE and np == npc:
                                cm = conn.read(worksheet="UserMaster", ttl="0s").astype(str)
                                idx = cm[cm['emp_id'].apply(normalize_id) == target_id_norm].index[0]
                                cm.at[idx, 'password_hash'], cm.at[idx, 'nickname'] = str(make_hash(np)), target_id_norm
                                conn.update(worksheet="UserMaster", data=cm)
                                st.session_state.authenticated, st.session_state.current_user = True, target_id_norm
                                st.cache_data.clear(); st.rerun()
                else:
                    with st.form("login_form"):
                        ip = st.text_input("パスワード", type="password")
                        if st.form_submit_button("ログイン"):
                            if make_hash(ip) == stored_hash:
                                st.session_state.authenticated, st.session_state.current_user = True, target_id_norm
                                st.cache_data.clear(); st.rerun()
        st.stop()

    # データ準備
    current_emp_id = st.session_state.current_user
    master_data = load_data_cached("UserMaster")
    user_info = master_data[master_data['emp_id'].apply(normalize_id) == current_emp_id].iloc[0]
    current_nickname = clean_val(user_info['nickname']) if clean_val(user_info['nickname']) != "" else current_emp_id
    all_recs = load_data_cached("Records")
    user_recs = all_recs[all_recs['real_name'].apply(normalize_id) == current_emp_id] if not all_recs.empty else pd.DataFrame()

    st.title("📊 Dopamine Tracker")
    with st.sidebar:
        st.write(f"ログイン: **{current_nickname}**")
        if st.button("ログアウト"):
            st.session_state.authenticated = False
            st.rerun()

    tab1, tab2, tab3, tab4 = st.tabs(["今日の記録", "ランキング", "マイデータ", "設定"])

    # --- タブ1: 今日の記録 ---
    with tab1:
        total_pts = pd.to_numeric(user_recs['points'], errors='coerce').fillna(0).sum()
        st.write(f"### {current_nickname}さんの累計ポイントは {total_pts:g} ptです")
        
        target_date = st.date_input("対象日（７日前まで遡って登録、修正が出来ます）", value=date.today(), min_value=date.today()-timedelta(days=7), max_value=date.today())

        @st.fragment
        def record_ui():
            st.divider()
            # 【重要】星表示をチェックボックスの上に置くためのプレースホルダー
            top_stars_p = st.empty()
            
            v = st.session_state.form_version
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("#### 🟢 投資型")
                sel_inv = [i for i in INVESTMENT_ITEMS if st.checkbox(i, key=f"inv_{i}_{v}")]
            with col2:
                st.markdown("#### 🔴 借金型")
                sel_debt = [i for i in DEBT_ITEMS if st.checkbox(i, key=f"debt_{i}_{v}")]
            
            # 星表示ロジック
            n_inv, n_debt = len(sel_inv), len(sel_debt)
            inv_s, debt_s = "★" * min(n_inv, 10) + "☆" * max(0, 10 - n_inv), "★" * min(n_debt, 10) + "☆" * max(0, 10 - n_debt)
            
            # 【重要】個数表示ロジック（0個なら非表示、11個以上なら「10個以上」）
            inv_txt = f"{n_inv}個実施！" if 0 < n_inv <= 10 else ("10個以上実施！" if n_inv > 10 else "")
            debt_txt = f"{n_debt}個実施！" if 0 < n_debt <= 10 else ("10個以上実施！" if n_debt > 10 else "")

            # プレースホルダーに星カードを流し込み
            with top_stars_p.container():
                sc1, sc2 = st.columns(2)
                with sc1: st.markdown(f'<div class="status-card"><div class="status-label" style="color:#0066cc;">投資型</div><div class="star-display" style="color:#00cc99;">{inv_s}</div><div class="status-count">{inv_txt}</div></div>', unsafe_allow_html=True)
                with sc2: st.markdown(f'<div class="status-card"><div class="status-label" style="color:#cc3333;">借金型</div><div class="star-display" style="color:#ff4b4b;">{debt_s}</div><div class="status-count">{debt_txt}</div></div>', unsafe_allow_html=True)
            
            st.metric("本日のポイント", f"{n_inv - n_debt:+d}")
            if st.button("登録する", type="primary", use_container_width=True):
                with st.spinner("登録中..."):
                    db = conn.read(worksheet="Records", ttl="0s").astype(str)
                    new_row = pd.DataFrame([{"real_name": current_emp_id, "date": str(target_date), "points": str(n_inv - n_debt), "entry_date": str(datetime.now()), "investment_items": ", ".join(sel_inv), "debt_items": ", ".join(sel_debt)}])
                    others = db[~((db['real_name'].apply(normalize_id) == current_emp_id) & (db['date'] == str(target_date)))]
                    conn.update(worksheet="Records", data=pd.concat([others, new_row]).reset_index(drop=True))
                    st.session_state.form_version += 1
                    st.cache_data.clear(); st.balloons(); st.rerun()
        record_ui()

    # --- タブ2: ランキング ---
    with tab2:
        st.subheader("🏆 累計ポイントランキング")
        if not all_recs.empty:
            rdf = all_recs.copy()
            rdf["points"] = pd.to_numeric(rdf["points"], errors='coerce').fillna(0)
            summary = rdf.groupby("real_name")["points"].sum().reset_index()
            summary = summary.merge(master_data[['emp_id', 'nickname']], left_on='real_name', right_on='emp_id', how='left')
            summary['表示名'] = summary['nickname'].apply(display_format)
            summary["順位"] = summary["points"].rank(ascending=False, method='min').astype(int)
            st.dataframe(summary.sort_values("順位")[["順位", "表示名", "points"]].rename(columns={"points":"累計"}), 
                         use_container_width=True, hide_index=True,
                         column_config={"順位": st.column_config.NumberColumn(alignment="left"), "累計": st.column_config.NumberColumn(format="%d", alignment="left")})

    # --- タブ3: マイデータ ---
    with tab3:
        st.subheader("🗓 履歴の確認")
        sel_date = st.date_input("確認したい日を選択してください", value=date.today())
        year, month = sel_date.year, sel_date.month
        cal = calendar.monthcalendar(year, month)
        recorded_dates = user_recs['date'].unique().tolist() if not user_recs.empty else []
        st.write(f"▼ {month}月の記録状況 (🔵=記録あり)")
        map_html = "<table style='width:100%; text-align:center; border-collapse:collapse; font-size:14px;'><tr><td>月</td><td>火</td><td>水</td><td>木</td><td>金</td><td>土</td><td>日</td></tr>"
        for week in cal:
            map_html += "<tr>"
            for day in week:
                if day == 0: map_html += "<td></td>"
                else:
                    d_str = f"{year}-{month:02d}-{day:02d}"
                    dot = "🔵" if d_str in recorded_dates else ""
                    map_html += f"<td style='border:1px solid #eee; padding:5px;'>{day}<br>{dot}</td>"
            map_html += "</tr>"
        map_html += "</table>"
        st.markdown(map_html, unsafe_allow_html=True)
        st.divider()
        det = user_recs[user_recs['date'] == str(sel_date)]
        if not det.empty:
            d = det.iloc[0]
            st.info(f"📅 {sel_date} の詳細\n\n🟢 投資型: {display_format(d['investment_items'])}\n\n🔴 借金型: {display_format(d['debt_items'])}")
        else: st.warning("この日の記録はありません。")

    # --- タブ4: 設定 ---
    with tab4:
        new_nick = st.text_input("ニックネーム変更", value=current_nickname)
        if st.button("保存"):
            m_db = conn.read(worksheet="UserMaster", ttl="0s").astype(str)
            idx = m_db[m_db['emp_id'].apply(normalize_id) == current_emp_id].index[0]
            m_db.at[idx, 'nickname'] = new_nick
            conn.update(worksheet="UserMaster", data=m_db)
            st.cache_data.clear(); st.success("更新しました。"); time.sleep(1); st.rerun()

if __name__ == "__main__":
    main()
