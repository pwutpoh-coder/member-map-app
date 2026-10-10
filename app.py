from urllib.parse import quote
import folium
import pandas as pd
import streamlit as st
from streamlit_folium import st_folium

# ตั้งค่าหน้าเว็บ Streamlit
st.set_page_config(
    page_title="ระบบแผนที่จัดส่งสินค้า", page_icon="🗺️", layout="wide"
)

# ตกแต่ง UI เล็กน้อย
st.markdown(
    """
    <style>
        .main-header {
            font-size: 24px;
            font-weight: bold;
            color: #1e293b;
            margin-bottom: 10px;
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


# ฟังก์ชันโหลดข้อมูลพร้อมแคช
@st.cache_data(ttl=600)
def load_data():
  encoded_sheet_name = quote(SHEET_NAME)
  url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet={encoded_sheet_name}"
  df = pd.read_csv(url, encoding="utf-8", dtype=str)
  return df


# โหลดข้อมูลแบบปลอดภัย ป้องกันแอปพัง
try:
  with st.spinner("กำลังเชื่อมต่อและโหลดข้อมูลจาก Google Sheets..."):
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

# ทำความสะอาดข้อมูลพิกัด
df = df.dropna(subset=["พิกัด GPS"])
df = df[df["พิกัด GPS"].str.contains(",", na=False)]


def parse_lat_lon(val):
  try:
    parts = str(val).split(",")
    return float(parts[0].strip()), float(parts[1].strip())
  except:
    return None, None


lat_lon_df = df["พิกัด GPS"].apply(lambda x: pd.Series(parse_lat_lon(x)))
df["lat"] = lat_lon_df[0]
df["lon"] = lat_lon_df[1]
df = df.dropna(subset=["lat", "lon"])

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

# --- ตั้งค่าจำนวนแถวแสดงผลตาราง (เพื่อให้ระบบโหลดเร็ว แต่แผนที่จะแสดงทั้งหมด) ---
st.sidebar.markdown("---")
row_limit = st.sidebar.selectbox(
    "⚡ แสดงตารางครั้งละ (แถว):", [50, 100, 500, "ทั้งหมด"], index=0
)

# --- ส่วนตารางข้อมูลและการเลือกพิกัด ---
st.subheader("📋 รายละเอียดข้อมูลและเลือกพิกัด")
st.info(
    "💡 คลิกเลือกแถวในตารางด้านล่างเพื่อเน้นพิกัดบนแผนที่"
    " (พิกัดอื่นจะเปลี่ยนเป็นสีเทา) *หมายเหตุ: บนแผนที่แสดงพิกัดทั้งหมดตามตัวกรอง*"
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

selected_indices = []
table_display = pd.DataFrame()

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
      key="main_table",
  )

  if event and "selection" in event and "rows" in event["selection"]:
    selected_row_positions = event["selection"]["rows"]
    # แปลง index ของตารางที่แสดง ให้ตรงกับ index ใน filtered_df จริงๆ
    selected_indices = table_display.index[selected_row_positions].tolist()

# --- สร้างแผนที่ (แสดงพิกัดทั้งหมดจาก filtered_df โดยไม่จำกัดด้วยแถวของตาราง) ---
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

# วาดหมุดทั้งหมดใน map_df ลงบนแผนที่ (แสดงทุกพิกัดตามตัวกรอง)
for idx, row in map_df.iterrows():
  lat, lon = float(row["lat"]), float(row["lon"])

  # ตรวจสอบว่าแถวนี้ถูกเลือกในตารางหรือไม่
  # เนื่องจาก table_display อาจแสดงแค่ 50 แถว แต่ map_df มีทั้งหมด
  # เราจะตรวจสอบว่าถ้ารายการนั้นอยู่ใน selected_indices (อิงจาก table_display) หรือถ้าไม่มีการเลือกเลย ให้แสดงสีปกติ
  is_selected = True
  if selected_indices:
    # ค้นหาว่า idx นี้ตรงกับแถวที่ถูกเลือกในตารางหรือไม่
    if idx in selected_indices:
      is_selected = True
    else:
      is_selected = False

  if is_selected:
    cat_val = str(row.get(color_col, "default"))
    pin_color = color_map.get(cat_val, "blue")
  else:
    pin_color = "gray"  # เปลี่ยนเป็นสีเทาเมื่อไม่ได้เลือกในตาราง

  # เนื้อหาที่จะแสดงเมื่อเอาเมาส์ชี้ (Tooltip / Hover) โดยไม่ต้องกดคลิก
  tooltip_html = f"""
    <b>รหัส:</b> {row.get('รหัสสมาชิก', '-')}<br>
    <b>ชื่อ:</b> {row.get('ชื่อ-นามสกุล', '-')}<br>
    <b>คลัง:</b> {row.get('คลัง', '-')}<br>
    <b>เบอร์รถ:</b> {row.get('เบอร์รถ', '-')}<br>
    <b>รอบส่ง:</b> {row.get('รอบส่งประจำสัปดาห์', '-')}
    """

  # กล่องรายละเอียดเพิ่มเติมเมื่อคลิกหมุด (Popup)
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

# เรนเดอร์แผนที่ลงบน Streamlit
st_data = st_folium(m, width="100%", height=550)
