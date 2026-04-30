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
    .star-display { font-size: 26px; letter-spacing: 2px; margin: 5px 0; }
    .status-label { font-size: 16px; font-weight: bold; }
    .cal-day-header { text-align: center; font-weight: bold; padding: 5px; border-bottom: 1px solid #eee; }
    </style>
    """, unsafe_allow_html=True)

# パスワード用ハッシュ関数
def make_hash(password):
    return hashlib.sha256(str.encode(password)).hexdigest()

# データを読み込む関数（キャッシュ付き）
@st.cache_data(ttl=60)
def load_data_cached(sheet_name):
    try:
        return conn.read(worksheet=sheet_name, ttl="1m")
    except:
        return pd.DataFrame()

# リスト定義
INVESTMENT_ITEMS = ["料理", "掃除", "睡眠が8時間以上", "湯舟に入浴、サウナ", "朝10分前に出社", "身体を動かした", "健康的な食生活", "洗濯", "ニュースをみる", "学習", "読書", "創作", "音楽", "挨拶", "感謝", "家族との時間", "植物", "ペット", "新しい挑戦"]
DEBT_ITEMS = ["外食オンリー", "掃除なし", "睡眠不足", "シャワーのみ", "朝ギリギリ", "1日ゴロゴロ", "ギルティ食", "アルコール", "タバコ", "スマホ2h以上", "映像2h以上", "SNS2h以上", "ゲーム2h以上", "ソシャゲ起動", "ゲーム課金", "ギャンブル", "無駄な出費", "独り言", "倫理欠如"]

# --- 2. メイン認証処理 ---
def main():
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
        st.session_state.current_user = None

    # --- ログイン・登録画面 ---
    if not st.session_state.authenticated:
        st.title("🔒 Dopamine Tracker - 認証")
        
        target_id = st.text_input("社員番号(4桁)", max_chars=4, key="login_id")
        
        if target_id:
            master = load_data_cached("UserMaster")
            if master.empty:
                st.error("マスターデータが読み込めません。")
                return

            # 【強化版比較ロジック】前ゼロ対応
            # スプレッドシート側の「1」も「0001」も、すべて「0001」という文字列に揃えて比較
            def normalize_id(x):
                try:
                    return str(int(float(x))).zfill(4)
                except:
                    return str(x).strip()

            master['emp_id_norm'] = master['emp_id'].apply(normalize_id)
            target_id_norm = normalize_id(target_id)
            
            user_row = master[master['emp_id_norm'] == target_id_norm]

            if user_row.empty:
                st.error(f"社員番号「{target_id}」は登録を許可されていません。")
            else:
                stored_hash = user_row.iloc[0]['password_hash']
                
                # ケースA：パスワード未設定（初回登録）
                if pd.isna(stored_hash) or stored_hash == "":
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
                                st.error("パスワードは4文字以上で設定してください。")
                            else:
                                # DB更新（インデックス特定には正規化前のデータを使用）
                                current_master = conn.read(worksheet="UserMaster", ttl="0s")
                                current_master['emp_id_norm'] = current_master['emp_id'].apply(normalize_id)
                                idx = current_master[current_master['emp_id_norm'] == target_id_norm].index[0]
                                
                                current_master.at[idx, 'password_hash'] = make_hash(new_pw)
                                current_master.at[idx, 'nickname'] = target_id_norm
                                
                                # 不要な列を消して更新
                                final_master = current_master.drop(columns=['emp_id_norm'])
                                conn.update(worksheet="UserMaster", data=final_master)
                                
                                st.session_state.authenticated = True
                                st.session_state.current_user = target_id_norm
                                st.cache_data.clear()
                                st.success("登録完了！")
                                time.sleep(1); st.rerun()
                
                # ケースB：パスワード設定済みの通常ログイン
                else:
                    with st.form("normal_login_form"):
                        input_pw = st.text_input("パスワード", type="password")
                        if st.form_submit_button("ログイン"):
                            if make_hash(input_pw) == stored_hash:
                                st.session_state.authenticated = True
                                st.session_state.current_user = target_id_norm
                                st.rerun()
                            else:
                                st.error("パスワードが違います。")
        st.stop()

    # --- メインコンテンツ（認証済み） ---
    current_emp_id = st.session_state.current_user
    master = load_data_cached("UserMaster")
    # master側の正規化
    master['emp_id_norm'] = master['emp_id'].apply(lambda x: str(int(float(x))).zfill(4) if str(x).replace('.','',1).isdigit() else str(x).strip())
    user_info = master[master['emp_id_norm'] == current_emp_id].iloc[0]
    current_nickname = user_info['nickname'] if pd.notna(user_info['nickname']) else current_emp_id

    st.title("📊 Dopamine Tracker")
    with st.sidebar:
        st.write(f"ログイン: **{current_nickname}**")
        if st.button("ログアウト"):
            st.session_state.authenticated = False
            st.rerun()

    all_records = load_data_cached("Records")
    user_records = all_records[all_records['real_name'].astype(str).str.zfill(4) == current_emp_id].copy() if not all_records.empty else pd.DataFrame()
    
    tab1, tab2, tab3, tab4 = st.tabs(["今日の記録", "ランキング", "マイデータ", "設定"])

    # --- タブ1: 今日の記録 ---
    with tab1:
        user_records['points'] = pd.to_numeric(user_records['points'], errors='coerce').fillna(0)
        st.write(f"### 累計ポイント: {user_records['points'].sum():g}")
        target_date = st.date_input("対象日", value=date.today(), min_value=date.today()-timedelta(days=7), max_value=date.today())

        @st.fragment
        def record_ui():
            st.divider()
            c1, c2 = st.columns(2)
            with c1:
                st.markdown("#### 🟢 投資型")
                sel_inv = [i for i in INVESTMENT_ITEMS if st.checkbox(i, key=f"inv_{i}")]
            with c2:
                st.markdown("#### 🔴 借金型")
                sel_debt = [i for i in DEBT_ITEMS if st.checkbox(i, key=f"debt_{i}")]
            
            day_count = len(sel_inv) - len(sel_debt)
            st.metric("獲得予定", f"{day_count:+d}")

            if st.button("登録する", type="primary"):
                db = conn.read(worksheet="Records", ttl="0s")
                new_row = pd.DataFrame([{"real_name": current_emp_id, "nickname": current_nickname, "date": str(target_date), "points": day_count, "entry_date": str(datetime.now()), "investment_items": ", ".join(sel_inv), "debt_items": ", ".join(sel_debt)}])
                # 重複削除ロジックの強化（型を揃えて比較）
                db['real_name_norm'] = db['real_name'].astype(str).str.zfill(4)
                others = db[~((db['real_name_norm'] == current_emp_id) & (db['date'] == str(target_date)))].drop(columns=['real_name_norm'])
                conn.update(worksheet="Records", data=pd.concat([others, new_row]).reset_index(drop=True))
                st.cache_data.clear(); st.success("登録完了！"); time.sleep(1); st.rerun()
        record_ui()

    # --- タブ2: ランキング (左寄せ) ---
    with tab2:
        st.subheader("🏆 累計ポイントランキング")
        if not all_records.empty:
            rdf = all_records.copy()
            rdf["points"] = pd.to_numeric(rdf["points"], errors='coerce').fillna(0)
            rdf['real_name_norm'] = rdf['real_name'].astype(str).str.zfill(4)
            summary = rdf.groupby("real_name_norm")["points"].sum().reset_index()
            summary = summary.merge(master[['emp_id_norm', 'nickname']], left_on='real_name_norm', right_on='emp_id_norm', how='left')
            summary['ニックネーム'] = summary['nickname'].fillna(summary['real_name_norm'])
            summary = summary.rename(columns={"points": "ポイント累計"})
            summary["順位"] = summary["ポイント累計"].rank(ascending=False, method='min').astype(int)
            summary = summary.sort_values("順位").reset_index(drop=True)
            st.dataframe(summary[["順位", "ニックネーム", "ポイント累計"]], use_container_width=True, hide_index=True, 
                         column_config={
                             "順位": st.column_config.NumberColumn(alignment="left"),
                             "ニックネーム": st.column_config.TextColumn(alignment="left"),
                             "ポイント累計": st.column_config.NumberColumn(alignment="left")
                         })

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
                    has_d = not user_records[user_records['date'] == t_str].empty
                    if cols[i].button(f"{day} 🔴" if has_d else f"{day}", key=f"btn_{t_str}", use_container_width=True):
                        st.session_state.sel_d = t_str
        if st.session_state.get('sel_d'):
            det = user_records[user_records['date'] == st.session_state.sel_d]
            if not det.empty:
                st.markdown(f"#### 📅 {st.session_state.sel_d}")
                st.write(f"**獲得ポイント:** {det.iloc[0]['points']:+g}")
                st.write("**🟢 投資型:**", det.iloc[0].get('investment_items', ""))
                st.write("**🔴 借金型:**", det.iloc[0].get('debt_items', ""))

    # --- タブ4: 設定 ---
    with tab4:
        st.subheader("⚙️ 設定")
        new_nick = st.text_input("ニックネーム変更", value=current_nickname)
        edit_pw = st.text_input("新しいパスワードに変更(空欄なら変更なし)", type="password")
        if st.button("設定を保存する"):
            m_db = conn.read(worksheet="UserMaster", ttl="0s")
            m_db['emp_id_norm'] = m_db['emp_id'].apply(normalize_id)
            idx = m_db[m_db['emp_id_norm'] == current_emp_id].index[0]
            m_db.at[idx, 'nickname'] = new_nick
            if edit_pw: m_db.at[idx, 'password_hash'] = make_hash(edit_pw)
            final_m = m_db.drop(columns=['emp_id_norm'])
            conn.update(worksheet="UserMaster", data=final_m)
            st.cache_data.clear(); st.success("更新しました。"); time.sleep(1); st.rerun()

if __name__ == "__main__":
    main()
