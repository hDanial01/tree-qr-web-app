import streamlit as st
import cv2
import numpy as np
from PIL import Image
import os
import re
import json
import gspread
from streamlit_js_eval import get_geolocation
from oauth2client.service_account import ServiceAccountCredentials
from openpyxl import Workbook
from openpyxl.drawing.image import Image as XLImage
import pandas as pd
from pydrive.auth import GoogleAuth
from pydrive.drive import GoogleDrive

# Setup folders
IMAGE_DIR = "tree_images"
EXPORT_DIR = "exports"
os.makedirs(IMAGE_DIR, exist_ok=True)
os.makedirs(EXPORT_DIR, exist_ok=True)

# Google Sheets and Drive Setup
SHEET_NAME = "TreeQRDatabase"
GOOGLE_DRIVE_FOLDER_ID = "1iddkNU3O1U6bsoHge1m5a-DDZA_NjSVz"
creds_dict = st.secrets["CREDS_JSON"]
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
        if len(row) >= 12:
            entries.append({
                "ID": row[0], "Tree Name": row[1], "Name": row[2], "Overall Height": row[3], "DBH": row[4],
                "Canopy": row[5], "IUCN": row[6], "Classification": row[7], "CSP": row[8],
                "Image": row[9], "Latitude": row[10], "Longitude": row[11]
            })
    return entries

