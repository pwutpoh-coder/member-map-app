from urllib.parse import quote
import pandas as pd
import streamlit as st

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
    </style>
""",
    unsafe_allow_html=True,
)

st.markdown(
    '<div class="main-header">🗺️ ระบบแผนที่และข้อมูลการจัดส่งสินค้า (โหมดเสถียรสูงสุด 100%)</div>',
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
      # ช่วงพิกัดประเทศไทยและใกล้เคียง
      if 5.0 <= lat_val <= 25.0 and 95.0 <= lon_val <= 107.0:
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
  return data_frame.dropna(subset=["lat", "lon"]).reset_index(drop=True)


df = process_coordinates(df)

# --- เลือกหน้า (แยกสี 3 หน้า) ---
st.sidebar.markdown("---")
page = st.sidebar.radio(
    "📊 เลือกมุมมองแผนที่",
    [
        "หน้า 1: ข้อมูลคลัง",
        "หน้า 2: ข้อมูลเบอร์รถ",
        "หน้า 3: รอบส่งประจำสัปดาห์",
    ],
    key="page_selector_key",
)

# --- ตัวกรองย่อยเพิ่มเติม (เบอร์รถ / รอบส่ง) ---
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

# กรองข้อมูลตามตัวกรองย่อยสำหรับแผนที่และตาราง
filtered_df = df.copy()
if sel_truck != "ทั้งหมด":
  filtered_df = filtered_df[filtered_df["เบอร์รถ"] == sel_truck]
if sel_round != "ทั้งหมด":
  filtered_df = filtered_df[filtered_df["รอบส่งประจำสัปดาห์"] == sel_round]

# --- ตั้งค่าจำนวนแถวแสดงผลตารางด้านล่าง ---
st.sidebar.markdown("---")
row_limit = st.sidebar.selectbox(
    "⚡ แสดงตารางด้านล่างครั้งละ (แถว):",
    [50, 100, 500, "ทั้งหมด"],
    index=0,
    key="row_limit_key",
)


# ==========================================
# 1. ส่วนแผนที่ (ใช้ st.map เสถียร 100% ไม่หลุดไม่หาย)
# ==========================================
total_points = len(filtered_df)
st.subheader(
    f"🗺️ แผนที่แสดงพิกัด (คลัง: {selected_warehouse}, แสดง {total_points:,} จุด)"
)

if not filtered_df.empty:
  # st.map ต้องการคอลัมน์ชื่อ lat และ lon เท่านั้น
  map_data = filtered_df[["lat", "lon"]].copy()
  st.map(map_data, zoom=10, use_container_width=True)
else:
  st.warning("⚠️ ไม่มีข้อมูลพิกัดตามเงื่อนไขที่เลือกสำหรับแสดงบนแผนที่")


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
