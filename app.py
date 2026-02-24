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
        # ttl="0m"でキャッシュを無効化し、常に最新のスプレッドシートを読み込む
        return conn.read(worksheet="Records", ttl="0m")
    except:
        return pd.DataFrame(columns=["real_name", "password", "nickname", "team", "date", "points", "entry_date"])

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
    
    # URLから保存情報を取得
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
                    # 既存ユーザー照合
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
                        st.success(f"🎉 認証に成功しました！ようこそ、{u_nickname} さん。")
                        time.sleep(1.5)
                        st.rerun()
                else:
                    # 新規ユーザー
                    st
