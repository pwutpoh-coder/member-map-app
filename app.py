from urllib.parse import quote
import folium
import pandas as pd
import streamlit as st
from streamlit_folium import st_folium

# ตั้งค่าหน้าเว็บ Streamlit (Layout กว้างเต็มจอ)
st.set_page_config(
    page_title="ระบบแผนที่จัดส่งสินค้าประสิทธิภาพสูง",
    page_icon="🗺️",
    layout="wide",
)

# ตกแต่งหน้าตาด้วย CSS (กำหนดสีพื้นหลังตาราง โทนเทา-น้ำเงิน และสไตล์ UI)
st.markdown(
    """
    <style>
        .stApp {
            background-color: #f4f6f9;
        }
        .main-header {
            font-size: 26px;
            font-weight: bold;
            color: #1e293b;
            margin-bottom: 10px;
        }
        /* ปรับแต่งส่วน Sidebar ให้สวยงาม */
        [data-testid="stSidebar"] {
            background-color: #1e293b;
            color: #ffffff;
        }
        [data-testid="stSidebar"] label, [data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 {
            color: #ffffff !important;
        }
    </style>
""",
    unsafe_allow_html=True,
)

st.markdown(
    '<div class="main-header">🗺️ ระบบแผนที่และข้อมูลการจัดส่งสินค้า (High Performance)</div>',
    unsafe_allow_html=True,
)

# กำหนด Spreadsheet ID และชื่อชีตของคุณ
SHEET_ID = "1Ze82Uc0r179gcGvfCyE4KsrK5n8wFTAzZmLh1If1-9A"
SHEET_NAME = "ข้อมูล"


# ฟังก์ชันโหลดข้อมูลจาก Google Sheets ผ่าน CSV Export พร้อมระบบ Cache (โหลดเร็วขึ้น)
@st.cache_data(ttl=600)
def load_data():
  encoded_sheet_name = quote(SHEET_NAME)
  url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet={encoded_sheet_name}"
  # โหลดข้อมูลแบบกำหนดประเภทข้อมูลเบื้องต้นเพื่อความเร็ว
  df = pd.read_csv(url, encoding="utf-8", dtype=str)
  return df


# โหลดข้อมูล
try:
  with st.spinner("กำลังโหลดข้อมูลจาก Google Sheets..."):
    df = load_data()
except Exception as e:
  st.error(f"ไม่สามารถโหลดข้อมูลจาก Google Sheets ได้: {e}")
  st.stop()

# ตรวจสอบและทำความสะอาดข้อมูลพิกัด (คอลัมน์ C: พิกัด GPS)
if "พิกัด GPS" in df.columns:
  df = df.dropna(subset=["พิกัด GPS"])
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


# แปลงพิกัด (ใช้ vectorized apply เพื่อความเร็ว)
lat_lon_df = df["พิกัด GPS"].apply(lambda x: pd.Series(parse_lat_lon(x)))
df["lat"] = lat_lon_df[0]
df["lon"] = lat_lon_df[1]
df = df.dropna(subset=["lat", "lon"])


# --- Sidebar: ตัวกรองข้อมูล (Filters) เปลี่ยนเป็น Dropdown (Selectbox) ---
st.sidebar.header("🔍 ตัวกรองข้อมูล (Filters)")

# 1. ตัวกรองคลัง (Dropdown แบบเลือกได้ หรือเลือก "ทั้งหมด")
all_warehouses = (
    ["ทั้งหมด"] + df["คลัง"].dropna().unique().tolist()
    if "คลัง" in df.columns
    else ["ทั้งหมด"]
)
selected_warehouse = st.sidebar.selectbox(
    "เลือกคลังสินค้า", all_warehouses, index=0
)

# 2. ตัวกรองเบอร์รถ (Dropdown)
all_trucks = (
    ["ทั้งหมด"] + df["เบอร์รถ"].dropna().unique().tolist()
    if "เบอร์รถ" in df.columns
    else ["ทั้งหมด"]
)
selected_truck = st.sidebar.selectbox("เลือกเบอร์รถ", all_trucks, index=0)

# 3. ตัวกรองรอบส่ง (Dropdown)
all_rounds = (
    ["ทั้งหมด"] + df["รอบส่งประจำสัปดาห์"].dropna().unique().tolist()
    if "รอบส่งประจำสัปดาห์" in df.columns
    else ["ทั้งหมด"]
)
selected_round = st.sidebar.selectbox("เลือกรอบส่งประจำสัปดาห์", all_rounds, index=0)

# กรองข้อมูลตาม Dropdown ที่เลือก
filtered_df = df.copy()
if selected_warehouse != "ทั้งหมด":
  filtered_df = filtered_df[filtered_df["คลัง"] == selected_warehouse]
if selected_truck != "ทั้งหมด":
  filtered_df = filtered_df[filtered_df["เบอร์รถ"] == selected_truck]
if selected_round != "ทั้งหมด":
  filtered_df = filtered_df[
      filtered_df["รอบส่งประจำสัปดาห์"] == selected_round
  ]

