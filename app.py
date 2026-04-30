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

# 【秘密の合言葉】
SECRET_AUTH_CODE = "feelist2026" 

# デザインCSS（カレンダーのみを狙い撃ちして幅を固定）
st.markdown("""
    <style>
    /* 共通：ステータスカード */
    .status-card {
        border: 1px solid #e6e9ef; border-radius: 15px; padding: 15px; text-align: center;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.05); background-color: white; margin-bottom: 10px;
    }
    .star-display { font-size: 26px; letter-spacing: 2px; margin: 5px 0; font-family: monospace; }
    .status-label { font-size: 16px; font-weight: bold; margin-bottom: 5px; }
    .status-count { font-size: 14px; color: #5e6064; }
    .cal-day-header { text-align: center; font-weight: bold; padding: 5px; border-bottom: 1px solid #eee; font-size: 12px; }

    /* 【重要】7列あるブロック（カレンダー）のみ横幅を固定して中央寄せ */
    div[data-testid="stHorizontalBlock"]:has(div[data-testid="column"]:nth-child(7)) {
        display: flex !important;
        justify-content: center !important;
        flex-direction: row !important;
        flex-wrap: nowrap !important;
        gap: 4px !important;
    }

    /* カレンダーの日付ボタンを小さく固定 */
    div[data-testid="stHorizontalBlock"]:has(div[data-testid="column"]:nth-child(7)) div[data-testid="column"] {
        min-width: 40px !important;
        max-width: 50px !important;
        flex: 1 1 0% !important;
    }

    /* ボタン内の余白と文字サイズ調整 */
    div[data-testid="stHorizontalBlock"]:has(div[data-testid="column"]:nth-child(7)) button {
        padding: 4px 0px !important;
        font-size: 12px !important;
        min-height: 45px !important;
        border-radius: 8px !important;
    }
    </style>
    """, unsafe_allow_html=True)

# パスワード用ハッシュ関数
def make_hash(password):
    return hashlib.sha256(str.encode(password)).hexdigest()

# 文字列クリーニング
def clean_string_strictly(x):
    s = str(x).strip()
    if '.' in s: s = s.split('.')[0]
    if s.lower() in ["nan", "none", "", "none"]: return ""
    return s

# 表示用フォーマッタ（空なら全角ハイフンにする）
def display_format(val):
    if pd.isna(val): return "－"
    s = str(val).strip()
    if s.lower() in ["nan", "none", "", "null", "undefined"]: return "－"
    return s

# ID正規化
def normalize_id_strictly(x):
    s = clean_string_strictly(x)
    if s == "": return ""
    try: return str(int(float(s))).zfill(4)
    except: return s.zfill(4)

