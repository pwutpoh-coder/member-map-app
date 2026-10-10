from urllib.parse import quote
import folium
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
    '<div class="main-header">🗺️ ระบบแผนที่และข้อมูลการจัดส่งสินค้า</div>',
    unsafe_allow_html=True,
)

# ข้อมูล Google Sheets
SHEET_ID = "1Ze82Uc0r179gcGvfCyE4KsrK5n8wFTAzZmLh1If1-9A"
SHEET_NAME = "ข้อมูล"


# ฟังก์ชันโหลดข้อมูลพร้อมแคชระดับสูง (เพิ่มความเร็วในการเปิดใช้งานครั้งถัดไป)
@st.cache_data(ttl=600, show_spinner=False)
def load_data():
  encoded_sheet_name = quote(SHEET_NAME)
  url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet={encoded_sheet_name}"
  # โหลดเฉพาะคอลัมน์ที่จำเป็นหรือโหลดแบบกำหนดประเภทข้อมูล string เพื่อความเร็ว
  df = pd.read_csv(url, encoding="utf-8", dtype=str, low_memory=False)
  return df


# โหลดข้อมูลแบบปลอดภัย พร้อมแสดงสถานะกำลังโหลด
try:
  with st.spinner("กำลังโหลดข้อมูลจาก Google Sheets (ความเร็วสูง)..."):
    df = load_data()
except Exception as e:
  st.error(f"❌ ไม่สามารถโหลดข้อมูลจาก Google Sheets ได้: {e}")
  st.info(
      "คำแนะนำ: ตรวจสอบว่าลิงก์ Google Sheets เปิดแชร์สิทธิ์เป็น 'Anyone with"
      " the link can view' หรือยัง"
  )
  st.stop()

# ตรวจสอบคอลัมน์พิกัด
if "พิกัด GPS" not in df.columns:
  st.error(
      "❌ ไม่พบคอลัมน์ 'พิกัด GPS' ในไฟล์ กรุณาตรวจสอบชื่อคอลัมน์ใน Google"
      " Sheets อีกครั้ง"
  )
  st.stop()

# ทำความสะอาดข้อมูลพิกัดเบื้องต้น
df = df.dropna(subset=["พิกัด GPS"])
df = df[df["พิกัด GPS"].str.contains(",", na=False)]


# ฟังก์ชันแปลงพิกัดอย่างรวดเร็ว
@st.cache_data(show_spinner=False)
def process_coordinates(data_frame):
  lats = []
  lons = []
  for val in data_frame["พิกัด GPS"]:
    try:
      parts = val.split(",")
      lats.append(float(parts[0].strip()))
      lons.append(float(parts[1].strip()))
    except:
      lats.append(None)
      lons.append(None)
  data_frame["lat"] = lats
  data_frame["lon"] = lons
  return data_frame.dropna(subset=["lat", "lon"])


df = process_coordinates(df)

# --- Sidebar: ตัวกรองข้อมูล (Dropdown) ---
st.sidebar.header("🔍 ตัวกรองข้อมูล (Filters)")

# คลัง
warehouses = (
    ["ทั้งหมด"] + df["คลัง"].dropna().unique().tolist()
    if "คลัง" in df.columns
    else ["ทั้งหมด"]
)
sel_warehouse = st.sidebar.selectbox("เลือกคลังสินค้า", warehouses, index=0)

# เบอร์รถ
trucks = (
    ["ทั้งหมด"] + df["เบอร์รถ"].dropna().unique().tolist()
    if "เบอร์รถ" in df.columns
    else ["ทั้งหมด"]
)
sel_truck = st.sidebar.selectbox("เลือกเบอร์รถ", trucks, index=0)

# รอบส่ง
rounds = (
    ["ทั้งหมด"] + df["รอบส่งประจำสัปดาห์"].dropna().unique().tolist()
    if "รอบส่งประจำสัปดาห์" in df.columns
    else ["ทั้งหมด"]
)
sel_round = st.sidebar.selectbox("เลือกรอบส่งประจำสัปดาห์", rounds, index=0)

# กรองข้อมูลตาม Dropdown (ใช้วิธี vectorized เพื่อความเร็ว)
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
# 1. ส่วนแผนที่ (แสดงอยู่ด้านบนสุด)
# ==========================================
st.subheader("🗺️ แผนที่แสดงตำแหน่งพิกัดทั้งหมด")

map_df = filtered_df.reset_index(drop=True)

if not map_df.empty:
  center_lat = map_df["lat"].astype(float).mean()
  center_lon = map_df["lon"].astype(float).mean()
else:
  center_lat, center_lon = 13.7563, 100.5018

m = folium.Map(
    location=[center_lat, center_lon], zoom_start=11, tiles="CartoDB positron"
)


def get_color_mapping(categories):
  colors = [
      "blue",
      "darkblue",
      "cadetblue",
      "purple",
      "darkpurple",
      "pink",
      "orange",
      "lightred",
      "beige",
      "green",
      "darkgreen",
      "lightgreen",
  ]
  return {
      str(cat): colors[i % len(colors)] for i, cat in enumerate(categories)
  }


if "หน้า 1" in page:
  color_col = "คลัง"
elif "หน้า 2" in page:
  color_col = "เบอร์รถ"
