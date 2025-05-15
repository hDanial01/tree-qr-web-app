import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from PIL import Image
import pandas as pd
import os
import re
import json
import cv2
import numpy as np
from pydrive.auth import GoogleAuth
from pydrive.drive import GoogleDrive
from openpyxl import Workbook
from openpyxl.drawing.image import Image as XLImage

# Constants
SHEET_NAME = "TreeQRDatabase"
GOOGLE_DRIVE_FOLDER_ID = "1iddkNU3O1U6bsoHge1m5a-DDZA_NjSVz"
EXPORT_DIR = "exports"
os.makedirs(EXPORT_DIR, exist_ok=True)

# Authenticate with Google APIs
creds_dict = json.loads(st.secrets["CREDS_JSON"])
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
client = gspread.authorize(creds)
gauth = GoogleAuth()
gauth.credentials = creds
drive = GoogleDrive(gauth)

# Google Sheet access
def get_worksheet():
    return client.open(SHEET_NAME).sheet1

def load_entries_from_gsheet():
    sheet = get_worksheet()
    rows = sheet.get_all_values()[1:]
    return [
        dict(zip(["ID", "Type", "Height", "Canopy", "IUCN", "Classification", "CSP", "Image"], row))
        for row in rows if len(row) >= 8
    ]

def save_to_gsheet(entry):
    sheet = get_worksheet()
    sheet.append_row([entry[k] for k in ["ID", "Type", "Height", "Canopy", "IUCN", "Classification", "CSP", "Image"]])

# Google Drive upload
def upload_image_to_drive(image_file, filename):
    with open(filename, "wb") as f:
        f.write(image_file.read())
    file_drive = drive.CreateFile({"title": filename, "parents": [{"id": GOOGLE_DRIVE_FOLDER_ID}]})
    file_drive.SetContentFile(filename)
    file_drive.Upload()
    os.remove(filename)
    return f"https://drive.google.com/uc?id={file_drive['id']}"

# QR decoding from image
def decode_qr_image(uploaded_file):
    try:
        image = Image.open(uploaded_file).convert('RGB')
        st.image(image, caption="QR Image", use_column_width=True)
        img_np = np.array(image)
        img_bgr = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)
        detector = cv2.QRCodeDetector()
        data, _, _ = detector.detectAndDecode(img_bgr)
        return data
    except:
        return ""

# Initialize session state
if "entries" not in st.session_state:
    st.session_state.entries = load_entries_from_gsheet()
if "qr_result" not in st.session_state:
    st.session_state.qr_result = ""

# App UI
st.title("🌳 Tree QR Web App")

# QR Section
st.header("1. Upload QR Code Image")
uploaded_qr = st.file_uploader("Upload a QR code image", type=["jpg", "jpeg", "png"])
if uploaded_qr:
    result = decode_qr_image(uploaded_qr)
    if result:
        st.session_state.qr_result = result
        st.success(f"QR Code Detected: {result}")
    else:
        st.error("No QR code found in the image.")

# Tree form
st.header("2. Enter Tree Details")
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
            image_url = upload_image_to_drive(tree_image, filename)

            entry = {
                "ID": id_val,
                "Type": tree_type,
                "Height": height,
                "Canopy": canopy,
                "IUCN": iucn_status,
                "Classification": classification,
                "CSP": csp,
                "Image": image_url
            }

            st.session_state.entries.append(entry)
            save_to_gsheet(entry)
            st.success("Entry added and image uploaded to Google Drive!")

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
