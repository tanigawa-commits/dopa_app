import streamlit as st
import pandas as pd
from datetime import datetime, date, timedelta
from streamlit_gsheets import GSheetsConnection
import hashlib
import time

# --- 1. アプリ設定とDB接続 ---
st.set_page_config(page_title="Dopa-Balance Pro", layout="wide")
conn = st.connection("gsheets", type=GSheetsConnection)

def make_hash(password):
    return hashlib.sha256(str.encode(password)).hexdigest()

def load_data():
    try:
        df = conn.read(worksheet="Records", ttl="0m")
        # 自己学習関連の列(learning_type, learning_minutes)を削除
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

INVESTMENT_MASTER = {
    "楽器の即興演奏": 9.5, "ライブに行く": 9.3, "スキー・スノーボード": 9.2, "サウナと水風呂": 9.0,
    "海で泳ぐ": 8.8, "作曲・DTM": 8.4, "長期プロジェクトの完遂": 8.2, "追い込む筋トレ": 8.1,
    "小説を読む": 8.0, "キャンプ": 7.1, "映画鑑賞": 6.7, "部屋の徹底的な断捨離": 6.0,
    "家庭菜園": 5.4, "犬の散歩": 5.0, "十分な睡眠": 2.0, "何もしないでボーッとする": 1.0
}

DEBT_MASTER = {
    "借金をしてのギャンブル": 10.0, "イヤホンでの爆音視聴": 9.6, "スマホゲームの課金ガチャ": 9.5,
    "アルコール過剰摂取(泥酔)": 9.1, "SNSでバズる体験": 8.8,
    "YouTubeショート・TikTok": 8.5, "深夜のジャンクフード・ドカ食い": 8.0, "エナジードリンクの常飲": 7.8,
    "SNSのいいねに一喜一憂": 6.5, "陰口やゴシップで盛り上がる": 5.7,
    "TVをダラダラ見続ける": 4.5, "掃除をしない": 3.8, "夜更かし": 2.0
}

INV_OPTIONS = [f"{k} (+{v})" for k, v in INVESTMENT_MASTER.items()]
DEBT_OPTIONS = [f"{k} (-{v})" for k, v in DEBT_MASTER.items()]

def get_brain_rank(points):
    if points >= 500: return "プラチナ脳（Flow Master）"
    elif points >= 300: return "ゴールド脳（Investment King）"
    elif points >= 100: return "シルバー脳（Self-Control）"
    else: return "ブロンズ脳（Dopamine Beginner）"

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
        
        default_team_idx = TEAM_OPTIONS.index(saved_team) if saved_team in TEAM_OPTIONS else 0
        t_name = st.selectbox("所属チーム", TEAM_OPTIONS, index=default_team_idx, key="login_team")
        
        if st.button("認証"):
            if not u_real_name or not u_pass or not u_nickname or t_name == TEAM_OPTIONS[0]:
                st.error("全項目を入力してください。")
            else:
                st.query_params.update(rn=u_real_name, nn=u_nickname, t=t_name)
                st.success("認証完了")
                time.sleep(0.5)
                st.rerun()

    if not (saved_real_name and saved_nickname and u_pass):
        st.warning("サイドバーでログインしてください。")
        return

    tab1, tab2, tab3 = st.tabs(["📊 今日の記録", "🏆 ランキング", "📈 マイデータ"])

    with tab1:
        st.write(f"### 投資と借金のバランスを整えましょう、{u_nickname} さん")
        
        target_date = st.date_input(
            "対象日（２日前まで遡って登録、修正が出来ます）", 
            value=date.today(),
            min_value=date.today() - timedelta(days=2),
            max_value=date.today()
        )
        
        col1, col2 = st.columns(2) # 3列から2列に変更
        with col1:
            st.markdown("#### 🟢 投資型 (+)")
            inv_sel_raw = st.multiselect("未来を創る行動", INV_OPTIONS, placeholder="-- 未選択 --")
        with col2:
            st.markdown("#### 🔴 借金型 (-)")
            debt_sel_raw = st.multiselect("エネルギーの前借り", DEBT_OPTIONS, placeholder="-- 未選択 --")

        if st.button("この内容で決算する"):
            inv_keys = [s.split(" (+")[0] for s in inv_sel_raw]
            debt_keys = [s.split(" (-")[0] for s in debt_sel_raw]
            
            day_points = sum(INVESTMENT_MASTER[k] for k in inv_keys) - sum(DEBT_MASTER[k] for k in debt_keys)
            selected_items_str = ", ".join(inv_keys + debt_keys)
            
            # 累積ポイントの計算
            past_points_total = all_data[(all_data['real_name'] == u_real_name) & (all_data['date'] != str(target_date))]['points'].sum()
            new_total = past_points_total + day_points
            
            hashed_input_pass = make_hash(u_pass)
            new_row = pd.DataFrame([{
                "real_name": u_real_name, "password": hashed_input_pass, "nickname": u_nickname, 
                "team": t_name, "date": str(target_date), "points": round(day_points, 1), 
                "total_points": round(new_total, 1), "entry_date": str(date.today()),
                "selected_items": selected_items_str
            }])
            
            updated_df = pd.concat([
                all_data[~((all_data['real_name'] == u_real_name) & (all_data['date'] == str(target_date)))], 
                new_row
            ]).reset_index(drop=True)
            
            conn.update(worksheet="Records", data=updated_df)
            
            st.balloons()
            st.success(f"記録しました！ 今日のDP収支: {day_points:+.1f}")
            time.sleep(3)
            st.rerun()

    with tab2:
        st.subheader("🏆 DP収支ランキング")
        if not all_data.empty:
            rank_df = all_data.groupby(['nickname', 'team'])['points'].sum().reset_index()
            rank_df['称号'] = rank_df['points'].apply(get_brain_rank)
            st.dataframe(rank_df.sort_values("points", ascending=False), use_container_width=True, hide_index=True)

    with tab3:
        user_data = all_data[all_data['real_name'] == u_real_name].copy()
        if not user_data.empty:
            user_data['date'] = pd.to_datetime(user_data['date'])
            user_data = user_data.sort_values("date")
            
            st.subheader("📈 ドーパミン投資推移 (累積)")
            st.line_chart(user_data.set_index("date")["total_points"])
            
            st.divider()
            st.subheader("📋 収支履歴")
            history_df = user_data.copy()
            history_df['日付'] = history_df['date'].dt.strftime('%Y-%m-%d')
            st.dataframe(
                history_df[['日付', 'points', 'selected_items', 'total_points']].rename(
                    columns={'points':'収支', 'selected_items':'選択項目', 'total_points':'累積DP'}
                ), 
                hide_index=True, use_container_width=True
            )
        else:
            st.info("データがまだありません。")

if __name__ == "__main__":
    main()
