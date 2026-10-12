from urllib.parse import quote
import folium
import pandas as pd
import streamlit as st
from streamlit_folium import st_folium

# ตั้งค่าหน้าเว็บ Streamlit (Layout กว้างเต็มจอ)
st.set_page_config(
    page_title="ระบบแผนที่และตารางสรุปข้อมูลการจัดส่งสินค้า",
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
    '<div class="main-header">🗺️ ระบบแผนที่ ตารางสรุป และตัวกรองข้อมูลสมาชิก (เลือกได้หลายตัวกรอง)</div>',
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

# แปลงคอลัมน์ยอดส่งให้เป็นตัวเลขเพื่อใช้คำนวณสรุป
if "ยอดส่ง/เดือน ( ก.ย.69)" in df.columns:
  df["ยอดส่ง_numeric"] = (
      df["ยอดส่ง/เดือน ( ก.ย.69)"]
      .astype(str)
      .str.replace(",", "")
      .str.extract(r"([\d\.]+)")[0]
      .astype(float)
      .fillna(0)
  )
else:
  df["ยอดส่ง_numeric"] = 0.0

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

# --- ตัวกรองย่อยเพิ่มเติม (เปลี่ยนเป็น multiselect เลือกได้มากกว่า 1 ตัว) ---
st.sidebar.markdown("---")
st.sidebar.header("⚙️ ตัวกรองเพิ่มเติม (เลือกได้หลายรายการ)")

truck_options = (
    df["เบอร์รถ"].dropna().unique().tolist()
    if "เบอร์รถ" in df.columns
    else []
)
sel_trucks = st.sidebar.multiselect(
    "เลือกเบอร์รถ (เลือกได้หลายคัน / ไม่เลือก = ทั้งหมด)",
    truck_options,
    default=[],
    key="truck_multiselect_key",
)

round_options = (
    df["รอบส่งประจำสัปดาห์"].dropna().unique().tolist()
    if "รอบส่งประจำสัปดาห์" in df.columns
    else []
)
sel_rounds = st.sidebar.multiselect(
    "เลือกรอบส่งประจำสัปดาห์ (เลือกได้หลายรอบ / ไม่เลือก = ทั้งหมด)",
    round_options,
    default=[],
    key="round_multiselect_key",
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

# --- ตั้งค่าจำนวนแถวแสดงผลตารางด้านล่าง ---
st.sidebar.markdown("---")
row_limit = st.sidebar.selectbox(
    "⚡ แสดงตารางด้านล่างครั้งละ (แถว):",
    [50, 100, 500, "ทั้งหมด"],
    index=0,
    key="row_limit_key",
)


# ==========================================
# สร้างชุดข้อมูลที่ผ่านการกรองจาก Sidebar (ใช้ร่วมกันทั้งแผนที่, ตารางสรุป และตารางรายละเอียด)
# ==========================================
filtered_df = df.copy()
if sel_trucks:
  filtered_df = filtered_df[filtered_df["เบอร์รถ"].isin(sel_trucks)]
if sel_rounds:
  filtered_df = filtered_df[filtered_df["รอบส่งประจำสัปดาห์"].isin(sel_rounds)]


# ==========================================
# 1. ส่วนแผนที่ (อยู่ด้านบนสุด - รองรับการคลิกหมุด)
# ==========================================
st.subheader(
    f"🗺️ แผนที่แสดงพิกัด (คลัง: {selected_warehouse}, แสดง {len(filtered_df):,} จากทั้งหมด {len(df):,} จุด)"
)
st.info(
    "💡 คำแนะนำ: คุณสามารถใช้เมาส์ **คลิกที่จุดหมุดบนแผนที่**"
    " เพื่อกรองดูข้อมูลเฉพาะสมาชิกคนนั้นในตารางรายละเอียดด้านล่างได้ทันที"
)

if not df.empty:
  center_lat = float(df["lat"].mean())
  center_lon = float(df["lon"].mean())
else:
  center_lat, center_lon = 13.7563, 100.5018

m = folium.Map(
    location=[center_lat, center_lon], zoom_start=11, tiles="OpenStreetMap"
)


# ฟังก์ชันกำหนดสีตามหน้า
def get_color_mapping(categories, page_type):
  if "หน้า 3" in page_type:
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
elif "หน้า 2" in page:
  color_col = "เบอร์รถ"
else:
  color_col = (
      "รอบส่งประจำสัปดาห์" if "รอบส่งประจำสัปดาห์" in df.columns else "คลัง"
  )

unique_cats = (
    df[color_col].dropna().unique().tolist()
    if color_col in df.columns
    else []
)
color_map = get_color_mapping(unique_cats, page)

# วาดหมุดลงบนแผนที่โดยอ้างอิงจาก Multiselect ใน Sidebar
for idx, row in df.iterrows():
  lat, lon = float(row["lat"]), float(row["lon"])

  matches_truck = (not sel_trucks) or (str(row.get("เบอร์รถ", "")) in sel_trucks)
  matches_round = (not sel_rounds) or (
      str(row.get("รอบส่งประจำสัปดาห์", "")) in sel_rounds
  )

  is_fully_matched = matches_truck and matches_round

  if not is_fully_matched:
    if filter_display_mode == "ซ่อนจุดที่ไม่เลือก (หายไปไม่ปรากฎ)":
      continue
    else:
      pin_color = "#64748b"  # สีเทาทึบ
      opacity = 0.5
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
      weight=1,
      fill=True,
      fill_color=pin_color,
      fill_opacity=opacity,
      tooltip=folium.Tooltip(tooltip_html, className="custom-tooltip"),
      popup=str(row.get("รหัสสมาชิก", "")),
  ).add_to(m)

map_output = st_folium(
    m, width="100%", height=500, returned_objects=["last_clicked", "last_object_clicked"]
)


# ==========================================
# 2. ส่วนตารางสรุปข้อมูล (Summary Table - แปรผันตามตัวกรอง Sidebar)
# ==========================================
st.markdown("---")
if "หน้า 1" in page:
  st.subheader("📊 ตารางสรุปภาพรวมตาม 'คลัง' (ตามตัวกรอง)")
  if not filtered_df.empty and "คลัง" in filtered_df.columns:
    summary_df = (
        filtered_df.groupby("คลัง")
        .agg(
            จำนวนเบอร์รถ=("เบอร์รถ", "nunique"),
            จำนวนสมาชิก=("รหัสสมาชิก", "count"),
            ยอดส่งรวม=("ยอดส่ง_numeric", "sum"),
        )
        .reset_index()
    )
    summary_df["ยอดส่งรวม"] = summary_df["ยอดส่งรวม"].apply(lambda x: f"{x:,.2f}")
    st.dataframe(summary_df, use_container_width=True)
  else:
    st.warning("⚠️ ไม่มีข้อมูลสรุปตามเงื่อนไขที่เลือก")

elif "หน้า 2" in page:
  st.subheader("📊 ตารางสรุปข้อมูลแยกตาม 'คลัง และ เบอร์รถ' (ตามตัวกรอง)")
  if not filtered_df.empty and "เบอร์รถ" in filtered_df.columns:
    group_cols = (
        ["คลัง", "เบอร์รถ"]
        if "คลัง" in filtered_df.columns
        else ["เบอร์รถ"]
    )
    summary_df = (
        filtered_df.groupby(group_cols)
        .agg(
            จำนวนสมาชิก=("รหัสสมาชิก", "count"),
            ยอดส่งรวม=("ยอดส่ง_numeric", "sum"),
        )
        .reset_index()
    )
    summary_df["ยอดส่งรวม"] = summary_df["ยอดส่งรวม"].apply(lambda x: f"{x:,.2f}")
    st.dataframe(summary_df, use_container_width=True)
  else:
    st.warning("⚠️ ไม่มีข้อมูลสรุปตามเงื่อนไขที่เลือก")

else:
  st.subheader("📊 ตารางสรุปข้อมูลแยกตาม 'รอบส่งประจำสัปดาห์ และ เบอร์รถ' (ตามตัวกรอง)")
  if not filtered_df.empty and "รอบส่งประจำสัปดาห์" in filtered_df.columns:
    group_cols = (
        ["รอบส่งประจำสัปดาห์", "เบอร์รถ"]
        if "เบอร์รถ" in filtered_df.columns
        else ["รอบส่งประจำสัปดาห์"]
    )
    summary_df = (
        filtered_df.groupby(group_cols)
        .agg(
            จำนวนสมาชิก=("รหัสสมาชิก", "count"),
            ยอดส่งรวม=("ยอดส่ง_numeric", "sum"),
        )
        .reset_index()
    )
    summary_df["ยอดส่งรวม"] = summary_df["ยอดส่งรวม"].apply(lambda x: f"{x:,.2f}")
    st.dataframe(summary_df, use_container_width=True)
  else:
    st.warning("⚠️ ไม่มีข้อมูลสรุปตามเงื่อนไขที่เลือก")


# ==========================================
# 3. ส่วนตารางรายละเอียดข้อมูล (Detailed Table)
# ==========================================
st.markdown("---")
st.subheader("📋 รายละเอียดข้อมูลสมาชิก (แสดงด้านล่าง)")

# ตรวจสอบว่าผู้ใช้คลิกเลือกหมุดบนแผนที่หรือไม่
clicked_member_id = None
if map_output and map_output.get("last_object_clicked"):
  clicked_member_id = map_output["last_object_clicked"].get("popup")

table_display_df = filtered_df.copy()

if clicked_member_id:
  st.success(
      f"🎯 กำลังแสดงข้อมูลเฉพาะสมาชิกที่คลิกเลือกจากแผนที่: รหัส {clicked_member_id}"
  )
  if st.button("🔄 ล้างการเลือก (แสดงทั้งหมดตามตัวกรอง Sidebar)"):
    st.rerun()
  table_display_df = table_display_df[
      table_display_df["รหัสสมาชิก"] == str(clicked_member_id)
  ]
else:
  st.info(
      "💡 แสดงข้อมูลตามตัวกรองใน Sidebar สามารถเลือกดูแบบ 50, 100, 500"
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
    if c in table_display_df.columns
]

if not table_display_df.empty:
  table_df = table_display_df[display_cols].reset_index(drop=True)
  table_limited = (
      table_df.head(int(row_limit)) if row_limit != "ทั้งหมด" else table_df
  )

  st.dataframe(table_limited, use_container_width=True)
else:
  st.warning("⚠️ ไม่พบข้อมูลตามเงื่อนไขที่เลือก")
