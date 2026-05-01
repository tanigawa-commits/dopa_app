import streamlit as st
import pandas as pd
import streamlit.components.v1 as components
from datetime import datetime, date, timedelta
from streamlit_gsheets import GSheetsConnection
import hashlib
import time
import calendar

# --- 1. アプリ設定 ---
st.set_page_config(page_title="Dopamine Tracker", layout="wide")
conn = st.connection("gsheets", type=GSheetsConnection)

SECRET_AUTH_CODE = "2026"

st.markdown("""
    <style>
    .status-card {
        border: 1px solid #e6e9ef; border-radius: 15px; padding: 15px; text-align: center;
        background-color: white; margin-bottom: 10px; box-shadow: 0 4px 6px rgba(0, 0, 0, 0.05);
    }
    .star-display { font-size: 26px; letter-spacing: 2px; margin: 5px 0; font-family: monospace; }
    .status-label { font-size: 16px; font-weight: bold; margin-bottom: 5px; }
    .status-count { font-size: 15px; color: #333; font-weight: bold; height: 22px; }

    /* カレンダー強制横並び */
    div[data-testid="stHorizontalBlock"] {
        flex-wrap: nowrap !important;
        gap: 2px !important;
    }
    div[data-testid="stHorizontalBlock"] > div[data-testid="column"] {
        min-width: 0 !important;
        flex: 1 1 0 !important;
        padding: 0 !important;
        overflow: hidden !important;
    }
    /* カレンダーボタン */
    div[data-testid="stHorizontalBlock"] button[kind="secondary"] {
        width: 100% !important;
        min-width: 0 !important;
        padding: 2px 0px !important;
        font-size: 11px !important;
        line-height: 1.3 !important;
        border-radius: 6px !important;
        white-space: pre-wrap !important;
        height: 44px !important;
    }
    </style>
    """, unsafe_allow_html=True)

# ヘルパー関数
def make_hash(password): return hashlib.sha256(str.encode(password)).hexdigest()
def clean_val(x):
    if pd.isna(x): return ""
    s = str(x).strip()
    if s.endswith('.0'): s = s[:-2]
    if s.lower() in ["nan", "none", "", "null"]: return ""
    return s
def normalize_id(x):
    s = clean_val(x)
    if not s: return ""
    try: return str(int(float(s))).zfill(4)
    except: return s.zfill(4)
def display_format(val):
    s = clean_val(val)
    return s if s != "" else "－"

@st.cache_data(ttl=60)
def load_data_cached(sheet_name):
    try:
        df = conn.read(worksheet=sheet_name, ttl="1m")
        if df is None or df.empty: return pd.DataFrame()
        df = df.astype(str)
        if "emp_id" in df.columns: df["emp_id_norm"] = df["emp_id"].apply(normalize_id)
        if "real_name" in df.columns: df["real_name_norm"] = df["real_name"].apply(normalize_id)
        return df
    except: return pd.DataFrame()

INVESTMENT_ITEMS = ["料理", "掃除", "睡眠が8時間以上", "湯舟に入浴、サウナ", "朝10分前に出社", "身体を動かした", "健康的な食生活", "洗濯", "ニュースをみる", "学習", "読書", "創作", "音楽", "挨拶", "感謝", "家族との時間", "植物", "ペット", "新しい挑戦"]
DEBT_ITEMS = ["外食オンリー", "掃除なし", "睡眠不足", "シャワーのみ", "朝ギリギリ", "1日ゴロゴロ", "ギルティ食", "アルコール", "タバコ", "スマホ2h以上", "映像2h以上", "SNS2h以上", "ゲーム2h以上", "ソシャゲ起動", "ゲーム課金", "ギャンブル", "無駄な出費", "独り言", "倫理欠如"]

