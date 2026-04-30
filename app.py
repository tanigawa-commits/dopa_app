import streamlit as st
import pandas as pd
from datetime import datetime, date, timedelta
from streamlit_gsheets import GSheetsConnection
import hashlib
import time
import calendar

# --- 1. アプリ設定とDB接続 ---
st.set_page_config(page_title="Dopamine Tracker", layout="wide")
conn = st.connection("gsheets", type=GSheetsConnection)

# カスタムCSS：表のヘッダーとセル、カード類をすべてセンタリング
st.markdown("""
    <style>
    /* ステータスカード */
    .status-card {
        border: 1px solid #e6e9ef;
        border-radius: 15px;
        padding: 15px;
        text-align: center;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.05);
        background-color: white;
        margin-bottom: 10px;
    }
    .star-display { font-size: 26px; letter-spacing: 2px; margin: 5px 0; }
    .status-label { font-size: 16px; font-weight: bold; }
    .status-count { font-size: 14px; color: #5e6064; }
    .cal-day-header { text-align: center; font-weight: bold; padding: 5px; border-bottom: 1px solid #eee; }
    
    /* ランキング表のヘッダー(タイトル欄)を強制的にセンタリング 
       Glide Data Gridの内部クラスをターゲットにします
    */
    [data-testid="stDataFrame"] div[data-testid="column-header-content"] {
        justify-content: center !important;
        text-align: center !important;
    }
    
    /* データフレーム全体のコンテナを中央に寄せる補助 */
    [data-testid="stDataFrame"] div {
        text-align: center !important;
    }
    </style>
    """, unsafe_allow_html=True)

def make_hash(password):
    return hashlib.sha256(str.encode(password)).hexdigest()

@st.cache_data(ttl=60)
def load_data_cached():
    try:
        df = conn.read(worksheet="Records", ttl="1m")
        return df
    except:
        return pd.DataFrame(columns=["real_name", "password", "nickname", "team", "date", "points", "total_points", "entry_date", "investment_items", "debt_items"])

# --- 2. リスト・マスタ定義 ---
INVESTMENT_ITEMS = [
    "料理", "掃除", "睡眠が8時間以上", "湯舟に入浴、サウナ", "朝10分前に出社",
    "身体を動かした（ウォーキング以上の負荷）", "健康的な食生活（栄養バランスが取れている）",
    "洗濯", "ニュースを30分みる（ネット可）", "学習", "読書（活字限定）",
    "創作（プログラミング、絵、小説、DTM、DIY）", "音楽（音楽鑑賞、楽器、カラオケ）",
    "大きな声で挨拶", "感謝の言葉を伝える", "家族との時間を過ごす", "植物を育てる",
    "ペットと触れ合う", "普段やらない事を挑戦（旅行、模様替え、ファッション、美容）"
]

DEBT_ITEMS = [
    "外食オンリー", "掃除をしなかった", "睡眠が6時間以下", "シャワーのみ／お風呂に入らなかった",
    "朝ギリギリに出社", "家で1日ゴロゴロ", "ギルティな食生活（ドカ食い、間食、炭酸飲料、エナドリ）",
    "アルコール摂取（缶ビール1本以上）", "タバコ（紙、加熱式、電子）", "スマホを2時間以上使用",
    "TV/YouTubeなど映像を2時間以上視聴", "SNSアプリを2時間以上使用", "ゲームを2時間以上プレイ",
    "ソシャゲのログイン報酬を受け取るためだけに起動", "ゲームへの課金", "ギャンブル",
    "無駄な出費", "独り言が多かった", "倫理観に欠ける行動（電車で席を譲らない、夜にゴミを出す等）"
]

