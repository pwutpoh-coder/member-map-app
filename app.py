from urllib.parse import quote
import folium
import pandas as pd
import streamlit as st
from streamlit_folium import st_folium

# ตั้งค่าหน้าเว็บ Streamlit (Layout กว้างเต็มจอ)
st.set_page_config(
    page_title="ระบบแผนที่จัดส่งสินค้า (Ultra Fast)",
    page_icon="🗺️",
    layout="wide",
)

# ตกแต่ง UI ด้วย CSS กำหนดโทนสีปุ่มและธีมเป็น "เทาน้ำเงิน" (Slate / Navy)
st.markdown(
    """
    <style>
        .main-header {
            font-size: 24px;
            font-weight: bold;
            color: #1e293b;
            margin-bottom: 5px;
        }
        .stMultiSelect [data-baseweb="tag"] {
            background-color: #334155 !important;
            color: white !important;
        }
    </style>
""",
    unsafe_allow_html=True,
)

st.markdown(
    '<div class="main-header">🗺️ ระบบแผนที่และข้อมูลการจัดส่งสินค้า (โหมดความเร็วสูงสุด ไม่ค้าง)</div>',
    unsafe_allow_html=True,
)

# ข้อมูล Google Sheets
SHEET_ID = "1Ze82Uc0r179gcGvfCyE4KsrK5n8wFTAzZmLh1If1-9A"
SHEET_NAME = "ข้อมูล"


# 1. โหลดเฉพาะรายชื่อคลังทั้งหมดก่อน (โหลดเร็วมากเพราะอ่านแค่คอลัมน์คลัง)
@st.cache_data(ttl=600, show_spinner=False)
def load_warehouse_list():
  encoded_sheet_name = quote(SHEET_NAME)
  # ดึงเฉพาะคอลัมน์คลัง (คอลัมน์ E) เพื่อมาสร้างเมนูตัวเลือก
  url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet={encoded_sheet_name}&tq=select%20E"
  df = pd.read_csv(url, encoding="utf-8", dtype=str)
  # คืนค่ารายการคลังที่ไม่ซ้ำกัน
  if not df.empty and "คลัง" in df.columns:
    return sorted(df["คลัง"].dropna().unique().tolist())
  return []


try:
  all_warehouses = load_warehouse_list()
except Exception as e:
  all_warehouses = []

# --- Sidebar: ตัวกรองหลักเลือกคลังสินค้า ---
st.sidebar.header("🔍 ตัวกรองหลัก (เพื่อความเร็วสูงสุด)")

if all_warehouses:
  default_wh = [all_warehouses[0]]
else:
  default_wh = []

selected_warehouses = st.sidebar.multiselect(
    "1. เลือกคลังสินค้า (เลือกได้หลายคลัง):",
    all_warehouses,
    default=default_wh,
    key="warehouse_filter_key",
)


# 2. ฟังก์ชันโหลดข้อมูลเฉพาะคลังที่ถูกเลือก (Query เฉพาะข้อมูลที่จำเป็น ไม่โหลดทั้งหมด 1.4 แสนแถว)
@st.cache_data(ttl=600, show_spinner=False)
def load_data_by_warehouses(warehouses_tuple):
  if not warehouses_tuple:
    return pd.DataFrame()

  encoded_sheet_name = quote(SHEET_NAME)
  # สร้างเงื่อนไข SQL สำหรับ Google Visualization API เพื่อดึงเฉพาะคลังที่ผู้ใช้เลือก
  wh_conditions = " or ".join([f"E = '{wh}'" for wh in warehouses_tuple])
  query = f"select * where {wh_conditions}"
  encoded_query = quote(query)

  url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet={encoded_sheet_name}&tq={encoded_query}"

  df = pd.read_csv(url, encoding="utf-8", dtype=str, low_memory=False)
  return df


if not selected_warehouses:
  st.warning(
      "⚠️ กรุณาเลือกคลังสินค้าอย่างน้อย 1 คลังในแถบด้านข้าง (Sidebar)"
      " เพื่อเริ่มแสดงข้อมูล"
  )
  st.stop()

# โหลดข้อมูลเฉพาะคลังที่เลือก (ทำให้โหลดเสร็จภายใน 1-2 วินาที ไม่ค้าง)
try:
  with st.spinner("กำลังดึงข้อมูลเฉพาะคลังที่เลือกอย่างรวดเร็ว..."):
    df = load_data_by_warehouses(tuple(selected_warehouses))
except Exception as e:
  st.error(f"❌ ไม่สามารถโหลดข้อมูลจาก Google Sheets ได้: {e}")
  st.stop()

if "พิกัด GPS" not in df.columns:
  st.error("❌ ไม่พบคอลัมน์ 'พิกัด GPS' ในไฟล์ Google Sheets")
  st.stop()

# กรองแถวที่ไม่มีพิกัดออก
df = df.dropna(subset=["พิกัด GPS"])
df = df[df["พิกัด GPS"].str.contains(",", na=False)]


# ฟังก์ชันแปลงพิกัดแบบรวดเร็ว (Vectorized Parsing)
@st.cache_data(show_spinner=False)
def process_coordinates(data_frame):
  split_coords = data_frame["พิกัด GPS"].str.split(",", expand=True)
  if split_coords.shape[1] >= 2:
    data_frame["lat"] = pd.to_numeric(split_coords[0], errors="coerce")
    data_frame["lon"] = pd.to_numeric(split_coords[1], errors="coerce")
  else:
    data_frame["lat"] = None
    data_frame["lon"] = None
  return data_frame.dropna(subset=["lat", "lon"])