def main():
    if 'authenticated' not in st.session_state: st.session_state.authenticated = False
    if 'last_logged_id' not in st.session_state: st.session_state.last_logged_id = ""
    if 'form_version' not in st.session_state: st.session_state.form_version = 0
    if 'cal_sel_date' not in st.session_state: st.session_state.cal_sel_date = str(date.today())
    if 'cal_y' not in st.session_state: st.session_state.cal_y = date.today().year
    if 'cal_m' not in st.session_state: st.session_state.cal_m = date.today().month

    # ★ クエリパラメータから日付を受け取る（カレンダークリック時）
    params = st.query_params
    if "cal_date" in params:
        incoming = params["cal_date"]
        if incoming != st.session_state.cal_sel_date:
            st.session_state.cal_sel_date = incoming
            # パラメータをクリアして再描画
            st.query_params.clear()
            st.rerun()

    # 認証セクション
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
                        stored_hash = clean_val(user_row.iloc[0].get('password_hash', ""))
                        if stored_hash == "":
                            with st.form("init_reg"):
                                st.info("初回登録：パスワードを設定してください（４文字以上）")
                                r_msg = st.empty()
                                ac, np, npc = st.text_input("秘密の合言葉", type="password"), st.text_input("PW", type="password"), st.text_input("確認", type="password")
                                if st.form_submit_button("登録"):
                                    if ac != SECRET_AUTH_CODE: r_msg.error("秘密の合言葉が違います")
                                    elif len(np) < 4: r_msg.error("パスワードは４文字以上")
                                    elif np != npc: r_msg.error("不一致")
                                    else:
                                        cm = conn.read(worksheet="UserMaster", ttl="0s").astype(str)
                                        cm['tmp'] = cm['emp_id'].apply(normalize_id)
                                        idx = cm[cm['tmp'] == tid_norm].index[0]
                                        cm.at[idx, 'password_hash'], cm.at[idx, 'nickname'] = str(make_hash(np)), tid_norm
                                        conn.update(worksheet="UserMaster", data=cm.drop(columns=['tmp']))
                                        st.session_state.update({"authenticated":True, "current_user":tid_norm, "last_logged_id":tid_norm})
                                        st.cache_data.clear(); st.rerun()
                        else:
                            with st.form("login_f"):
                                l_msg = st.empty()
                                ip = st.text_input("パスワード", type="password")
                                if st.form_submit_button("ログイン"):
                                    if make_hash(ip) == stored_hash:
                                        st.session_state.update({"authenticated":True, "current_user":tid_norm, "last_logged_id":tid_norm})
                                        st.cache_data.clear(); st.rerun()
                                    else: l_msg.error("パスワードが違います")
        st.stop()

    # データ読み込み
    current_emp_id = st.session_state.current_user
    master_data = load_data_cached("UserMaster")
    user_info = master_data[master_data['emp_id_norm'] == current_emp_id].iloc[0]
    current_nickname = clean_val(user_info['nickname']) if clean_val(user_info['nickname']) != "" else current_emp_id
    all_recs = load_data_cached("Records")
    user_recs = all_recs[all_recs['real_name_norm'] == current_emp_id] if not all_recs.empty else pd.DataFrame()

    st.title("📊 Dopamine Tracker")
    tab1, tab2, tab3, tab4 = st.tabs(["今日の記録", "ランキング", "マイデータ", "設定"])

    # --- タブ1: 今日の記録 ---
    with tab1:
        total_pts = pd.to_numeric(user_recs['points'], errors='coerce').fillna(0).sum()
        st.write(f"### {current_nickname}さんの累計ポイントは {total_pts:g} ptです")
        target_date = st.date_input("対象日（７日前まで遡って登録、修正が出来ます）", value=date.today(), min_value=date.today()-timedelta(days=7), max_value=date.today())
        @st.fragment
        def record_ui():
            st.divider()
            top_stars_p = st.empty()
            v = st.session_state.form_version
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("#### 🟢 投資型")
                sel_inv = [i for i in INVESTMENT_ITEMS if st.checkbox(i, key=f"inv_{i}_{v}")]
            with col2:
                st.markdown("#### 🔴 借金型")
                sel_debt = [i for i in DEBT_ITEMS if st.checkbox(i, key=f"debt_{i}_{v}")]
            n_inv, n_debt = len(sel_inv), len(sel_debt)
            inv_s, debt_s = "★"*min(n_inv,10)+"☆"*max(0,10-n_inv), "★"*min(n_debt,10)+"☆"*max(0,10-n_debt)
            inv_t = f"{n_inv}個実施！" if 0 < n_inv <= 10 else ("10個以上実施！" if n_inv > 10 else "")
            debt_t = f"{n_debt}個実施！" if 0 < n_debt <= 10 else ("10個以上実施！" if n_debt > 10 else "")
            with top_stars_p.container():
                sc1, sc2 = st.columns(2)
                with sc1: st.markdown(f'<div class="status-card"><div class="status-label" style="color:#0066cc;">投資型</div><div class="star-display" style="color:#00cc99;">{inv_s}</div><div class="status-count">{inv_t}</div></div>', unsafe_allow_html=True)
                with sc2: st.markdown(f'<div class="status-card"><div class="status-label" style="color:#cc3333;">借金型</div><div class="star-display" style="color:#ff4b4b;">{debt_s}</div><div class="status-count">{debt_t}</div></div>', unsafe_allow_html=True)
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

    # --- タブ3: マイデータ ---
    with tab3:
        st.subheader("🗓 履歴の確認")
        from streamlit_calendar import calendar as st_calendar

        # 記録済みイベントをカレンダー形式に変換
        events = []
        if not user_recs.empty:
            for _, row in user_recs.iterrows():
                d = clean_val(row['date'])
                pts = clean_val(row['points'])
                if not d: continue
                try:
                    pts_num = int(pts)
                except:
                    pts_num = 0
                color = "#0066cc" if pts_num > 0 else ("#cc3333" if pts_num < 0 else "#888")
                events.append({
                    "title": f"{pts_num:+d}pt",
                    "start": d,
                    "end": d,
                    "backgroundColor": color,
                    "borderColor": color,
                    "textColor": "#ffffff",
                    "extendedProps": {"date": d}
                })

        calendar_options = {
            "initialView": "dayGridMonth",
            "locale": "ja",
            "headerToolbar": {
                "left": "prev",
                "center": "title",
                "right": "next"
            },
            "selectable": True,
            "height": 400,
            "buttonText": {"today": "今日"},
            "dayCellClassNames": "",
            "dayMaxEvents": True,
        }

        custom_css = """
        .fc-event { cursor: pointer; font-size: 11px; }
        .fc-daygrid-day { cursor: pointer; }
        .fc-col-header-cell-cushion { font-size: 12px; }
        .fc-daygrid-day-number { font-size: 12px; }
        """

        result = st_calendar(
            events=events,
            options=calendar_options,
            custom_css=custom_css,
            key="main_calendar"
        )

        # クリックイベントを受け取る
        clicked_date = None
        if result:
            # 日付セルのクリック
            if result.get("dateClick"):
                clicked_date = result["dateClick"].get("date", "")[:10]
            # イベント（ポイント表示）のクリック
            elif result.get("eventClick"):
                clicked_date = result["eventClick"]["event"].get("start", "")[:10]

        if clicked_date:
            st.session_state.cal_sel_date = clicked_date

        # 詳細表示
        st.divider()
        sel_d = st.session_state.get("cal_sel_date", str(date.today()))
        st.markdown(f"**📅 {sel_d} の記録**")

        det = user_recs[user_recs['date'] == sel_d]
        if not det.empty:
            row = det.iloc[0]
            pts = clean_val(row['points'])
            inv = display_format(row['investment_items'])
            debt = display_format(row['debt_items'])
            try:
                pts_num = int(pts)
            except:
                pts_num = 0
            pts_color = "#0066cc" if pts_num > 0 else ("#cc3333" if pts_num < 0 else "#888")
            st.markdown(
                f"<div style='background:#f8f9fa;border-radius:12px;padding:15px;'>"
                f"<p>💰 <b>ポイント：</b>"
                f"<span style='color:{pts_color};font-weight:bold;font-size:18px;'>{pts}pt</span></p>"
                f"<p>🟢 <b>投資型：</b>{inv}</p>"
                f"<p>🔴 <b>借金型：</b>{debt}</p>"
                f"</div>",
                unsafe_allow_html=True
            )
        else:
            st.info("この日の記録はありません。")

    with tab2: st.subheader("🏆 ランキング"); st.write("（ランキングコードがここに入ります）")
    with tab4: st.subheader("⚙️ 設定"); st.write("（設定コードがここに入ります）")

if __name__ == "__main__":
    main()
