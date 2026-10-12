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
    '<div class="main-header">🗺️ ระบบแผนที่และข้อมูลการจัดส่งสินค้า (แสดงพิกัดสมบูรณ์)</div>',
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


# 2. ฟังก์ชันโหลดข้อมูลเฉพาะคลังที่เลือก
@st.cache_data(ttl=600, show_spinner=False)
def load_data_by_warehouse(warehouse_name):
  if not warehouse_name:
    return pd.DataFrame()

  encoded_sheet_name = quote(SHEET_NAME)
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

try:
  with st.spinner(f"กำลังดึงข้อมูลคลัง {selected_warehouse}..."):
    df = load_data_by_warehouse(selected_warehouse)
except Exception as e:
  st.error(f"❌ ไม่สามารถโหลดข้อมูลจาก Google Sheets ได้: {e}")
  st.stop()

if "พิกัด GPS" not in df.columns:
  st.error("❌ ไม่พบคอลัมน์ 'พิกัด GPS' ในไฟล์ Google Sheets")
  st.stop()

# กรองแถวที่ไม่มีพิกัดออกอย่างปลอดภัย
df = df.dropna(subset=["พิกัด GPS"])
df = df[df["พิกัด GPS"].str.contains(",", na=False)]


# ฟังก์ชันแปลงพิกัดและกรองค่าที่ผิดพลาดออกทันที
@st.cache_data(show_spinner=False)
def process_coordinates(data_frame):
  lats = []
  lons = []
  for val in data_frame["พิกัด GPS"]:
    try:
      parts = str(val).split(",")
      lat_val = float(parts[0].strip())
      lon_val = float(parts[1].strip())
      # ตรวจสอบช่วงพิกัดประเทศไทยเบื้องต้นเพื่อป้องกันค่าเพี้ยน
      if 5.0 <= lat_val <= 21.0 and 97.0 <= lon_val <= 106.0:
        lats.append(lat_val)
        lons.append(lon_val)
      else:
        lats.append(None)
        lons.append(None)
    except:
      lats.append(None)
      lons.append(None)

  data_frame["lat"] = lats
  data_frame["lon"] = lons
  # ตัดแถวที่แปลงพิกัดไม่สำเร็จออกเด็ดขาด
  return data_frame.dropna(subset=["lat", "lon"]).reset_index(drop=True)


df = process_coordinates(df)

# --- เลือกหน้า (แยกสี 3 หน้า) ---
st.sidebar.markdown("---")
page = st.sidebar.radio(
    "📊 เลือกมุมมองแผนที่แยกสี",
    [
        "หน้า 1: แยกสีตาม 'คลัง'",
        "หน้า 2: แยกสีตาม 'เบอร์รถ'",
        "หน้า 3: แยกสีตาม 'รอบส่งประจำสัปดาห์' (กำหนดสีตามวัน)",
    ],
    key="page_selector_key",
)

# --- ตัวเลือกสไตล์แผนที่ ---
st.sidebar.markdown("---")
map_theme = st.sidebar.radio(
    "🗺️ เลือกสไตล์แผนที่:",
    [
        "แผนที่สีจาง (CartoDB Positron - แนะนำไม่ให้สีแผนที่ทับกับสีพิกัด)",
        "แผนที่ปกติ (OpenStreetMap)",
    ],
    index=0,
    key="map_theme_key",
)

# --- ตัวกรองย่อยเพิ่มเติม (เบอร์รถ / รอบส่ง) ---
st.sidebar.markdown("---")
st.sidebar.header("⚙️ ตัวกรองเพิ่มเติมและเงื่อนไขการแสดงผล")

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

# ทางเลือกการแสดงผลเมื่อใช้ตัวกรองย่อย
st.sidebar.markdown("---")
filter_display_mode = st.sidebar.radio(
    "รูปแบบการแสดงผลจุดที่ไม่ได้เลือกในตัวกรอง:",
    [
        "ซ่อนจุดที่ไม่เลือก (หายไปไม่ปรากฎ)",
        "แสดงจุดที่ไม่เลือกเป็น 'สีเทาทึบ' (ไม่มีรูกลวง)",
    ],
    index=0,
    key="filter_mode_key",
)

# แยกตารางสำหรับข้อมูลที่จะนำไปแสดงในตารางด้านล่าง
table_filtered_df = df.copy()
if sel_truck != "ทั้งหมด":
  table_filtered_df = table_filtered_df[
      table_filtered_df["เบอร์รถ"] == sel_truck
  ]
if sel_round != "ทั้งหมด":
  table_filtered_df = table_filtered_df[
      table_filtered_df["รอบส่งประจำสัปดาห์"] == sel_round
  ]

# --- ตั้งค่าจำนวนแถวแสดงผลตารางด้านล่าง ---
st.sidebar.markdown("---")
row_limit = st.sidebar.selectbox(
    "⚡ แสดงตารางด้านล่างครั้งละ (แถว):",
    [50, 100, 500, "ทั้งหมด"],
    index=0,
    key="row_limit_key",
)


