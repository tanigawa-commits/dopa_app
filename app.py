import streamlit as st
import pandas as pd
from datetime import datetime, date, timedelta
from streamlit_gsheets import GSheetsConnection
import hashlib
import time

# --- 1. アプリ設定とDB接続 ---
st.set_page_config(page_title="Dopa-Balance Pro", layout="wide")
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
    </style>
    """, unsafe_allow_html=True)

def make_hash(password):
    return hashlib.sha256(str.encode(password)).hexdigest()

@st.cache_data(ttl=60)
def load_data_cached():
    try:
        return conn.read(worksheet="Records", ttl="1m")
    except:
        return pd.DataFrame(columns=["real_name", "password", "nickname", "team", "date", "points", "total_points", "entry_date", "selected_items"])

# --- 2. リスト・マスタ定義 (image_4ee5a8.pngの内容に更新) ---
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
    st.title("🧠 脳内ドーパミン収支報告")
    st.subheader("幸せホルモンを育てよう！")
    
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
    tab1, tab2, tab3 = st.tabs(["📊 今日の記録", "🏆 ランキング", "📈 マイデータ"])

    with tab1:
        st.write(f"### 投資と借金のバランスを整えましょう、{u_nickname} さん")
        target_date = st.date_input("対象日（２日前まで修正可）", value=date.today(), min_value=date.today()-timedelta(days=2), max_value=date.today())

        @st.fragment
        def record_ui():
            st.divider()
            # ステータス表示用プレースホルダー
            status_placeholder = st.empty()
            
            st.write("") 
            col_inv, col_debt = st.columns(2)
            
            with col_inv:
                st.markdown("#### 🟢 投資型 (自己投資)")
                sel_inv = []
                for item in INVESTMENT_ITEMS:
                    if st.checkbox(item, key=f"inv_{item}"):
                        sel_inv.append(item)

            with col_debt:
                st.markdown("#### 🔴 借金型 (即時快楽)")
                sel_debt = []
                for item in DEBT_ITEMS:
                    if st.checkbox(item, key=f"debt_{item}"):
                        sel_debt.append(item)
            
            # --- ロジック計算 ---
            n_inv = len(sel_inv)
            n_debt = len(sel_debt)
            
            # 星は常に10個表示
            inv_stars = "★" * min(n_inv, 10) + "☆" * max(0, 10 - n_inv)
            debt_stars = "★" * min(n_debt, 10) + "☆" * max(0, 10 - n_debt)
            
            # 11個以上のラベル表示切り替え
            inv_label = f"{n_inv}個達成" if n_inv <= 10 else "10個以上達成"
            debt_label = f"{n_debt}個実行" if n_debt <= 10 else "10個以上達成" # 要望に従い、借金型も達成と表記

            # ステータスカード更新
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
                    selected_items_str = ", ".join(sel_inv + sel_debt)
                    past_points = current_all_data[(current_all_data['real_name'] == saved_real_name) & (current_all_data['date'] != str(target_date))]['points'].sum()
                    
                    new_row = pd.DataFrame([{
                        "real_name": saved_real_name, "password": make_hash(u_pass), "nickname": saved_nickname, 
                        "team": saved_team, "date": str(target_date), "points": day_count, 
                        "total_points": past_points + day_count, "entry_date": str(date.today()),
                        "selected_items": selected_items_str
                    }])
                    
                    updated_df = pd.concat([current_all_data[~((current_all_data['real_name'] == saved_real_name) & (current_all_data['date'] == str(target_date)))], new_row]).reset_index(drop=True)
                    conn.update(worksheet="Records", data=updated_df)
                    st.cache_data.clear()
                    st.balloons()
                    st.success("決算が完了しました！")
                    time.sleep(2)
                    st.rerun()

        record_ui()

    with tab2:
        st.subheader("🏆 累計アクション収支ランキング")
        if not all_data.empty:
            rdf = all_data.groupby(['nickname', 'team'])['points'].sum().reset_index()
            st.dataframe(rdf.sort_values("points", ascending=False).rename(columns={'points':'累計収支'}), use_container_width=True, hide_index=True)

    with tab3:
        udata = all_data[all_data['real_name'] == saved_real_name].copy()
        if not udata.empty:
            udata['date'] = pd.to_datetime(udata['date'])
            udata = udata.sort_values("date")
            st.subheader("📈 アクション収支推移 (累積)")
            st.line_chart(udata.set_index("date")["total_points"])
            st.divider()
            st.subheader("📋 履歴詳細")
            h_df = udata.copy()
            h_df['日付'] = h_df['date'].dt.strftime('%Y-%m-%d')
            st.dataframe(h_df[['日付', 'points', 'selected_items']].rename(columns={'points':'収支','selected_items':'選択項目'}), hide_index=True, use_container_width=True)
        else:
            st.info("データがまだありません。")

if __name__ == "__main__":
    main()
