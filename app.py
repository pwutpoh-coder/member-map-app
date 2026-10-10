from urllib.parse import quote
import folium
import pandas as pd
import streamlit as st
from streamlit_folium import st_folium

# ตั้งค่าหน้าเว็บ Streamlit
st.set_page_config(
    page_title="ระบบแผนที่จัดส่งสินค้า", page_icon="🗺️", layout="wide"
)

st.title("🗺️ ระบบแสดงแผนที่และข้อมูลการจัดส่งสินค้า")

# กำหนด Spreadsheet ID และชื่อชีตของคุณ
SHEET_ID = "1Ze82Uc0r179gcGvfCyE4KsrK5n8wFTAzZmLh1If1-9A"
SHEET_NAME = "ข้อมูล"


# ฟังก์ชันโหลดข้อมูลจาก Google Sheets ผ่าน CSV Export พร้อมป้องกันปัญหา Encoding
@st.cache_data(ttl=600)
def load_data():
  # เข้ารหัสชื่อชีตที่เป็นภาษาไทยให้เป็นรูปแบบ URL-safe เพื่อป้องกัน error 'ascii' codec
  encoded_sheet_name = quote(SHEET_NAME)
  url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet={encoded_sheet_name}"

  # อ่านข้อมูลด้วย pandas โดยกำหนด encoding เป็น utf-8
  df = pd.read_csv(url, encoding="utf-8")
  return df


# โหลดข้อมูล
try:
  df = load_data()
except Exception as e:
  st.error(f"ไม่สามารถโหลดข้อมูลจาก Google Sheets ได้: {e}")
  st.stop()

# ตรวจสอบและทำความสะอาดข้อมูลพิกัด (คอลัมน์ C: พิกัด GPS)
if "พิกัด GPS" in df.columns:
  # ตัดแถวที่พิกัดว่างออก
  df = df.dropna(subset=["พิกัด GPS"])
  # กรองเฉพาะแถวที่มีเครื่องหมายจุลภาค (,) แยกละติจูด ลองจิจูด
  df = df[df["พิกัด GPS"].str.contains(",", na=False)]
else:
  st.error("ไม่พบคอลัมน์ 'พิกัด GPS' ใน Google Sheets ของคุณ")
  st.stop()


# ฟังก์ชันแปลงพิกัดสตริงเป็นตัวเลข float
def parse_lat_lon(val):
  try:
    parts = str(val).split(",")
    return float(parts[0].strip()), float(parts[1].strip())
  except:
    return None, None


# สร้างคอลัมน์ lat และ lon
df[["lat", "lon"]] = df["พิกัด GPS"].apply(lambda x: pd.Series(parse_lat_lon(x)))
df = df.dropna(subset=["lat", "lon"])

# --- Sidebar: ตัวกรองข้อมูล (Filters) ---
st.sidebar.header("🔍 ตัวกรองข้อมูล (Filters)")

# 1. ตัวกรองคลัง
all_warehouses = (
    df["คลัง"].dropna().unique().tolist() if "คลัง" in df.columns else []
)
selected_warehouses = st.sidebar.multiselect(
    "เลือกคลัง (เลือกได้หลายคลัง)", all_warehouses, default=all_warehouses
)

# 2. ตัวกรองเบอร์รถ
all_trucks = (
    df["เบอร์รถ"].dropna().unique().tolist() if "เบอร์รถ" in df.columns else []
)
selected_trucks = st.sidebar.multiselect(
    "เลือกเบอร์รถ (เลือกได้หลายคัน)", all_trucks, default=all_trucks
)

# 3. ตัวกรองรอบส่ง
all_rounds = (
    df["รอบส่งประจำสัปดาห์"].dropna().unique().tolist()
    if "รอบส่งประจำสัปดาห์" in df.columns
    else []
)
selected_rounds = st.sidebar.multiselect(
    "ือกรอบส่ง (เลือกได้หลายรอบ)", all_rounds, default=all_rounds
)

# กรองข้อมูลตาม Sidebar
filtered_df = df.copy()
if selected_warehouses:
  filtered_df = filtered_df[
      filtered_df["คลัง"].isin(selected_warehouses)
  ]
if selected_trucks:
  filtered_df = filtered_df[
      filtered_df["เบอร์รถ"].isin(selected_trucks)
  ]
