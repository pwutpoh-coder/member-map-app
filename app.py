from urllib.parse import quote
import folium
from folium.plugins import FastMarkerCluster
import pandas as pd
import streamlit as st
from streamlit_folium import st_folium

# ตั้งค่าหน้าเว็บ Streamlit (Layout กว้างเต็มจอ)
st.set_page_config(
    page_title="ระบบแผนที่จัดส่งสินค้า (High Performance)",
    page_icon="🗺️",
    layout="wide",
)

# ตกแต่ง UI เล็กน้อย
st.markdown(
    """
    <style>
        .main-header {
            font-size: 24px;
            font-weight: bold;
            color: #1e293b;
            margin-bottom: 5px;
        }
    </style>
""",
    unsafe_allow_html=True,
)

st.markdown(
    '<div class="main-header">🗺️ ระบบแผนที่และข้อมูลการจัดส่งสินค้า (โหมดความเร็วสูง)</div>',
    unsafe_allow_html=True,
)

# ข้อมูล Google Sheets
SHEET_ID = "1Ze82Uc0r179gcGvfCyE4KsrK5n8wFTAzZmLh1If1-9A"
SHEET_NAME = "ข้อมูล"


# 1. โหลดข้อมูลแบบแคชระดับสูง
@st.cache_data(ttl=600, show_spinner=False)
def load_data():
  encoded_sheet_name = quote(SHEET_NAME)
  url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet={encoded_sheet_name}"
  df = pd.read_csv(url, encoding="utf-8", dtype=str, low_memory=False)
  return df


try:
  with st.spinner(
      "กำลังโหลดข้อมูลจำนวนมากจาก Google Sheets กรุณารอสักครู่..."
  ):
    df = load_data()
except Exception as e:
  st.error(f"❌ ไม่สามารถโหลดข้อมูลจาก Google Sheets ได้: {e}")
  st.stop()

if "พิกัด GPS" not in df.columns:
  st.error("❌ ไม่พบคอลัมน์ 'พิกัด GPS' ในไฟล์ Google Sheets")
  st.stop()

# กรองแถวที่ไม่มีพิกัดออกอย่างรวดเร็ว
df = df.dropna(subset=["พิกัด GPS"])
df = df[df["พิกัด GPS"].str.contains(",", na=False)]


# 2. แปลงพิกัดแบบความเร็วสูง (Vectorized / Optimized parsing)
@st.cache_data(show_spinner=False)
def process_coordinates(data_frame):
  # แยกสตริงพิกัดแบบรวดเร็ว
  split_coords = data_frame["พิกัด GPS"].str.split(",", expand=True)
  if split_coords.shape[1] >= 2:
    data_frame["lat"] = pd.to_numeric(split_coords[0], errors="coerce")
    data_frame["lon"] = pd.to_numeric(split_coords[1], errors="coerce")
  else:
    data_frame["lat"] = None
    data_frame["lon"] = None
  return data_frame.dropna(subset=["lat", "lon"])


df = process_coordinates(df)

# --- Sidebar: ตัวกรองข้อมูล (Dropdown) ---
st.sidebar.header("🔍 ตัวกรองข้อมูล (Filters)")

warehouses = (
    ["ทั้งหมด"] + df["คลัง"].dropna().unique().tolist()
    if "คลัง" in df.columns
    else ["ทั้งหมด"]
)
sel_warehouse = st.sidebar.selectbox("เลือกคลังสินค้า", warehouses, index=0)

trucks = (
    ["ทั้งหมด"] + df["เบอร์รถ"].dropna().unique().tolist()
    if "เบอร์รถ" in df.columns
    else ["ทั้งหมด"]
)
sel_truck = st.sidebar.selectbox("เลือกเบอร์รถ", trucks, index=0)

rounds = (
    ["ทั้งหมด"] + df["รอบส่งประจำสัปดาห์"].dropna().unique().tolist()
    if "รอบส่งประจำสัปดาห์" in df.columns
    else ["ทั้งหมด"]
)
sel_round = st.sidebar.selectbox("เลือกรอบส่งประจำสัปดาห์", rounds, index=0)

# กรองข้อมูลตาม Dropdown
filtered_df = df.copy()
if sel_warehouse != "ทั้งหมด":
  filtered_df = filtered_df[filtered_df["คลัง"] == sel_warehouse]
