import streamlit as st
import pandas as pd
from datetime import datetime, date, timedelta
from streamlit_gsheets import GSheetsConnection
import hashlib
import time

# --- 1. アプリ設定とDB接続 ---
st.set_page_config(page_title="Dopa-Balance Pro", layout="wide")
conn = st.connection("gsheets", type=GSheetsConnection)

# カスタムCSS：顔文字のサイズとボタンのデザイン
st.markdown("""
    <style>
    /* メインエリアのボタン設定 */
    [data-testid="stMain"] div.stButton > button {
        height: 100px !important; 
        border-radius: 15px !important;
        padding: 0px 15px !important;
    }
    
    /* 顔文字を大きく表示 */
    [data-testid="stMain"] div.stButton > button p {
        font-size: 40px !important; 
        font-weight: bold;
        line-height: 1.1 !important;
    }

    /* サイドバーの認証ボタン（標準サイズ） */
    [data-testid="stSidebar"] div.stButton > button {
        height: auto !important;
    }
    [data-testid="stSidebar"] div.stButton > button p {
        font-size: 16px !important; 
    }
    
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
        # 自己学習関連の列を除外した期待される列
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

# 投資型項目
INVESTMENT_ITEMS = [
    "経験のない事に挑戦", "料理", "掃除", "睡眠が8時間以上", "入浴、サウナ（シャワーのみはNG）", 
    "朝10分前に出社", "身体を動かす（階段、ウォーキング、ストレッチ等）", "勉強", "読書", 
    "創作活動（プログラミング、絵、作曲、動画編集等）", "音楽（音楽鑑賞、楽器、カラオケ）", 
    "ニュースを調べる", "旅行", "行ったことのない店にいく", "普段しないファッションに挑戦", 
    "普段しないメイク、ネイルに挑戦", "模様替え", "家族で食事", "感謝の言葉を伝える", 
    "植物を育てる", "ペットと触れ合う"
]

# 借金型項目
DEBT_ITEMS = [
    "倫理観に欠ける行動", "外食オンリー", "掃除をしない", "睡眠が6時間未満", 
    "シャワーのみで済ます／お風呂に入らない", "過度な飲酒", "晩御飯の後に、お菓子や食事をしてしまう", 
    "ドカ食い（1食2000kcal以上）", "テレビ／動画を見ながら、お菓子を食べる", 
    "炭酸飲料を飲む（エナドリ、コーラ等）", "タバコの喫煙（紙、加熱式、電子）", 
    "スマホを1日2時間以上利用", "動画視聴が1日2時間以上利用", "SNSを1日2時間以上利用", 
    "ゲームを1日2時間以上プレイ", "ログイン報酬のためだけに起動", "ゲームへの課金", 
    "ギャンブル", "借金（リボ、キャッシング等）をして浪費", "ECサイトで衝動買い", "外に出ない"
]

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
        target_date = st.date_input("対象日（２日前まで修正可）", value=date.today(), min_value=date.today()-timedelta(days=2), max_value=date.today())
        
        st.markdown("#### 🟢 投資型 - 未来を創る行動")
        cols_inv = st.columns(2)
        for i, item in enumerate(INVESTMENT_ITEMS):
            active = item in st.session_state.selected_inv
            if cols_inv[i % 2].button(f"{'😊' if active else '😐'} {item}", key=f"inv_{item}", use_container_width=True):
                st.session_state.selected_inv.remove(item) if active else st.session_state.selected_inv.add(item)
                st.rerun()

        st.divider()
        st.markdown("#### 🔴 借金型 - エネルギーの前借り")
        cols_debt = st.columns(2)
        for i, item in enumerate(DEBT_ITEMS):
            active = item in st.session_state.selected_debt
            if cols_debt[i % 2].button(f"{'😊' if active else '😐'} {item}", key=f"debt_{item}", use_container_width=True):
                st.session_state.selected_debt.remove(item) if active else st.session_state.selected_debt.add(item)
                st.rerun()

        st.divider()

        # 収支計算
        day_count = len(st.session_state.selected_inv) - len(st.session_state.selected_debt)
        st.metric("本日の収支", f"{day_count:+d} アクション")

        if st.button("この内容で決算する", type="primary"):
            selected_items_str = ", ".join(list(st.session_state.selected_inv) + list(st.session_state.selected_debt))
            past_points_total = all_data[(all_data['real_name'] == u_real_name) & (all_data['date'] != str(target_date))]['points'].sum()
            
            new_row = pd.DataFrame([{
                "real_name": u_real_name, "password": make_hash(u_pass), "nickname": u_nickname, 
                "team": t_name, "date": str(target_date), "points": day_count, 
                "total_points": past_points_total + day_count, "entry_date": str(date.today()),
                "selected_items": selected_items_str
            }])
            
            updated_df = pd.concat([all_data[~((all_data['real_name'] == u_real_name) & (all_data['date'] == str(target_date)))], new_row]).reset_index(drop=True)
            conn.update(worksheet="Records", data=updated_df)
            
            st.balloons()
            st.success(f"記録しました！ 本日の収支: {day_count:+d} アクション")
            st.session_state.selected_inv, st.session_state.selected_debt = set(), set()
            time.sleep(3)
            st.rerun()

    with tab2:
        if not all_data.empty:
            st.subheader("🏆 収支累計ランキング")
            rdf = all_data.groupby(['nickname', 'team'])['points'].sum().reset_index()
            st.dataframe(rdf.sort_values("points", ascending=False).rename(columns={'points':'累計アクション収支'}), use_container_width=True, hide_index=True)

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
