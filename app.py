import streamlit as st
import pandas as pd
from datetime import datetime, date, timedelta
from streamlit_gsheets import GSheetsConnection
import hashlib
import time
import calendar

# --- 1. アプリ設定（安定のcenteredレイアウト） ---
st.set_page_config(page_title="Dopamine Tracker", layout="centered")
conn = st.connection("gsheets", type=GSheetsConnection)

SECRET_AUTH_CODE = "feelist2026" 

# デザインCSS（壊さないよう、必要なカードデザインだけに限定）
st.markdown("""
    <style>
    .status-card {
        border: 1px solid #e6e9ef; border-radius: 15px; padding: 20px; text-align: center;
        background-color: white; margin-bottom: 20px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05);
    }
    .star-display { font-size: 28px; letter-spacing: 2px; margin: 10px 0; font-family: monospace; }
    .status-label { font-size: 18px; font-weight: bold; margin-bottom: 5px; }
    .status-count { font-size: 16px; color: #5e6064; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. 徹底的なデータクリーニング関数 ---

def make_hash(password): return hashlib.sha256(str.encode(password)).hexdigest()

def clean_val(x):
    """すべての不純物（.0, None, nan）を消し去る"""
    s = str(x).strip()
    if '.' in s: s = s.split('.')[0]
    if s.lower() in ["nan", "none", "", "null"]: return ""
    return s

def display_format(val):
    """表示時に空なら全角ハイフンにする"""
    s = clean_val(val)
    return s if s != "" else "－"

def normalize_id(x):
    """IDを4桁0埋めにする"""
    s = clean_val(x)
    if s == "": return ""
    try: return s.zfill(4)
    except: return s

@st.cache_data(ttl=60)
def load_data_cached(sheet_name):
    try:
        df = conn.read(worksheet=sheet_name, ttl="1m")
        if df.empty: return pd.DataFrame()
        return df.astype(str)
    except: return pd.DataFrame()

# 項目
INVESTMENT_ITEMS = ["料理", "掃除", "睡眠が8時間以上", "湯舟に入浴、サウナ", "朝10分前に出社", "身体を動かした", "健康的な食生活", "洗濯", "ニュースをみる", "学習", "読書", "創作", "音楽", "挨拶", "感謝", "家族との時間", "植物", "ペット", "挑戦"]
DEBT_ITEMS = ["外食オンリー", "掃除なし", "睡眠不足", "シャワーのみ", "朝ギリギリ", "1日ゴロゴロ", "ギルティ食", "アルコール", "タバコ", "スマホ2h+", "映像2h+", "SNS2h+", "ゲーム2h+", "ソシャゲ", "課金", "ギャンブル", "無駄遣い", "独り言", "倫理欠如"]

# --- 3. メイン処理 ---
def main():
    if 'authenticated' not in st.session_state: st.session_state.authenticated = False
    if 'last_logged_id' not in st.session_state: st.session_state.last_logged_id = ""
    if 'form_version' not in st.session_state: st.session_state.form_version = 0

    # 認証
    if not st.session_state.authenticated:
        st.title("🔒 Dopamine Tracker")
        target_id = st.text_input("社員番号(4桁)", value=st.session_state.last_logged_id, max_chars=4)
        if target_id:
            master = load_data_cached("UserMaster")
            target_id_norm = normalize_id(target_id)
            user_row = master[master['emp_id'].apply(normalize_id) == target_id_norm] if not master.empty else pd.DataFrame()
            if not user_row.empty:
                stored_hash = clean_val(user_row.iloc[0].get('password_hash', ""))
                if stored_hash == "":
                    with st.form("reg"):
                        st.info("初回登録が必要です")
                        ac, np, npc = st.text_input("秘密の合言葉", type="password"), st.text_input("新パスワード", type="password"), st.text_input("確認用", type="password")
                        if st.form_submit_button("登録"):
                            if ac == SECRET_AUTH_CODE and np == npc:
                                cm = conn.read(worksheet="UserMaster", ttl="0s").astype(str)
                                idx = cm[cm['emp_id'].apply(normalize_id) == target_id_norm].index[0]
                                cm.at[idx, 'password_hash'], cm.at[idx, 'nickname'] = str(make_hash(np)), target_id_norm
                                conn.update(worksheet="UserMaster", data=cm)
                                st.session_state.authenticated, st.session_state.current_user, st.session_state.last_logged_id = True, target_id_norm, target_id_norm
                                st.cache_data.clear(); st.rerun()
                            else: st.error("入力内容を確認してください")
                else:
                    with st.form("login"):
                        ip = st.text_input("パスワード", type="password")
                        if st.form_submit_button("ログイン"):
                            if make_hash(ip) == stored_hash:
                                st.session_state.authenticated, st.session_state.current_user, st.session_state.last_logged_id = True, target_id_norm, target_id_norm
                                st.cache_data.clear(); st.rerun()
                            else: st.error("パスワードが違います")
        st.stop()

    # データ準備
    current_emp_id = st.session_state.current_user
    all_recs = load_data_cached("Records")
    user_recs = all_recs[all_recs['real_name'].apply(normalize_id) == current_emp_id] if not all_recs.empty else pd.DataFrame()

    tab1, tab2, tab3, tab4 = st.tabs(["今日の記録", "ランキング", "マイデータ", "設定"])

    # --- タブ1: 今日の記録（完全復活） ---
    with tab1:
        total_pts = pd.to_numeric(user_recs['points'], errors='coerce').fillna(0).sum()
        st.subheader(f"累計ポイント: {total_pts:g}")
        target_date = st.date_input("登録・修正する日を選択", value=date.today())

        @st.fragment
        def record_ui():
            st.divider()
            v = st.session_state.form_version
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("#### 🟢 投資型")
                sel_inv = [i for i in INVESTMENT_ITEMS if st.checkbox(i, key=f"inv_{i}_{v}")]
            with col2:
                st.markdown("#### 🔴 借金型")
                sel_debt = [i for i in DEBT_ITEMS if st.checkbox(i, key=f"debt_{i}_{v}")]
            
            n_inv, n_debt = len(sel_inv), len(sel_debt)
            inv_s, debt_s = "★" * min(n_inv, 10) + "☆" * max(0, 10 - n_inv), "★" * min(n_debt, 10) + "☆" * max(0, 10 - n_debt)
            
            # 星カード復活
            c1, c2 = st.columns(2)
            c1.markdown(f'<div class="status-card"><div class="status-label" style="color:#0066cc;">投資型</div><div class="star-display" style="color:#00cc99;">{inv_s}</div><div class="status-count">{n_inv if n_inv <= 10 else "10個以上"}個実施！</div></div>', unsafe_allow_html=True)
            c2.markdown(f'<div class="status-card"><div class="status-label" style="color:#cc3333;">借金型</div><div class="star-display" style="color:#ff4b4b;">{debt_s}</div><div class="status-count">{n_debt if n_debt <= 10 else "10個以上"}個実施！</div></div>', unsafe_allow_html=True)
            
            st.metric("本日のポイント", f"{n_inv - n_debt:+d}")
            if st.button("この内容で登録する", type="primary", use_container_width=True):
                db = conn.read(worksheet="Records", ttl="0s").astype(str)
                new_row = pd.DataFrame([{"real_name": current_emp_id, "date": str(target_date), "points": str(n_inv - n_debt), "investment_items": ", ".join(sel_inv), "debt_items": ", ".join(sel_debt)}])
                # 重複削除して保存
                others = db[~((db['real_name'].apply(normalize_id) == current_emp_id) & (db['date'] == str(target_date)))]
                conn.update(worksheet="Records", data=pd.concat([others, new_row]).reset_index(drop=True))
                st.session_state.form_version += 1
                st.cache_data.clear(); st.balloons(); st.rerun()
        record_ui()

    # --- タブ2: ランキング（左寄せ・小数なし復活） ---
    with tab2:
        st.subheader("🏆 累計ランキング")
        if not all_recs.empty:
            master = load_data_cached("UserMaster")
            rdf = all_recs.copy()
            rdf["points"] = pd.to_numeric(rdf["points"], errors='coerce').fillna(0)
            summary = rdf.groupby("real_name")["points"].sum().reset_index()
            summary = summary.merge(master[['emp_id', 'nickname']], left_on='real_name', right_on='emp_id', how='left')
            summary['表示名'] = summary['nickname'].apply(display_format)
            summary["順位"] = summary["points"].rank(ascending=False, method='min').astype(int)
            st.dataframe(summary.sort_values("順位")[["順位", "表示名", "points"]].rename(columns={"points":"累計"}), 
                         use_container_width=True, hide_index=True,
                         column_config={"順位": st.column_config.NumberColumn(alignment="left"), "累計": st.column_config.NumberColumn(format="%d", alignment="left")})

    # --- タブ3: マイデータ（安定のカレンダー方式） ---
    with tab3:
        st.subheader("🗓 履歴の確認")
        sel_date = st.date_input("確認したい日を選択してください", value=date.today())
        
        # 簡易マップ（表形式）で今月の記録状況を表示
        year, month = sel_date.year, sel_date.month
        cal = calendar.monthcalendar(year, month)
        recorded_dates = user_recs['date'].unique().tolist() if not user_recs.empty else []
        
        st.write(f"▼ {month}月の記録状況 (🔵=記録あり)")
        map_html = "<table style='width:100%; text-align:center; border-collapse:collapse; font-size:14px;'>"
        map_html += "<tr style='color:#666;'><td>月</td><td>火</td><td>水</td><td>木</td><td>金</td><td>土</td><td>日</td></tr>"
        for week in cal:
            map_html += "<tr>"
            for day in week:
                if day == 0: map_html += "<td></td>"
                else:
                    d_str = f"{year}-{month:02d}-{day:02d}"
                    dot = "🔵" if d_str in recorded_dates else ""
                    map_html += f"<td style='border:1px solid #eee; padding:5px;'>{day}<br>{dot}</td>"
            map_html += "</tr>"
        map_html += "</table>"
        st.markdown(map_html, unsafe_allow_html=True)
        
        st.divider()
        det = user_recs[user_recs['date'] == str(sel_date)]
        if not det.empty:
            d = det.iloc[0]
            st.info(f"📅 {sel_date} の詳細\n\n🟢 投資型: {display_format(d['investment_items'])}\n\n🔴 借金型: {display_format(d['debt_items'])}")
        else:
            st.warning("この日の記録はありません。")

    # --- タブ4: 設定 ---
    with tab4:
        st.button("ログアウト", on_click=lambda: st.session_state.update({"authenticated": False}))

if __name__ == "__main__":
    main()
