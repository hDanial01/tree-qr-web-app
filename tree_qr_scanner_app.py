import streamlit as st
import cv2
import numpy as np
from PIL import Image
import os
import re
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from openpyxl import Workbook
from openpyxl.drawing.image import Image as XLImage
import pandas as pd
from pydrive.auth import GoogleAuth
from pydrive.drive import GoogleDrive
from streamlit_js_eval import streamlit_js_eval  # NEW for GPS

# Setup folders
IMAGE_DIR = "tree_images"
EXPORT_DIR = "exports"
os.makedirs(IMAGE_DIR, exist_ok=True)
os.makedirs(EXPORT_DIR, exist_ok=True)

# Google Sheets and Drive Setup
SHEET_NAME = "TreeQRDatabase"
GOOGLE_DRIVE_FOLDER_ID = "1iddkNU3O1U6bsoHge1m5a-DDZA_NjSVz"
creds_dict = json.loads(st.secrets["CREDS_JSON"])
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
client = gspread.authorize(creds)

gauth = GoogleAuth()
gauth.credentials = creds
drive = GoogleDrive(gauth)

def get_worksheet():
    return client.open(SHEET_NAME).sheet1

def load_entries_from_gsheet():
    sheet = get_worksheet()
    rows = sheet.get_all_values()[1:]
    entries = []
    for row in rows:
        entry = {
            "ID": row[0], "Type": row[1], "Height": row[2], "Canopy": row[3],
            "IUCN": row[4], "Classification": row[5], "CSP": row[6], "Image": row[7]
        }
        if len(row) > 9:
            entry["Latitude"] = row[8]
            entry["Longitude"] = row[9]
        else:
            entry["Latitude"] = ""
            entry["Longitude"] = ""
        entries.append(entry)
    return entries

def save_to_gsheet(entry):
    sheet = get_worksheet()
    sheet.append_row([
        entry["ID"], entry["Type"], entry["Height"], entry["Canopy"],
        entry["IUCN"], entry["Classification"], entry["CSP"], entry["Image"],
        entry.get("Latitude", ""), entry.get("Longitude", "")
    ])

def upload_image_to_drive(image_file, filename):
    with open(filename, "wb") as f:
        f.write(image_file.read())
    file_drive = drive.CreateFile({"title": filename, "parents": [{"id": GOOGLE_DRIVE_FOLDER_ID}]})
    file_drive.SetContentFile(filename)
    file_drive.Upload()
    file_drive.InsertPermission({
        'type': 'anyone',
        'value': 'anyone',
        'role': 'reader'
    })
    os.remove(filename)
    return f"https://drive.google.com/uc?id={file_drive['id']}"

# Session state
if "entries" not in st.session_state:
    st.session_state.entries = load_entries_from_gsheet()
if "qr_result" not in st.session_state:
    st.session_state.qr_result = ""
if "qr_status" not in st.session_state:
    st.session_state.qr_status = None
if "coords" not in st.session_state:
    st.session_state.coords = {}

st.title("🌳 Tree QR Scanner")

# 1. Capture QR Code
st.header("1. Capture QR Code (Camera Input)")
captured = st.camera_input("📸 Take a photo of the QR code")

if captured:
    file_bytes = np.asarray(bytearray(captured.read()), dtype=np.uint8)
    img = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
    detector = cv2.QRCodeDetector()
    data, bbox, _ = detector.detectAndDecode(img)

    if data:
        data = data.strip()
        st.session_state.qr_result = data
        existing_ids = [entry["ID"].lower() for entry in st.session_state.entries]
        st.session_state.qr_status = "duplicate" if data.lower() in existing_ids else "unique"
    else:
        st.error("❌ No QR code detected.")

