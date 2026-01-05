import os
from datetime import datetime
import pandas as pd
import streamlit as st

# ------------------------
# Settings
# ------------------------
APP_TITLE = "🐰 うさぎグルーミング管理"

DATA_DIR = "data"
PHOTO_DIR = os.path.join(DATA_DIR, "photos")
DATA_FILE = os.path.join(DATA_DIR, "rabbit_data.csv")

RABBITS = [
    ("R01", "kurumi"),
    ("R02", "みらい"),
    ("R03", "麦"),
    ("R04", "サントス"),
    ("R05", "咲希（チビトス）"),
]

LOG_COLUMNS = ["実施日時", "体重(g)", "メモ", "写真ファイル"]

# ------------------------
# Utility
# ------------------------
def base_dir() -> str:
    return os.path.dirname(os.path.abspath(__file__))

def abs_path(rel_path: str) -> str:
    return os.path.join(base_dir(), rel_path)

def ensure_dirs():
    os.makedirs(abs_path(DATA_DIR), exist_ok=True)
    os.makedirs(abs_path(PHOTO_DIR), exist_ok=True)

def to_dt_str(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d %H:%M")

def parse_dt_str(s: str):
    if not isinstance(s, str) or not s.strip():
        return None
    try:
        return datetime.strptime(s.strip(), "%Y-%m-%d %H:%M")
    except Exception:
        return None

# ------------------------
# Data (Rabbit master)
# ------------------------
def init_data():
    ensure_dirs()
    path = abs_path(DATA_FILE)
    if os.path.exists(path):
        return

    df = pd.DataFrame(
        {
            "RabbitID": [r[0] for r in RABBITS],
            "名前": [r[1] for r in RABBITS],
            "次回予約日時": ["" for _ in RABBITS],
        }
    )
    df.to_csv(path, index=False, encoding="utf-8-sig")

def load_data() -> pd.DataFrame:
    return pd.read_csv(abs_path(DATA_FILE), encoding="utf-8-sig")

def save_data(df: pd.DataFrame):
    df.to_csv(abs_path(DATA_FILE), index=False, encoding="utf-8-sig")

# ------------------------
# Logs
# ------------------------
def log_file_path(rabbit_id: str) -> str:
    ensure_dirs()
    return abs_path(os.path.join(DATA_DIR, f"grooming_{rabbit_id}.csv"))

def migrate_log_df(df: pd.DataFrame) -> pd.DataFrame:
    """
    既存CSVの列名が古くても、新仕様（実施日時/体重(g)/メモ/写真ファイル）に寄せる。
    想定する旧列:
      - datetime / weight_g / memo
      - 実施日時 / 体重(g) / メモ（写真ファイルなし）
    """
    if df is None or df.empty:
        return pd.DataFrame(columns=LOG_COLUMNS)

    df = df.copy()

    # 旧 -> 新 の列名マップ
    rename_map = {}
    if "datetime" in df.columns and "実施日時" not in df.columns:
        rename_map["datetime"] = "実施日時"
    if "weight_g" in df.columns and "体重(g)" not in df.columns:
        rename_map["weight_g"] = "体重(g)"
    if "memo" in df.columns and "メモ" not in df.columns:
        rename_map["memo"] = "メモ"
    if rename_map:
        df = df.rename(columns=rename_map)

    # 写真列がなければ追加
    if "写真ファイル" not in df.columns:
        df["写真ファイル"] = ""

    # 必須列がなければ作る
    for col in ["実施日時", "体重(g)", "メモ"]:
        if col not in df.columns:
            df[col] = ""

    # 型整形
    df["実施日時"] = pd.to_datetime(df["実施日時"], errors="coerce")
    df["体重(g)"] = pd.to_numeric(df["体重(g)"], errors="coerce")

    # 表示用に列順を固定
    df = df[LOG_COLUMNS]

    return df

def init_log(rabbit_id: str):
    path = log_file_path(rabbit_id)
    if os.path.exists(path):
        return
    pd.DataFrame(columns=LOG_COLUMNS).to_csv(path, index=False, encoding="utf-8-sig")

def load_log(rabbit_id: str) -> pd.DataFrame:
    path = log_file_path(rabbit_id)
    if not os.path.exists(path):
        init_log(rabbit_id)
        return pd.DataFrame(columns=LOG_COLUMNS)

    df = pd.read_csv(path, encoding="utf-8-sig")
    df2 = migrate_log_df(df)

    # 移行が入ったら保存し直しておく（次回以降安定）
    df2_save = df2.copy()
    df2_save["実施日時"] = df2_save["実施日時"].dt.strftime("%Y-%m-%d %H:%M")
    df2_save.to_csv(path, index=False, encoding="utf-8-sig")

    return df2

def save_uploaded_photo(rabbit_id: str, dt: datetime, uploaded_file) -> str:
    if uploaded_file is None:
        return ""

    ensure_dirs()

    ext = os.path.splitext(uploaded_file.name)[1].lower()
    if ext not in [".jpg", ".jpeg", ".png", ".webp"]:
        ext = ".jpg"

    safe_dt = dt.strftime("%Y%m%d_%H%M")
    filename = f"{rabbit_id}_{safe_dt}{ext}"
    path = abs_path(os.path.join(PHOTO_DIR, filename))

    with open(path, "wb") as f:
        f.write(uploaded_file.getbuffer())

    return filename

def append_log(rabbit_id: str, dt: datetime, weight_g: float | None, memo: str, photo_filename: str = ""):
    df = load_log(rabbit_id)

    new_row = {
        "実施日時": dt,
        "体重(g)": (pd.NA if weight_g is None else float(weight_g)),
        "メモ": memo,
        "写真ファイル": photo_filename,
    }

    df2 = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
    df2 = migrate_log_df(df2)

    # 保存は文字列で
    out = df2.copy()
    out["実施日時"] = out["実施日時"].dt.strftime("%Y-%m-%d %H:%M")
    out.to_csv(log_file_path(rabbit_id), index=False, encoding="utf-8-sig")

# ------------------------
# UI
# ------------------------
st.set_page_config(page_title=APP_TITLE, layout="wide")
st.title(APP_TITLE)
st.caption("✅ データはこのフォルダ内のCSVに保存されます（簡単・壊れにくい）")

init_data()
df = load_data()

rabbit_labels = [f"{row.RabbitID}：{row.名前}" for row in df.itertuples()]
sel_label = st.sidebar.selectbox("うさぎを選択", rabbit_labels)
sel_id = sel_label.split("：")[0]

row_idx = df.index[df["RabbitID"] == sel_id][0]
next_str = str(df.loc[row_idx, "次回予約日時"]) if "次回予約日時" in df.columns else ""
next_dt = parse_dt_str(next_str)

tab1, tab2, tab3 = st.tabs(["📅 次回予約（1件）", "🧼 当日完了登録", "📈 体重グラフ・履歴"])

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

with tab2:
    st.subheader("当日のグルーミング完了を登録")
    st.caption("完了を記録すると、次回予約は空になります（次回を改めて設定する運用）。")

    done_base = datetime.now().replace(second=0, microsecond=0)
    done_date = st.date_input("実施日", value=done_base.date(), key="done_date")
    done_time = st.time_input("実施時刻", value=done_base.time(), key="done_time")

    weight_g = st.number_input("体重（g）※未入力なら0のまま", min_value=0.0, max_value=10000.0, value=0.0, step=1.0)
    memo = st.text_area("メモ", placeholder="例）換毛多め、爪切りOK、耳掃除…", height=120)
    photo = st.file_uploader("写真（任意）", type=["jpg", "jpeg", "png", "webp"])

    if st.button("🧼 完了を記録する"):
        done_dt = datetime.combine(done_date, done_time)
        init_log(sel_id)

        w = None if weight_g == 0.0 else float(weight_g)
        photo_filename = save_uploaded_photo(sel_id, done_dt, photo)

        append_log(sel_id, done_dt, w, memo.strip(), photo_filename)

        df.loc[row_idx, "次回予約日時"] = ""
        save_data(df)

        st.success("記録しました（次回予約はクリアされました）")
        st.rerun()

with tab3:
    st.subheader("体重グラフ・履歴")

    init_log(sel_id)
    log_df = load_log(sel_id)

    if log_df.empty or log_df["実施日時"].dropna().empty:
        st.info("まだ履歴がありません。『当日完了登録』で記録してください。")
    else:
        view_df = log_df.copy().sort_values("実施日時", ascending=False)

        st.markdown("### 履歴（カード表示）")
        for _, row in view_df.iterrows():
            cols = st.columns([2, 1, 3])
            with cols[0]:
                dtv = row.get("実施日時")
                if pd.isna(dtv):
                    st.write("🕒 （日時不明）")
                else:
                    st.write(f"🕒 {pd.to_datetime(dtv).strftime('%Y-%m-%d %H:%M')}")
            with cols[1]:
                wv = row.get("体重(g)")
                st.write(f"⚖️ {'' if pd.isna(wv) else wv}")
            with cols[2]:
                st.write(str(row.get("メモ", "")))

            photo_name = str(row.get("写真ファイル", "")).strip()
            if photo_name:
                photo_path = abs_path(os.path.join(PHOTO_DIR, photo_name))
                if os.path.exists(photo_path):
                    st.image(photo_path, width=350)
                else:
                    st.caption("（写真ファイルが見つかりません）")

            st.divider()

        st.markdown("### 履歴データ（表）")
        with st.expander("開く / 閉じる", expanded=False):
            df_show = view_df.copy()
            df_show["実施日時"] = pd.to_datetime(df_show["実施日時"], errors="coerce").dt.strftime("%Y-%m-%d %H:%M")
            st.dataframe(df_show, width="stretch")

        st.markdown("### 体重推移")
        wdf = view_df.copy()
        wdf["体重(g)"] = pd.to_numeric(wdf["体重(g)"], errors="coerce")
        wdf = wdf.dropna(subset=["実施日時", "体重(g)"]).sort_values("実施日時")

        if wdf.empty:
            st.info("体重が入力された記録がないため、グラフは表示されません。")
        else:
            min_d = wdf["実施日時"].min().date()
            max_d = wdf["実施日時"].max().date()
            start_d, end_d = st.date_input("表示期間", value=(min_d, max_d), key="weight_range")

            wview = wdf[(wdf["実施日時"].dt.date >= start_d) & (wdf["実施日時"].dt.date <= end_d)]
            if wview.empty:
                st.warning("この期間には体重データがありません。期間を広げてください。")
            else:
                st.line_chart(wview.set_index("実施日時")["体重(g)"])
                st.caption("※単位：g（グラム）")
