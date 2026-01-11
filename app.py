import os
from datetime import datetime
from uuid import uuid4

import pandas as pd
import streamlit as st


# ========================
# Settings
# ========================
APP_TITLE = "🐰 うさぎグルーミング管理"

DATA_DIR = "data"
PHOTO_DIR = os.path.join(DATA_DIR, "photos")

# ★プロフィール画像置き場（GitHubに入れる）
PROFILE_DIR = os.path.join("assets", "profiles")

MASTER_FILE = os.path.join(DATA_DIR, "rabbit_data.csv")  # うさぎマスタ
LOG_FILE_TEMPLATE = os.path.join(DATA_DIR, "grooming_{rabbit_id}.csv")  # 履歴ログ

RABBITS = [
    ("R01", "kurumi"),
    ("R02", "みらい"),
    ("R03", "麦"),
    ("R04", "サントス"),
    ("R05", "咲希（チビトス）"),
]

# CSV列
COL_DT = "実施日時"
COL_W = "体重(g)"
COL_MEMO = "メモ"
COL_PHOTOS = "写真ファイル"  # 1行に複数写真を "a.jpg|b.png" のように保存


# ========================
# Utility
# ========================
def ensure_dirs():
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(PHOTO_DIR, exist_ok=True)
    # PROFILE_DIR はGit管理の想定。無くても動くが、あれば使う。
    os.makedirs(PROFILE_DIR, exist_ok=True)


