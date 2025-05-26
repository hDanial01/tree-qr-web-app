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
    required_keys = ["ID", "Tree Name", "Name", "Overall Height", "DBH", "Canopy",
                     "Image A", "Image B", "Latitude", "Longitude"]
    for entry in st.session_state.entries:
        for key in required_keys:
            entry.setdefault(key, "")

if "qr_result" not in st.session_state:
    st.session_state.qr_result = ""
if "latitude" not in st.session_state:
    st.session_state.latitude = None
if "longitude" not in st.session_state:
    st.session_state.longitude = None

st.title("\U0001F333 Tree QR Scanner")

# QR Capture
st.header("1. Capture QR Code (Camera Input)")
captured = st.camera_input("\U0001F4F8 Take a photo of the QR code")

if captured:
    file_bytes = np.asarray(bytearray(captured.read()), dtype=np.uint8)
    img = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
    detector = cv2.QRCodeDetector()
    data, bbox, _ = detector.detectAndDecode(img)

    if data:
        latest_entries = load_entries_from_gsheet()
        existing_ids = [entry["ID"] for entry in latest_entries]

        if data in existing_ids:
            st.error(f"\u274C This QR Code (ID: '{data}') already exists. Please scan a unique QR code.")
            st.session_state.qr_result = ""
        else:
            st.success(f"\u2705 QR Code Found and ID is unique: {data}")
            st.session_state.qr_result = data
    else:
        st.error("\u274C No QR code detected.")

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

if st.session_state.latitude is not None and st.session_state.longitude is not None:
    st.write(f"\U0001F4CD Latitude: `{st.session_state.latitude}`")
    st.write(f"\U0001F4CD Longitude: `{st.session_state.longitude}`")
else:
    st.info("\u26A0\uFE0F No coordinates yet. Click 'Get Location' to allow access.")

if st.session_state.qr_result == "":
    st.warning("\u26A0\uFE0F Please scan a unique QR code before filling in the form.")
else:
    existing_tree_names = [entry["Tree Name"] for entry in st.session_state.entries]

    with st.form("tree_form"):
        id_val = st.text_input("Tree ID", value=st.session_state.qr_result)
        tree_name_suffix = st.text_input("Tree Name (Suffix only)", value="1")
        tree_custom_name = f"GGN/25/{tree_name_suffix}"
        st.markdown(f"\U0001F516 **Full Tree Name:** `{tree_custom_name}`")

        if tree_custom_name in existing_tree_names:
            st.warning("⚠️ This Tree Name already exists. Please enter a unique suffix.")

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
            if tree_custom_name in existing_tree_names:
                st.error("❌ This Tree Name already exists. Please use a different suffix.")
            elif not all([id_val, tree_name, overall_height, dbh, canopy, tree_image_a, tree_image_b]):
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

# Edit entry
st.subheader("📂 Edit Entry")

if st.session_state.entries:
    edit_map = {entry["Tree Name"]: entry for entry in st.session_state.entries}
    selected_edit_name = st.selectbox("Select a tree to edit", list(edit_map.keys()))
    entry_to_edit = edit_map[selected_edit_name]

    if "edit_enabled" not in st.session_state:
        st.session_state.edit_enabled = False

    if st.button("✏️ Enable Edit Mode"):
        st.session_state.edit_enabled = True

    if st.session_state.edit_enabled:
        with st.form("edit_form"):
            id_val = st.text_input("Tree ID", value=entry_to_edit["ID"])
            tree_name = st.text_input("Tree Name", value=entry_to_edit["Tree Name"])
            species_name = st.text_input("Species Name", value=entry_to_edit["Name"])
            overall_height = st.text_input("Overall Height (m)", value=entry_to_edit["Overall Height"])
            dbh = st.text_input("DBH (cm)", value=entry_to_edit["DBH"])
            canopy = st.text_input("Canopy Diameter (cm)", value=entry_to_edit["Canopy"])

            new_image_a = st.file_uploader("Replace Image A (optional)", type=["jpg", "jpeg", "png"])
            new_image_b = st.file_uploader("Replace Image B (optional)", type=["jpg", "jpeg", "png"])

            edit_submit = st.form_submit_button("Save Changes")
            if edit_submit:
                try:
                    sheet = get_worksheet()
                    all_rows = sheet.get_all_values()
                    for idx, row in enumerate(all_rows[1:], start=2):
                        if row and row[0] == entry_to_edit["ID"]:
                            sheet.delete_rows(idx)
                            break

                    safe_tree_name = re.sub(r'[^a-zA-Z0-9_-]', '_', tree_name)

                    image_url_a = entry_to_edit["Image A"]
                    image_url_b = entry_to_edit["Image B"]

                    if new_image_a:
                        delete_file_from_drive(image_url_a)
                        _, ext_a = os.path.splitext(new_image_a.name)
                        filename_a = f"{safe_tree_name}_A{ext_a}"
                        image_url_a = upload_image_to_drive(new_image_a, filename_a)

                    if new_image_b:
                        delete_file_from_drive(image_url_b)
                        _, ext_b = os.path.splitext(new_image_b.name)
                        filename_b = f"{safe_tree_name}_B{ext_b}"
                        image_url_b = upload_image_to_drive(new_image_b, filename_b)

                    updated_entry = {
                        "ID": id_val,
                        "Tree Name": tree_name,
                        "Name": species_name,
                        "Overall Height": overall_height,
                        "DBH": dbh,
                        "Canopy": canopy,
                        "Image A": image_url_a,
                        "Image B": image_url_b,
                        "Latitude": entry_to_edit["Latitude"],
                        "Longitude": entry_to_edit["Longitude"]
                    }

                    save_to_gsheet(updated_entry)
                    st.session_state.entries = load_entries_from_gsheet()
                    st.success(f"✅ Updated entry: {tree_name}")
                    st.session_state.edit_enabled = False

                except Exception as e:
                    st.error(f"❌ Failed to edit entry: {e}")
else:
    st.info("No entries found. Add a tree entry first to enable editing.")