# データ読み込み
@st.cache_data(ttl=60)
def load_data_cached(sheet_name):
    try:
        df = conn.read(worksheet=sheet_name, ttl="1m")
        if df.empty:
            if sheet_name == "UserMaster": return pd.DataFrame(columns=["emp_id", "password_hash", "nickname"])
            return pd.DataFrame(columns=["real_name", "date", "points", "entry_date", "investment_items", "debt_items"])
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
            user_row = master[master['emp_id'] == target_id_norm]
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
    user_records = all_records[all_records['real_name'] == current_emp_id].copy()

    tab1, tab2, tab3, tab4 = st.tabs(["今日の記録", "ランキング", "マイデータ", "設定"])

    # --- 今日の記録 ---
    with tab1:
        pts = pd.to_numeric(user_records['points'], errors='coerce').fillna(0).sum()
        st.write(f"### {current_nickname}さんの累計ポイント: {pts:g}")
        target_date = st.date_input("対象日", value=date.today(), min_value=date.today()-timedelta(days=7), max_value=date.today())
        @st.fragment
        def record_ui():
            st.divider()
            status_placeholder = st.empty()
            col_inv, col_debt = st.columns(2)
            v = st.session_state.form_version
            with col_inv:
                st.markdown("#### 🟢 投資型")
                sel_inv = [i for i in INVESTMENT_ITEMS if st.checkbox(i, key=f"inv_{i}_{v}")]
            with col_debt:
                st.markdown("#### 🔴 借金型")
                sel_debt = [i for i in DEBT_ITEMS if st.checkbox(i, key=f"debt_{i}_{v}")]
            n_inv, n_debt = len(sel_inv), len(sel_debt)
            inv_stars = "★" * min(n_inv, 10) + "☆" * max(0, 10 - n_inv)
            debt_stars = "★" * min(n_debt, 10) + "☆" * max(0, 10 - n_debt)
            inv_l = f"{n_inv}個実施！" if n_inv <= 10 else "10個以上実施！"
            debt_l = f"{n_debt}個実施！" if n_debt <= 10 else "10個以上実施！"
            with status_placeholder.container():
                sc1, sc2 = st.columns(2)
                with sc1: st.markdown(f"""<div class="status-card"><div class="status-label" style="color:#0066cc;">投資型</div><div class="star-display" style="color:#00cc99;">{inv_stars}</div><div class="status-count">{inv_l}</div></div>""", unsafe_allow_html=True)
                with sc2: st.markdown(f"""<div class="status-card"><div class="status-label" style="color:#cc3333;">借金型</div><div class="star-display" style="color:#ff4b4b;">{debt_stars}</div><div class="status-count">{debt_l}</div></div>""", unsafe_allow_html=True)
            day_pts = n_inv - n_debt
            st.metric("本日のポイント", f"{day_pts:+d}")
            if st.button("登録する", type="primary", use_container_width=True):
                db = conn.read(worksheet="Records", ttl="0s").astype(str)
                db['real_name'] = db['real_name'].apply(normalize_id_strictly)
                new_row = pd.DataFrame([{"real_name": current_emp_id, "date": str(target_date), "points": str(day_pts), "entry_date": str(datetime.now()), "investment_items": ", ".join(sel_inv), "debt_items": ", ".join(sel_debt)}])
                others = db[~((db['real_name'] == current_emp_id) & (db['date'] == str(target_date)))]
                conn.update(worksheet="Records", data=pd.concat([others, new_row]).reset_index(drop=True).astype(str))
                st.session_state.form_version += 1
                st.cache_data.clear(); st.balloons(); st.rerun()
        record_ui()

    # --- ランキング ---
    with tab2:
        if not all_records.empty:
            rdf = all_records.copy()
            rdf["points"] = pd.to_numeric(rdf["points"], errors='coerce').fillna(0)
            summary = rdf.groupby("real_name")["points"].sum().reset_index()
            summary = summary.merge(master_data[['emp_id', 'nickname']], left_on='real_name', right_on='emp_id', how='left')
            summary['名'] = summary['nickname'].apply(clean_string_strictly).replace('', None).fillna(summary['real_name'])
            summary["順位"] = summary["points"].rank(ascending=False, method='min').astype(int)
            st.dataframe(summary.sort_values("順位")[["順位", "名", "points"]], use_container_width=True, hide_index=True, column_config={"順位": st.column_config.NumberColumn(alignment="left"), "points": st.column_config.NumberColumn("累計", format="%d", alignment="left")})

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
        with c2: st.markdown(f"<h3 style='text-align:center;'>{st.session_state.cal_y}年 {st.session_state.cal_m}月</h3>", unsafe_allow_html=True)
        with c3:
            if st.button("➡️", key="next"):
                st.session_state.cal_m += 1
                if st.session_state.cal_m == 13: st.session_state.cal_m, st.session_state.cal_y = 1, st.session_state.cal_y + 1
                st.rerun()
        cal = calendar.monthcalendar(st.session_state.cal_y, st.session_state.cal_m)
        days_names = ["月", "火", "水", "木", "金", "土", "日"]
        cols_h = st.columns(7)
        for i, d in enumerate(days_names): cols_h[i].markdown(f"<div class='cal-day-header'>{d}</div>", unsafe_allow_html=True)
        recorded_dates = user_records['date'].unique().tolist() if not user_records.empty else []
        for week in cal:
            cols = st.columns(7)
            for i, day in enumerate(week):
                if day != 0:
                    t_str = f"{st.session_state.cal_y}-{st.session_state.cal_m:02d}-{day:02d}"
                    has_d = t_str in recorded_dates
                    if cols[i].button(f"{day} 🔵" if has_d else f"{day}", key=f"btn_{t_str}", use_container_width=True, disabled=not has_d):
                        st.session_state.sel_d = t_str
        if st.session_state.get('sel_d'):
            det = user_records[user_records['date'] == st.session_state.sel_d]
            if not det.empty:
                st.info(f"📅 {st.session_state.sel_d} ({pd.to_numeric(det.iloc[0]['points'], errors='coerce'):+g}pt)\n\n🟢 投資: {display_format(det.iloc[0]['investment_items'])}\n\n🔴 借金: {display_format(det.iloc[0]['debt_items'])}")
        st.divider()
        with st.expander("📝 全履歴を表示"):
            if not user_records.empty:
                h_df = user_records.sort_values("date", ascending=False).copy()
                h_df["points"] = pd.to_numeric(h_df["points"], errors="coerce").fillna(0).astype(int)
                for c in ["investment_items", "debt_items"]: h_df[c] = h_df[c].apply(display_format)
                st.dataframe(h_df[["date", "points", "investment_items", "debt_items"]], use_container_width=True, hide_index=True, column_config={"points": st.column_config.NumberColumn(format="%d", alignment="left")})

    # --- 設定 ---
    with tab4:
        new_nick = st.text_input("ニックネーム変更", value=current_nickname)
        edit_pw = st.text_input("パスワード変更(空欄なら維持)", type="password")
        if st.button("設定を保存する", use_container_width=True):
            m_db = conn.read(worksheet="UserMaster", ttl="0s").astype(str)
            m_db['emp_id'] = m_db['emp_id'].apply(normalize_id_strictly)
            idx = m_db[m_db['emp_id'] == current_emp_id].index[0]
            m_db.at[idx, 'nickname'] = new_nick
            if edit_pw: m_db.at[idx, 'password_hash'] = str(make_hash(edit_pw))
            conn.update(worksheet="UserMaster", data=m_db.astype(str))
            st.cache_data.clear(); st.rerun()

if __name__ == "__main__":
    main()
