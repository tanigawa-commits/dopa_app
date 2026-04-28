import streamlit as st
import pandas as pd
from datetime import datetime, date, timedelta
from streamlit_gsheets import GSheetsConnection
import hashlib
import time

# --- 1. アプリ設定とDB接続 ---
st.set_page_config(page_title="Dopa-Balance Pro", layout="wide")
conn = st.connection("gsheets", type=GSheetsConnection)

# カスタムCSS：ステータスカードのデザイン調整
st.markdown("""
    <style>
    .status-card {
        border: 1px solid #e6e9ef;
        border-radius: 15px;
        padding: 20px;
        text-align: center;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.05);
        background-color: white;
        margin-bottom: 20px;
    }
    .star-display {
        font-size: 32px;
        color: #ff4b4b; /* 借金用は赤、投資用は青に動的に変える */
        margin: 10px 0;
    }
    .status-label {
        font-size: 18px;
        font-weight: bold;
        color: #31333F;
    }
    .status-count {
        font-size: 14px;
        color: #5e6064;
    }
    </style>
    """, unsafe_allow_html=True)

def make_hash(password):
    return hashlib.sha256(str.encode(password)).hexdigest()

def load_data():
    try:
        df = conn.read(worksheet="Records", ttl="0m")
        expected_cols = ["real_name", "password", "nickname", "team", "date", "points", "total_points", 
                         "entry_date", "selected_items"]
        for col in expected_cols:
            if col not in df.columns:
                df[col] = 0
        return df
    except:
        return pd.DataFrame(columns=["real_name", "password", "nickname", "team", "date", "points", "total_points", 
                                     "entry_date", "selected_items"])

# --- 2. リスト・マスタ定義 ---
TEAM_OPTIONS = ["-- 選択してください --", "経営層", "第一システム部", "第二システム部", "第三システム部", "第四システム部", "営業部", "総務部", "新人"]

INVESTMENT_ITEMS = [
    "経験のない事への挑戦", "料理", "掃除", "睡眠が8時間以上", "入浴、サウナ", 
    "朝10分前に出社", "身体を動かす", "勉強", "読書", "創作活動"
]

DEBT_ITEMS = [
    "倫理観に欠ける行動", "外食オンリー", "掃除をしない", "睡眠が6時間未満", 
    "シャワーのみ/風呂抜き", "朝ギリギリに出社", "過度な飲酒", "食後の間食", 
    "ドカ食い(2000kcal+)", "動画見ながらお菓子"
]

# --- 3. メイン処理 ---
def main():
    st.title("🧠 脳内ドーパミン収支報告")
    st.subheader("幸せホルモンを育てよう！")
    
    saved_real_name = st.query_params.get("rn", "")
    saved_nickname = st.query_params.get("nn", "")
    saved_team = st.query_params.get("t", TEAM_OPTIONS[0])
    
    all_data = load_data()

    with st.sidebar:
        st.header("🔑 ユーザー認証")
        u_real_name = st.text_input("氏名（実名）", value=saved_real_name, key="login_rn")
        u_pass = st.text_input("パスワード", type="password", key="login_pw")
        u_nickname = st.text_input("ニックネーム", value=saved_nickname, key="login_nn")
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

    tab1, tab2, tab3 = st.tabs(["📊 今日の記録", "🏆 ランキング", "📈 マイデータ"])

    with tab1:
        st.write(f"### 投資と借金のバランスを整えましょう、{u_nickname} さん")
        target_date = st.date_input("対象日（２日前まで修正可）", value=date.today(), min_value=date.today()-timedelta(days=2), max_value=date.today())

        # --- 選択状態の管理 ---
        if 'selected_inv' not in st.session_state: st.session_state.selected_inv = []
        if 'selected_debt' not in st.session_state: st.session_state.selected_debt = []

        # --- ステータスカード表示領域 ---
        c1, c2 = st.columns(2)
        
        # 投資型ステータス
        n_inv = len(st.session_state.selected_inv)
        inv_stars = "★" * min(n_inv, 10) + "☆" * max(0, 10 - n_inv)
        with c1:
            st.markdown(f"""
                <div class="status-card">
                    <div class="status-label" style="color:#0066cc;">投資型ステータス</div>
                    <div class="star-display" style="color:#00cc99;">{inv_stars}</div>
                    <div class="status-count">{n_inv}個達成</div>
                </div>
                """, unsafe_allow_html=True)

        # 借金型ステータス
        n_debt = len(st.session_state.selected_debt)
        debt_stars = "★" * min(n_debt, 10) + "☆" * max(0, 10 - n_debt)
        with c2:
            st.markdown(f"""
                <div class="status-card">
                    <div class="status-label" style="color:#cc3333;">借金型ステータス</div>
                    <div class="star-display" style="color:#ff4b4b;">{debt_stars}</div>
                    <div class="status-count">{n_debt}個実行</div>
                </div>
                """, unsafe_allow_html=True)

        st.divider()

        # --- メイン選択領域 ---
        col_inv, col_debt = st.columns(2)
        
        with col_inv:
            st.markdown("#### 🟢 投資型 (自己投資)")
            temp_inv = []
            for item in INVESTMENT_ITEMS:
                if st.checkbox(item, key=f"chk_inv_{item}"):
                    temp_inv.append(item)
            st.session_state.selected_inv = temp_inv

        with col_debt:
            st.markdown("#### 🔴 借金型 (即時快楽)")
            temp_debt = []
            for item in DEBT_ITEMS:
                if st.checkbox(item, key=f"chk_debt_{item}"):
                    temp_debt.append(item)
            st.session_state.selected_debt = temp_debt

        st.divider()
        
        day_count = len(st.session_state.selected_inv) - len(st.session_state.selected_debt)
        st.metric("本日の収支累計", f"{day_count:+d} アクション")

        if st.button("この内容で決算する", type="primary"):
            selected_items_str = ", ".join(st.session_state.selected_inv + st.session_state.selected_debt)
            past_points = all_data[(all_data['real_name'] == u_real_name) & (all_data['date'] != str(target_date))]['points'].sum()
            
            new_row = pd.DataFrame([{
                "real_name": u_real_name, "password": make_hash(u_pass), "nickname": u_nickname, 
                "team": t_name, "date": str(target_date), "points": day_count, 
                "total_points": past_points + day_count, "entry_date": str(date.today()),
                "selected_items": selected_items_str
            }])
            
            updated_df = pd.concat([all_data[~((all_data['real_name'] == u_real_name) & (all_data['date'] == str(target_date)))], new_row]).reset_index(drop=True)
            conn.update(worksheet="Records", data=updated_df)
            
            st.balloons()
            st.success("決算が完了しました！")
            time.sleep(3)
            st.rerun()

    with tab2:
        if not all_data.empty:
            st.subheader("🏆 累計アクション収支ランキング")
            rdf = all_data.groupby(['nickname', 'team'])['points'].sum().reset_index()
            st.dataframe(rdf.sort_values("points", ascending=False).rename(columns={'points':'累計収支'}), use_container_width=True, hide_index=True)

    with tab3:
        udata = all_data[all_data['real_name'] == u_real_name].copy()
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
