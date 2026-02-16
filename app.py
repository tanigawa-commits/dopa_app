import streamlit as st
import pandas as pd
from datetime import datetime, date, timedelta
from streamlit_gsheets import GSheetsConnection

# --- 1. アプリ設定とDB接続 ---
st.set_page_config(page_title="Dopa-Balance", layout="wide")

# スプレッドシート接続の初期化
conn = st.connection("gsheets", type=GSheetsConnection)
# スプレッドシートからデータを読み込む関数
def load_data():
    try:
        # worksheet="Records" という名前のシートを読み込む
        return conn.read(worksheet="Records", ttl="0m")
    except:
        # シートがない場合や接続できない場合は空の枠組みを返す
        return pd.DataFrame(columns=["user_id", "team", "date", "points", "entry_date"])

# --- 2. ポイントマスタ定義 ---
POINT_MASTER = {
    "資産": {
        "ウォーキング(1k歩毎)": 10, "階段利用": 30, "朝活": 50, "筋トレ": 40,
        "7h以上睡眠": 50, "脱スマホ入眠": 40, "ベジ・ファースト": 20, "休肝日": 50
    },
    "負債": {
        "SNSダラダラ": -30, "寝床スマホ": -50, "深夜ゲーム": -60,
        "ドカ食い": -40, "締めのアレ": -50, "座りっぱなし": -30
    },
    "特別利益": {
        "衝動のリセット": 100, "デトックス成功": 80, "運動への変換": 100
    }
}

# ランク判定
def get_brain_rank(points):
    if points >= 5000:
        return "ゴールド脳（Prefrontal Hero）"
    elif points >= 3000:
        return "シルバー脳（Control Master）"
    else:
        return "ブロンズ脳（Dopamine Beginner）"

# --- 3. メイン処理 ---
def main():
    st.title("🧠 脳内ドーパミン収支決算書")
    
    # スプレッドシートから最新データを取得
    all_data = load_data()
    # --- ユーザー登録（サイドバー） ---
    with st.sidebar:
        st.header("👤 ユーザー設定")
        u_name = st.text_input("名前（ニックネーム可）")
        t_name = st.text_input("チーム名")
        st.info("※チーム変更は不可です。")

    if not u_name or not t_name:
        st.warning("サイドバーで名前とチーム名を入力してください。")
        return

    tab1, tab2, tab3 = st.tabs(["📊 今日の収支", "🏆 ランキング", "📈 マイデータ"])

    # --- Tab 1: 入力 ---
    with tab1:
        st.subheader("本日のドーパミン収支を記録")
        # 3日前まで入力可能 
        target_date = st.date_input("対象日", 
                                    min_value=date.today() - timedelta(days=2), 
                                    max_value=date.today())
        
        # 既存データの確認
        existing = all_data[(all_data['user_id'] == u_name) & (all_data['date'] == str(target_date))]
        
        can_edit = True
        if not existing.empty:
            # 入力日が今日でない場合は訂正不可
            if existing.iloc[0]['entry_date'] != str(date.today()):
                can_edit = False
                st.error("⚠️ 訂正は当日のみ可能です。")

        if can_edit:
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("#### 資産 (+)")
                a_sel = st.multiselect("良い習慣", list(POINT_MASTER["資産"].keys()))
                s_sel = st.multiselect("特別利益", list(POINT_MASTER["特別利益"].keys()))
            with col2:
                st.markdown("#### 負債 (-)")
                l_sel = st.multiselect("悪い習慣", list(POINT_MASTER["負債"].keys()))
                confess = st.checkbox("「正直な懺悔」をする（負債が半分になります）")
            
            if st.button("この内容で保存する"):
                # スコア計算
                score = sum(POINT_MASTER["資産"][i] for i in a_sel) + \
                        sum(POINT_MASTER["特別利益"][i] for i in s_sel) + \
                        (sum(POINT_MASTER["負債"][i] for i in l_sel) * (0.5 if confess else 1))
                
                new_row = pd.DataFrame([{
                    "user_id": u_name, "team": t_name, "date": str(target_date),
                    "points": score, "entry_date": str(date.today())
                }])
                
                # データの更新
                updated_df = pd.concat([
                    all_data[~((all_data['user_id'] == u_name) & (all_data['date'] == str(target_date)))], 
                    new_row
                ])
                
                # スプレッドシートへ書き込み
                conn.update(worksheet="Records", data=updated_df)
                st.success(f"{target_date} のデータを保存しました！")
                st.balloons()

    # --- Tab 2: ランキング ---
    with tab2:
        st.subheader("社員間ランキング")
        if not all_data.empty:
            summary = all_data.groupby(['user_id', 'team'])['points'].sum().reset_index()
            summary['称号'] = summary['points'].apply(get_brain_rank)
            st.dataframe(summary.sort_values("points", ascending=False), use_container_width=True)
            
            st.subheader("チーム対抗戦")
            team_sum = summary.groupby('team')['points'].mean().reset_index()
            st.dataframe(team_sum.sort_values("points", ascending=False), use_container_width=True)

    # --- Tab 3: マイデータ ---
    with tab3:
        user_data = all_data[all_data['user_id'] == u_name].sort_values("date")
        if not user_data.empty:
            total = user_data['points'].sum()
            st.metric("累計ポイント (6か月間目標)", f"{total} DP")
            st.info(f"現在の称号: {get_brain_rank(total)}")
            st.line_chart(user_data.set_index("date")["points"])

if __name__ == "__main__":
    main()