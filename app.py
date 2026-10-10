import pandas as pd
import streamlit as st
from streamlit_folium import st_folium
import folium
from folium.features import DivIcon

# ตั้งค่าหน้าเว็บ Streamlit
st.set_page_config(
    page_title="ระบบแผนที่จัดส่งสินค้า", page_icon="🗺️", layout="wide"
)

st.title("🗺️ ระบบแสดงแผนที่และข้อมูลการจัดส่งสินค้า")

# กำหนดลิงก์ Google Sheets (แปลงเป็นรูปแบบ export CSV)
SHEET_ID = "1Ze82Uc0r179gcGvfCyE4KsrK5n8wFTAzZmLh1If1-9A"  # รหัสชีตจากลิงก์ของคุณ[cite: 1.2]
SHEET_NAME = "ข้อมูล"  # ชื่อแท็บชีตของคุณ[cite: 1.2]


@st.cache_data(ttl=600)
def load_data():
  url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet={SHEET_NAME}"
  df = pd.read_csv(url)
  return df


try:
  df = load_data()
except Exception as e:
  st.error(f"ไม่สามารถโหลดข้อมูลจาก Google Sheets ได้: {e}")
  st.stop()

# ทำความสะอาดข้อมูลพิกัด (คอลัมน์ C: พิกัด GPS)
# สมมติชื่อคอลัมน์ในไฟล์คือ 'พิกัด GPS' และคลัง, เบอร์รถ, รอบส่งประจำสัปดาห์, ยอดส่ง/เดือน (ก.ย.69) หรือตามหัวตารางจริง
# ตรวจสอบชื่อคอลัมน์จริงจากไฟล์: รหัสสมาชิก, ชื่อ-นามสกุล, พิกัด GPS, ที่อยู่จัดส่ง บ้านเลขที่/อาคาร, คลัง, เบอร์รถ, รอบส่งประจำสัปดาห์
if "พิกัด GPS" in df.columns:
  # ตัดช่องว่างและแยกละติจูด ลองจิจูด
  df = df.dropna(subset=["พิกัด GPS"])
  # กรองแถวที่พิกัดมีเครื่องหมายคอมมา
  df = df[df["พิกัด GPS"].str.contains(",", na=False)]


# ฟังก์ชันแปลงพิกัด
def parse_lat_lon(val):
  try:
    parts = str(val).split(",")
    return float(parts[0].strip()), float(parts[1].strip())
  except:
    return None, None


df[["lat", "lon"]] = df["พิกัด GPS"].apply(lambda x: pd.Series(parse_lat_lon(x)))
df = df.dropna(subset=["lat", "lon"])

# --- Sidebar (แถบด้านข้างสำหรับตัวกรอง) ---
st.sidebar.header("🔍 ตัวกรองข้อมูล (Filters)")

# ตัวเลือกตัวกรอง: คลัง, เบอร์รถ, รอบส่งประจำสัปดาห์
all_warehouses = (
    df["คลัง"].dropna().unique().tolist() if "คลัง" in df.columns else []
)
selected_warehouses = st.sidebar.multiselect(
    "เลือกคลัง (เลือกได้หลายคลัง)", all_warehouses, default=all_warehouses
)

all_trucks = (
    df["เบอร์รถ"].dropna().unique().tolist() if "เบอร์รถ" in df.columns else []
)
selected_trucks = st.sidebar.multiselect(
    "เลือกเบอร์รถ (เลือกได้หลายคัน)", all_trucks, default=all_trucks
)

all_rounds = (
    df["รอบส่งประจำสัปดาห์"].dropna().unique().tolist()
    if "รอบส่งประจำสัปดาห์" in df.columns
    else []
)
selected_rounds = st.sidebar.multiselect(
    "ือกรอบส่ง (เลือกได้หลายรอบ)", all_rounds, default=all_rounds
)

# กรองข้อมูลเบื้องต้นตาม Sidebar
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

# --- เมนูเลือกหน้า (3 หน้า) ---
page = st.sidebar.radio(
    "เลือกมุมมองแผนที่ (3 หน้า)",
    [
        "หน้า 1: แยกสีตาม 'คลัง'",
        "หน้า 2: แยกสีตาม 'เบอร์รถ'",
        "หน้า 3: แยกสีตาม 'ยอดส่งประจำสัปดาห์'",
    ],
)

# --- ตารางด้านล่างและการเลือกพิกัดด้วยการคลิก (Interactive Table Selection) ---
st.subheader("📋 รายละเอียดข้อมูลและเลือกพิกัด")
st.info(
    "💡 คุณสามารถคลิกเลือกแถวในตารางด้านล่างเพื่อเน้นพิกัดบนแผนที่ได้"
    " (เลือกได้หลายรายการ)"
)

