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
# Paths (data/ 統一)
# ------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
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
    return pd.read_csv(DATA_FILE, encoding="utf-8-sig")


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


def _normalize_log_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    旧形式/揺れを吸収して、最終的に
    ["実施日時","体重(g)","メモ","写真ファイル"]
    を必ず持つ形にする。
    """
    if df is None or df.empty:
        return pd.DataFrame(columns=["実施日時", "体重(g)", "メモ", "写真ファイル"])

    # ありがちな旧列名 -> 新列名へ
    rename_map = {
        "datetime": "実施日時",
        "date": "実施日時",
        "日時": "実施日時",
        "weight_g": "体重(g)",
        "weight": "体重(g)",
        "体重": "体重(g)",
        "memo": "メモ",
        "photo": "写真ファイル",
        "photo_filename": "写真ファイル",
        "写真": "写真ファイル",
    }
    df = df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns})

    # 必須列が無ければ追加
    for c in ["実施日時", "体重(g)", "メモ", "写真ファイル"]:
        if c not in df.columns:
            df[c] = ""

    # 型を整える（ここが Streamlit Cloud の .dt エラー回避の本丸）
    df["実施日時"] = pd.to_datetime(df["実施日時"], errors="coerce")
    df["体重(g)"] = pd.to_numeric(df["体重(g)"], errors="coerce")

    return df


def load_log(rabbit_id: str) -> pd.DataFrame:
    path = log_file_path(rabbit_id)
    if not os.path.exists(path):
        init_log(rabbit_id)

    df = pd.read_csv(path, encoding="utf-8-sig")
    df = _normalize_log_columns(df)

    # 実施日時が読めない行は落とす（空行など）
    df = df.dropna(subset=["実施日時"]).sort_values("実施日時", ascending=False)
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
    # 既存ログを読む（列ゆれ吸収済）
    df = load_log(rabbit_id)

    new_row = {
        "実施日時": dt,  # datetimeで持つ
        "体重(g)": (None if weight_g is None else float(weight_g)),
        "メモ": memo,
        "写真ファイル": photo_filename,
    }
    df2 = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
    df2 = _normalize_log_columns(df2).sort_values("実施日時", ascending=False)

    # 保存時は文字列にしてCSVへ（dt accessorで落ちないように必ず to_datetime 済）
    out = df2.copy()
    out["実施日時"] = pd.to_datetime(out["実施日時"], errors="coerce").dt.strftime("%Y-%m-%d %H:%M")
    out.to_csv(log_file_path(rabbit_id), index=False, encoding="utf-8-sig")


# ------------------------
# UI
# ------------------------
st.set_page_config(page_title=APP_TITLE, layout="wide")
st.title(APP_TITLE)
st.caption("✅ VS Code不要 / データはこのフォルダ内のCSVに保存されます（簡単・壊れにくい）")

init_data()
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

    weight_g = st.number_input("体重（g）※未入力なら0のまま", min_value=0.0, max_value=10000.0, value=0.0, step=1.0)
    memo = st.text_area("メモ", placeholder="例）換毛多め、爪切りOK、耳掃除…", height=120)

    photo = st.file_uploader("写真（任意）", type=["jpg", "jpeg", "png", "webp"])

    if st.button("🧼 完了を記録する"):
        done_dt = datetime.combine(done_date, done_time)
        init_log(sel_id)

        w = None if weight_g == 0.0 else float(weight_g)

        # 写真を保存
        photo_filename = save_uploaded_photo(sel_id, done_dt, photo)

        # ログ追記
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
        # 履歴（カード表示）
        st.markdown("### 履歴（新しい順）")
        for _, row in log_df.iterrows():
            dt = row["実施日時"]
            w = row.get("体重(g)", None)
            memo_txt = str(row.get("メモ", "") or "")

            cols = st.columns([2, 1, 4])
            with cols[0]:
                st.write(f"🕒 {dt.strftime('%Y-%m-%d %H:%M') if pd.notna(dt) else ''}")
            with cols[1]:
                st.write(f"⚖️ {'' if pd.isna(w) else int(w)} g")
            with cols[2]:
                st.write(memo_txt)

            photo_name = str(row.get("写真ファイル", "") or "").strip()
            if photo_name:
                photo_path = os.path.join(PHOTO_DIR, photo_name)
                if os.path.exists(photo_path):
                    st.image(photo_path, width=360)
                else:
                    st.caption("（写真ファイルが見つかりません）")

            st.divider()

        # 表（デバッグ用）
        with st.expander("履歴データ（表）"):
            view = log_df.copy()
            view["実施日時"] = view["実施日時"].dt.strftime("%Y-%m-%d %H:%M")
            st.dataframe(view, width="stretch")

        # 体重グラフ（体重があるものだけ）
        wdf = log_df.dropna(subset=["体重(g)"]).copy()
        wdf = wdf.sort_values("実施日時", ascending=True)

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