def to_dt_str(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d %H:%M")


def parse_dt_str(s: str):
    if not isinstance(s, str) or not s.strip():
        return None
    try:
        return datetime.strptime(s.strip(), "%Y-%m-%d %H:%M")
    except Exception:
        return None


def split_photos(cell) -> list[str]:
    """CSVの '写真ファイル' セル → ['a.jpg','b.png'] に変換（空やnanに強い）"""
    if cell is None:
        return []
    s = str(cell).strip()
    if s == "" or s.lower() == "nan":
        return []
    parts = [p.strip() for p in s.split("|")]
    return [p for p in parts if p]


def join_photos(files: list[str]) -> str:
    """['a.jpg','b.png'] → 'a.jpg|b.png'"""
    files = [f.strip() for f in files if f and str(f).strip()]
    return "|".join(files)


def photo_path(filename: str) -> str:
    return os.path.join(PHOTO_DIR, filename)


def safe_delete_file(path: str) -> bool:
    try:
        if os.path.exists(path):
            os.remove(path)
        return True
    except Exception:
        return False


# ========================
# Profile Image
# ========================
def profile_path(rabbit_id: str) -> str | None:
    """
    assets/profiles/ に置いたプロフィール画像を探して返す。
    推奨ファイル名： R01.jpg / R02.png など（RabbitIDと同じ）
    """
    candidates = [
        os.path.join(PROFILE_DIR, f"{rabbit_id}.jpg"),
        os.path.join(PROFILE_DIR, f"{rabbit_id}.jpeg"),
        os.path.join(PROFILE_DIR, f"{rabbit_id}.png"),
        os.path.join(PROFILE_DIR, f"{rabbit_id}.webp"),
    ]
    for p in candidates:
        if os.path.exists(p):
            return p
    return None


# ========================
# Zoom (Dialog)
# ========================
def open_zoom(label: str, path: str):
    st.session_state["zoom_photo_label"] = label
    st.session_state["zoom_photo_path"] = path
    st.rerun()


def render_zoom_dialog_if_needed():
    p = st.session_state.get("zoom_photo_path")
    if not p:
        return

    label = st.session_state.get("zoom_photo_label", "写真")

    # Streamlit v1.25+ の dialog が使える環境はこれが一番安定
    try:
        @st.dialog(label)
        def _zoom_dialog():
            st.image(p, use_container_width=True)
            st.caption("※ Safari など一部ブラウザはピンチ拡大できます。")
            if st.button("閉じる"):
                st.session_state["zoom_photo_path"] = None
                st.rerun()

        _zoom_dialog()
    except Exception:
        # dialog が無い/効かない環境向けフォールバック（画面内に表示）
        st.markdown(f"## 🔎 {label}")
        st.image(p, use_container_width=True)
        st.caption("※ Safari など一部ブラウザはピンチ拡大できます。")
        if st.button("閉じる（拡大解除）"):
            st.session_state["zoom_photo_path"] = None
            st.rerun()


# ========================
# Master (Rabbit)
# ========================
def init_master():
    ensure_dirs()
    if os.path.exists(MASTER_FILE):
        return

    df = pd.DataFrame(
        {
            "RabbitID": [r[0] for r in RABBITS],
            "名前": [r[1] for r in RABBITS],
            "次回予約日時": ["" for _ in RABBITS],  # 次回1件だけ
        }
    )
    df.to_csv(MASTER_FILE, index=False, encoding="utf-8-sig")


def load_master() -> pd.DataFrame:
    init_master()
    return pd.read_csv(MASTER_FILE, encoding="utf-8-sig")


def save_master(df: pd.DataFrame):
    ensure_dirs()
    df.to_csv(MASTER_FILE, index=False, encoding="utf-8-sig")


# ========================
# Logs (Grooming)
# ========================
def log_file_path(rabbit_id: str) -> str:
    ensure_dirs()
    return LOG_FILE_TEMPLATE.format(rabbit_id=rabbit_id)


def init_log(rabbit_id: str):
    path = log_file_path(rabbit_id)
    if os.path.exists(path):
        return
    df = pd.DataFrame(columns=[COL_DT, COL_W, COL_MEMO, COL_PHOTOS])
    df.to_csv(path, index=False, encoding="utf-8-sig")


def load_log(rabbit_id: str) -> pd.DataFrame:
    path = log_file_path(rabbit_id)
    if not os.path.exists(path):
        init_log(rabbit_id)

    df = pd.read_csv(path, encoding="utf-8-sig")

    # 旧CSVとの互換（列が無い場合に追加）
    for c in [COL_DT, COL_W, COL_MEMO, COL_PHOTOS]:
        if c not in df.columns:
            df[c] = ""

    # 並び替え用のdt列
    df["_dt"] = pd.to_datetime(df[COL_DT], errors="coerce")
    df = df.dropna(subset=["_dt"])
    return df


def save_log(rabbit_id: str, df: pd.DataFrame):
    """内部列 _dt を除いて保存"""
    out = df.copy()
    if "_dt" in out.columns:
        out = out.drop(columns=["_dt"])
    out.to_csv(log_file_path(rabbit_id), index=False, encoding="utf-8-sig")


def save_uploaded_photos(rabbit_id: str, dt: datetime, uploaded_files) -> list[str]:
    """
    uploaded_files: list[UploadedFile] or None
    data/photos/ に保存して、保存したファイル名リストを返す
    """
    if not uploaded_files:
        return []

    ensure_dirs()

    saved = []
    base_dt = dt.strftime("%Y%m%d_%H%M")
    for uf in uploaded_files:
        if uf is None:
            continue
        ext = os.path.splitext(uf.name)[1].lower()
        if ext not in [".jpg", ".jpeg", ".png", ".webp"]:
            ext = ".jpg"

        unique = uuid4().hex[:8]
        filename = f"{rabbit_id}_{base_dt}_{unique}{ext}"
        path = photo_path(filename)

        with open(path, "wb") as f:
            f.write(uf.getbuffer())

        saved.append(filename)

    return saved


def append_log_row(
    rabbit_id: str,
    dt: datetime,
    weight_g: float | None,
    memo: str,
    photo_files: list[str],
):
    df = load_log(rabbit_id)

    new_row = {
        COL_DT: to_dt_str(dt),
        COL_W: ("" if weight_g is None else float(weight_g)),
        COL_MEMO: memo,
        COL_PHOTOS: join_photos(photo_files),
        "_dt": pd.to_datetime(to_dt_str(dt), errors="coerce"),
    }

    df2 = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
    save_log(rabbit_id, df2)


def delete_one_photo_from_row(rabbit_id: str, row_index: int, filename: str):
    """
    指定の行の写真リストから filename を1つ外す + ファイルも削除
    """
    df = load_log(rabbit_id).reset_index(drop=True)

    if row_index < 0 or row_index >= len(df):
        return

    photos = split_photos(df.loc[row_index, COL_PHOTOS])
    photos = [p for p in photos if p != filename]
    df.loc[row_index, COL_PHOTOS] = join_photos(photos)

    # 保存（CSV反映）
    save_log(rabbit_id, df)

    # ファイル削除（存在すれば）
    safe_delete_file(photo_path(filename))


# ========================
# UI
# ========================
ICON_PATH = os.path.join("assets", "icons", "icon.png")

st.set_page_config(
    page_title=APP_TITLE,
    page_icon=ICON_PATH,
    layout="wide"
)
st.title(APP_TITLE)
st.caption("✅ データは data/ に保存されます（Streamlit Cloud でも動作）")

init_master()
master_df = load_master()

# --- うさぎ選択（ここで sel_id が確定する） ---
rabbit_labels = [f"{row.RabbitID}：{row.名前}" for row in master_df.itertuples()]
sel_label = st.sidebar.selectbox("うさぎを選択", rabbit_labels)
sel_id = sel_label.split("：")[0]

# --- サイドバー：プロフィール画像（sel_id の後に置くのが正解） ---
st.sidebar.markdown("### 🐰 プロフィール")
pp = profile_path(sel_id)
if pp:
    st.sidebar.image(pp, use_container_width=True)
else:
    st.sidebar.info("プロフィール画像が未設定です（assets/profiles に R01.jpg などを置く）")

# 選択行（次回予約）
row_idx = master_df.index[master_df["RabbitID"] == sel_id][0]
next_str = str(master_df.loc[row_idx, "次回予約日時"]) if "次回予約日時" in master_df.columns else ""
next_dt = parse_dt_str(next_str)

tab1, tab2, tab3 = st.tabs(["📅 次回予約（1件）", "🧼 当日完了登録", "📈 体重グラフ・履歴（写真削除）"])


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
            master_df.loc[row_idx, "次回予約日時"] = to_dt_str(combined)
            save_master(master_df)
            st.success("保存しました")
            st.rerun()

    with col_b:
        if st.button("🗑 次回予約をクリア"):
            master_df.loc[row_idx, "次回予約日時"] = ""
            save_master(master_df)
            st.info("クリアしました")
            st.rerun()


# ------------------------
# Tab2: Done log + Photo upload (multiple)
# ------------------------
with tab2:
    st.subheader("当日のグルーミング完了を登録")
    st.caption("完了を記録すると、次回予約は“消化した”扱いで空になります。")

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

    st.markdown("### 写真（任意：複数OK）")
    photos = st.file_uploader(
        "写真を選択（複数選択できます）",
        type=["jpg", "jpeg", "png", "webp"],
        accept_multiple_files=True,
    )

    if st.button("🧼 完了を記録する"):
        done_dt = datetime.combine(done_date, done_time)
        init_log(sel_id)

        w = None if weight_g == 0.0 else float(weight_g)
        saved_files = save_uploaded_photos(sel_id, done_dt, photos)

        append_log_row(sel_id, done_dt, w, memo.strip(), saved_files)

        # 次回予約を消化してクリア
        master_df.loc[row_idx, "次回予約日時"] = ""
        save_master(master_df)

        st.success("記録しました（次回予約はクリアされました）")
        st.rerun()


# ------------------------
# Tab3: History + chart + delete photo + zoom
# ------------------------
with tab3:
    st.subheader("体重グラフ・履歴（写真の削除もここ）")

    init_log(sel_id)
    log_df = load_log(sel_id)

    if log_df.empty:
        st.info("まだ履歴がありません。『当日完了登録』で記録してください。")
    else:
        # 表示用（新しい順）
        view_df = log_df.copy()
        view_df = view_df.sort_values("_dt", ascending=False).reset_index(drop=True)

        st.markdown("### 履歴（新しい順）")
        with st.expander("履歴データ（CSV）", expanded=False):
            show_df = view_df.drop(columns=["_dt"], errors="ignore")
            st.dataframe(show_df, width="stretch")

        st.markdown("### 履歴カード（写真は1枚ずつ削除できます）")

        for i, row in view_df.iterrows():
            dt_str = str(row.get(COL_DT, ""))
            w_str = str(row.get(COL_W, ""))
            memo_str = str(row.get(COL_MEMO, ""))

            st.write(f"🕒 **{dt_str}**　　⚖️ **{w_str} g**")
            if memo_str and str(memo_str).lower() != "nan":
                st.write(memo_str)

            photos_list = split_photos(row.get(COL_PHOTOS, ""))

            if photos_list:
                for p in photos_list:
                    p_path = photo_path(p)

                    # 画像 + ボタン群
                    cols = st.columns([3, 1])
                    with cols[0]:
                        if os.path.exists(p_path):
                            st.image(p_path, width=420)
                        else:
                            st.caption(f"（写真が見つかりません：{p}）")

                    with cols[1]:
                        if os.path.exists(p_path):
                            if st.button("🔎 拡大", key=f"zoom_{sel_id}_{i}_{p}"):
                                open_zoom(f"📸 写真を拡大（{sel_id} / {dt_str}）", p_path)

                        if st.button("🗑 この写真を削除", key=f"del_{sel_id}_{i}_{p}"):
                            delete_one_photo_from_row(sel_id, i, p)
                            st.success("削除しました")
                            st.rerun()

            st.divider()

        # ---- 体重グラフ（体重があるものだけ）----
        wdf = log_df.copy()
        wdf[COL_W] = pd.to_numeric(wdf[COL_W], errors="coerce")
        wdf = wdf.dropna(subset=["_dt", COL_W]).sort_values("_dt")

        st.markdown("### 体重推移")
        if wdf.empty:
            st.info("体重が入力された記録がないため、グラフは表示されません。")
        else:
            min_d = wdf["_dt"].min().date()
            max_d = wdf["_dt"].max().date()

            start_d, end_d = st.date_input(
                "表示期間",
                value=(min_d, max_d),
                key="weight_range",
            )

            wview = wdf[(wdf["_dt"].dt.date >= start_d) & (wdf["_dt"].dt.date <= end_d)]
            if wview.empty:
                st.warning("この期間には体重データがありません。期間を広げてください。")
            else:
                st.line_chart(wview.set_index("_dt")[COL_W])
                st.caption("※単位：g（グラム）")

# ---- 画面の最後で、必要なら拡大ダイアログを出す ----
render_zoom_dialog_if_needed()
