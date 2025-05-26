import streamlit as st
import cv2
import numpy as np
from PIL import Image
import os
import re
import gspread
from streamlit_js_eval import get_geolocation
from oauth2client.service_account import ServiceAccountCredentials
from openpyxl import Workbook
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
        if len(row) >= 9:
            entries.append({
                "Tree Name": row[0], "Name": row[1],
                "Overall Height": row[2], "DBH": row[3], "Canopy": row[4],
                "Image A": row[5], "Image B": row[6], "Latitude": row[7], "Longitude": row[8]
            })
    return entries

def save_to_gsheet(entry):
    sheet = get_worksheet()
    sheet.append_row([
        entry["Tree Name"], entry["Name"],
        entry["Overall Height"], entry["DBH"], entry["Canopy"],
        entry["Image A"], entry["Image B"],
        entry.get("Latitude", ""), entry.get("Longitude", "")
    ])

def delete_file_from_drive(file_url):
    try:
        match = re.search(r'id=([a-zA-Z0-9_-]+)', file_url)
        if match:
            file_id = match.group(1)
            file_drive = drive.CreateFile({'id': file_id})
            file_drive.Delete()
    except Exception as e:
        st.warning(f"Could not delete image from Drive: {e}")

def upload_image_to_drive(image_file, filename):
    with open(filename, "wb") as f:
        f.write(image_file.getbuffer())  # FIXED

    file_list = drive.ListFile({
        'q': f"'{GOOGLE_DRIVE_FOLDER_ID}' in parents and title = '{filename}' and trashed = false"
    }).GetList()

    for old_file in file_list:
        old_file.Delete()

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

# Session state setup
if "entries" not in st.session_state:
    st.session_state.entries = load_entries_from_gsheet()
    required_keys = ["Tree Name", "Name", "Overall Height", "DBH", "Canopy", "Image A", "Image B", "Latitude", "Longitude"]
    for entry in st.session_state.entries:
        for key in required_keys:
            entry.setdefault(key, "")

if "latitude" not in st.session_state:
    st.session_state.latitude = None
if "longitude" not in st.session_state:
    st.session_state.longitude = None

st.title("\U0001F333 Tree QR Scanner")

st.header("1. Capture QR Code Photo")
captured = st.camera_input("\U0001F4F8 Take a photo of the QR code (no scanning required)")
if captured:
    st.session_state.qr_image = captured
    st.success("\u2705 QR image captured.")

st.header("2. Fill Tree Details")
st.header("\U0001F4CD Capture Your GPS Location")

if "location_requested" not in st.session_state:
    st.session_state.location_requested = False

if st.button("Get Location"):
    st.session_state.location_requested = True

if st.session_state.location_requested:
    location = get_geolocation()
    if location:
        st.session_state.latitude = location["coords"]["latitude"]
        st.session_state.longitude = location["coords"]["longitude"]
        st.success("\U0001F4E1 Location captured!")
    else:
        st.info("\U0001F4CD Waiting for browser permission or location data...")

if st.session_state.latitude is not None and st.session_state.longitude is not None:
    st.write(f"\U0001F4CD Latitude: `{st.session_state.latitude}`")
    st.write(f"\U0001F4CD Longitude: `{st.session_state.longitude}`")
else:
    st.info("\u26A0\uFE0F No coordinates yet. Click 'Get Location' to allow access.")

existing_tree_names = [entry["Tree Name"] for entry in st.session_state.entries]