# --- 3. メイン処理 ---
def main():
    st.title("Dopamine Tracker")
    st.subheader("今日の行動を記録して、脳の健康状態を可視化しましょう")
    
    saved_emp_id = st.query_params.get("eid", "")
    
    with st.sidebar:
        st.header("🔑 ユーザー認証")
        u_emp_id = st.text_input("社員番号(4桁)", value=saved_emp_id, max_chars=4)
        u_pass = st.text_input("パスワード", type="password")
        
        if st.button("認証"):
            if not u_emp_id or not u_pass:
                st.error("認証情報を入力してください。")
            else:
                st.query_params.update(eid=u_emp_id)
                st.rerun()

    if not (saved_emp_id and u_pass):
        st.warning("左側のサイドバーで社員番号とパスワードを入力し、認証ボタンを押してください。")
        return

    all_data = load_data_cached()
    
    # ニックネームの特定（最新の登録を優先）
    latest_nicks = {}
    if not all_data.empty:
        rdf_sorted = all_data.sort_values("entry_date", ascending=True)
        for _, row in rdf_sorted.iterrows():
            eid = str(row['real_name'])
            nick = str(row['nickname'])
            if nick.strip() != "" and nick != eid and nick != "nan" and nick != "0":
                latest_nicks[eid] = nick

    current_nickname = latest_nicks.get(str(saved_emp_id), str(saved_emp_id))
    user_records = all_data[all_data['real_name'].astype(str) == str(saved_emp_id)].copy()
    user_records['points'] = pd.to_numeric(user_records['points'], errors='coerce').fillna(0)
    user_total_pts = user_records['points'].sum()

    tab1, tab2, tab3, tab4 = st.tabs(["📊 今日の記録", "🏆 ランキング", "📈 マイデータ", "⚙️ 設定"])

    # --- タブ1: 今日の記録 ---
    with tab1:
        # ポイント前後に半角スペース
        st.write(f"### {current_nickname}さんのこれまでのポイントは {user_total_pts:g} です")
        
        target_date = st.date_input("対象日（７日前まで遡って登録、修正が出来ます）", 
                                     value=date.today(), 
                                     min_value=date.today()-timedelta(days=7), 
                                     max_value=date.today())

        @st.fragment
        def record_ui():
            st.divider()
            status_placeholder = st.empty()
            col_inv, col_debt = st.columns(2)
            with col_inv:
                st.markdown("#### 🟢 投資型 (自己投資)")
                sel_inv = [item for item in INVESTMENT_ITEMS if st.checkbox(item, key=f"inv_{item}")]
            with col_debt:
                st.markdown("#### 🔴 借金型 (即時快楽)")
                sel_debt = [item for item in DEBT_ITEMS if st.checkbox(item, key=f"debt_{item}")]
            
            n_inv, n_debt = len(sel_inv), len(sel_debt)
            inv_stars = "★" * min(n_inv, 10) + "☆" * max(0, 10 - n_inv)
            debt_stars = "★" * min(n_debt, 10) + "☆" * max(0, 10 - n_debt)
            inv_label = f"{n_inv}個実施" if n_inv <= 10 else "10個以上実施"
            debt_label = f"{n_debt}個実施" if n_debt <= 10 else "10個以上実施"

            with status_placeholder.container():
                sc1, sc2 = st.columns(2)
                with sc1:
                    st.markdown(f"""<div class="status-card"><div class="status-label" style="color:#0066cc;">投資型ステータス</div>
                                <div class="star-display" style="color:#00cc99;">{inv_stars}</div><div class="status-count">{inv_label}</div></div>""", unsafe_allow_html=True)
                with sc2:
                    st.markdown(f"""<div class="status-card"><div class="status-label" style="color:#cc3333;">借金型ステータス</div>
                                <div class="star-display" style="color:#ff4b4b;">{debt_stars}</div><div class="status-count">{debt_label}</div></div>""", unsafe_allow_html=True)

            st.divider()
            day_count = n_inv - n_debt
            st.metric("本日のポイント累計", f"{day_count:+d} アクション")

            if st.button("この内容で登録する", type="primary"):
                with st.spinner("送信中..."):
                    current_all_data = conn.read(worksheet="Records", ttl="0s")
                    past_pts = pd.to_numeric(current_all_data[(current_all_data['real_name'].astype(str) == str(saved_emp_id)) & (current_all_data['date'] != str(target_date))]['points'], errors='coerce').sum()
                    
                    new_row = pd.DataFrame([{
                        "real_name": saved_emp_id, "password": make_hash(u_pass), "nickname": current_nickname, 
                        "team": "", "date": str(target_date), "points": day_count, 
                        "total_points": past_pts + day_count, "entry_date": str(datetime.now()),
                        "investment_items": ", ".join(sel_inv), "debt_items": ", ".join(sel_debt)
                    }])
                    
                    updated_df = pd.concat([current_all_data[~((current_all_data['real_name'].astype(str) == str(saved_emp_id)) & (current_all_data['date'] == str(target_date)))], new_row]).reset_index(drop=True)
                    conn.update(worksheet="Records", data=updated_df)
                    st.cache_data.clear()
                    st.balloons()
                    st.success("登録しました！")
                    time.sleep(2)
                    st.rerun()
        record_ui()

    # --- タブ2: ランキング (ヘッダーとデータのセンタリング徹底) ---
    with tab2:
        st.markdown("<h3 style='text-align: center;'>🏆 累計ポイントランキング</h3>", unsafe_allow_html=True)
        
        if not all_data.empty:
            rdf = all_data.copy()
            rdf["points"] = pd.to_numeric(rdf["points"], errors='coerce').fillna(0)
            rdf["表示名"] = rdf["real_name"].astype(str).map(lambda x: latest_nicks.get(x, x))
            
            summary = rdf.groupby("表示名")["points"].sum().reset_index()
            summary = summary.rename(columns={"points": "ポイント累計", "表示名": "ニックネーム"})
            
            # 順位計算：method='min'（競技方式: 1-2-2-5）
            summary["順位"] = summary["ポイント累計"].rank(ascending=False, method='min').astype(int)
            summary = summary.sort_values("順位").reset_index(drop=True)
            summary = summary[["順位", "ニックネーム", "ポイント累計"]]
            
            # データフレームの表示設定
            st.dataframe(
                summary, 
                use_container_width=True, 
                hide_index=True,
                column_config={
                    "順位": st.column_config.NumberColumn("順位", alignment="center"),
                    "ニックネーム": st.column_config.TextColumn("ニックネーム", alignment="center"),
                    "ポイント累計": st.column_config.NumberColumn("ポイント累計", alignment="center"),
                }
            )

    # --- タブ3: マイデータ ---
    with tab3:
        st.subheader("🗓 履歴カレンダー")
        if 'cal_year' not in st.session_state:
            st.session_state.cal_year, st.session_state.cal_month = date.today().year, date.today().month
        
        nav_col1, nav_col2, nav_col3 = st.columns([1, 2, 1])
        with nav_col1:
            if st.button("⬅️ 前の月"):
                st.session_state.cal_month -= 1
                if st.session_state.cal_month == 0: st.session_state.cal_month, st.session_state.cal_year = 12, st.session_state.cal_year - 1
                st.rerun()
        with nav_col2: st.markdown(f"<h3 style='text-align: center;'>{st.session_state.cal_year}年 {st.session_state.cal_month}月</h3>", unsafe_allow_html=True)
        with nav_col3:
            if st.button("次の月 ➡️"):
                st.session_state.cal_month += 1
                if st.session_state.cal_month == 13: st.session_state.cal_month, st.session_state.cal_year = 1, st.session_state.cal_year + 1
                st.rerun()

        cal = calendar.monthcalendar(st.session_state.cal_year, st.session_state.cal_month)
        cols = st.columns(7)
        for i, d in enumerate(["月", "火", "水", "木", "金", "土", "日"]): cols[i].markdown(f"<div class='cal-day-header'>{d}</div>", unsafe_allow_html=True)

        for week in cal:
            cols = st.columns(7)
            for i, day in enumerate(week):
                if day != 0:
                    target_str = f"{st.session_state.cal_year}-{st.session_state.cal_month:02d}-{day:02d}"
                    has_data = not user_records[user_records['date'] == target_str].empty
                    if cols[i].button(f"{day} 🔴" if has_data else f"{day}", key=f"btn_{target_str}", use_container_width=True):
                        st.session_state.selected_cal_date = target_str

        if st.session_state.get('selected_cal_date'):
            st.divider()
            detail = user_records[user_records['date'] == st.session_state.selected_cal_date]
            if not detail.empty:
                st.markdown(f"#### 📅 {st.session_state.selected_cal_date} の詳細")
                st.write(f"**ポイント:** {detail.iloc[0]['points']:+g}")
                c1, c2 = st.columns(2)
                with c1: st.write("**🟢 投資型:**"); st.write(detail.iloc[0].get('investment_items', "なし"))
                with c2: st.write("**🔴 借金型:**"); st.write(detail.iloc[0].get('debt_items', "なし"))
            else: st.info("データはありません。")

        st.divider()
        if st.button("全ての履歴を表示／非表示"): st.session_state.show_history = not st.session_state.get('show_history', False)
        if st.session_state.get('show_history'):
            st.dataframe(user_records.sort_values("date", ascending=False)[['date', 'points', 'investment_items', 'debt_items']].rename(columns={'date':'日付','points':'ポイント','investment_items':'投資型','debt_items':'借金型'}), hide_index=True, use_container_width=True)

    # --- タブ4: 設定 ---
    with tab4:
        st.subheader("⚙️ ユーザー設定")
        st.info(f"社員番号: {saved_emp_id}")
        new_nick = st.text_input("ニックネームの登録・変更", value=current_nickname if current_nickname != str(saved_emp_id) else "")
        
        if st.button("設定を保存"):
            if new_nick.strip():
                with st.spinner("設定中..."):
                    current_all_data = conn.read(worksheet="Records", ttl="0s")
                    mask = current_all_data['real_name'].astype(str) == str(saved_emp_id)
                    if mask.any(): current_all_data.loc[mask, 'nickname'] = new_nick
                    else:
                        new_entry = pd.DataFrame([{"real_name": saved_emp_id, "password": make_hash(u_pass), "nickname": new_nick, "date": "SETTING", "points": 0, "total_points": 0, "entry_date": str(datetime.now()), "investment_items": "", "debt_items": ""}])
                        current_all_data = pd.concat([current_all_data, new_entry])
                    conn.update(worksheet="Records", data=current_all_data)
                    st.cache_data.clear() 
                    st.success("設定を保存しました。")
                    time.sleep(1); st.rerun()

if __name__ == "__main__":
    main()
