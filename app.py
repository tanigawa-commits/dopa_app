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
    .star-display {
        font-size: 26px;
        letter-spacing: 2px;
        margin: 5px 0;
    }
    .status-label {
        font-size: 16px;
        font-weight: bold;
    }
    .status-count {
        font-size: 14px;
        color: #5e6064;
    }
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
        # investment_items と debt_items を含む初期構成
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

TEAM_OPTIONS = ["-- 選択してください --", "経営層", "第一システム部", "第二システム部", "第三システム部", "第四システム部", "営業部", "総務部", "新人"]

# --- 3. メイン処理 ---
def main():
    st.title("Dopamine Tracker")
    st.subheader("今日の行動を記録して、脳の健康状態を可視化しましょう")
    
    saved_real_name = st.query_params.get("rn", "")
    saved_nickname = st.query_params.get("nn", "")
    saved_team = st.query_params.get("t", TEAM_OPTIONS[0])
    
    with st.sidebar:
        st.header("🔑 ユーザー認証")
        u_real_name = st.text_input("氏名（実名）", value=saved_real_name)
        u_pass = st.text_input("パスワード", type="password")
        u_nickname = st.text_input("ニックネーム", value=saved_nickname)
        t_name = st.selectbox("所属チーム", TEAM_OPTIONS, index=TEAM_OPTIONS.index(saved_team) if saved_team in TEAM_OPTIONS else 0)
        
        if st.button("認証"):
            if not u_real_name or not u_pass or not u_nickname or t_name == TEAM_OPTIONS[0]:
                st.error("全項目を入力してください。")
            else:
                st.query_params.update(rn=u_real_name, nn=u_nickname, t=t_name)
                st.rerun()

    if not (saved_real_name and saved_nickname and u_pass):
        st.warning("左側のサイドバーで情報を入力し、認証ボタンを押してください。")
        return

    all_data = load_data_cached()
    user_records = all_data[all_data['real_name'] == saved_real_name].copy()
    user_total_pts = user_records['points'].sum()

    tab1, tab2, tab3 = st.tabs(["📊 今日の記録", "🏆 ランキング", "📈 マイデータ"])

    # --- タブ1: 記録 ---
    with tab1:
        st.write(f"### {saved_nickname}さんのこれまでのポイントは{user_total_pts:g}です")
        target_date = st.date_input("対象日（２日前まで修正可）", value=date.today(), min_value=date.today()-timedelta(days=2), max_value=date.today())

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

            if st.button("この内容で決算する", type="primary"):
                with st.spinner("送信中..."):
                    current_all_data = conn.read(worksheet="Records", ttl="0s")
                    past_points = current_all_data[(current_all_data['real_name'] == saved_real_name) & (current_all_data['date'] != str(target_date))]['points'].sum()
                    
                    new_row = pd.DataFrame([{
                        "real_name": saved_real_name, "password": make_hash(u_pass), "nickname": saved_nickname, 
                        "team": saved_team, "date": str(target_date), "points": day_count, 
                        "total_points": past_points + day_count, "entry_date": str(date.today()),
                        "investment_items": ", ".join(sel_inv), # 分割保存
                        "debt_items": ", ".join(sel_debt)      # 分割保存
                    }])
                    
                    # 古い構成（selected_items）の列がある場合は削除して更新
                    if 'selected_items' in current_all_data.columns:
                        current_all_data = current_all_data.drop(columns=['selected_items'])
                        
                    updated_df = pd.concat([current_all_data[~((current_all_data['real_name'] == saved_real_name) & (current_all_data['date'] == str(target_date)))], new_row]).reset_index(drop=True)
                    conn.update(worksheet="Records", data=updated_df)
                    st.cache_data.clear()
                    st.balloons()
                    st.success("決算が完了しました！")
                    time.sleep(2)
                    st.rerun()
        record_ui()

    # --- タブ2: ランキング ---
    with tab2:
        st.subheader("🏆 累計アクション収支ランキング")
        if not all_data.empty:
            rdf = all_data.groupby(['nickname', 'team'])['points'].sum().reset_index()
            st.dataframe(rdf.sort_values("points", ascending=False).rename(columns={'points':'累計収支'}), use_container_width=True, hide_index=True)

    # --- タブ3: マイデータ（カレンダー表示） ---
    with tab3:
        st.subheader("🗓 履歴カレンダー")
        
        if 'cal_year' not in st.session_state:
            st.session_state.cal_year = date.today().year
            st.session_state.cal_month = date.today().month
        if 'selected_cal_date' not in st.session_state:
            st.session_state.selected_cal_date = None
        if 'show_all_history' not in st.session_state:
            st.session_state.show_all_history = False

        # 月のナビゲーション
        nav_col1, nav_col2, nav_col3 = st.columns([1, 2, 1])
        with nav_col1:
            if st.button("⬅️ 前の月"):
                st.session_state.cal_month -= 1
                if st.session_state.cal_month == 0:
                    st.session_state.cal_month = 12
                    st.session_state.cal_year -= 1
                st.rerun()
        with nav_col2:
            st.markdown(f"<h3 style='text-align: center;'>{st.session_state.cal_year}年 {st.session_state.cal_month}月</h3>", unsafe_allow_html=True)
        with nav_col3:
            if st.button("次の月 ➡️"):
                st.session_state.cal_month += 1
                if st.session_state.cal_month == 13:
                    st.session_state.cal_month = 1
                    st.session_state.cal_year += 1
                st.rerun()

        # カレンダー生成
        cal = calendar.monthcalendar(st.session_state.cal_year, st.session_state.cal_month)
        days = ["月", "火", "水", "木", "金", "土", "日"]
        cols = st.columns(7)
        for i, d in enumerate(days):
            cols[i].markdown(f"<div class='cal-day-header'>{d}</div>", unsafe_allow_html=True)

        for week in cal:
            cols = st.columns(7)
            for i, day in enumerate(week):
                if day == 0:
                    cols[i].write("")
                else:
                    target_str = f"{st.session_state.cal_year}-{st.session_state.cal_month:02d}-{day:02d}"
                    has_data = not user_records[user_records['date'] == target_str].empty
                    label = f"{day} 🔴" if has_data else f"{day}"
                    if cols[i].button(label, key=f"btn_{target_str}", use_container_width=True):
                        st.session_state.selected_cal_date = target_str

        # 特定日の詳細表示（投資型・借金型を分けて表示）
        if st.session_state.selected_cal_date:
            st.divider()
            detail = user_records[user_records['date'] == st.session_state.selected_cal_date]
            if not detail.empty:
                st.markdown(f"#### 📅 {st.session_state.selected_cal_date} の詳細")
                st.write(f"**収支ポイント:** {detail.iloc[0]['points']:+g}")
                
                det_c1, det_c2 = st.columns(2)
                with det_c1:
                    st.write("**🟢 投資型項目:**")
                    inv_raw = detail.iloc[0].get('investment_items', "")
                    st.write(inv_raw if pd.notna(inv_raw) and str(inv_raw) != "" else "なし")
                with det_c2:
                    st.write("**🔴 借金型項目:**")
                    debt_raw = detail.iloc[0].get('debt_items', "")
                    st.write(debt_raw if pd.notna(debt_raw) and str(debt_raw) != "" else "なし")
            else:
                st.info(f"{st.session_state.selected_cal_date} のデータはありません。")

        # --- 全ての履歴表示ボタン ---
        st.divider()
        if st.button("全ての履歴を表示／非表示"):
            st.session_state.show_all_history = not st.session_state.show_all_history

        if st.session_state.show_all_history:
            if not user_records.empty:
                st.markdown("#### 📋 全登録データ一覧")
                h_df = user_records.sort_values("date", ascending=False).copy()
                st.dataframe(
                    h_df[['date', 'points', 'investment_items', 'debt_items']].rename(
                        columns={'date': '日付', 'points': '収支', 'investment_items': '投資型項目', 'debt_items': '借金型項目'}
                    ),
                    hide_index=True,
                    use_container_width=True
                )
            else:
                st.info("データがまだありません。")

if __name__ == "__main__":
    main()
