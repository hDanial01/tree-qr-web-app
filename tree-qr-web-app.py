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
        if len(row) >= 10:
            entries.append({
                "ID": row[0], "Tree Name": row[1], "Name": row[2],
                "Overall Height": row[3], "DBH": row[4], "Canopy": row[5],
                "Image A": row[6], "Image B": row[7], "Latitude": row[8], "Longitude": row[9]
            })
    return entries

def save_to_gsheet(entry):
    sheet = get_worksheet()
    sheet.append_row([
        entry["ID"], entry["Tree Name"], entry["Name"],
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
        f.write(image_file.read())

    # Remove old file with same name
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

# Session state
if "entries" not in st.session_state:
    st.session_state.entries = load_entries_from_gsheet()
    required_keys = ["ID", "Tree Name", "Name", "Overall Height", "DBH", "Canopy",
                     "Image A", "Image B", "Latitude", "Longitude"]
    for entry in st.session_state.entries:
        for key in required_keys:
            entry.setdefault(key, "")

if "latitude" not in st.session_state:
    st.session_state.latitude = None
if "longitude" not in st.session_state:
    st.session_state.longitude = None

st.title("\U0001F333 Tree QR Photo Uploader")

# QR Photo Capture (no scanning)
st.header("1. Capture QR Code Photo")
captured_qr = st.camera_input("\U0001F4F8 Take a photo of the QR code (no scanning required)")
if captured_qr:
    st.session_state.qr_image = captured_qr
    st.success("\u2705 QR image captured.")

# Tree data entry
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
        st.session_state.location_requested = False
    else:
        st.info("\U0001F4CD Waiting for browser permission or location data...")

st.write(f"\U0001F4CD Latitude: `{st.session_state.latitude}`")
st.write(f"\U0001F4CD Longitude: `{st.session_state.longitude}`")

with st.form("tree_form"):
    id_val = st.text_input("Tree ID")
    tree_name_suffix = st.text_input("Tree Name (Suffix only)", value="1")
    tree_custom_name = f"GGN/25/{tree_name_suffix}"
    st.markdown(f"\U0001F516 **Full Tree Name:** `{tree_custom_name}`")

    # List of species (make sure it's defined here or globally)
    tree_names = [
        "Alstonia angustiloba", "Aquilaria malaccensis", "Azadirachta indica",
        "Baringtonia acutangula", "Buchanania arborescens", "Callophyllum inophyllum",
        "Cerbera odollam rubra", "Cinnamomum iners", "Coccoloba uvifera",
        "Cratoxylum chochinchinensis", "Cratoxylum cochichinensis", "Cratoxylum formosum",
        "Dillenia indica", "Diospyros blancoi", "Diptercarpus baudi", "Diptercarpus gracilis",
        "Dyera costulata", "Eleocarpus grandiflorus", "Ficus lyrate",
        "Filicium decipiens", "Garcinia hombroniana", "Gardenia carinata",
        "Heteropanax fragrans", "Hopea ferrea", "Hopea odorata",
        "Leptospermum brachyandrum", "Licuala grandis", "Maniltoa browneoides",
        "Mesua ferrea", "Michelia champaka", "Milingtonia hortensis",
        "Millettia pinnata", "Mimusops elengi", "Pentaspadon monteylii",
        "Podocarpus macrophyllus", "Podocarpus polystachyus", "Pometia pinnata",
        "Saraca thaipingensis", "Shorea roxburghii", "Spathodea campanulata",
        "Sterculia foetida", "Sterculia paviflora", "Sygzium polyanthum",
        "Syzgium grande", "Syzgium spicata", "Tabebuia argentea",
        "Tabebuia rosea", "Terminalia calamansanai", "Terminalia catappa",
        "Tristania obovata", "Tristaniopsis whiteana", "Unknown sp", "Mixed sp"
    ]
    tree_name = st.selectbox("Tree Name", tree_names)
    overall_height = st.text_input("Overall Height (m)")
    dbh = st.text_input("DBH (cm)")
    canopy = st.text_input("Canopy Diameter (cm)")

    tree_image_a = st.file_uploader("Upload Tree Image (Overall)", type=["jpg", "jpeg", "png"], key="tree_a")
    tree_image_b = st.file_uploader("Upload Tree Image (Canopy)", type=["jpg", "jpeg", "png"], key="tree_b")

    submitted = st.form_submit_button("Add Entry")
    if submitted:
        if not all([id_val, tree_name, overall_height, dbh, canopy, tree_image_a, tree_image_b]):
            st.error("\u274C Please complete all fields.")
        elif st.session_state.latitude is None or st.session_state.longitude is None:
            st.error("\u274C GPS location is missing. Please click 'Get Location' and try again.")
        else:
            safe_tree_name = re.sub(r'[^a-zA-Z0-9_-]', '_', tree_custom_name)

            _, ext_a = os.path.splitext(tree_image_a.name)
            filename_a = f"{safe_tree_name}_A{ext_a}"
            image_url_a = upload_image_to_drive(tree_image_a, filename_a)

            _, ext_b = os.path.splitext(tree_image_b.name)
            filename_b = f"{safe_tree_name}_B{ext_b}"
            image_url_b = upload_image_to_drive(tree_image_b, filename_b)

            qr_image_url = ""
            if "qr_image" in st.session_state and st.session_state.qr_image:
                qr_filename = f"{safe_tree_name}_QR.jpg"
                qr_image_url = upload_image_to_drive(st.session_state.qr_image, qr_filename)
                st.success(f"\U0001F4F7 QR image saved as {qr_filename}")

            entry = {
                "ID": id_val,
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