# ==========================================
# 1. ส่วนแผนที่ (อยู่ด้านบนสุด)
# ==========================================
st.subheader(
    f"🗺️ แผนที่แสดงพิกัด (คลัง: {selected_warehouse}, ทั้งหมด {len(df):,} จุด)"
)

if not df.empty:
  center_lat = float(df["lat"].mean())
  center_lon = float(df["lon"].mean())
else:
  center_lat, center_lon = 13.7563, 100.5018

# กำหนด Tile Provider ตามตัวเลือก
tile_name = "cartodbpositron" if "สีจาง" in map_theme else "openstreetmap"

m = folium.Map(
    location=[center_lat, center_lon], zoom_start=11, tiles=tile_name
)


# ฟังก์ชันกำหนดสีตามหน้า
def get_color_mapping(categories, page_type):
  if page_type == "หน้า 3":
    day_colors = {
        "จันทร์": "#ca8a04",  # สีเหลือง
        "อังคาร": "#be185d",  # สีชมพู
        "พุธ": "#16a34a",  # สีเขียว
        "พฤหัสบดี": "#ea580c",  # สีส้ม
        "พฤหัส": "#ea580c",
        "ศุกร์": "#0284c7",  # สีฟ้า
        "เสาร์": "#9333ea",  # สีม่วง
        "อาทิตย์": "#dc2626",  # สีแดง
    }
    mapping = {}
    fallback_colors = ["#2563eb", "#0d9488", "#4f46e5", "#eab308"]
    for i, cat in enumerate(categories):
      cat_str = str(cat).strip()
      matched = False
      for day_key in day_colors:
        if day_key in cat_str:
          mapping[cat_str] = day_colors[day_key]
          matched = True
          break
      if not matched:
        mapping[cat_str] = fallback_colors[i % len(fallback_colors)]
    return mapping
  else:
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
  p_type = "หน้า 1"
elif "หน้า 2" in page:
  color_col = "เบอร์รถ"
  p_type = "หน้า 2"
else:
  color_col = (
      "รอบส่งประจำสัปดาห์" if "รอบส่งประจำสัปดาห์" in df.columns else "คลัง"
  )
  p_type = "หน้า 3"

unique_cats = (
    df[color_col].dropna().unique().tolist()
    if color_col in df.columns
    else []
)
color_map = get_color_mapping(unique_cats, p_type)

# วาดหมุดลงบนแผนที่ทีละจุดอย่างปลอดภัย
for idx, row in df.iterrows():
  lat, lon = float(row["lat"]), float(row["lon"])

  matches_truck = (
      (sel_truck == "All" or sel_truck == "ทั้งหมด")
      or (str(row.get("เบอร์รถ", "")) == sel_truck)
  )
  matches_round = (
      (sel_round == "All" or sel_round == "ทั้งหมด")
      or (str(row.get("รอบส่งประจำสัปดาห์", "")) == sel_round)
  )

  is_fully_matched = matches_truck and matches_round

  if not is_fully_matched:
    if filter_display_mode == "ซ่อนจุดที่ไม่เลือก (หายไปไม่ปรากฎ)":
      continue
    else:
      pin_color = "#64748b"  # สีเทาทึบ
      opacity = 0.6
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
          radius=3,
          color=pin_color,
          fill=True,
          fill_color=pin_color,
          fill_opacity=opacity,
          tooltip=folium.Tooltip(tooltip_html, className="custom-tooltip"),
      ).add_to(m)
      continue
  else:
    cat_val = str(row.get(color_col, "default"))
    pin_color = color_map.get(cat_val, "#2563eb")
    opacity = 0.9

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
      radius=3,
      color=pin_color,
      fill=True,
      fill_color=pin_color,
      fill_opacity=opacity,
      tooltip=folium.Tooltip(tooltip_html, className="custom-tooltip"),
  ).add_to(m)

# แสดงแผนที่ (returned_objects=[] ป้องกันการรีเฟรชซ้ำเมื่อซูม)
st_data = st_folium(m, width="100%", height=500, returned_objects=[])


# ==========================================
# 2. ส่วนตารางข้อมูล (อยู่ด้านล่าง)
# ==========================================
st.markdown("---")
st.subheader("📋 รายละเอียดข้อมูล (แสดงด้านล่าง)")
st.info(
    "💡 แสดงข้อมูลตามตัวกรองที่เลือก สามารถเลือกดูแบบ 50, 100, 500"
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
    if c in table_filtered_df.columns
]

if not table_filtered_df.empty:
  table_df = table_filtered_df[display_cols].reset_index(drop=True)
  table_display = (
      table_df.head(int(row_limit)) if row_limit != "ทั้งหมด" else table_df
  )

  st.dataframe(table_display, use_container_width=True)
else:
  st.warning("⚠️ ไม่พบข้อมูลตามเงื่อนไขที่เลือก")
