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
        font-size: 28px;
        margin: 5px 0;
    }
    .status-label {
        font-size: 16px;
        font-weight: bold;
    }
    </style>
    """, unsafe_allow_html=True)

def make_hash(password):
    return hashlib.sha256(str.encode(password)).hexdigest()

# 読み込みを高速化するためのキャッシュ（TTLを1分に設定）
@st.cache_data(ttl=60)
def load_data_cached():
    try:
        df = conn.read(worksheet="Records", ttl="1m")
        return df
    except:
        return pd.DataFrame(columns=["real_name", "password", "nickname", "team", "date", "points", "total_points", "entry_date", "selected_items"])

# --- 2. リスト・マスタ定義 ---
INVESTMENT_ITEMS = [
    "経験のない事への挑戦", "料理", "掃除", "睡眠が8時間以上", "入浴、サウナ", 
    "朝10分前に出社", "身体を動かす", "勉強", "読書", "創作活動"
]

DEBT_ITEMS = [
    "倫理観に欠ける行動", "外食オンリー", "掃除をしない", "睡眠が6時間未満", 
    "シャワーのみ/風呂抜き", "朝ギリギリに出社", "過度な飲酒", "食後の間食", 
    "ドカ食い(2000kcal+)", "動画見ながらお菓子"
]

TEAM_OPTIONS = ["-- 選択してください --", "経営層", "第一システム部", "第二システム部", "第三システム部", "第四システム部", "営業部", "総務部", "新人"]

# --- 3. メイン処理 ---
def main():
    st.title("🧠 脳内ドーパミン収支報告")
    st.subheader("幸せホルモンを育てよう！")
    
    # URLパラメータからユーザー情報を取得
    saved_real_name = st.query_params.get("rn", "")
    saved_nickname = st.query_params.get("nn", "")
    saved_team = st.query_params.get("t", TEAM_OPTIONS[0])
    
    # サイドバー：認証
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

    # ログイン済みのデータ読み込み
    all_data = load_data_cached()

    tab1, tab2, tab3 = st.tabs(["📊 今日の記録", "🏆 ランキング", "📈 マイデータ"])

    with tab1:
        st.write(f"### 投資と借金のバランスを整えましょう、{u_nickname} さん")
        target_date = st.date_input("対象日（２日前まで修正可）", value=date.today(), min_value=date.today()-timedelta(days=2), max_value=date.today())

        # --- 部分更新（Fragment）の定義 ---
        # これによりチェックボックスを触っても全データ再読み込みが走りません
        @st.fragment
        def record_ui():
            st.divider()
            c1, c2 = st.columns(2)
            
            # コンテナを作成して動的に中身を更新
            status_placeholder = st.empty()
            
            st.write("") # スペース
            
            col_inv, col_debt = st.columns(2)
            
            with col_inv:
                st.markdown("#### 🟢 投資型 (自己投資)")
                sel_inv = []
                for item in INVESTMENT_ITEMS:
                    if st.checkbox(item, key=f"v2_inv_{item}"):
                        sel_inv.append(item)

            with col_debt:
                st.markdown("#### 🔴 借金型 (即時快楽)")
                sel_debt = []
                for item in DEBT_ITEMS:
                    if st.checkbox(item, key=f"v2_debt_{item}"):
                        sel_debt.append(item)
            
            # ステータスカードのリアルタイム更新
            n_inv = len(sel_inv)
            n_debt = len(sel_debt)
            inv_stars = "★" * min(n_inv, 10) + "☆" * max(0, 10 - n_inv)
            debt_stars = "★" * min(n_debt, 10) + "☆" * max(0, 10 - n_debt)

            with status_placeholder.container():
                sc1, sc2 = st.columns(2)
                with sc1:
                    st.markdown(f"""<div class="status-card"><div class="status-label" style="color:#0066cc;">投資型ステータス</div>
                                <div class="star-display" style="color:#00cc99;">{inv_stars}</div><div class="status-count">{n_inv}個達成</div></div>""", unsafe_allow_html=True)
                with sc2:
                    st.markdown(f"""<div class="status-card"><div class="status-label" style="color:#cc3333;">借金型ステータス</div>
                                <div class="star-display" style="color:#ff4b4b;">{debt_stars}</div><div class="status-count">{n_debt}個実行</div></div>""", unsafe_allow_html=True)

            st.divider()
            day_count = n_inv - n_debt
            st.metric("本日の収支累計", f"{day_count:+d} アクション")

            if st.button("この内容で決算する", type="primary"):
                with st.spinner("スプレッドシートに書き込み中..."):
                    # 保存時のみ、最新の全データを（キャッシュなしで）読み込んで更新
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
                    st.cache_data.clear() # 保存後はキャッシュをクリア
                    st.balloons()
                    st.success("決算が完了しました！")
                    time.sleep(2)
                    st.rerun()

        # UIの呼び出し
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
