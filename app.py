import streamlit as st
import pandas as pd
from datetime import datetime, date, timedelta
from streamlit_gsheets import GSheetsConnection
import hashlib
import time
import calendar

# --- 1. アプリ設定とセキュリティ設定 ---
st.set_page_config(page_title="Dopamine Tracker", layout="wide")
conn = st.connection("gsheets", type=GSheetsConnection)

# 【秘密の合言葉】初回登録時のみ必要
SECRET_AUTH_CODE = "feelist2026" 

# デザインCSS
st.markdown("""
    <style>
    .status-card {
        border: 1px solid #e6e9ef; border-radius: 15px; padding: 15px; text-align: center;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.05); background-color: white; margin-bottom: 10px;
    }
    .star-display { font-size: 26px; letter-spacing: 2px; margin: 5px 0; font-family: monospace; }
    .status-label { font-size: 16px; font-weight: bold; margin-bottom: 5px; }
    .status-count { font-size: 14px; color: #5e6064; }
    .cal-day-header { text-align: center; font-weight: bold; padding: 5px; border-bottom: 1px solid #eee; }
    </style>
    """, unsafe_allow_html=True)

# パスワード用ハッシュ関数
def make_hash(password):
    return hashlib.sha256(str.encode(password)).hexdigest()

# ID正規化関数（前ゼロ4桁に揃える）
def normalize_id(x):
    try:
        return str(int(float(x))).zfill(4)
    except:
        return str(x).strip().zfill(4)

# データを読み込む関数（型エラー防止済み）
@st.cache_data(ttl=60)
def load_data_cached(sheet_name):
    try:
        df = conn.read(worksheet=sheet_name, ttl="1m")
        if df.empty:
            if sheet_name == "UserMaster":
                return pd.DataFrame(columns=["emp_id", "password_hash", "nickname"])
            else:
                return pd.DataFrame(columns=["real_name", "nickname", "date", "points", "entry_date", "investment_items", "debt_items"])
        return df.astype(str)
    except:
        return pd.DataFrame()

# 項目リスト
INVESTMENT_ITEMS = ["料理", "掃除", "睡眠が8時間以上", "湯舟に入浴、サウナ", "朝10分前に出社", "身体を動かした", "健康的な食生活", "洗濯", "ニュースをみる", "学習", "読書", "創作", "音楽", "挨拶", "感謝", "家族との時間", "植物", "ペット", "新しい挑戦"]
DEBT_ITEMS = ["外食オンリー", "掃除なし", "睡眠不足", "シャワーのみ", "朝ギリギリ", "1日ゴロゴロ", "ギルティ食", "アルコール", "タバコ", "スマホ2h以上", "映像2h以上", "SNS2h以上", "ゲーム2h以上", "ソシャゲ起動", "ゲーム課金", "ギャンブル", "無駄な出費", "独り言", "倫理欠如"]

