import streamlit as st
import pandas as pd
from datetime import datetime, date, timedelta
from streamlit_gsheets import GSheetsConnection
import hashlib
import time

# --- 1. アプリ設定とDB接続 ---
st.set_page_config(page_title="Dopa-Balance Pro", layout="wide")
conn = st.connection("gsheets", type=GSheetsConnection)

# カスタムCSS：場所によってボタンのサイズを使い分ける
st.markdown("""
    <style>
    /* 1. メインエリアの「投資・借金」ボタンの設定 */
    [data-testid="stMain"] div.stButton > button {
        height: 60px !important;    /* 囲みの四角形は標準的な高さに */
        border-radius: 12px !important;
        padding: 0px 20px !important;
    }
    
    /* ボタン内のテキスト（顔文字を大きく、文字はほどよく） */
    [data-testid="stMain"] div.stButton > button p {
        font-size: 32px !important;  /* 顔文字を以前の約2倍のサイズに */
        font-weight: bold;
        line-height: 1.2 !important;
    }

    /* 2. サイドバーの「認証」ボタンは元のサイズを維持 */
    [data-testid="stSidebar"] div.stButton > button {
        height: auto !important;
        padding: 0.25rem 0.75rem !important;
    }
    [data-testid="stSidebar"] div.stButton > button p {
        font-size: 16px !important;  /* 標準的なサイズ */
    }
    
    /* ボタン押下時のエフェクト */
    div.stButton > button:active {
        transform: scale(0.98);
    }
    </style>
    """, unsafe_allow_html=True)

def make_hash(password):
    return hashlib.sha256(str.encode(password)).hexdigest()

def load_data():
    try:
        df = conn.read(worksheet="Records", ttl="0m")
        # 必要な列の存在確認と数値補完
        expected_cols = ["real_name", "password", "nickname", "team", "date", "points", "total_points", 
                         "entry_date", "selected_items", "learning_type", "learning_minutes"]
        for col in expected_cols:
            if col not in df.columns:
                df[col] = 0
        return df
    except:
        return pd.DataFrame(columns=["real_name", "password", "nickname", "team", "date", "points", "total_points", 
                                     "entry_date", "selected_items", "learning_type", "learning_minutes"])

# --- 2. リスト・マスタ定義（PPT：脳科学からメンタルやマネジメントを考える より） ---
TEAM_OPTIONS = ["-- 選択してください --", "経営層", "第一システム部", "第二システム部", "第三システム部", "第四システム部", "営業部", "総務部", "新人"]

# 投資型：自己研鑽や創造的活動を通じ、脳のベースラインを向上させる領域
INVESTMENT_MASTER = {
    "楽器の即興演奏": 9.5, "ライブに行く": 9.3, "スキー・スノーボード": 9.2, "サウナと水風呂": 9.0,
    "海で泳ぐ": 8.8, "作曲・DTM": 8.4, "長期プロジェクトの完遂": 8.2, "追い込む筋トレ": 8.1,
    "小説を読む": 8.0, "キャンプ": 7.1, "映画鑑賞": 6.7, "部屋の徹底的な断捨離": 6.0,
    "家庭菜園": 5.4, "犬の散歩": 5.0, "十分な睡眠": 2.0, "何もしないでボーッとする": 1.0
}

# 借金型：即座に快楽を得るが、活力を前借りし依存リスクが高い領域
DEBT_MASTER = {
    "借金をしてのギャンブル": 10.0, "イヤホンでの爆音視聴": 9.6, "スマホゲームの課金ガチャ": 9.5,
    "アルコール過剰摂取(泥酔)": 9.1, "SNSでバズる体験": 8.8,
    "YouTubeショート・TikTok": 8.5, "深夜のジャンクフード・ドカ食い": 8.0, "エナジードリンクの常飲": 7.8,
    "SNSのいいねに一喜一憂": 6.5, "陰口やゴシップで盛り上がる": 5.7,
    "TVをダラダラ見続ける": 4.5, "掃除をしない": 3.8, "夜更かし": 2.0
}

LEARNING_OPTIONS = ["読書", "動画視聴", "対面式学習", "プログラム作成", "ネット記事調査"]

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

    if 'selected_inv' not in st.session_state: st.session_state.selected_inv = set()
    if 'selected_debt' not in st.session_state: st.session_state.selected_debt = set()

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
                st.query_params
