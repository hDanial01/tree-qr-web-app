import streamlit as st
import streamlit.components.v1 as components
from PIL import Image
import pandas as pd
import numpy as np
import os
import re
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from pyzbar.pyzbar import decode
from openpyxl import Workbook
from openpyxl.drawing.image import Image as XLImage
import cv2

# Directories
IMAGE_DIR = "tree_images"
EXPORT_DIR = "exports"
os.makedirs(IMAGE_DIR, exist_ok=True)
os.makedirs(EXPORT_DIR, exist_ok=True)

# Google Sheets Setup
SHEET_NAME = "TreeQRDatabase"
CREDENTIALS_FILE = "creds.json"

def get_worksheet():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_name(CREDENTIALS_FILE, scope)
    client = gspread.authorize(creds)
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

def preprocess_image_for_qr(pil_img):
    img_cv = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
    gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
    gray = cv2.resize(gray, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return thresh

# Initialize
if "entries" not in st.session_state:
    st.session_state.entries = load_entries_from_gsheet()
if "qr_result" not in st.session_state:
    st.session_state.qr_result = ""

st.title("🌳 Tree QR Scanner with Google Sheets Database")

# QR Input Method
st.header("1. Upload QR Code Image")
uploaded_qr = st.file_uploader("Upload QR Code Image", type=["png", "jpg", "jpeg"])
if uploaded_qr:
    img = Image.open(uploaded_qr)
    st.image(img, caption="Uploaded QR", use_column_width=True)
    processed = preprocess_image_for_qr(img)
    decoded = decode(processed)
    if decoded:
        qr_text = decoded[0].data.decode("utf-8")
        st.success(f"Decoded QR: {qr_text}")
        st.session_state.qr_result = qr_text
    else:
        st.error("No QR code found in uploaded image.")

# Data Entry
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
            new_filename = f"{safe_id}{ext}"
            image_path = os.path.join(IMAGE_DIR, new_filename)
            with open(image_path, "wb") as f:
                f.write(tree_image.read())
            entry = {
                "ID": id_val, "Type": tree_type, "Height": height, "Canopy": canopy,
                "IUCN": iucn_status, "Classification": classification, "CSP": csp, "Image": new_filename
            }
            st.session_state.entries.append(entry)
            save_to_gsheet(entry)
            st.success(f"Entry added and saved! Image: {new_filename}")

# Display Entries
if st.session_state.entries:
    st.header("3. Current Entries")
    df = pd.DataFrame(st.session_state.entries)
    st.dataframe(df)

# Export Options
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