# --- เมนูเลือกหน้า (3 หน้าตามเงื่อนไขสี) ---
st.sidebar.markdown("---")
page = st.sidebar.radio(
    "📊 เลือกมุมมองแผนที่แยกสี",
    [
        "หน้า 1: แยกสีตาม 'คลัง'",
        "หน้า 2: แยกสีตาม 'เบอร์รถ'",
        "หน้า 3: แยกสีตาม 'ยอดส่งประจำสัปดาห์'",
    ],
)

# --- ส่วนควบคุมจำนวนแถวที่แสดงผลตาราง (เพื่อความเร็ว เริ่มต้นที่ 50 แถว) ---
st.sidebar.markdown("---")
st.sidebar.subheader("⚡ การตั้งค่าการแสดงผล")
row_limit_option = st.sidebar.selectbox(
    "แสดงตารางครั้งละ (แถว):", [50, 100, 500, "ทั้งหมด"], index=0
)

# --- ส่วนตารางด้านล่างและการเลือกพิกัด (Interactive Selection) ---
st.subheader("📋 รายละเอียดข้อมูลและเลือกพิกัด")
st.info(
    "💡 คลิกเลือกแถวในตารางด้านล่างเพื่อเน้นพิกัดบนแผนที่"
    " (พิกัดอื่นจะเปลี่ยนเป็นสีเทาโดยอัตโนมัติ)"
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

  # จำกัดจำนวนแถวตามที่ผู้ใช้เลือก เพื่อให้ระบบโหลดเร็ว (เริ่มต้น 50 แถว)
  if row_limit_option != "ทั้งหมด":
    table_df_display = table_df.head(int(row_limit_option))
  else:
    table_df_display = table_df

  # แสดงตารางแบบเลือกแถวได้
  event = st.dataframe(
      table_df_display,
      use_container_width=True,
      on_select="rerun",
      selection_mode="multi-row",
      key="data_table_selection",
  )

  if event and "selection" in event and "rows" in event["selection"]:
    selected_row_positions = event["selection"]["rows"]
    # แปลง index ของหน้าที่แสดงผลกลับเป็น index จริงของ filtered_df
    selected_indices = table_df_display.index[
        selected_row_positions
    ].tolist()

# กำหนดชุดข้อมูลที่จะนำไปแสดงบนแผนที่ (ถ้ามีการจำกัดแถวตาราง แผนที่สามารถแสดงผลสอดคล้องกันหรือทั้งหมดตาม filtered_df ได้)
map_df = filtered_df.reset_index(drop=True)

# --- สร้างแผนที่ Folium ---
st.subheader("🗺️ แผนที่แสดงตำแหน่งพิกัด")

if not map_df.empty:
  center_lat = map_df["lat"].astype(float).mean()
  center_lon = map_df["lon"].astype(float).mean()
else:
  center_lat, center_lon = 13.7563, 100.5018  # ค่าเริ่มต้นกรุงเทพฯ

m = folium.Map(
    location=[center_lat, center_lon], zoom_start=11, tiles="CartoDB positron"
)


# ฟังก์ชันกำหนดสีสำหรับหมวดหมู่ต่างๆ (โทนสีสวยงามสบายตา สไตล์เทา-น้ำเงิน-พาสเทล)
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
  mapping = {}
  for i, cat in enumerate(categories):
    mapping[str(cat)] = colors[i % len(colors)]
  return mapping


# เลือกคอลัมน์ในการแบ่งสีตามหน้า
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

# เพื่อความเร็วในการเรนเดอร์หมุดจำนวนมากบนแผนที่ หากข้อมูลมากกว่า 1,000 จุด จะแสดงเฉพาะจุดที่กรองหรือจำกัดการวาด
render_df = map_df.head(1000) if len(map_df) > 1000 else map_df

if len(map_df) > 1000:
  st.warning(
      "⚠️ ข้อมูลมีมากกว่า 1,000 จุด ระบบแสดงผลหมุด 1,000 จุดแรกบนแผนที่เพื่อความเร็ว"
  )

# วาดหมุดลงบนแผนที่
for idx, row in render_df.iterrows():
  lat, lon = float(row["lat"]), float(row["lon"])

  # เงื่อนไขการเปลี่ยนเป็นสีเทา ถ้าผู้ใช้กดเลือกแถวในตาราง
  is_table_selected = (not selected_indices) or (idx in selected_indices)

  if is_table_selected:
    cat_val = str(row.get(color_col, "default"))
    pin_color = color_map.get(cat_val, "blue")
  else:
    pin_color = "gray"  # แถวที่ไม่ได้เลือกในตารางจะกลายเป็นสีเทาทั้งหมด

  # กล่องรายละเอียดเมื่อเอาเมาส์ชี้ ขนาดความกว้างประมาณ 4 ซม. (~200px)
  detail_html = f"""
    <div style="width: 200px; font-size: 12px; font-family: sans-serif; background-color: #ffffff; padding: 8px; border-radius: 6px; border: 1px solid #cbd5e1; box-shadow: 0px 2px 6px rgba(0,0,0,0.15);">
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
