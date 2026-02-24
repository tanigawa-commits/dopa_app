import streamlit as st
import pandas as pd
from datetime import datetime, date, timedelta
from streamlit_gsheets import GSheetsConnection
import hashlib  # パスワードハッシュ化用に追加

# --- 1. アプリ設定とDB接続 ---
st.set_page_config(page_title="Dopa-Balance", layout="wide")
conn = st.connection("gsheets", type=GSheetsConnection)

# パスワードをハッシュ化する関数
def make_hash(password):
    return hashlib.sha256(str.encode(password)).hexdigest()

def load_data():
    try:
        return conn.read(worksheet="Records", ttl="0m")
    except:
        return pd.DataFrame(columns=["real_name", "password", "nickname", "team", "date", "points", "entry_date"])

# チーム名のリスト
TEAM_LIST = ["経営層", "第一システム部", "第二システム部", "第三システム部", "第四システム部", "営業部", "総務部", "新人"]

# ポイント定義
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

def get_brain_rank(points):
    if points >= 5000: return "ゴールド脳（Prefrontal Hero）"
    elif points >= 3000: return "シルバー脳（Control Master）"
    else: return "ブロンズ脳（Dopamine Beginner）"

# --- 3. メイン処理 ---
def main():
    st.title("🧠 脳内ドーパミン収支決算書")
    
    saved_real_name = st.query_params.get("rn", "")
    saved_nickname = st.query_params.get("nn", "")
    saved_team = st.query_params.get("t", TEAM_LIST[0])
    
    all_data = load_data()

    with st.sidebar:
        st.header("🔑 ログイン / 会員登録")
        u_real_name = st.text_input("氏名（実名）", value=saved_real_name)
        u_pass = st.text_input("パスワード", type="password")
        u_nickname = st.text_input("ニックネーム", value=saved_nickname)
        
        default_team_idx = TEAM_LIST.index(saved_team) if saved_team in TEAM_LIST else 0
        t_name = st.selectbox("所属チーム", TEAM_LIST, index=default_team_idx)
        
        login_btn = st.button("ログイン情報を保持して認証")

        if login_btn:
            st.query_params["rn"] = u_real_name
            st.query_params["nn"] = u_nickname
            st.query_params["t"] = t_name
            st.success("ログイン情報を保持しました。")

st.divider() 
        with st.expander("⚠️ アカウント・全データ削除"):
            st.write("この操作は取り消せません。あなたの全記録がDBから完全に削除されます。")
            
            # 削除専用の入力欄（誤操作・なりすまし防止）
            del_real_name = st.text_input("削除確認：登録した氏名を入力", key="del_rn")
            del_pass = st.text_input("削除確認：パスワードを入力", type="password", key="del_pw")
            del_confirm = st.checkbox("全てのデータを削除することに同意します", key="del_chk")
            
            if st.button("アカウント削除を確定する", type="secondary"):
                if not del_confirm:
                    st.error("同意チェックを入れてください。")
                elif not del_real_name or not del_pass:
                    st.error("本人確認のため、氏名とパスワードを正しく入力してください。")
                else:
                    # パスワードハッシュ化して照合
                    hashed_del_pass = make_hash(del_pass)
                    # スプレッドシート内の当該ユーザーデータを確認
                    user_records = all_data[all_data['real_name'] == del_real_name]
                    
                    if user_records.empty:
                        st.error("該当する氏名のデータが見つかりません。")
                    elif str(user_records.iloc[0].get('password', '')) != hashed_del_pass:
                        st.error("パスワードが一致しません。")
                    else:
                        # 削除実行：本人以外のデータだけを抽出して上書き
                        updated_df = all_data[all_data['real_name'] != del_real_name]
                        conn.update(worksheet="Records", data=updated_df)
                        
                        # URLパラメータもクリア（ログアウト状態にする）
                        st.query_params.clear()
                        st.success("全てのデータを削除しました。")
                        st.balloons()
                        st.rerun()
    
    if not u_real_name or not u_pass or not u_nickname:
        st.warning("氏名・パスワード・ニックネームをすべて入力してください。")
        return

    tab1, tab2, tab3 = st.tabs(["📊 今日の収支", "🏆 ランキング", "📈 マイデータ"])

    # --- Tab 1: 入力 ---
    with tab1:
        st.subheader(f"こんにちは、{u_nickname} さん")
        target_date = st.date_input("対象日", 
                                    min_value=date.today() - timedelta(days=2), 
                                    max_value=date.today())
        
        # 入力されたパスワードをハッシュ化して照合
        hashed_input_pass = make_hash(u_pass)
        existing = all_data[(all_data['real_name'] == u_real_name) & (all_data['date'] == str(target_date))]
        
        can_edit = True
        if not existing.empty:
            # DBに保存されているハッシュ値と比較
            if str(existing.iloc[0].get('password', '')) != hashed_input_pass:
                st.error("❌ パスワードが一致しません。")
                can_edit = False
            elif existing.iloc[0]['entry_date'] != str(date.today()):
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
                confess = st.checkbox("「正直な懺悔」をする（負債半減）")
            
            if st.button("この内容で保存する"):
                score = sum(POINT_MASTER["資産"][i] for i in a_sel) + \
                        sum(POINT_MASTER["特別利益"][i] for i in s_sel) + \
                        (sum(POINT_MASTER["負債"][i] for i in l_sel) * (0.5 if confess else 1))
                
                # パスワードをハッシュ化して保存
                new_row = pd.DataFrame([{
                    "real_name": u_real_name, "password": hashed_input_pass, "nickname": u_nickname, 
                    "team": t_name, "date": str(target_date), "points": score, "entry_date": str(date.today())
                }])
                
                updated_df = pd.concat([
                    all_data[~((all_data['real_name'] == u_real_name) & (all_data['date'] == str(target_date)))], 
                    new_row
                ])
                
                conn.update(worksheet="Records", data=updated_df)
                st.success(f"✅ {target_date} のデータを保存しました！")
                st.metric(label="本日の獲得ポイント", value=f"{score} DP") # 大きく表示
                
                if score > 0:
                    st.write("ナイス！前頭前野が鍛えられています。")
                    st.balloons()
                elif score < 0:
                    st.write("明日は理性の脳を味方につけましょう！") 
                    st.balloons()

    # --- Tab 2 & 3: ランキング・マイデータ (既存通り) ---
    with tab2:
        st.subheader("ランキング")
        if not all_data.empty:
            summary = all_data.groupby(['nickname', 'team'])['points'].sum().reset_index()
            summary['称号'] = summary['points'].apply(get_brain_rank)
            st.dataframe(summary.sort_values("points", ascending=False), use_container_width=True)

    with tab3:
        user_data = all_data[all_data['real_name'] == u_real_name].sort_values("date")
        if not user_data.empty:
            total = user_data['points'].sum()
            st.metric("累計ポイント", f"{total} DP")
            st.line_chart(user_data.set_index("date")["points"])

if __name__ == "__main__":
    main()