with st.form("tree_form"):
    tree_name_suffix = st.text_input("Tree Name (Suffix only)", value="1")
    tree_custom_name = f"GGN/25/{tree_name_suffix}"
    st.markdown(f"\U0001F516 **Full Tree Name:** `{tree_custom_name}`")

    if tree_custom_name in existing_tree_names:
        st.warning("\u26A0\uFE0F This Tree Name already exists. Please enter a unique suffix.")

    tree_name = st.selectbox("Tree Name", [...])  # shortened here for brevity
    overall_height = st.selectbox("Overall Height (m)", ["1", "2", "3", "4", "5", "6", "7"])
    dbh = st.selectbox("DBH (cm)", ["1", "2", "3", "4", "5", "6", "7", "8", "9"])
    canopy = st.text_input("Canopy Diameter (cm)")

    st.subheader("\U0001F4F8 Step-by-Step Tree Photo Capture")

    if "tree_image_a" not in st.session_state:
        st.session_state.tree_image_a = None
    if "tree_image_b" not in st.session_state:
        st.session_state.tree_image_b = None

    if st.session_state.tree_image_a is None:
        st.session_state.tree_image_a = st.camera_input("\U0001F333 Capture Tree Image A (Overall View)")

    if st.session_state.tree_image_a:
        st.success("\u2705 Tree Image A captured.")
        if st.button("\U0001F501 Retake Tree Image A"):
            st.session_state.tree_image_a = None

        if st.session_state.tree_image_b is None:
            st.session_state.tree_image_b = st.camera_input("\U0001F33F Capture Tree Image B (Canopy View)")

        if st.session_state.tree_image_b:
            st.success("\u2705 Tree Image B captured.")
            if st.button("\U0001F501 Retake Tree Image B"):
                st.session_state.tree_image_b = None

    submitted = st.form_submit_button("Add Entry")

    if submitted:
        if tree_custom_name in existing_tree_names:
            st.error("\u274C This Tree Name already exists. Please use a different suffix.")
        elif not all([tree_name, overall_height, dbh, canopy, st.session_state.tree_image_a, st.session_state.tree_image_b]):
            st.error("\u274C Please complete all fields.")
        elif st.session_state.latitude is None or st.session_state.longitude is None:
            st.error("\u274C GPS location is missing. Please click 'Get Location' and try again.")
        else:
            safe_tree_name = re.sub(r'[^a-zA-Z0-9_-]', '_', tree_custom_name)

            filename_a = f"{safe_tree_name}_A.jpg"
            image_url_a = upload_image_to_drive(st.session_state.tree_image_a, filename_a)

            filename_b = f"{safe_tree_name}_B.jpg"
            image_url_b = upload_image_to_drive(st.session_state.tree_image_b, filename_b)

            if "qr_image" in st.session_state and st.session_state.qr_image is not None:
                qr_filename = f"GGN_25_{tree_name_suffix}_QR.jpg"
                with open(qr_filename, "wb") as f:
                    f.write(st.session_state.qr_image.getbuffer())
                file_drive = drive.CreateFile({"title": qr_filename, "parents": [{"id": GOOGLE_DRIVE_FOLDER_ID}]})
                file_drive.SetContentFile(qr_filename)
                file_drive.Upload()
                file_drive.InsertPermission({
                    'type': 'anyone',
                    'value': 'anyone',
                    'role': 'reader'
                })
                os.remove(qr_filename)
                st.success(f"\U0001F4F8 QR image saved as `{qr_filename}`")

            entry = {
                "Tree Name": tree_custom_name,
                "Name": tree_name,
                "Overall Height": overall_height,
                "DBH": dbh,
                "Canopy": canopy,
                "Image A": image_url_a,
                "Image B": image_url_b,
                "Latitude": st.session_state.latitude,
                "Longitude": st.session_state.longitude
            }

            st.session_state.entries.append(entry)
            save_to_gsheet(entry)
            st.success("\u2705 Entry added and images saved!")

            st.session_state.latitude = None
            st.session_state.longitude = None
            st.session_state.tree_image_a = None
            st.session_state.tree_image_b = None

if st.session_state.entries:
    st.header("3. Current Entries")
    df = pd.DataFrame(st.session_state.entries)
    st.dataframe(df)

# Export
st.header("4. Export Data")
if st.session_state.entries:
    csv_data = pd.DataFrame(st.session_state.entries).to_csv(index=False).encode("utf-8")
    st.download_button("Download CSV", csv_data, "tree_data.csv", "text/csv")

    if st.button("Download Excel with Images"):
        path = os.path.join(EXPORT_DIR, "tree_data.xlsx")
        wb = Workbook()
        ws = wb.active
        headers = ["Tree Name", "Name", "Overall Height", "DBH", "Canopy", "Image A", "Image B", "Latitude", "Longitude"]
        ws.append(headers)
        for i, entry in enumerate(st.session_state.entries, start=2):
            ws.append([entry.get(k, "") for k in headers])
            ws.cell(row=i, column=6).value = f'=HYPERLINK("{entry.get("Image A", "")}", "View A")'
            ws.cell(row=i, column=7).value = f'=HYPERLINK("{entry.get("Image B", "")}", "View B")'
        wb.save(path)
        with open(path, "rb") as f:
            st.download_button("Download Excel File", f, "tree_data.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