# --- 2. メイン認証処理 ---
def main():
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
        st.session_state.current_user = None

    if not st.session_state.authenticated:
        st.title("🔒 Dopamine Tracker - 認証")
        target_id = st.text_input("社員番号(4桁)", max_chars=4, key="login_id")
        
        if target_id:
            master = load_data_cached("UserMaster")
            if master.empty:
                st.error("マスターデータが読み込めません。")
                return

            master['emp_id_norm'] = master['emp_id'].apply(normalize_id)
            target_id_norm = normalize_id(target_id)
            user_row = master[master['emp_id_norm'] == target_id_norm]

            if user_row.empty:
                st.error(f"社員番号「{target_id}」は登録を許可されていません。")
            else:
                stored_hash = None
                if 'password_hash' in user_row.columns:
                    val = user_row.iloc[0]['password_hash']
                    if pd.notna(val) and str(val).strip() != "" and str(val).lower() != "nan":
                        stored_hash = str(val)
                
                if not stored_hash:
                    st.warning("⚠️ パスワード未設定です。初回認証を行ってください。")
                    with st.form("init_reg_form"):
                        auth_code = st.text_input("秘密の合言葉", type="password")
                        new_pw = st.text_input("新しいパスワード", type="password")
                        new_pw_confirm = st.text_input("パスワード(確認)", type="password")
                        if st.form_submit_button("登録してログイン"):
                            if auth_code != SECRET_AUTH_CODE:
                                st.error("合言葉が違います。")
                            elif new_pw != new_pw_confirm:
                                st.error("パスワードが一致しません。")
                            elif len(new_pw) < 4:
                                st.error("パスワードは4文字以上です。")
                            else:
                                current_m = conn.read(worksheet="UserMaster", ttl="0s").astype(str)
                                current_m['emp_id_norm'] = current_m['emp_id'].apply(normalize_id)
                                idx = current_m[current_m['emp_id_norm'] == target_id_norm].index[0]
                                if 'password_hash' not in current_m.columns: current_m['password_hash'] = ""
                                current_m.at[idx, 'password_hash'] = str(make_hash(new_pw))
                                current_m.at[idx, 'nickname'] = target_id_norm
                                conn.update(worksheet="UserMaster", data=current_m.drop(columns=['emp_id_norm']))
                                st.session_state.authenticated, st.session_state.current_user = True, target_id_norm
                                st.cache_data.clear(); st.success("登録完了！"); time.sleep(1); st.rerun()
                else:
                    with st.form("normal_login_form"):
                        input_pw = st.text_input("パスワード", type="password")
                        if st.form_submit_button("ログイン"):
                            if make_hash(input_pw) == stored_hash:
                                st.session_state.authenticated, st.session_state.current_user = True, target_id_norm
                                st.rerun()
                            else: st.error("パスワードが違います。")
        st.stop()

    # --- メインコンテンツ ---
    current_emp_id = st.session_state.current_user
    master_data = load_data_cached("UserMaster")
    master_data['emp_id_norm'] = master_data['emp_id'].apply(normalize_id)
    user_info = master_data[master_data['emp_id_norm'] == current_emp_id].iloc[0]
    current_nickname = user_info['nickname'] if pd.notna(user_info['nickname']) and str(user_info['nickname']) != "nan" else current_emp_id

    st.title("📊 Dopamine Tracker")
    with st.sidebar:
        st.write(f"ログイン: **{current_nickname}**")
        if st.button("ログアウト"):
            st.session_state.authenticated = False
            st.rerun()

    all_records = load_data_cached("Records")
    if not all_records.empty and 'real_name' in all_records.columns:
        user_records = all_records[all_records['real_name'].astype(str).str.zfill(4) == current_emp_id].copy()
    else:
        user_records = pd.DataFrame(columns=["real_name", "nickname", "date", "points", "entry_date", "investment_items", "debt_items"])

    tab1, tab2, tab3, tab4 = st.tabs(["今日の記録", "ランキング", "マイデータ", "設定"])

    # --- タブ1: 今日の記録 ---
    with tab1:
        pts_series = pd.to_numeric(user_records['points'], errors='coerce').fillna(0)
        st.write(f"### {current_nickname}さんの累計ポイント: {pts_series.sum():g}")
        
        # 説明テキストを復活させた日付入力
        target_date = st.date_input(
            "対象日（７日前まで遡って登録、修正が出来ます）", 
            value=date.today(), 
            min_value=date.today()-timedelta(days=7), 
            max_value=date.today()
        )

        @st.fragment
        def record_ui():
            st.divider()
            status_placeholder = st.empty()
            
            col_inv, col_debt = st.columns(2)
            with col_inv:
                st.markdown("#### 🟢 投資型 (自己投資)")
                sel_inv = [i for i in INVESTMENT_ITEMS if st.checkbox(i, key=f"inv_{i}")]
            with col_debt:
                st.markdown("#### 🔴 借金型 (即時快楽)")
                sel_debt = [i for i in DEBT_ITEMS if st.checkbox(i, key=f"debt_{i}")]
            
            # 星表示のロジック
            n_inv, n_debt = len(sel_inv), len(sel_debt)
            inv_stars = "★" * min(n_inv, 10) + "☆" * max(0, 10 - n_inv)
            debt_stars = "★" * min(n_debt, 10) + "☆" * max(0, 10 - n_debt)
            inv_label = f"{n_inv}個実施"
            debt_label = f"{n_debt}個実施"

            with status_placeholder.container():
                sc1, sc2 = st.columns(2)
                with sc1:
                    st.markdown(f"""<div class="status-card">
                                <div class="status-label" style="color:#0066cc;">投資型ステータス</div>
                                <div class="star-display" style="color:#00cc99;">{inv_stars}</div>
                                <div class="status-count">{inv_label}</div></div>""", unsafe_allow_html=True)
                with sc2:
                    st.markdown(f"""<div class="status-card">
                                <div class="status-label" style="color:#cc3333;">借金型ステータス</div>
                                <div class="star-display" style="color:#ff4b4b;">{debt_stars}</div>
                                <div class="status-count">{debt_label}</div></div>""", unsafe_allow_html=True)

            st.divider()
            day_count = n_inv - n_debt
            st.metric("本日の獲得予定ポイント", f"{day_count:+d}")

            if st.button("登録する", type="primary"):
                with st.spinner("送信中..."):
                    db = conn.read(worksheet="Records", ttl="0s")
                    if not db.empty: db = db.astype(str)
                    new_row = pd.DataFrame([{
                        "real_name": current_emp_id, "nickname": current_nickname, 
                        "date": str(target_date), "points": day_count, 
                        "entry_date": str(datetime.now()), 
                        "investment_items": ", ".join(sel_inv), "debt_items": ", ".join(sel_debt)
                    }])
                    if not db.empty and 'real_name' in db.columns:
                        db['real_name_norm'] = db['real_name'].str.zfill(4)
                        others = db[~((db['real_name_norm'] == current_emp_id) & (db['date'] == str(target_date)))].drop(columns=['real_name_norm'])
                        updated = pd.concat([others, new_row]).reset_index(drop=True)
                    else: updated = new_row
                    conn.update(worksheet="Records", data=updated)
                    st.cache_data.clear(); st.success("登録完了！"); time.sleep(1); st.rerun()
        record_ui()

    # --- タブ2: ランキング ---
    with tab2:
        st.subheader("🏆 累計ポイントランキング")
        if not all_records.empty and 'points' in all_records.columns:
            rdf = all_records.copy()
            rdf["points"] = pd.to_numeric(rdf["points"], errors='coerce').fillna(0)
            rdf['real_name_norm'] = rdf['real_name'].astype(str).str.zfill(4)
            summary = rdf.groupby("real_name_norm")["points"].sum().reset_index()
            summary = summary.merge(master_data[['emp_id_norm', 'nickname']], left_on='real_name_norm', right_on='emp_id_norm', how='left')
            summary['ニックネーム'] = summary['nickname'].fillna(summary['real_name_norm'])
            summary = summary.rename(columns={"points": "ポイント累計"})
            summary["順位"] = summary["ポイント累計"].rank(ascending=False, method='min').astype(int)
            summary = summary.sort_values("順位").reset_index(drop=True)
            st.dataframe(summary[["順位", "ニックネーム", "ポイント累計"]], use_container_width=True, hide_index=True, column_config={"順位": st.column_config.NumberColumn(alignment="left")})

    # --- タブ3: マイデータ ---
    with tab3:
        st.subheader("🗓 カレンダー履歴")
        if 'cal_y' not in st.session_state: st.session_state.cal_y, st.session_state.cal_m = date.today().year, date.today().month
        c1, c2, c3 = st.columns([1, 2, 1])
        with c1:
            if st.button("⬅️"):
                st.session_state.cal_m -= 1
                if st.session_state.cal_m == 0: st.session_state.cal_m, st.session_state.cal_y = 12, st.session_state.cal_y - 1
                st.rerun()
        with c2: st.markdown(f"<h3 style='text-align: center;'>{st.session_state.cal_y}年 {st.session_state.cal_m}月</h3>", unsafe_allow_html=True)
        with c3:
            if st.button("➡️"):
                st.session_state.cal_m += 1
                if st.session_state.cal_m == 13: st.session_state.cal_m, st.session_state.cal_y = 1, st.session_state.cal_y + 1
                st.rerun()
        cal = calendar.monthcalendar(st.session_state.cal_y, st.session_state.cal_m)
        cols = st.columns(7)
        for i, d in enumerate(["月", "火", "水", "木", "金", "土", "日"]): cols[i].markdown(f"<div class='cal-day-header'>{d}</div>", unsafe_allow_html=True)
        for week in cal:
            cols = st.columns(7)
            for i, day in enumerate(week):
                if day != 0:
                    t_str = f"{st.session_state.cal_y}-{st.session_state.cal_m:02d}-{day:02d}"
                    has_d = not user_records[user_records['date'] == t_str].empty if not user_records.empty else False
                    if cols[i].button(f"{day} 🔴" if has_d else f"{day}", key=f"btn_{t_str}", use_container_width=True):
                        st.session_state.sel_d = t_str
        if st.session_state.get('sel_d') and not user_records.empty:
            det = user_records[user_records['date'] == st.session_state.sel_d]
            if not det.empty:
                st.markdown(f"#### 📅 {st.session_state.sel_d}"); st.write(f"**獲得ポイント:** {det.iloc[0]['points']:+g}")
                st.write("**🟢 投資型:**", det.iloc[0].get('investment_items', "")); st.write("**🔴 借金型:**", det.iloc[0].get('debt_items', ""))

    # --- タブ4: 設定 ---
    with tab4:
        st.subheader("⚙️ 設定")
        new_nick = st.text_input("ニックネーム変更", value=current_nickname)
        edit_pw = st.text_input("新しいパスワードに変更(空欄なら変更なし)", type="password")
        if st.button("設定を保存する"):
            m_db = conn.read(worksheet="UserMaster", ttl="0s").astype(str)
            m_db['emp_id_norm'] = m_db['emp_id'].apply(normalize_id)
            idx = m_db[m_db['emp_id_norm'] == current_emp_id].index[0]
            m_db.at[idx, 'nickname'] = new_nick
            if edit_pw: m_db.at[idx, 'password_hash'] = make_hash(edit_pw)
            conn.update(worksheet="UserMaster", data=m_db.drop(columns=['emp_id_norm']))
            st.cache_data.clear(); st.success("更新しました。"); time.sleep(1); st.rerun()

if __name__ == "__main__":
    main()
