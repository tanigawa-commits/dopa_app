import streamlit as st
import pandas as pd
from datetime import datetime, date, timedelta
from streamlit_gsheets import GSheetsConnection
import hashlib
import time

# --- 1. アプリ設定とDB接続 ---
st.set_page_config(page_title="Dopa-Balance Pro", layout="wide")
conn = st.connection("gsheets", type=GSheetsConnection)

# カスタムCSS：ボタン内の顔文字と文字を大きくして視認性をアップ
st.markdown("""
    <style>
    div.stButton > button {
        font-size: 32px !important; /* 顔文字をさらに大きく設定 */
        height: 3em !important;
        border-radius: 15px !important;
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

# --- 2. リスト・マスタ定義（脳科学に基づいた幸福の三段ピラミッド） ---
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

    # 顔文字ボタンの状態をセッションに保持
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
        
        # 対象日の選択制限：本日、昨日、一昨日まで
        target_date = st.date_input(
            "対象日（２日前まで遡って登録、修正が出来ます）", 
            value=date.today(),
            min_value=date.today() - timedelta(days=2),
            max_value=date.today()
        )
        
        # 投資型セクション
        st.markdown("#### 🟢 投資型 (+) - 未来を創る行動")
        cols_inv = st.columns(3)
        for i, (item, val) in enumerate(INVESTMENT_MASTER.items()):
            active = item in st.session_state.selected_inv
            # 顔文字が変化する大きなトグルボタン
            if cols_inv[i % 3].button(f"{'😊' if active else '😐'} {item}", key=f"inv_{item}", use_container_width=True):
                if active: st.session_state.selected_inv.remove(item)
                else: st.session_state.selected_inv.add(item)
                st.rerun()

        st.divider()
        
        # 借金型セクション
        st.markdown("#### 🔴 借金型 (-) - エネルギーの前借り")
        cols_debt = st.columns(3)
        for i, (item, val) in enumerate(DEBT_MASTER.items()):
            active = item in st.session_state.selected_debt
            if cols_debt[i % 3].button(f"{'😊' if active else '😐'} {item}", key=f"debt_{item}", use_container_width=True):
                if active: st.session_state.selected_debt.remove(item)
                else: st.session_state.selected_debt.add(item)
                st.rerun()

        st.divider()
        
        # 自己学習入力
        col_l1, col_l2 = st.columns(2)
        with col_l1:
            l_type = st.selectbox("📚 自己学習項目", ["-- 未選択 --"] + LEARNING_OPTIONS)
        with col_l2:
            l_min = st.selectbox("⏱️ 学習時間 (分)", options=list(range(0, 601, 10)), index=0)

        # 暫定スコアの計算
        day_points = sum(INVESTMENT_MASTER[k] for k in st.session_state.selected_inv) - \
                     sum(DEBT_MASTER[k] for k in st.session_state.selected_debt)
        
        st.metric("暫定スコア", f"{day_points:+.1f} DP")

        if st.button("この内容で決算する", type="primary"):
            selected_items_str = ", ".join(list(st.session_state.selected_inv) + list(st.session_state.selected_debt))
            # 同一実名の他日の累積合計を取得
            past_points_total = all_data[(all_data['real_name'] == u_real_name) & (all_data['date'] != str(target_date))]['points'].sum()
            
            new_row = pd.DataFrame([{
                "real_name": u_real_name, "password": make_hash(u_pass), "nickname": u_nickname, 
                "team": t_name, "date": str(target_date), "points": round(day_points, 1), 
                "total_points": round(past_points_total + day_points, 1), "entry_date": str(date.today()),
                "selected_items": selected_items_str, 
                "learning_type": l_type if l_type != "-- 未選択 --" else None,
                "learning_minutes": l_min
            }])
            
            # 既存の同日データを上書き
            updated_df = pd.concat([
                all_data[~((all_data['real_name'] == u_real_name) & (all_data['date'] == str(target_date)))], 
                new_row
            ]).reset_index(drop=True)
            
            conn.update(worksheet="Records", data=updated_df)
            
            st.balloons()
            st.success(f"記録しました！ 今日の収支: {day_points:+.1f} / 学習: {l_min}分")
            # セッションをクリア
            st.session_state.selected_inv, st.session_state.selected_debt = set(), set()
            # 結果を3秒間表示して反映
            time.sleep(3)
            st.rerun()

    with tab2:
        col_r1, col_r2 = st.columns(2)
        if not all_data.empty:
            with col_r1:
                st.subheader("🏆 DP収支ランキング")
                rdf = all_data.groupby(['nickname', 'team'])['points'].sum().reset_index()
                rdf['称号'] = rdf['points'].apply(get_brain_rank)
                st.dataframe(rdf.sort_values("points", ascending=False), use_container_width=True, hide_index=True)
            with col_r2:
                st.subheader("📖 自己学習ランキング")
                ldf = all_data.groupby(['nickname', 'team'])['learning_minutes'].sum().reset_index()
                st.dataframe(ldf.sort_values("learning_minutes", ascending=False).rename(columns={'learning_minutes':'合計学習(分)'}), use_container_width=True, hide_index=True)

    with tab3:
        udata = all_data[all_data['real_name'] == u_real_name].copy()
        if not udata.empty:
            udata['date'] = pd.to_datetime(udata['date'])
            udata = udata.sort_values("date")
            
            st.subheader("📈 ドーパミン投資推移 (累積)")
            st.line_chart(udata.set_index("date")["total_points"])
            
            st.subheader("📖 学習時間の推移 (累積分)")
            udata['累積学習'] = udata['learning_minutes'].cumsum()
            st.line_chart(udata.set_index("date")["累積学習"])
            
            st.divider()
            st.subheader("📋 履歴詳細")
            h_df = udata.copy()
            h_df['日付'] = h_df['date'].dt.strftime('%Y-%m-%d')
            st.dataframe(
                h_df[['日付', 'points', 'selected_items', 'learning_minutes']].rename(
                    columns={'points':'収支','selected_items':'選択項目','learning_minutes':'学習(分)'}
                ), 
                hide_index=True, use_container_width=True
            )
        else:
            st.info("データがまだありません。")

if __name__ == "__main__":
    main()