if selected_rounds:
  filtered_df = filtered_df[
      filtered_df["รอบส่งประจำสัปดาห์"].isin(selected_rounds)
  ]

# --- เมนูเลือกหน้า (3 หน้าตามเงื่อนไขสี) ---
page = st.sidebar.radio(
    "เลือกมุมมองแผนที่ (3 หน้า)",
    [
        "หน้า 1: แยกสีตาม 'คลัง'",
        "หน้า 2: แยกสีตาม 'เบอร์รถ'",
        "หน้า 3: แยกสีตาม 'ยอดส่งประจำสัปดาห์'",
    ],
)

# --- ส่วนตารางด้านล่างและการเลือกพิกัด (Interactive Selection) ---
st.subheader("📋 รายละเอียดข้อมูลและเลือกพิกัด")
st.info(
    "💡 คลิกเลือกแถวในตารางด้านล่างเพื่อเน้นพิกัดบนแผนที่"
    " (เลือกได้หลายแถวพร้อมกัน พิกัดอื่นจะกลายเป็นสีเทา)"
)

display_columns = [
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
if not filtered_df.empty:
  table_df = filtered_df[display_columns].reset_index(drop=True)

  # แสดงตารางแบบเลือกแถวได้
  event = st.dataframe(
      table_df,
      use_container_width=True,
      on_select="rerun",
      selection_mode="multi-row",
      key="data_table_selection",
  )

  if event and "selection" in event and "rows" in event["selection"]:
    selected_row_positions = event["selection"]["rows"]
    selected_indices = table_df.index[selected_row_positions].tolist()

map_df = filtered_df.reset_index(drop=True)

# --- สร้างแผนที่ Folium ---
st.subheader("🗺️ แผนที่แสดงตำแหน่งพิกัด")

if not map_df.empty:
  center_lat = map_df["lat"].mean()
  center_lon = map_df["lon"].mean()
else:
  center_lat, center_lon = 13.7563, 100.5018  # ค่าเริ่มต้นกรุงเทพฯ

m = folium.Map(location=[center_lat, center_lon], zoom_start=11)


# ฟังก์ชันกำหนดสีสำหรับหมวดหมู่ต่างๆ
def get_color_mapping(categories):
  colors = [
      "red",
      "blue",
      "green",
      "purple",
      "orange",
      "darkred",
      "lightred",
      "beige",
      "darkblue",
      "darkgreen",
      "cadetblue",
      "darkpurple",
      "pink",
      "lightblue",
      "lightgreen",
      "gray",
      "black",
  ]
  mapping = {}
  for i, cat in enumerate(categories):
    mapping[cat] = colors[i % len(colors)]
  return mapping


# เลือกคอลัมน์ในการแบ่งสีตามหน้าที่ผู้ใช้เลือก
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

# วาดหมุดลงบนแผนทีทีละจุด
for idx, row in map_df.iterrows():
  lat, lon = row["lat"], row["lon"]

  # เงื่อนไขการเปลี่ยนเป็นสีเทา ถ้าผู้ใช้กดเลือกในตาราง
  is_table_selected = (not selected_indices) or (idx in selected_indices)

  if is_table_selected:
    cat_val = row.get(color_col, "default")
    pin_color = color_map.get(cat_val, "blue")
  else:
    pin_color = "gray"  # แถวที่ไม่ได้เลือกในตารางจะกลายเป็นสีเทา

  # หน้าต่างข้อมูลเมื่อเอาเมาส์ชี้ / คลิก (ขนาดความกว้างประมาณ 4 ซม. หรือ ~200px)
  detail_html = f"""
    <div style="width: 200px; font-size: 12px; font-family: sans-serif; background-color: white; padding: 8px; border-radius: 6px; border: 1px solid #ddd; box-shadow: 0px 2px 4px rgba(0,0,0,0.1);">
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
      popup=folium.Popup(detail_html, max_width=300),
      tooltip=folium.Tooltip(f"คลิกดูรายละเอียด: {row.get('ชื่อ-นามสกุล', '')}", sticky=True),
      icon=folium.Icon(color=pin_color, icon="info-sign"),
  ).add_to(m)

# แสดงผลแผนที่บนหน้าเว็บ Streamlit
st_data = st_folium(m, width="100%", height=550)
