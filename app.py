from urllib.parse import quote
import folium
import pandas as pd
import streamlit as st
from streamlit_folium import st_folium

# ตั้งค่าหน้าเว็บ Streamlit (Layout กว้างเต็มจอ)
st.set_page_config(
    page_title="ระบบแผนที่จัดส่งสินค้า (Super Fast)",
    page_icon="🗺️",
    layout="wide",
)

# ตกแต่ง UI ด้วย CSS
st.markdown(
    """
    <style>
        .main-header {
            font-size: 24px;
            font-weight: bold;
            color: #1e293b;
            margin-bottom: 5px;
        }
        /* กำหนดขนาดกล่อง Tooltip เมื่อเอาเมาส์ชี้ กว้างประมาณ 5 ซม. (190px) ตัดคำและขึ้นบรรทัดใหม่ */
        .leaflet-tooltip.custom-tooltip {
            background-color: #ffffff !important;
            border: 1px solid #cbd5e1 !important;
            border-radius: 6px !important;
            padding: 8px !important;
            font-size: 12px !important;
            font-family: sans-serif !important;
            color: #1e293b !important;
            width: 190px !important;
            white-space: normal !important;
            word-wrap: break-word !important;
            box-shadow: 0px 2px 6px rgba(0,0,0,0.15);
        }
    </style>
""",
    unsafe_allow_html=True,
)

st.markdown(
    '<div class="main-header">🗺️ ระบบแผนที่และข้อมูลการจัดส่งสินค้า (โหมดความเร็วสูงพิเศษไม่เกิน 15 วินาที)</div>',
    unsafe_allow_html=True,
)

# ข้อมูล Google Sheets
SHEET_ID = "1Ze82Uc0r179gcGvfCyE4KsrK5n8wFTAzZmLh1If1-9A"
SHEET_NAME = "ข้อมูล"


# 1. โหลดเฉพาะรายชื่อคลังทั้งหมดก่อนเพื่อมาสร้างตัวเลือก (รวดเร็วมาก)
@st.cache_data(ttl=600, show_spinner=False)
def load_warehouse_list():
  encoded_sheet_name = quote(SHEET_NAME)
  url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet={encoded_sheet_name}&tq=select%20E"
  df = pd.read_csv(url, encoding="utf-8", dtype=str)
  if not df.empty and "คลัง" in df.columns:
    return sorted(df["คลัง"].dropna().unique().tolist())
  return []


try:
  all_warehouses = load_warehouse_list()
except Exception as e:
  all_warehouses = []

# --- Sidebar: ตัวกรองหลักเลือกคลังสินค้า ---
st.sidebar.header("🔍 ตัวกรองหลัก (เลือกทีละสาขา)")

selected_warehouse = st.sidebar.selectbox(
    "1. เลือกคลังสินค้าที่ต้องการแสดง:",
    all_warehouses,
    index=0 if all_warehouses else 0,
    key="warehouse_select_key",
)


# 2. ฟังก์ชันโหลดข้อมูลเฉพาะคลังที่เลือก (จำกัดการดึงข้อมูลเฉพาะแถวของคลังนั้นๆ เพื่อความเร็วระดับวินาที)
@st.cache_data(ttl=600, show_spinner=False)
def load_data_by_warehouse(warehouse_name):
  if not warehouse_name:
    return pd.DataFrame()

  encoded_sheet_name = quote(SHEET_NAME)
  # ดึงเฉพาะข้อมูลที่ตรงกับคลังที่เลือกเพื่อลดขนาดข้อมูลที่ส่งผ่านเครือข่าย
  query = f"select A, B, C, D, E, F, G, J where E = '{warehouse_name}'"
  encoded_query = quote(query)

  url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet={encoded_sheet_name}&tq={encoded_query}"

  df = pd.read_csv(url, encoding="utf-8", dtype=str, low_memory=False)
  return df


if not selected_warehouse:
  st.warning(
      "⚠️ กรุณาเลือกคลังสินค้าในแถบด้านข้าง (Sidebar) เพื่อเริ่มแสดงข้อมูล"
  )
  st.stop()

# โหลดข้อมูลเฉพาะคลังที่เลือก (เสร็จภายในไม่กี่วินาที)
try:
  with st.spinner(f"กำลังดึงข้อมูลคลัง {selected_warehouse}..."):
    df = load_data_by_warehouse(selected_warehouse)
except Exception as e:
  st.error(f"❌ ไม่สามารถโหลดข้อมูลจาก Google Sheets ได้: {e}")
  st.stop()

if "พิกัด GPS" not in df.columns:
  st.error("❌ ไม่พบคอลัมน์ 'พิกัด GPS' ในไฟล์ Google Sheets")
  st.stop()

# กรองแถวที่ไม่มีพิกัดออก
df = df.dropna(subset=["พิกัด GPS"])
df = df[df["พิกัด GPS"].str.contains(",", na=False)]


# ฟังก์ชันแปลงพิกัดแบบรวดเร็ว
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

# ตัวกรองย่อยเพิ่มเติม (เบอร์รถ / รอบส่ง)
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

# กรองข้อมูลตามตัวกรองย่อย
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
# 1. ส่วนแผนที่ (อยู่ด้านบนสุด - โหลดไว ไม่รีเฟรชเมื่อซูม)
# ==========================================
total_points = len(filtered_df)
st.subheader(
    f"🗺️ แผนที่แสดงพิกัด (รวม {total_points:,} จุด ของคลัง {selected_warehouse})"
)

map_df = filtered_df.reset_index(drop=True)

# จำกัดจุดสูงสุดไม่เกิน 20,000 จุด เพื่อความปลอดภัยของเบราว์เซอร์
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
    zoom_start=11,
    tiles="OpenStreetMap",
)


# ฟังก์ชันกำหนดสี (เน้นสีสันสดใส ไร้สีเทา/ดำ)
def get_color_mapping(categories):
  colors = [
      "#2563eb",
      "#dc2626",
      "#16a34a",
      "#9333ea",
      "#ea580c",
      "#0891b2",
      "#4f46e5",
      "#ca8a04",
      "#0d9488",
      "#be185d",
      "#22c55e",
      "#eab308",
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
  pin_color = color_map.get(cat_val, "#2563eb")

  # ข้อความเมื่อเอาเมาส์ชี้ (Tooltip กว้าง 5 ซม. / 190px และขึ้นบรรทัดใหม่ได้)
  tooltip_html = f"""
    <b>รหัส:</b> {row.get('รหัสสมาชิก', '-')}<br>
    <b>ชื่อ:</b> {row.get('ชื่อ-นามสกุล', '-')}<br>
    <b>ที่อยู่:</b> {row.get('ที่อยู่จัดส่ง บ้านเลขที่/อาคาร', '-')}<br>
    <b>คลัง:</b> {row.get('คลัง', '-')}<br>
    <b>รถ:</b> {row.get('เบอร์รถ', '-')}<br>
    <b>รอบส่ง:</b> {row.get('รอบส่งประจำสัปดาห์', '-')}
    """

  folium.CircleMarker(
      location=[lat, lon],
      radius=5,
      color=pin_color,
      fill=True,
      fill_color=pin_color,
      fill_opacity=0.9,
      tooltip=folium.Tooltip(tooltip_html, className="custom-tooltip"),
  ).add_to(m)

# แสดงแผนที่ด้วย st_folium โดยกำหนด returned_objects=[] เพื่อป้องกันการรีเฟรชซ้ำเมื่อซูม
st_data = st_folium(m, width="100%", height=500, returned_objects=[])


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
  st.warning("⚠️ ไม่พบข้อมูลตามเงื่อนไขที่เลือก")