# 2. QR Status & GPS
if st.session_state.qr_result:
    st.header("2. QR Code Status and GPS Location")

    if st.session_state.qr_status == "duplicate":
        st.error(f"🚫 QR Code ID '{st.session_state.qr_result}' already exists in the system.")
    elif st.session_state.qr_status == "unique":
        st.success(f"✅ QR Code Found: {st.session_state.qr_result} (ID is unique)")

        if st.button("📍 Get Location"):
            try:
                coords = streamlit_js_eval(
                    js_expressions='navigator.geolocation.getCurrentPosition((pos) => pos.coords)',
                    key="get_coords"
                )
                if coords and "latitude" in coords:
                    st.session_state.coords = coords
                    st.success(f"📍 Location captured: {coords['latitude']}, {coords['longitude']}")
                else:
                    st.warning("⚠️ GPS request sent but no location returned. Try again or use manual input.")
            except Exception as e:
                st.error(f"📍 GPS error: {e}")

        if st.session_state.coords:
            st.markdown(f"**Latitude:** {st.session_state.coords.get('latitude', '')}")
            st.markdown(f"**Longitude:** {st.session_state.coords.get('longitude', '')}")
        else:
            st.info("📍 If location isn't captured, enter manually below.")
            manual_lat = st.text_input("Latitude (manual)")
            manual_lon = st.text_input("Longitude (manual)")
            if manual_lat and manual_lon:
                st.session_state.coords = {"latitude": manual_lat, "longitude": manual_lon}
                st.success("📍 Manual coordinates saved.")

# 3. Form
existing_ids = [entry["ID"].lower() for entry in st.session_state.entries]
qr_id = st.session_state.qr_result.lower() if st.session_state.qr_result else ""

if qr_id and qr_id not in existing_ids:
    st.header("3. Fill Tree Details")
    with st.form("tree_form"):
        id_val = st.text_input("Tree ID", value=st.session_state.qr_result)
        tree_type = st.selectbox("Tree Type", ["A - Hibiscus/Hibiscus rosa-sinensis", "B -  Rubber tree/Hevea brasiliensis", "C - Mango tree/Mangifera indica", "D - Jackfruit tree/Artocarpus heterophyllus", "E - Merbau/Intsia palembanica"])
        height = st.text_input("Height (cm)")
        canopy = st.text_input("Canopy Diameter (cm)")
        iucn_status = st.selectbox("IUCN Status", ["Not Evaluated", "Data Deficient", "Least Concern", "Near Threatened", "Vulnerable", "Endangered", "Critically Endangered", "Extinct in the Wild", "Extinct"])
        classification = st.selectbox("Classification", ["Native", "Non-native"])
        csp = st.selectbox("CSP", ["0%~20%", "21%~40%", "41%~60%", "61%~80%", "81%~100%"])
        tree_image = st.file_uploader("Upload Tree Image", type=["jpg", "jpeg", "png"], key="tree")

        submitted = st.form_submit_button("Add Entry")
        if submitted:
            if not all([id_val, tree_type, height, canopy, iucn_status, classification, csp, tree_image]):
                st.error("❌ Please complete all fields.")
            elif id_val.lower() in [entry["ID"].lower() for entry in st.session_state.entries]:
                st.error("🚫 A tree with this ID already exists. Please enter a unique Tree ID.")
            else:
                safe_id = re.sub(r'[^a-zA-Z0-9_-]', '_', id_val)
                _, ext = os.path.splitext(tree_image.name)
                filename = f"{safe_id}{ext}"
                image_url = upload_image_to_drive(tree_image, filename)
                entry = {
                    "ID": id_val,
                    "Type": tree_type,
                    "Height": height,
                    "Canopy": canopy,
                    "IUCN": iucn_status,
                    "Classification": classification,
                    "CSP": csp,
                    "Image": image_url,
                    "Latitude": st.session_state.coords.get("latitude", ""),
                    "Longitude": st.session_state.coords.get("longitude", "")
                }
                st.session_state.entries.append(entry)
                save_to_gsheet(entry)
                st.success("✅ Entry added and image saved!")

# 4. Table
if st.session_state.entries:
    st.header("4. Current Entries")
    df = pd.DataFrame(st.session_state.entries)
    st.dataframe(df)

# 5. Export
if st.session_state.entries:
    st.header("5. Export Data")
    csv_data = pd.DataFrame(st.session_state.entries).to_csv(index=False).encode("utf-8")
    st.download_button("Download CSV", csv_data, "tree_data.csv", "text/csv")

    if st.button("Download Excel with Images"):
        path = os.path.join(EXPORT_DIR, "tree_data.xlsx")
        wb = Workbook()
        ws = wb.active
        headers = ["ID", "Type", "Height", "Canopy", "IUCN", "Classification", "CSP", "Image", "Latitude", "Longitude"]
        ws.append(headers)
        for i, entry in enumerate(st.session_state.entries, start=2):
            ws.append([entry.get(k, "") for k in headers])
            ws.cell(row=i, column=8).value = f'=HYPERLINK("{entry["Image"]}", "View Image")'
        wb.save(path)
        with open(path, "rb") as f:
            st.download_button("Download Excel File", f, "tree_data.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
