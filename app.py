import os
from datetime import datetime
import pandas as pd
import streamlit as st

APP_TITLE = "🐰 うさぎグルーミング管理"

RABBITS = [
    ("R01", "kurumi"),
    ("R02", "みらい"),
    ("R03", "麦"),
    ("R04", "サントス"),
    ("R05", "咲希（チビトス）"),
]

# ------------------------
# Paths
# ------------------------
def here_path(*parts: str) -> str:
    """この app.py がある場所を起点にパスを作る（Cloudでもローカルでも安定）"""
    base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, *parts)

DATA_DIR = here_path("data")
PHOTO_DIR = os.path.join(DATA_DIR, "photos")
DATA_FILE = os.path.join(DATA_DIR, "rabbit_data.csv")

# ------------------------
# Utility
# ------------------------
def to_dt_str(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d %H:%M")

def parse_dt_str(s: str):
    if not isinstance(s, str) or not s.strip():
        return None
    try:
        return datetime.strptime(s.strip(), "%Y-%m-%d %H:%M")
    except Exception:
        return None

def ensure_dirs():
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(PHOTO_DIR, exist_ok=True)

# ------------------------
# Data (Rabbit master)
# ------------------------
def init_data():
    ensure_dirs()
    if os.path.exists(DATA_FILE):
        return

    df = pd.DataFrame(
        {
            "RabbitID": [r[0] for r in RABBITS],
            "名前": [r[1] for r in RABBITS],
            "次回予約日時": ["" for _ in RABBITS],  # 1件だけ管理
        }
    )
    df.to_csv(DATA_FILE, index=False, encoding="utf-8-sig")

def load_data() -> pd.DataFrame:
    init_data()
    df = pd.read_csv(DATA_FILE, encoding="utf-8-sig")
    # 念のため列が欠けていたら補完
    if "次回予約日時" not in df.columns:
        df["次回予約日時"] = ""
    return df

def save_data(df: pd.DataFrame):
    ensure_dirs()
    df.to_csv(DATA_FILE, index=False, encoding="utf-8-sig")

# ------------------------
# Data (Logs)
# ------------------------
def log_file_path(rabbit_id: str) -> str:
    ensure_dirs()
    return os.path.join(DATA_DIR, f"grooming_{rabbit_id}.csv")

def init_log(rabbit_id: str):
    path = log_file_path(rabbit_id)
    if os.path.exists(path):
        return
    df = pd.DataFrame(columns=["実施日時", "体重(g)", "メモ", "写真ファイル"])
    df.to_csv(path, index=False, encoding="utf-8-sig")

def load_log(rabbit_id: str) -> pd.DataFrame:
    path = log_file_path(rabbit_id)
    if not os.path.exists(path):
        init_log(rabbit_id)

    df = pd.read_csv(path, encoding="utf-8-sig")

    # 列補完（古いCSV/途中変更でも落ちないように）
    for col in ["実施日時", "体重(g)", "メモ", "写真ファイル"]:
        if col not in df.columns:
            df[col] = ""

    # 型整形（ここが Cloud で落ちてたポイント）
    df["実施日時"] = pd.to_datetime(df["実施日時"], errors="coerce")
    df["体重(g)"] = pd.to_numeric(df["体重(g)"], errors="coerce")

    return df

def save_uploaded_photo(rabbit_id: str, dt: datetime, uploaded_file) -> str:
    """uploaded_file があれば data/photos に保存してファイル名を返す。なければ空文字。"""
    if uploaded_file is None:
        return ""

    ensure_dirs()

    ext = os.path.splitext(uploaded_file.name)[1].lower()
    if ext not in [".jpg", ".jpeg", ".png", ".webp"]:
        ext = ".jpg"

    safe_dt = dt.strftime("%Y%m%d_%H%M")
    filename = f"{rabbit_id}_{safe_dt}{ext}"
    path = os.path.join(PHOTO_DIR, filename)

    with open(path, "wb") as f:
        f.write(uploaded_file.getbuffer())

    return filename

def append_log(rabbit_id: str, dt: datetime, weight_g: float | None, memo: str, photo_filename: str = ""):
    df = load_log(rabbit_id)
    new_row = {
        "実施日時": to_dt_str(dt),
        "体重(g)": ("" if weight_g is None else float(weight_g)),
        "メモ": memo,
        "写真ファイル": photo_filename,
    }
    df2 = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
    df2.to_csv(log_file_path(rabbit_id), index=False, encoding="utf-8-sig")

# ------------------------
# UI
# ------------------------
st.set_page_config(page_title=APP_TITLE, layout="wide")
st.title(APP_TITLE)
st.caption("✅ VS Code不要 / データは data/ フォルダ内のCSVに保存されます（簡単・壊れにくい）")

df = load_data()

# うさぎ選択
rabbit_labels = [f"{row.RabbitID}：{row.名前}" for row in df.itertuples()]
sel_label = st.sidebar.selectbox("うさぎを選択", rabbit_labels)
sel_id = sel_label.split("：")[0]

# 選択行
row_idx = df.index[df["RabbitID"] == sel_id][0]
next_str = str(df.loc[row_idx, "次回予約日時"]) if "次回予約日時" in df.columns else ""
next_dt = parse_dt_str(next_str)

# タブ
tab1, tab2, tab3 = st.tabs(["📅 次回予約（1件）", "🧼 当日完了登録", "📈 体重グラフ・履歴"])

# ------------------------
# Tab1: Next booking
# ------------------------
with tab1:
    st.subheader("次回グルーミング予約（うさぎごとに“次回1件だけ”）")

    if next_dt:
        st.success(f"次回予約日時：{to_dt_str(next_dt)}")
    else:
        st.warning("次回予約が未設定です")

    st.markdown("### 次回予約を設定 / 更新")
    base = next_dt if next_dt else datetime.now().replace(second=0, microsecond=0)

    d = st.date_input("日付", value=base.date(), key="next_date")
    t = st.time_input("時刻", value=base.time(), key="next_time")

    col_a, col_b = st.columns(2)
    with col_a:
        if st.button("✅ 次回予約を保存"):
            combined = datetime.combine(d, t)
            df.loc[row_idx, "次回予約日時"] = to_dt_str(combined)
            save_data(df)
            st.success("保存しました")
            st.rerun()

    with col_b:
        if st.button("🗑 次回予約をクリア"):
            df.loc[row_idx, "次回予約日時"] = ""
            save_data(df)
            st.info("クリアしました")
            st.rerun()

# ------------------------
# Tab2: Done log
# ------------------------
with tab2:
    st.subheader("当日のグルーミング完了を登録")
    st.caption("完了を記録すると、次回予約は“消化した”扱いで空になります（次回を改めて設定する運用）。")

    done_base = datetime.now().replace(second=0, microsecond=0)
    done_date = st.date_input("実施日", value=done_base.date(), key="done_date")
    done_time = st.time_input("実施時刻", value=done_base.time(), key="done_time")

    weight_g = st.number_input(
        "体重（g）※未入力なら0のまま",
        min_value=0.0,
        max_value=10000.0,
        value=0.0,
        step=1.0,
    )
    memo = st.text_area("メモ", placeholder="例）換毛多め、爪切りOK、耳掃除…", height=120)

    photo = st.file_uploader("写真（任意）", type=["jpg", "jpeg", "png", "webp"])

    if st.button("🧼 完了を記録する"):
        done_dt = datetime.combine(done_date, done_time)
        init_log(sel_id)

        w = None if weight_g == 0.0 else float(weight_g)

        # 写真保存（任意）
        photo_filename = save_uploaded_photo(sel_id, done_dt, photo)

        append_log(sel_id, done_dt, w, memo.strip(), photo_filename)

        # 次回予約を消化してクリア
        df.loc[row_idx, "次回予約日時"] = ""
        save_data(df)

        st.success("記録しました（次回予約はクリアされました）")
        st.rerun()

# ------------------------
# Tab3: Weight chart & history
# ------------------------
with tab3:
    st.subheader("体重グラフ・履歴")

    init_log(sel_id)
    log_df = load_log(sel_id)

    if log_df.empty:
        st.info("まだ履歴がありません。『当日完了登録』で記録してください。")
    else:
        # --- 履歴（新しい順）
        view_df = log_df.copy()
        view_df = view_df.sort_values("実施日時", ascending=False)

        st.markdown("### 履歴（カード表示 / 新しい順）")
        for _, row in view_df.iterrows():
            dt = row["実施日時"]
            dt_str = dt.strftime("%Y-%m-%d %H:%M") if pd.notna(dt) else ""
            w = row["体重(g)"]
            w_str = "" if pd.isna(w) else f"{int(w)} g" if float(w).is_integer() else f"{w} g"
            memo_str = str(row.get("メモ", "") or "")

            cols = st.columns([2, 1, 4])
            with cols[0]:
                st.write(f"🕒 {dt_str}")
            with cols[1]:
                st.write(f"⚖️ {w_str}")
            with cols[2]:
                st.write(memo_str)

            photo_name = str(row.get("写真ファイル", "") or "").strip()
            if photo_name:
                photo_path = os.path.join(PHOTO_DIR, photo_name)
                if os.path.exists(photo_path):
                    st.image(photo_path, width=350)
                else:
                    st.caption("（写真ファイルが見つかりません：Cloudでは再起動等で消える場合があります）")

            st.divider()

        # --- 表（確認用）
        st.markdown("### 履歴データ（表）")
        with st.expander("履歴データ", expanded=False):
            # 実施日時を表示用文字列にしてから表示
            show_df = view_df.copy()
            show_df["実施日時"] = show_df["実施日時"].dt.strftime("%Y-%m-%d %H:%M")
            st.dataframe(show_df, width="stretch")

        # --- 体重グラフ（体重があるものだけ）
        wdf = log_df.copy()
        wdf = wdf.dropna(subset=["実施日時", "体重(g)"]).sort_values("実施日時")

        st.markdown("### 体重推移")
        if wdf.empty:
            st.info("体重が入力された記録がないため、グラフは表示されません。")
        else:
            min_d = wdf["実施日時"].min().date()
            max_d = wdf["実施日時"].max().date()

            start_d, end_d = st.date_input(
                "表示期間",
                value=(min_d, max_d),
                key="weight_range",
            )

            wview = wdf[(wdf["実施日時"].dt.date >= start_d) & (wdf["実施日時"].dt.date <= end_d)]
            if wview.empty:
                st.warning("この期間には体重データがありません。期間を広げてください。")
            else:
                st.line_chart(wview.set_index("実施日時")["体重(g)"])
                st.caption("※単位：g（グラム）")
