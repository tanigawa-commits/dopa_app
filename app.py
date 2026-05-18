import streamlit as st
import pandas as pd
from datetime import datetime, date, timedelta, timezone
from streamlit_gsheets import GSheetsConnection
import hashlib
import time

# --- 1. アプリ設定・定数 ---
st.set_page_config(page_title="Dopamine Tracker", layout="wide")
conn = st.connection("gsheets", type=GSheetsConnection)

# 合言葉
SECRET_AUTH_CODE = "feelist2026" 
# ★集計開始日を2026年6月1日に設定
APP_START_DATE = date(2026, 5, 1)
# JST（日本標準時）の設定
JST = timezone(timedelta(hours=9))

# デザインCSS
st.markdown("""
    <style>
    /* 記録カード */
    .status-card {
        border: 1px solid #e6e9ef; border-radius: 15px; padding: 15px; text-align: center;
        background-color: white; margin-bottom: 10px; box-shadow: 0 4px 6px rgba(0, 0, 0, 0.05);
    }
    .star-display { font-size: 26px; letter-spacing: 2px; margin: 5px 0; font-family: monospace; }
    .status-label { font-size: 16px; font-weight: bold; margin-bottom: 5px; }
    .status-count { font-size: 15px; color: #333; font-weight: bold; height: 22px; }

    /* 【修正】背景色・文字色はシステムに連動させつつ、罫線は両モードでクッキリ見える中間グレーに固定 */
    .history-table {
        width: 100%; 
        border-collapse: collapse !important; 
        font-size: 14px; 
        table-layout: fixed; 
        background-color: var(--background-color) !important;
        color: var(--text-color) !important;
        border: 1px solid #888888 !important; /* どちらのモードでも消えない外枠 */
    }
    .history-table th, .history-table td {
        border: 1px solid #888888 !important; /* 縦線・横線も中間グレーで確実に描画 */
        padding: 10px 8px; 
        text-align: left; 
        vertical-align: top;
        word-wrap: break-word; 
        white-space: normal; 
        overflow-wrap: break-word;
    }
    .history-table th { 
        background-color: var(--secondary-background-color) !important; 
        color: var(--text-color) !important; 
        font-weight: bold; 
    }

    .col-date { width: 100px; }
    .col-pts { width: 80px; text-align: right !important; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. ヘルパー関数 ---

def make_hash(password): return hashlib.sha256(str.encode(password)).hexdigest()

def clean_val_for_display(x):
    """ 表の表示用：空の値やNoneを全角ハイフンにする """
    if pd.isna(x): return "－"
    s = str(x).strip()
    if s.lower() in ["nan", "none", "", "null"]: return "－"
    return s

def normalize_id(x):
    """ .0を徹底排除して4桁文字列にする """
    s = str(x).strip()
    if s.endswith('.0'): s = s[:-2]
    if not s or s.lower() in ["nan", "none"]: return ""
    try: return str(int(float(s))).zfill(4)
    except: return s.zfill(4)

def clean_nick(x):
    """ ニックネーム用の「.0」除去関数 """
    s = str(x).strip()
    if s.endswith('.0'): s = s[:-2]
    return s

@st.cache_data(ttl=60)
def load_data_cached(sheet_name):
    try:
        df = conn.read(worksheet=sheet_name, ttl="1m")
        if df is None or df.empty: return pd.DataFrame()
        df = df.astype(str)
        if "emp_id" in df.columns:
            df["emp_id_norm"] = df["emp_id"].apply(normalize_id)
        if "real_name" in df.columns:
            df["real_name_norm"] = df["real_name"].apply(normalize_id)
        if "nickname" in df.columns:
            df["nickname"] = df["nickname"].apply(clean_nick)
        return df
    except Exception:
        return pd.DataFrame()

# 項目定義
INVESTMENT_ITEMS = [
    "料理", "掃除", "睡眠が8時間以上", "湯舟に入浴、サウナ", "朝10分前に出社",
    "身体を動かした（ウォーキング以上の負荷）",
    "健康的な食生活（栄養バランスが取れている）",
    "洗濯",
    "ニュースを30分みる（ネット可）",
    "学習",
    "読書（活字限定）",
    "創作（プログラミング、絵、小説、DTM、DIY）",
    "音楽（音楽鑑賞、楽器、カラオケ）",
    "大きな声で挨拶",
    "感謝の言葉を伝える",
    "家族との時間を過ごす",
    "植物を育てる",
    "ペットと触れ合う",
    "普段やらない事を挑戦（旅行、模様替え、ファッション、美容）"
]

DEBT_ITEMS = [
    "外食オンリー", "掃除をしなかった", "睡眠が6時間以下",
    "シャワーのみ／お風呂に入らなかった", "朝ギリギリに出社", "家で1日ゴロゴロ",
    "ギルティな食生活（ドカ食い、間食、炭酸飲料、エナドリ）",
    "アルコール摂取（缶ビール1本以上）",
    "タバコ（紙、加熱式、電子）",
    "スマホを2時間以上使用",
    "TV/Youtubeなど映像を2時間以上視聴",
    "SNSアプリを2時間以上使用",
    "ゲームを2時間以上プレイ",
    "ソシャゲのログイン報酬を受け取るためだけに起動",
    "ゲームへの課金", "ギャンブル", "無駄な出費", "独り言が多かった",
    "倫理観に欠ける行動（電車で席を譲らない、夜にゴミを出す等）"
]

# --- 3. メイン処理 ---
def main():
    if 'authenticated' not in st.session_state: st.session_state.authenticated = False
    if 'current_user' not in st.session_state: st.session_state.current_user = ""
    if 'form_version' not in st.session_state: st.session_state.form_version = 0

    # 認証
    if not st.session_state.authenticated:
        st.title("🔒 Dopamine Tracker - 認証")
        id_msg = st.empty()
        target_id = st.text_input("社員番号(4桁)", max_chars=4)
        if target_id:
            if len(target_id) != 4: id_msg.error("社員番号は4桁で入力してください")
            else:
                with st.spinner("認証中..."):
                    master = load_data_cached("UserMaster")
                    tid_norm = normalize_id(target_id)
                    user_row = master[master['emp_id_norm'] == tid_norm] if not master.empty else pd.DataFrame()
                    if user_row.empty: id_msg.error("この社員番号は使用できません")
                    else:
                        id_msg.empty()
                        raw_hash = user_row.iloc[0].get('password_hash', "")
                        stored_hash = str(raw_hash).strip() if pd.notna(raw_hash) and str(raw_hash).lower() not in ["nan", "none", ""] else None
                        if not stored_hash:
                            with st.form("init_reg"):
                                st.info("初回登録：パスワードを設定（4文字以上）")
                                ac, np, npc = st.text_input("秘密の合言葉", type="password"), st.text_input("新PW", type="password"), st.text_input("確認用", type="password")
                                if st.form_submit_button("登録してログイン"):
                                    if ac != SECRET_AUTH_CODE: st.error("合言葉が違います")
                                    elif len(np) < 4: st.error("4文字以上必要です")
                                    elif np != npc: st.error("不一致です")
                                    else:
                                        cm = conn.read(worksheet="UserMaster", ttl="0s").astype(str)
                                        cm['emp_id'] = cm['emp_id'].apply(normalize_id)
                                        idx = cm[cm['emp_id'] == tid_norm].index[0]
                                        cm.at[idx, 'password_hash'], cm.at[idx, 'nickname'] = str(make_hash(np)), tid_norm
                                        conn.update(worksheet="UserMaster", data=cm)
                                        st.session_state.update({"authenticated":True, "current_user":tid_norm})
                                        st.cache_data.clear(); st.rerun()
                        else:
                            with st.form("login_f"):
                                ip = st.text_input("パスワード", type="password")
                                if st.form_submit_button("ログイン"):
                                    if make_hash(ip) == stored_hash:
                                        st.session_state.update({"authenticated":True, "current_user":tid_norm})
                                        st.cache_data.clear(); st.rerun()
                                    else: st.error("パスワードが違います")
        st.stop()

    # データ同期
    current_emp_id = st.session_state.current_user
    master_data = load_data_cached("UserMaster")
    user_info = master_data[master_data['emp_id_norm'] == current_emp_id].iloc[0]
    nickname_raw = user_info.get('nickname', current_emp_id)
    current_nickname = clean_nick(nickname_raw) if pd.notna(nickname_raw) and str(nickname_raw).lower() not in ["nan", "none", ""] else clean_nick(current_emp_id)
    
    all_recs = load_data_cached("Records")
    user_recs = all_recs[all_recs['real_name_norm'] == current_emp_id] if not all_recs.empty else pd.DataFrame()

    st.title("📊 Dopamine Tracker")
    with st.sidebar:
        st.write(f"ログイン: **{current_nickname}**")
        if st.button("ログアウト"): st.session_state.authenticated = False; st.rerun()

    tab1, tab2, tab3, tab4 = st.tabs(["今日の記録", "ランキング", "マイデータ", "設定"])

    # --- タブ1: 今日の記録 ---
    with tab1:
        today_date = date.today()
        if not user_recs.empty:
            user_recs_filtered = user_recs.copy()
            user_recs_filtered['date_dt'] = pd.to_datetime(user_recs_filtered['date']).dt.date
            user_recs_filtered = user_recs_filtered[user_recs_filtered['date_dt'] >= APP_START_DATE]
        else:
            user_recs_filtered = pd.DataFrame()

        elapsed_days = max((today_date - APP_START_DATE).days + 1, 1) 
        recorded_days = user_recs_filtered['date'].nunique() if not user_recs_filtered.empty else 0
        input_rate = int(round((recorded_days / elapsed_days) * 100))
        filtered_pts = pd.to_numeric(user_recs_filtered['points'], errors='coerce').fillna(0).sum() if not user_recs_filtered.empty else 0
        avg_points = round(filtered_pts / recorded_days, 1) if recorded_days > 0 else 0.0

        st.write(f"### {current_nickname}さんの入力率は {input_rate} ％、平均ポイントは {avg_points:.1f} ptです")
        
        # 対象日の制限
        if today_date < APP_START_DATE:
            target_date = st.date_input("対象日（イベント開始前です）", value=APP_START_DATE, min_value=APP_START_DATE)
        else:
            back_7_days = today_date - timedelta(days=7)
            min_date = max(APP_START_DATE, back_7_days)
            target_date = st.date_input("対象日（7日前まで遡れます）", value=today_date, min_value=min_date, max_value=today_date)

        @st.fragment
        def record_ui():
            st.divider()
            top_stars_p = st.empty()
            v = st.session_state.form_version
            
            # 選択された日付の既存データを抽出（過去データ自動反映ロジック）
            day_rec = user_recs[user_recs['date'] == str(target_date)]
            if not day_rec.empty:
                raw_inv = day_rec.iloc[0].get('investment_items', '')
                raw_debt = day_rec.iloc[0].get('debt_items', '')
                existing_inv = [x.strip() for x in str(raw_inv).split(',')] if pd.notna(raw_inv) and str(raw_inv).strip() != '' else []
                existing_debt = [x.strip() for x in str(raw_debt).split(',')] if pd.notna(raw_debt) and str(raw_debt).strip() != '' else []
            else:
                existing_inv = []
                existing_debt = []

            c1, c2 = st.columns(2)
            with c1:
                st.markdown("#### 🟢 投資型（自己投資）")
                sel_inv = [i for i in INVESTMENT_ITEMS if st.checkbox(i, value=(i in existing_inv), key=f"inv_{i}_{target_date}_{v}")]
            with c2:
                st.markdown("#### 🔴 借金型（即時快楽）")
                sel_debt = [i for i in DEBT_ITEMS if st.checkbox(i, value=(i in existing_debt), key=f"debt_{i}_{target_date}_{v}")]
            
            n_inv, n_debt = len(sel_inv), len(sel_debt)
            inv_s, debt_s = "★" * min(n_inv, 10) + "☆" * max(0, 10 - n_inv), "★" * min(n_debt, 10) + "☆" * max(0, 10 - n_debt)
            inv_txt = f"{n_inv}個実施！" if 0 < n_inv <= 10 else ("10個以上実施！" if n_inv > 10 else "")
            debt_txt = f"{n_debt}個実施！" if 0 < n_debt <= 10 else ("10個以上実施！" if n_debt > 10 else "")

            with top_stars_p.container():
                sc1, sc2 = st.columns(2)
                with sc1: st.markdown(f'<div class="status-card"><div class="status-label" style="color:#0066cc;">投資型</div><div class="star-display" style="color:#00cc99;">{inv_s}</div><div class="status-count">{inv_txt}</div></div>', unsafe_allow_html=True)
                with sc2: st.markdown(f'<div class="status-card"><div class="status-label" style="color:#cc3333;">借金型</div><div class="star-display" style="color:#ff4b4b;">{debt_s}</div><div class="status-count">{debt_txt}</div></div>', unsafe_allow_html=True)
            
            st.metric("本日のポイント", f"{n_inv - n_debt:+d}")
            
            if st.button("登録する", type="primary", use_container_width=True):
                if target_date < APP_START_DATE:
                    st.error("イベント開始前のため登録できません")
                else:
                    with st.spinner("保存中..."):
                        db = conn.read(worksheet="Records", ttl="0s").astype(str)
                        db['real_name'] = db['real_name'].apply(normalize_id)
                        now_jst = datetime.now(JST).strftime('%Y-%m-%d %H:%M:%S')
                        new_row = pd.DataFrame([{
                            "real_name": current_emp_id, "date": str(target_date), 
                            "points": str(n_inv - n_debt), "entry_date": now_jst, 
                            "investment_items": ", ".join(sel_inv), "debt_items": ", ".join(sel_debt)
                        }])
                        others = db[~((db['real_name'] == current_emp_id) & (db['date'] == str(target_date)))]
                        conn.update(worksheet="Records", data=pd.concat([others, new_row]).reset_index(drop=True))
                        st.balloons(); time.sleep(2)
                        st.cache_data.clear(); st.rerun()
        record_ui()

    # --- タブ2: ランキング ---
    with tab2:
        st.subheader("🏆 ランキング")
        if not all_recs.empty:
            rdf = all_recs.copy()
            rdf['date_dt'] = pd.to_datetime(rdf['date']).dt.date
            rdf = rdf[rdf['date_dt'] >= APP_START_DATE]
            
            if not rdf.empty:
                summary = rdf.groupby("real_name_norm").agg({
                    'date': 'nunique',
                    'points': lambda x: pd.to_numeric(x, errors='coerce').fillna(0).sum()
                }).reset_index()
                summary.columns = ['real_name_norm', 'recorded_days', 'total_points']
                elapsed = max((date.today() - APP_START_DATE).days + 1, 1)
                
                summary['入力率'] = (summary['recorded_days'] / elapsed * 100).round().astype(int)
                summary['平均ポイント'] = (summary['total_points'] / summary['recorded_days']).round(1)
                
                mini = master_data[['emp_id_norm', 'nickname']].drop_duplicates()
                summary = summary.merge(mini, left_on='real_name_norm', right_on='emp_id_norm', how='left')
                summary['ニックネーム'] = summary['nickname'].apply(clean_nick)
                summary['ニックネーム'] = summary['ニックネーム'].apply(lambda x: x if pd.notna(x) and str(x).lower() not in ["nan", "none", "", "null"] else "－")
                
                summary = summary.sort_values(['入力率', '平均ポイント'], ascending=[False, False])
                summary["順位"] = range(1, len(summary) + 1)
                
                st.dataframe(
                    summary[["順位", "ニックネーム", "入力率", "平均ポイント"]],
                    use_container_width=True, hide_index=True,
                    column_config={
                        "順位": st.column_config.NumberColumn(alignment="left"),
                        "入力率": st.column_config.NumberColumn(format="%d ％", alignment="left"),
                        "平均ポイント": st.column_config.NumberColumn(format="%.1f pt", alignment="left")
                    }
                )
            else: st.info("集計対象期間(6/1〜)のデータがまだありません。")

    # --- タブ3: マイデータ ---
    with tab3:
        st.subheader("📋 全履歴の一覧")
        if not user_recs.empty:
            df_view = user_recs[['date', 'points', 'investment_items', 'debt_items']].copy()
            df_view = df_view.sort_values('date', ascending=False)
            table_html = '<table class="history-table"><tr><th class="col-date">日付</th><th class="col-pts">ポイント</th><th>投資</th><th>借金</th></tr>'
            for _, row in df_view.iterrows():
                d = row['date'].replace('-', '/')
                p = f"{int(float(row['points']))} pt"
                inv, dbt = clean_val_for_display(row['investment_items']), clean_val_for_display(row['debt_items'])
                table_html += f'<tr><td>{d}</td><td style="text-align:right;">{p}</td><td>{inv}</td><td>{dbt}</td></tr>'
            table_html += '</table>'
            st.markdown(table_html, unsafe_allow_html=True)
            st.caption("※ 項目が多い場合は自動的に折り返されます。")
        else: st.warning("記録がありません。")

    # --- タブ4: 設定 ---
    with tab4:
        st.subheader("⚙️ 設定")
        new_nick = st.text_input("ニックネーム変更", value=current_nickname)
        st.markdown("---")
        st.write("🔒 パスワードの変更")
        new_pw, new_pw_c = st.text_input("新PW", type="password"), st.text_input("確認用", type="password")
        if st.button("設定を更新する"):
            m_db = conn.read(worksheet="UserMaster", ttl="0s").astype(str)
            m_db['emp_id'] = m_db['emp_id'].apply(normalize_id)
            idx = m_db[m_db['emp_id'] == current_emp_id].index[0]
            m_db.at[idx, 'nickname'] = new_nick
            if new_pw:
                if len(new_pw) < 4: st.error("4文字以上必要です"); st.stop()
                if new_pw == new_pw_c: m_db.at[idx, 'password_hash'] = str(make_hash(new_pw))
                else: st.error("不一致です"); st.stop()
            conn.update(worksheet="UserMaster", data=m_db)
            st.cache_data.clear(); st.success("保存しました"); time.sleep(1); st.rerun()

if __name__ == "__main__":
    main()