else:
  color_col = (
      "รอบส่งประจำสัปดาห์"
      if "รอบส่งประจำสัปดาห์" in map_df.columns
      else "คลัง"
  )

unique_cats = (
    map_df[color_col].dropna().unique().tolist()
    if color_col in map_df.columns
    else []
)
color_map = get_color_mapping(unique_cats)

# ตัวแปรเก็บสถานะการเลือกแถวจากตารางด้านล่าง (ส่งผ่าน session_state)
selected_indices = st.session_state.get("selected_row_indices", [])

# วาดหมุดทั้งหมดลงบนแผนที่โดยไม่ถูกจำกัดด้วยตาราง 50 แถวแรก
for idx, row in map_df.iterrows():
  lat, lon = float(row["lat"]), float(row["lon"])

  # ตรวจสอบการเลือกแถวในตาราง
  is_selected = True
  if selected_indices:
    if idx in selected_indices:
      is_selected = True
    else:
      is_selected = False

  if is_selected:
    cat_val = str(row.get(color_col, "default"))
    pin_color = color_map.get(cat_val, "blue")
  else:
    pin_color = "gray"  # เปลี่ยนเป็นสีเทาเมื่อไม่ได้เลือกในตาราง

  # เอาเมาส์ชี้ (Tooltip) แสดงข้อมูลทันทีโดยไม่ต้องคลิก
  tooltip_html = f"""
    <b>รหัส:</b> {row.get('รหัสสมาชิก', '-')}<br>
    <b>ชื่อ:</b> {row.get('ชื่อ-นามสกุล', '-')}<br>
    <b>คลัง:</b> {row.get('คลัง', '-')}<br>
    <b>เบอร์รถ:</b> {row.get('เบอร์รถ', '-')}<br>
    <b>รอบส่ง:</b> {row.get('รอบส่งประจำสัปดาห์', '-')}
    """

  # คลิกเพื่อดูรายละเอียดเพิ่มเติม (Popup)
  popup_html = f"""
    <div style="width: 200px; font-size: 12px; font-family: sans-serif; background-color: #ffffff; padding: 8px; border-radius: 6px; border: 1px solid #cbd5e1;">
        <b>รหัสสมาชิก:</b> {row.get('รหัสสมาชิก', '-')}<br>
        <b>ชื่อ-นามสกุล:</b> {row.get('ชื่อ-นามสกุล', '-')}<br>
        <b>ที่อยู่:</b> {row.get('ที่อยู่จัดส่ง บ้านเลขที่/อาคาร', '-')}<br>
        <b>คลัง:</b> {row.get('คลัง', '-')}<br>
        <b>เบอร์รถ:</b> {row.get('เบอร์รถ', '-')}<br>
        <b>รอบส่ง:</b> {row.get('รอบส่งประจำสัปดาห์', '-')}<br>
        <b>ยอดส่ง:</b> {row.get('ยอดส่ง/เดือน ( ก.ย.69)', '-')}
    </div>
    """

  folium.Marker(
      location=[lat, lon],
      popup=folium.Popup(popup_html, max_width=300),
      tooltip=folium.Tooltip(tooltip_html, sticky=True),
      icon=folium.Icon(color=pin_color, icon="info-sign"),
  ).add_to(m)

# แสดงแผนที่ด้านบน
st_data = st_folium(m, width="100%", height=500)


# ==========================================
# 2. ส่วนตารางข้อมูล (แสดงอยู่ด้านล่าง)
# ==========================================
st.markdown("---")
st.subheader("📋 รายละเอียดข้อมูลและเลือกพิกัด (แสดงด้านล่าง)")
st.info(
    "💡 คลิกเลือกแถวในตารางด้านล่างเพื่อเน้นพิกัดบนแผนที่ด้านบน (พิกัดอื่นจะกลายเป็นสีเทา)"
)

display_cols = [
    c
    for c in [
        "รหัสสมาชิก",
        "ชื่อ-นามสกุล",
        "ที่อยู่จัดส่ง บ้านเลขที่/อาคาร",
        "คลัง",
        "เบอร์รถ",
        "รอบส่งประจำสัปดาห์",
        "ยอดส่ง/เดือน ( ก.ย.69)",
    ]
    if c in filtered_df.columns
]

if not filtered_df.empty:
  table_df = filtered_df[display_cols].reset_index(drop=True)
  table_display = (
      table_df.head(int(row_limit)) if row_limit != "ทั้งหมด" else table_df
  )

  event = st.dataframe(
      table_display,
      use_container_width=True,
      on_select="rerun",
      selection_mode="multi-row",
      key="main_table_bottom",
  )

  # ดึงข้อมูลแถวที่ถูกเลือกจากตารางด้านล่าง บันทึกลง session_state เพื่อสั่งรีเฟรชแผนที่ด้านบน
  current_selected_indices = []
  if event and "selection" in event and "rows" in event["selection"]:
    selected_row_positions = event["selection"]["rows"]
    current_selected_indices = table_display.index[
        selected_row_positions
    ].tolist()

  if "selected_row_indices" not in st.session_state:
    st.session_state["selected_row_indices"] = []

  if st.session_state["selected_row_indices"] != current_selected_indices:
    st.session_state["selected_row_indices"] = current_selected_indices
    st.rerun()
