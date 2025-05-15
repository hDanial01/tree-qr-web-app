
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

# Setup folders
IMAGE_DIR = "tree_images"
EXPORT_DIR = "exports"
os.makedirs(IMAGE_DIR, exist_ok=True)
os.makedirs(EXPORT_DIR, exist_ok=True)

# Google Sheets Setup
SHEET_NAME = "TreeQRDatabase"
creds_dict = json.loads(st.secrets["CREDS_JSON"])
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
client = gspread.authorize(creds)

# Google Drive Setup
def get_drive():
    gauth = GoogleAuth()
    gauth.credentials = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, [
        "https://www.googleapis.com/auth/drive"
    ])
    return GoogleDrive(gauth)

def upload_to_drive(filepath, filename, folder_id):
    drive = get_drive()
    file_drive = drive.CreateFile({
        'title': filename,
        'parents': [{'id': folder_id}]
    })
    file_drive.SetContentFile(filepath)
    file_drive.Upload()

GOOGLE_DRIVE_FOLDER_ID = "1iddkNU3O1U6bsoHge1m5a-DDZA_NjSVz"  # Replace with your folder ID

def get_worksheet():
    return client.open(SHEET_NAME).sheet1

def load_entries_from_gsheet():
    sheet = get_worksheet()
    rows = sheet.get_all_values()[1:]
    entries = []
    for row in rows:
        if len(row) >= 8:
            entries.append({
                "ID": row[0], "Type": row[1], "Height": row[2], "Canopy": row[3],
                "IUCN": row[4], "Classification": row[5], "CSP": row[6], "Image": row[7]
            })
    return entries

def save_to_gsheet(entry):
    sheet = get_worksheet()
    sheet.append_row([
        entry["ID"], entry["Type"], entry["Height"], entry["Canopy"],
        entry["IUCN"], entry["Classification"], entry["CSP"], entry["Image"]
    ])

# Session state
if "entries" not in st.session_state:
    st.session_state.entries = load_entries_from_gsheet()
if "qr_result" not in st.session_state:
    st.session_state.qr_result = ""

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
        st.success(f"✅ QR Code Found: {data}")
        st.session_state.qr_result = data
    else:
        st.error("❌ No QR code detected.")

# Tree data entry
st.header("2. Fill Tree Details")
with st.form("tree_form"):
    id_val = st.text_input("Tree ID", value=st.session_state.qr_result)
    tree_type = st.selectbox("Tree Type", ["Tree 1", "Tree 2", "Tree 3", "Tree 4", "Tree 5"])
    height = st.text_input("Height (m)")
    canopy = st.text_input("Canopy Diameter (m)")
    iucn_status = st.selectbox("IUCN Status", ["Native", "Non-Native"])
    classification = st.selectbox("Classification", ["Class 1", "Class 2"])
    csp = st.selectbox("CSP", ["0%~20%", "21%~40%", "41%~60%", "61%~80%", "81%~100%"])
    tree_image = st.file_uploader("Upload Tree Image", type=["jpg", "jpeg", "png"], key="tree")

    submitted = st.form_submit_button("Add Entry")
    if submitted:
        if not all([id_val, tree_type, height, canopy, iucn_status, classification, csp, tree_image]):
            st.error("Please complete all fields.")
        else:
            safe_id = re.sub(r'[^a-zA-Z0-9_-]', '_', id_val)
            _, ext = os.path.splitext(tree_image.name)
            filename = f"{safe_id}{ext}"
            image_path = os.path.join(IMAGE_DIR, filename)

            with open(image_path, "wb") as f:
                f.write(tree_image.read())

            # Upload to Google Drive
            upload_to_drive(image_path, filename, GOOGLE_DRIVE_FOLDER_ID)

            entry = {
                "ID": id_val, "Type": tree_type, "Height": height, "Canopy": canopy,
                "IUCN": iucn_status, "Classification": classification, "CSP": csp,
                "Image": filename
            }

            st.session_state.entries.append(entry)
            save_to_gsheet(entry)
            st.success("✅ Entry added and image uploaded to Google Drive!")

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
        headers = ["ID", "Type", "Height", "Canopy", "IUCN", "Classification", "CSP", "Image"]
        ws.append(headers)
        for i, entry in enumerate(st.session_state.entries, start=2):
            ws.append([entry[k] for k in headers])
            img_path = os.path.join(IMAGE_DIR, entry["Image"])
            if os.path.exists(img_path):
                img = XLImage(img_path)
                img.width = img.height = 60
                img.anchor = f"H{i}"
                ws.add_image(img)
        wb.save(path)
        with open(path, "rb") as f:
            st.download_button("Download Excel File", f, "tree_data.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
