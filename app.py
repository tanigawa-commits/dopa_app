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

# カスタムCSS（基本デザインのみ）
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

@st.cache_data(ttl=60)
def load_data_cached(sheet_name):
    try:
        return conn.read(worksheet=sheet_name, ttl="1m")
    except:
        if sheet_name == "UserMaster":
            return pd.DataFrame(columns=["email", "emp_id"])
        return pd.DataFrame(columns=["real_name", "nickname", "date", "points", "total_points", "entry_date", "investment_items", "debt_items"])

# --- 2. リスト定義 ---
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

    # --- 認証セクション ---
    # Streamlit CloudのPrivate設定時に有効。ローカル開発時は代替手段が必要。
    login_email = st.user.email 

    if not login_email:
        st.error("GoogleアカウントでStreamlitにログインしてください。")
        st.info("※アプリをPrivate設定にし、ユーザを招待する必要があります。")
        # ローカルデバッグ用（本番時は消してください）
        # login_email = "test@example.com" 
        return

    # マスタと記録の読み込み
    user_master = load_data_cached("UserMaster")
    all_data = load_data_cached("Records")

    # ログイン中のメールアドレスが登録済みか確認
    registered_row = user_master[user_master['email'] == login_email]

    if registered_row.empty:
        # 【未登録】初回紐づけ画面
        st.warning(f"ようこそ {login_email} さん。初回登録が必要です。")
        new_emp_id = st.text_input("あなたの社員番号(4桁)を入力してください", max_chars=4)
        
        if st.button("この社員番号で利用開始する"):
            if not new_emp_id or len(new_emp_id) != 4:
                st.error("社員番号は4桁で入力してください。")
            elif new_emp_id in user_master['emp_id'].astype(str).values:
                st.error("その社員番号は既に他のアカウントに紐づけられています。")
            else:
                # UserMasterへ書き込み
                new_user_df = pd.DataFrame([{"email": login_email, "emp_id": new_emp_id}])
                updated_master = pd.concat([user_master, new_user_df]).reset_index(drop=True)
                conn.update(worksheet="UserMaster", data=updated_master)
                st.success("紐づけが完了しました！")
                st.cache_data.clear()
                time.sleep(1)
                st.rerun()
        return # 登録完了までメイン画面は出さない
    
    # 【登録済み】社員番号を特定
    current_emp_id = str(registered_row.iloc[0]['emp_id'])

    # --- アプリ本体ロジック ---
    user_records = all_data[all_data['real_name'].astype(str) == current_emp_id].copy()
    user_records['points'] = pd.to_numeric(user_records['points'], errors='coerce').fillna(0)
    user_total_pts = user_records['points'].sum()

    # ニックネームの特定（Recordsシートから最新のものを取得）
    current_nickname = current_emp_id
    if not user_records.empty:
        valid_nick_df = user_records[user_records['nickname'].notna() & (user_records['nickname'] != "")].sort_values("entry_date")
        if not valid_nick_df.empty:
            current_nickname = valid_nick_df.iloc[-1]['nickname']

    tab1, tab2, tab3, tab4 = st.tabs(["📊 今日の記録", "🏆 ランキング", "📈 マイデータ", "⚙️ 設定"])

    # --- タブ1: 今日の記録 ---
    with tab1:
        st.write(f"### {current_nickname}さんのこれまでのポイントは {user_total_pts:g} です")
        
        target_date = st.date_input("対象日（７日前まで登録・修正可能）", 
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
                with st.spinner("登録中..."):
                    current_all_records = conn.read(worksheet="Records", ttl="0s")
                    past_pts = pd.to_numeric(current_all_records[(current_all_records['real_name'].astype(str) == current_emp_id) & (current_all_records['date'] != str(target_date))]['points'], errors='coerce').sum()
                    
                    new_row = pd.DataFrame([{
                        "real_name": current_emp_id, "nickname": current_nickname, 
                        "date": str(target_date), "points": day_count, 
                        "total_points": past_pts + day_count, "entry_date": str(datetime.now()),
                        "investment_items": ", ".join(sel_inv), "debt_items": ", ".join(sel_debt)
                    }])
                    
                    updated_df = pd.concat([current_all_records[~((current_all_records['real_name'].astype(str) == current_emp_id) & (current_all_records['date'] == str(target_date)))], new_row]).reset_index(drop=True)
                    conn.update(worksheet="Records", data=updated_df)
                    st.cache_data.clear(); st.balloons(); st.success("登録しました！"); time.sleep(1); st.rerun()
        record_ui()

    # --- タブ2: ランキング (左寄せ・競技方式順位) ---
    with tab2:
        st.subheader("🏆 累計ポイントランキング")
        if not all_data.empty:
            rdf = all_data.copy()
            rdf["points"] = pd.to_numeric(rdf["points"], errors='coerce').fillna(0)
            
            # 各社員番号の最新ニックネームをマッピング
            nick_map = rdf[rdf['nickname'].notna() & (rdf['nickname'] != "")].sort_values("entry_date").groupby("real_name")["nickname"].last().to_dict()
            rdf["表示名"] = rdf["real_name"].astype(str).map(lambda x: nick_map.get(x, x))
            
            summary = rdf.groupby("表示名")["points"].sum().reset_index()
            summary = summary.rename(columns={"points": "ポイント累計", "表示名": "ニックネーム"})
            
            # 競技順位 (1, 2, 2, 5)
            summary["順位"] = summary["ポイント累計"].rank(ascending=False, method='min').astype(int)
            summary = summary.sort_values("順位").reset_index(drop=True)
            summary = summary[["順位", "ニックネーム", "ポイント累計"]]
            
            st.dataframe(
                summary, use_container_width=True, hide_index=True,
                column_config={
                    "順位": st.column_config.NumberColumn(alignment="left"),
                    "ニックネーム": st.column_config.TextColumn(alignment="left"),
                    "ポイント累計": st.column_config.NumberColumn(alignment="left"),
                }
            )

    # --- タブ3: マイデータ ---
    with tab3:
        st.subheader("🗓 履歴カレンダー")
        if 'cal_year' not in st.session_state:
            st.session_state.cal_year, st.session_state.cal_month = date.today().year, date.today().month
        
        # カレンダーナビゲーション
        nav_c1, nav_c2, nav_c3 = st.columns([1, 2, 1])
        with nav_c1:
            if st.button("⬅️ 前の月"):
                st.session_state.cal_month -= 1
                if st.session_state.cal_month == 0: st.session_state.cal_month, st.session_state.cal_year = 12, st.session_state.cal_year - 1
                st.rerun()
        with nav_c2: st.markdown(f"<h3 style='text-align: center;'>{st.session_state.cal_year}年 {st.session_state.cal_month}月</h3>", unsafe_allow_html=True)
        with nav_c3:
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

    # --- タブ4: 設定 (ニックネーム変更) ---
    with tab4:
        st.subheader("⚙️ ユーザー設定")
        st.info(f"ログインアカウント: {login_email}\n社員番号: {current_emp_id}")
        new_nick = st.text_input("ニックネームの変更", value=current_nickname if current_nickname != current_emp_id else "")
        if st.button("設定を保存"):
            if new_nick.strip():
                with st.spinner("更新中..."):
                    current_all_records = conn.read(worksheet="Records", ttl="0s")
                    mask = current_all_records['real_name'].astype(str) == current_emp_id
                    if mask.any(): current_all_records.loc[mask, 'nickname'] = new_nick
                    else:
                        # まだ記録がない場合、名前登録用のダミーレコード
                        new_row = pd.DataFrame([{"real_name": current_emp_id, "nickname": new_nick, "date": "SETTING", "points": 0, "entry_date": str(datetime.now())}])
                        current_all_records = pd.concat([current_all_records, new_row])
                    conn.update(worksheet="Records", data=current_all_records)
                    st.cache_data.clear(); st.success("保存しました。"); time.sleep(1); st.rerun()

if __name__ == "__main__":
    main()