def save_to_gsheet(entry):
    sheet = get_worksheet()
    sheet.append_row([
        entry["ID"], entry["Tree Name"], entry["Name"], entry["Overall Height"], entry["DBH"], entry["Canopy"],
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

    required_keys = ["ID", "Tree Name", "Name", "Overall Height", "DBH", "Canopy", "IUCN",
                     "Classification", "CSP", "Image", "Latitude", "Longitude"]
    for entry in st.session_state.entries:
        for key in required_keys:
            entry.setdefault(key, "")

if "qr_result" not in st.session_state:
    st.session_state.qr_result = ""
if "latitude" not in st.session_state:
    st.session_state.latitude = None
if "longitude" not in st.session_state:
    st.session_state.longitude = None

st.title("🌳 Tree QR Scanner")

# QR Capture
st.header("1. Capture QR Code (Camera Input)")
captured = st.camera_input("📸 Take a photo of the QR code")

if captured:
    file_bytes = np.asarray(bytearray(captured.read()), dtype=np.uint8)
    img = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
    detector = cv2.QRCodeDetector()
    data, bbox, _ = detector.detectAndDecode(img)

    if data:
        latest_entries = load_entries_from_gsheet()
        existing_ids = [entry["ID"] for entry in latest_entries]

        if data in existing_ids:
            st.error(f"🚫 This QR Code (ID: '{data}') already exists in the database. Please scan a unique QR code.")
            st.session_state.qr_result = ""
        else:
            st.success(f"✅ QR Code Found and ID is unique: {data}")
            st.session_state.qr_result = data
    else:
        st.error("❌ No QR code detected.")

# Tree data entry
st.header("2. Fill Tree Details")

st.header("📍 Capture Your GPS Location")

if "location_requested" not in st.session_state:
    st.session_state.location_requested = False

if st.button("Get Location"):
    st.session_state.location_requested = True

if st.session_state.location_requested:
    location = get_geolocation()
    if location:
        st.session_state.latitude = location["coords"]["latitude"]
        st.session_state.longitude = location["coords"]["longitude"]
        st.success("📡 Location captured!")
        st.session_state.location_requested = False
    else:
        st.info("📍 Waiting for browser permission or location data...")

if st.session_state.latitude is not None and st.session_state.longitude is not None:
    st.write(f"📍 Latitude: `{st.session_state.latitude}`")
    st.write(f"📍 Longitude: `{st.session_state.longitude}`")
else:
    st.info("⚠️ No coordinates yet. Click 'Get Location' to allow access.")

if st.session_state.qr_result == "":
    st.warning("⚠️ Please scan a unique QR code before filling in the form.")
else:
    with st.form("tree_form"):
        id_val = st.text_input("Tree ID", value=st.session_state.qr_result)
        
        # NEW: Custom Tree Name
        tree_name_suffix = st.text_input("Tree Name (Suffix only)", value="1")
        tree_custom_name = f"GGN/25/{tree_name_suffix}"
        st.markdown(f"🔖 **Full Tree Name:** `{tree_custom_name}`")

        tree_name = st.selectbox("Common Name", ["Tree 1", "Tree 2", "Tree 3", "Tree 4", "Tree 5"])
        overall_height = st.text_input("Overall Height (m)")
        dbh = st.text_input("DBH (cm)")
        canopy = st.text_input("Canopy Diameter (cm)")
        iucn_status = st.selectbox("IUCN Status", ["Native", "Non-Native"])
        classification = st.selectbox("Classification", ["Class 1", "Class 2"])
        csp = st.selectbox("CSP", ["0%~20%", "21%~40%", "41%~60%", "61%~80%", "81%~100%"])
        tree_image = st.file_uploader("Upload Tree Image", type=["jpg", "jpeg", "png"], key="tree")

        submitted = st.form_submit_button("Add Entry")
        if submitted:
            if not all([id_val, tree_name, overall_height, dbh, canopy, iucn_status, classification, csp, tree_image]):
                st.error("❌ Please complete all fields.")
            elif st.session_state.latitude is None or st.session_state.longitude is None:
                st.error("❌ GPS location is missing. Please click 'Get Location' and try again.")
            else:
                safe_tree_name = re.sub(r'[^a-zA-Z0-9_-]', '_', tree_custom_name)
                _, ext = os.path.splitext(tree_image.name)
                filename = f"{safe_tree_name}{ext}"

                image_url = upload_image_to_drive(tree_image, filename)

                entry = {
                    "ID": id_val,
                    "Tree Name": tree_custom_name,
                    "Name": tree_name,
                    "Overall Height": overall_height,
                    "DBH": dbh,
                    "Canopy": canopy,
                    "IUCN": iucn_status,
                    "Classification": classification,
                    "CSP": csp,
                    "Image": image_url,
                    "Latitude": st.session_state.latitude,
                    "Longitude": st.session_state.longitude
                }

                st.session_state.entries.append(entry)
                save_to_gsheet(entry)
                st.success("✅ Entry added and image saved!")

                st.write(f"📍 Latitude saved: `{st.session_state.latitude}`")
                st.write(f"📍 Longitude saved: `{st.session_state.longitude}`")

                # Reset coordinates
                st.session_state.latitude = None
                st.session_state.longitude = None


# Display table
if st.session_state.entries:
    st.header("3. Current Entries")
    df = pd.DataFrame(st.session_state.entries)
    st.dataframe(df)

# Export section
if st.session_state.entries:
    st.header("4. Export Data")
    csv_data = pd.DataFrame(st.session_state.entries).to_csv(index=False).encode("utf-8")
    st.download_button("Download CSV", csv_data, "tree_data.csv", "text/csv")

    if st.button("Download Excel with Images"):
        path = os.path.join(EXPORT_DIR, "tree_data.xlsx")
        wb = Workbook()
        ws = wb.active
        headers = ["ID", "Tree Name", "Name", "Overall Height", "DBH", "Canopy", "IUCN", "Classification", "CSP", "Image", "Latitude", "Longitude"]
        ws.append(headers)
        for i, entry in enumerate(st.session_state.entries, start=2):
            ws.append([entry.get(k, "") for k in headers])
            img_url = entry.get("Image", "")
            ws.cell(row=i, column=10).value = f'=HYPERLINK("{img_url}", "View Image")'
        wb.save(path)
        with open(path, "rb") as f:
            st.download_button("Download Excel File", f, "tree_data.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