if sel_truck != "ทั้งหมด":
  filtered_df = filtered_df[filtered_df["เบอร์รถ"] == sel_truck]
if sel_round != "ทั้งหมด":
  filtered_df = filtered_df[filtered_df["รอบส่งประจำสัปดาห์"] == sel_round]

# --- เลือกหน้า (แยกสี 3 หน้า) ---
st.sidebar.markdown("---")
page = st.sidebar.radio(
    "📊 เลือกมุมมองแผนที่แยกสี",
    [
        "หน้า 1: แยกสีตาม 'คลัง'",
        "หน้า 2: แยกสีตาม 'เบอร์รถ'",
        "หน้า 3: แยกสีตาม 'ยอดส่งประจำสัปดาห์'",
    ],
)

# --- ตั้งค่าจำนวนแถวแสดงผลตาราง ---
st.sidebar.markdown("---")
row_limit = st.sidebar.selectbox(
    "⚡ แสดงตารางด้านล่างครั้งละ (แถว):", [50, 100, 500, "ทั้งหมด"], index=0
)


# ==========================================
# 1. ส่วนแผนที่ (อยู่ด้านบนสุด - ใช้ FastMarkerCluster โหลดเร็วสูงสุด)
# ==========================================
st.subheader(
    f"🗺️ แผนที่แสดงพิกัดทั้งหมด (จำนวน {len(filtered_df):,} จุดตามตัวกรอง)"
)

map_df = filtered_df.reset_index(drop=True)

if not map_df.empty:
  center_lat = map_df["lat"].mean()
  center_lon = map_df["lon"].mean()
else:
  center_lat, center_lon = 13.7563, 100.5018

# สร้างแผนที่พื้นฐาน
m = folium.Map(
    location=[center_lat, center_lon], zoom_start=10, tiles="CartoDB positron"
)

# เตรียมข้อมูลพิกัดสำหรับ FastMarkerCluster (รองรับข้อมูลแสนจุดโดยไม่กระตุก)
# สร้างลิสต์ของ [lat, lon, popup_text]
marker_data = []
for idx, row in map_df.iterrows():
  popup_info = (
      f"<b>รหัส:</b> {row.get('รหัสสมาชิก', '-')}<br>"
      f"<b>ชื่อ:</b> {row.get('ชื่อ-นามสกุล', '-')}<br>"
      f"<b>คลัง:</b> {row.get('คลัง', '-')}<br>"
      f"<b>เบอร์รถ:</b> {row.get('เบอร์รถ', '-')}<br>"
      f"<b>รอบส่ง:</b> {row.get('รอบส่งประจำสัปดาห์', '-')}"
  )
  marker_data.append(
      [float(row["lat"]), float(row["lon"]), popup_info]
  )

# ใช้ FastMarkerCluster เพื่อรวมจุดและเรนเดอร์ความเร็วสูง
if marker_data:
  FastMarkerCluster(marker_data).add_to(m)

# แสดงแผนที่ด้านบน
st_data = st_folium(m, width="100%", height=500)


# ==========================================
# 2. ส่วนตารางข้อมูล (อยู่ด้านล่าง)
# ==========================================
st.markdown("---")
st.subheader("📋 รายละเอียดข้อมูล (แสดงด้านล่าง)")
st.info(
    "💡 แสดงข้อมูลตามตัวกรองด้านข้าง สามารถเลือกดูแบบ 50, 100, 500 หรือทั้งหมดได้"
)

display_cols = [
    c
    for c in [
        "รหัสสมาชิก",
        "ชื่อ-นามสกุล",
        "ที่อยู่จัดส่ง บ้านเลขที่/อาคาร",
        "คลัง",
        "เบอร์รถ",
        "รอบส่งประจำสัปedarห์",
        "ยอดส่ง/เดือน ( ก.ย.69)",
    ]
    if c in filtered_df.columns
]

if not filtered_df.empty:
  table_df = filtered_df[display_cols].reset_index(drop=True)
  table_display = (
      table_df.head(int(row_limit)) if row_limit != "ทั้งหมด" else table_df
  )

  st.dataframe(table_display, use_container_width=True)
