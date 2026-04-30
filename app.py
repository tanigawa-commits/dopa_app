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

# カスタムCSS
st.markdown("""
    <style>
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
    </style>
    """, unsafe_allow_html=True)

def make_hash(password):
    return hashlib.sha256(str.encode(password)).hexdigest()

@st.cache_data(ttl=60)
def load_data_cached():
    try:
        return conn.read(worksheet="Records", ttl="1m")
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
                st.error("全項目を入力してください。")
            else:
                st.query_params.update(eid=u_emp_id)
                st.rerun()

    if not (saved_emp_id and u_pass):
        st.warning("左側のサイドバーで社員番号とパスワードを入力し、認証ボタンを押してください。")
        return

    all_data = load_data_cached()
    user_records = all_data[all_data['real_name'] == saved_emp_id].copy()
    user_total_pts = user_records['points'].sum()
    
    # --- 最新のニックネームを特定するロジック ---
    # 空でない有効なニックネームを全データから取得（社員番号でないもの）
    latest_nicks = all_data.sort_values("entry_date").groupby("real_name")["nickname"].last().to_dict()
    current_nickname = latest_nicks.get(saved_emp_id, saved_emp_id)
    # もし取得した名前が社員番号と同じか空なら、社員番号を表示
    if not current_nickname or current_nickname == saved_emp_id:
        current_nickname = saved_emp_id

    tab1, tab2, tab3, tab4 = st.tabs(["📊 今日の記録", "🏆 ランキング", "📈 マイデータ", "⚙️ 設定"])

    # --- タブ1: 記録 ---
    with tab1:
        st.write(f"### {current_nickname}さんのこれまでのポイントは {user_total_pts:g} です")
        # 遡り期間を7日前に変更
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
            st.metric("本日の収支累計", f"{day_count:+d} アクション")

            if st.button("この内容で登録する", type="primary"):
                with st.spinner("送信中..."):
                    current_all_data = conn.read(worksheet="Records", ttl="0s")
                    past_points = current_all_data[(current_all_data['real_name'] == saved_emp_id) & (current_all_data['date'] != str(target_date))]['points'].sum()
                    
                    new_row = pd.DataFrame([{
                        "real_name": saved_emp_id, "password": make_hash(u_pass), "nickname": current_nickname, 
                        "team": "", "date": str(target_date), "points": day_count, 
                        "total_points": past_points + day_count, "entry_date": str(date.today()),
                        "investment_items": ", ".join(sel_inv), "debt_items": ", ".join(sel_debt)
                    }])
                    
                    updated_df = pd.concat([current_all_data[~((current_all_data['real_name'] == saved_emp_id) & (current_all_data['date'] == str(target_date)))], new_row]).reset_index(drop=True)
                    conn.update(worksheet="Records", data=updated_df)
                    st.cache_data.clear()
                    st.balloons()
                    st.success("登録が完了しました！")
                    time.sleep(2)
                    st.rerun()
        record_ui()

    # --- タブ2: ランキング ---
    with tab2:
        st.subheader("🏆 累計アクション収支ランキング")
        if not all_data.empty:
            # 各社員番号の最新のニックネームをマッピングして表示
            latest_nick_map = all_data.sort_values("entry_date").groupby("real_name")["nickname"].last().to_dict()
            rdf = all_data.copy()
            rdf["ニックネーム"] = rdf["real_name"].map(latest_nick_map)
            
            summary = rdf.groupby("ニックネーム")["points"].sum().reset_index()
            summary = summary.rename(columns={"points": "累計収支"})
            st.dataframe(summary.sort_values("累計収支", ascending=False), use_container_width=True, hide_index=True)

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
                st.write(f"**収支ポイント:** {detail.iloc[0]['points']:+g}")
                c1, c2 = st.columns(2)
                with c1: st.write("**🟢 投資型:**"); st.write(detail.iloc[0].get('investment_items', "なし"))
                with c2: st.write("**🔴 借金型:**"); st.write(detail.iloc[0].get('debt_items', "なし"))
            else: st.info("データはありません。")

        st.divider()
        if st.button("全ての履歴を表示／非表示"): st.session_state.show_history = not st.session_state.get('show_history', False)
        if st.session_state.get('show_history'):
            st.dataframe(user_records.sort_values("date", ascending=False)[['date', 'points', 'investment_items', 'debt_items']].rename(columns={'date':'日付','points':'収支','investment_items':'投資型','debt_items':'借金型'}), hide_index=True, use_container_width=True)

    # --- タブ4: 設定 ---
    with tab4:
        st.subheader("⚙️ ユーザー設定")
        st.info(f"ログイン中の社員番号: {saved_emp_id}")
        new_nick = st.text_input("ニックネームの登録・変更", value=current_nickname if current_nickname != saved_emp_id else "")
        
        if st.button("設定を保存"):
            if new_nick:
                with st.spinner("設定を保存中..."):
                    current_all_data = conn.read(worksheet="Records", ttl="0s")
                    
                    # ユーザーの既存レコードがあれば全てニックネームを更新
                    if saved_emp_id in current_all_data['real_name'].values:
                        current_all_data.loc[current_all_data['real_name'] == saved_emp_id, 'nickname'] = new_nick
                    else:
                        # まだ一度も「今日の記録」をしていない場合でもニックネームを保持させる
                        dummy_row = pd.DataFrame([{
                            "real_name": saved_emp_id, "password": make_hash(u_pass), "nickname": new_nick, 
                            "date": "SETTING", "points": 0, "total_points": 0, "entry_date": str(date.today()),
                            "investment_items": "", "debt_items": ""
                        }])
                        current_all_data = pd.concat([current_all_data, dummy_row])
                    
                    conn.update(worksheet="Records", data=current_all_data)
                    st.cache_data.clear() 
                    st.success("ニックネームを更新しました！")
                    time.sleep(1)
                    st.rerun()
            else:
                st.error("ニックネームを入力してください。")

if __name__ == "__main__":
    main()