df = process_coordinates(df)

# ตัวกรองย่อยเพิ่มเติม (เบอร์รถ / รอบส่ง) จากข้อมูลคลังที่ดึงมาแล้ว
st.sidebar.markdown("---")
st.sidebar.header("⚙️ ตัวกรองเพิ่มเติม")

trucks = (
    ["ทั้งหมด"] + df["เบอร์รถ"].dropna().unique().tolist()
    if "เบอร์รถ" in df.columns
    else ["ทั้งหมด"]
)
sel_truck = st.sidebar.selectbox(
    "เลือกเบอร์รถ", trucks, index=0, key="truck_filter_key"
)

rounds = (
    ["ทั้งหมด"] + df["รอบส่งประจำสัปดาห์"].dropna().unique().tolist()
    if "รอบส่งประจำสัปดาห์" in df.columns
    else ["ทั้งหมด"]
)
sel_round = st.sidebar.selectbox(
    "เลือกรอบส่งประจำสัปดาห์", rounds, index=0, key="round_filter_key"
)

# กรองข้อมูลซ้ำตามตัวกรองย่อย
filtered_df = df.copy()
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
    key="page_selector_key",
)

# --- ตั้งค่าจำนวนแถวแสดงผลตารางด้านล่าง ---
st.sidebar.markdown("---")
row_limit = st.sidebar.selectbox(
    "⚡ แสดงตารางด้านล่างครั้งละ (แถว):",
    [50, 100, 500, "ทั้งหมด"],
    index=0,
    key="row_limit_key",
)


# ==========================================
# 1. ส่วนแผนที่ (อยู่ด้านบนสุด - โหลดไว ไม่มีสะดุด)
# ==========================================
total_points = len(filtered_df)
st.subheader(
    f"🗺️ แผนที่แสดงพิกัด (รวม {total_points:,} จุด จากคลังที่เลือก)"
)

map_df = filtered_df.reset_index(drop=True)

# จำกัดจุดสูงสุดไม่เกิน 20,000 จุดเพื่อความปลอดภัยของเบราว์เซอร์
MAX_POINTS = 20000
if total_points > MAX_POINTS:
  st.warning(
      f"⚠️ ข้อมูลมีจำนวน {total_points:,} จุด ซึ่งเกินขีดจำกัด {MAX_POINTS:,}"
      f" จุด ระบบจะแสดงหมุดบนแผนที่จำนวน {MAX_POINTS:,} จุดแรกเพื่อความลื่นไหล"
  )
  map_df = map_df.head(MAX_POINTS)

if not map_df.empty:
  center_lat = map_df["lat"].mean()
  center_lon = map_df["lon"].mean()
else:
  center_lat, center_lon = 13.7563, 100.5018

# สร้างแผนที่ด้วย OpenStreetMap (ฟรี 100% ไม่ใช้ API Key)
m = folium.Map(
    location=[center_lat, center_lon],
    zoom_start=10,
    tiles="OpenStreetMap",
)


# ฟังก์ชันกำหนดสีตามหมวดหมู่ (โทนสีเทาน้ำเงิน)
def get_color_mapping(categories):
  colors = [
      "#334155",
      "#1e40af",
      "#0369a1",
      "#0f766e",
      "#374151",
      "#475569",
      "#1d4ed8",
      "#0284c7",
      "#0d9488",
      "#4b5563",
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

# วาดหมุดวงกลมพิกัด (CircleMarker)
for idx, row in map_df.iterrows():
  lat, lon = float(row["lat"]), float(row["lon"])
  cat_val = str(row.get(color_col, "default"))
  pin_color = color_map.get(cat_val, "#334155")

  # ข้อความเมื่อเอาเมาส์ชี้ (Tooltip)
  tooltip_text = (
      f"รหัส: {row.get('รหัสสมาชิก', '-')}, ชื่อ: {row.get('ชื่อ-นามสกุล', '-')},"
      f" คลัง: {row.get('คลัง', '-')}, รถ: {row.get('เบอร์รถ', '-')}"
  )

  # ข้อมูลแบบละเอียดเมื่อคลิก (Popup)
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

  folium.CircleMarker(
      location=[lat, lon],
      radius=4,
      color=pin_color,
      fill=True,
      fill_color=pin_color,
      fill_opacity=0.8,
      popup=folium.Popup(popup_html, max_width=300),
      tooltip=tooltip_text,
  ).add_to(m)

# แสดงแผนที่ด้านบน
st_data = st_folium(m, width="100%", height=500)


# ==========================================
# 2. ส่วนตารางข้อมูล (อยู่ด้านล่าง)
# ==========================================
st.markdown("---")
st.subheader("📋 รายละเอียดข้อมูล (แสดงด้านล่าง)")
st.info(
    "💡 แสดงข้อมูลตามคลังและตัวกรองที่เลือก สามารถเลือกดูแบบ 50, 100, 500"
    " หรือทั้งหมดได้"
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

  st.dataframe(table_display, use_container_width=True)
else:
  st.warning("⚠️ กรุณาเลือกคลังสินค้าในแถบด้านข้าง (Sidebar) เพื่อแสดงข้อมูล")