# แสดงตารางให้เลือกแถวได้ (ใช้ st.dataframe พร้อม row selection)
# จัดเตรียมคอลัมน์ที่จะแสดงในตาราง
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

# ใช้ Ag-Grid หรือ Streamlit native selection
selected_indices = []
if not filtered_df.empty:
  # รีเซ็ต index เพื่อให้ตรงกัน
  table_df = filtered_df[display_columns].reset_index(drop=True)

  # ใช้ experimental_data_editor หรือ dataframe selection ในเวอร์ชันใหม่
  event = st.dataframe(
      table_df,
      use_container_width=True,
      on_select="rerun",
      selection_mode="multi-row",
      key="data_table",
  )

  # ดึง index ที่ผู้ใช้เลือกจากตาราง
  if event and "selection" in event and "rows" in event["selection"]:
    selected_row_positions = event["selection"]["rows"]
    # แปลงกลับเป็น index ของ filtered_df
    selected_indices = table_df.index[selected_row_positions].tolist()

# กรองข้อมูลที่จะแสดงบนแผนที่ตามการเลือกในตาราง (ถ้ามีการเลือกในตาราง)
map_df = filtered_df.reset_index(drop=True)

# --- สร้างแผนที่ Folium ---
st.subheader("🗺️ แผนที่แสดงตำแหน่งพิกัด")

# คำนวณจุดศูนย์กลางแผนที่
if not map_df.empty:
  center_lat = map_df["lat"].mean()
  center_lon = map_df["lon"].mean()
else:
  center_lat, center_lon = 13.7563, 100.5018  # กรุงเทพฯ

m = folium.Map(location=[center_lat, center_lon], zoom_start=11)

# กำหนดกลุ่มสีตามหน้าและเงื่อนไข
import random

# ฟังก์ชันสุ่มสีสำหรับหมวดหมู่ต่างๆ
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


# กำหนดคอลัมน์ที่จะใช้แยกสีตามหน้า
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

# วาดหมุดลงบนแผนที่
for idx, row in map_df.iterrows():
  lat, lon = row["lat"], row["lon"]

  # ตรวจสอบการเลือกจากตาราง: ถ้ามีการเลือกในตาราง แล้วแถวนี้ไม่อยู่ในที่เลือก -> ให้เป็นสีเทา
  is_table_selected = (not selected_indices) or (idx in selected_indices)

  if is_table_selected:
    cat_val = row.get(color_col, "default")
    pin_color = color_map.get(cat_val, "blue")
  else:
    pin_color = "gray"  # ไม่ได้เลือกในตาราง เปลี่ยนเป็นสีเทาทั้งหมด

  # สร้างเนื้อหา HTML สำหรับไอคอนเมื่อเอาเมาส์ชี้ (Hover / Tooltip หรือ Popup ขนาดใหญ่กว้าง 4 ซม. ~ 150-200px)
  # ตามโจทย์: เม้าส์ชี้พิกัด จะมีไอคอนขนาดกว้าง 4 ซม. แสดงรายละเอียดของแต่ละบรรทัด
  detail_html = f"""
    <div style="width: 200px; font-size: 12px; font-family: sans-serif; background-color: white; padding: 5px; border-radius: 5px; border: 1px solid #ccc;">
        <b>รหัส:</b> {row.get('รหัสสมาชิก', '-')}<br>
        <b>ชื่อ:</b> {row.get('ชื่อ-นามสกุล', '-')}<br>
        <b>ที่อยู่:</b> {row.get('ที่อยู่จัดส่ง บ้านเลขที่/อาคาร', '-')}<br>
        <b>คลัง:</b> {row.get('คลัง', '-')}<br>
        <b>เบอร์รถ:</b> {row.get('เบอร์รถ', '-')}<br>
        <b>รอบส่ง:</b> {row.get('รอบส่งประจำสัปดาห์', '-')}<br>
        <b>ยอดส่ง:</b> {row.get('ยอดส่ง/เดือน ( ก.ย.69)', '-')}
    </div>
    """

  # ใช้ Folium Marker พร้อม Tooltip (แสดงรายละเอียดเมื่อเอาเมาส์ชี้)
  folium.Marker(
      location=[lat, lon],
      popup=folium.Popup(detail_html, max_width=300),
      tooltip=folium.Tooltip(
          f"คลิกดูรายละเอียด: {row.get('ชื่อ-นามสกุล', '')}", sticky=True
      ),
      icon=folium.Icon(color=pin_color, icon="info-sign"),
  ).add_to(m)

# แสดงแผนที่ใน Streamlit
st_data = st_folium(m, width="100%", height=500)
