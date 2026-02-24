import streamlit as st
import pandas as pd
from datetime import datetime, date, timedelta
from streamlit_gsheets import GSheetsConnection
import hashlib
import time

# --- 1. アプリ設定とDB接続 ---
st.set_page_config(page_title="Dopa-Balance", layout="wide")
conn = st.connection("gsheets", type=GSheetsConnection)

def make_hash(password):
    return hashlib.sha256(str.encode(password)).hexdigest()

def load_data():
    try:
        # 累積値(total_points)列を含むデータを読み込む
        return conn.read(worksheet="Records", ttl="0m")
    except:
        # 初回起動時や列がない場合
        return pd.DataFrame(columns=["real_name", "password", "nickname", "team", "date", "points", "total_points", "entry_date"])

# --- 2. リスト・マスタ定義 ---
TEAM_OPTIONS = ["-- 選択してください --", "経営層", "第一システム部", "第二システム部", "第三システム部", "第四システム部", "営業部", "総務部", "新人"]

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
    saved_team = st.query_params.get("t", TEAM_OPTIONS[0])
    
    all_data = load_data()

    # --- サイドバー：ログイン / ユーザー設定 ---
    with st.sidebar:
        st.header("🔑 ログイン / 会員登録")
        u_real_name = st.text_input("氏名（実名）", value=saved_real_name, key="login_rn")
        u_pass = st.text_input("パスワード", type="password", key="login_pw")
        u_nickname = st.text_input("ニックネーム", value=saved_nickname, key="login_nn")
        
        default_team_idx = TEAM_OPTIONS.index(saved_team) if saved_team in TEAM_OPTIONS else 0
        t_name = st.selectbox("所属チーム", TEAM_OPTIONS, index=default_team_idx, key="login_team")
        
        login_btn = st.button("ログイン情報を保持して認証")
        
        if login_btn:
            if not u_real_name or not u_pass or not u_nickname or t_name == TEAM_OPTIONS[0]:
                st.error("全項目を入力し、所属チームを選択してください。")
            else:
                user_records = all_data[all_data['real_name'] == u_real_name]
                hashed_input_pass = make_hash(u_pass)

                if not user_records.empty:
                    db_pass = str(user_records.iloc[0].get('password', ''))
                    db_nick = str(user_records.iloc[0].get('nickname', ''))
                    db_team = str(user_records.iloc[0].get('team', ''))
                    
                    if db_pass != hashed_input_pass:
                        st.error("❌ パスワードが正しくありません。")
                    elif db_nick != u_nickname:
                        st.error(f"❌ ニックネームが登録情報と一致しません。")
                    elif db_team != t_name:
                        st.error(f"❌ 所属チームが登録情報と一致しません。")
                    else:
                        st.query_params.update(rn=u_real_name, nn=u_nickname, t=t_name)
                        st.success(f"🎉 認証に成功しました！")
                        time.sleep(1)
                        st.rerun()
                else:
                    st.query_params.update(rn=u_real_name, nn=u_nickname, t=t_name)
                    st.info("🆕 新規ユーザーとして認証しました。")
                    time.sleep(1)
                    st.rerun()

        # アカウント削除
        st.divider()
        with st.expander("⚠️ アカウント・全データ削除"):
            st.write("この操作は取り消せません。")
            del_real_name = st.text_input("削除確認：実名入力", key="del_rn")
            del_pass = st.text_input("削除確認：パスワード", type="password", key="del_pw")
            del_confirm = st.checkbox("データの削除に同意する", key="del_chk")
            
            if st.button("アカウント削除を確定する"):
                if del_confirm and del_real_name and del_pass:
                    hashed_del_pass = make_hash(del_pass)
                    user_records = all_data[all_data['real_name'] == del_real_name]
                    
                    if not user_records.empty and str(user_records.iloc[0].get('password', '')) != hashed_del_pass:
                        st.error("パスワードが一致しません。")
                    else:
                        if not user_records.empty:
                            updated_df = all_data[all_data['real_name'] != del_real_name]
                            conn.update(worksheet="Records", data=updated_df)
                        
                        st.query_params.clear()
                        for key in list(st.session_state.keys()): del st.session_state[key]
                        st.success("削除完了。リフレッシュします...")
                        st.markdown('<meta http-equiv="refresh" content="0.1; url=./">', unsafe_allow_html=True)
                        st.stop()

    # --- 表示判定 ---
    is_authenticated = (saved_real_name != "" and saved_nickname != "" and u_pass != "")
    if not is_authenticated:
        st.warning("左側のサイドバーで情報を入力し、認証ボタンを押してください。")
        return

    # --- メインコンテンツ ---
    tab1, tab2, tab3 = st.tabs(["📊 今日の収支", "🏆 ランキング", "📈 マイデータ"])

    with tab1:
        st.subheader(f"こんにちは、{u_nickname} さん")
        if "last_score" in st.session_state:
            st.success(f"✅ データを保存しました！ (獲得: {st.session_state['last_score']} DP)")
        
        target_date = st.date_input("対象日", min_value=date.today() - timedelta(days=2), max_value=date.today())
        hashed_input_pass = make_hash(u_pass)
        
        # 既存データの確認
        existing_user_data = all_data[all_data['real_name'] == u_real_name].sort_values("date")
        existing_day = existing_user_data[existing_user_data['date'] == str(target_date)]
        
        can_edit = True
        if not existing_day.empty:
            if str(existing_day.iloc[0].get('password', '')) != hashed_input_pass:
                st.error("❌ パスワードが一致しません。")
                can_edit = False
            elif existing_day.iloc[0]['entry_date'] != str(date.today()):
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
                # 今日のスコア計算
                day_score = sum(POINT_MASTER["資産"][i] for i in a_sel) + \
                            sum(POINT_MASTER["特別利益"][i] for i in s_sel) + \
                            (sum(POINT_MASTER["負債"][i] for i in l_sel) * (0.5 if confess else 1))
                
                # --- 累積値の計算 ---
                # 今回の対象日を除いた、過去の全累計を取得
                other_days_data = all_data[(all_data['real_name'] == u_real_name) & (all_data['date'] != str(target_date))]
                past_total = other_days_data['points'].sum()
                new_total = past_total + day_score
                
                new_row = pd.DataFrame([{
                    "real_name": u_real_name, "password": hashed_input_pass, "nickname": u_nickname, 
                    "team": t_name, "date": str(target_date), "points": day_score, 
                    "total_points": new_total, # ここで累積値を保持
                    "entry_date": str(date.today())
                }])
                
                updated_df = pd.concat([
                    all_data[~((all_data['real_name'] == u_real_name) & (all_data['date'] == str(target_date)))], 
                    new_row
                ])
                
                conn.update(worksheet="Records", data=updated_df)
                st.session_state["last_score"] = day_score
                st.balloons()
                time.sleep(1)
                st.rerun()

    with tab2:
        st.subheader("🏆 ランキング")
        if not all_data.empty:
            # 最新の累積値（ユーザーごとの合計）で集計
            summary = all_data.groupby(['nickname', 'team'])['points'].sum().reset_index()
            summary['称号'] = summary['points'].apply(get_brain_rank)
            st.dataframe(summary.sort_values("points", ascending=False), use_container_width=True, hide_index=True)

    with tab3:
        st.subheader("📈 あなたの成長記録（累積推移）")
        user_data = all_data[all_data['real_name'] == u_real_name].copy()
        if not user_data.empty:
            user_data['date'] = pd.to_datetime(user_data['date'])
            user_data = user_data.sort_values("date")
            
            # グラフ用の累積計算（DBのtotal_pointsを使わず、その場で計算して時系列を保証）
            user_data['累積DP'] = user_data['points'].cumsum()
            
            st.metric("現在の累計ポイント", f"{user_data['points'].sum()} DP")
            
            # 折れ線グラフ（累積推移）を表示
            st.line_chart(user_data.set_index("date")["累積DP"])
            
            # 詳細履歴表
            st.write("### 履歴")
            st.dataframe(user_data[['date', 'points', '累積DP']].rename(columns={'date':'日付', 'points':'獲得点'}), hide_index=True)
        else:
            st.info("データがまだありません。")

if __name__ == "__main__":
    main()
