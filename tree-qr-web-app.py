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
        if len(row) >= 13:
            entries.append({
                "ID": row[0], "Tree Name": row[1], "Name": row[2], "Overall Height": row[3], "DBH": row[4],
                "Canopy": row[5], "IUCN": row[6], "Classification": row[7], "CSP": row[8],
                "Image A": row[9], "Image B": row[10], "Latitude": row[11], "Longitude": row[12]
            })
    return entries

def save_to_gsheet(entry):
    sheet = get_worksheet()
    sheet.append_row([
        entry["ID"], entry["Tree Name"], entry["Name"], entry["Overall Height"], entry["DBH"], entry["Canopy"],
        entry["IUCN"], entry["Classification"], entry["CSP"], entry["Image A"], entry["Image B"],
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
                     "Classification", "CSP", "Image A", "Image B", "Latitude", "Longitude"]
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
    with st.form("tree_form"):
        id_val = st.text_input("Tree ID", value=st.session_state.qr_result)
        tree_name_suffix = st.text_input("Tree Name (Suffix only)", value="1")
        tree_custom_name = f"GGN/25/{tree_name_suffix}"
        st.markdown(f"\U0001F516 **Full Tree Name:** `{tree_custom_name}`")

        tree_names = [
            "Baeckea frutescens (BFr)", "Buchanania (BA)", "Caesalpinia ferrea (CFe)", "Calophyllum inophyllum (CIn)",
            "Canarium album (CAl)", "Cedrela (Cdl)", "Coccoloba uvifera (CUv)", "Dalbergia sissoo (DSi)",
            "Dillenia suffruticosa (DSu)", "Diospyros buxifolia (DBu)", "Diospyros discolor (DDi)",
            "Dipterocarpus turbinatus (DTu)", "Ficus Gold (FGo)", "Filicium decipiens (FDe)",
            "Gymnostoma rumphianum (GRu)", "Hopea ferrea (HFr)", "Hopea odorata (HOd)", "Lagerstroemia indica (LIn)",
            "Lagerstroemia speciosa (LSp)", "Maniltoa browneoides (MBr)", "Melaleuca cajuputi (MCa)",
            "Mesua ferrea (MFr)", "Ormasia pinnata (OPi)", "Planchonella obovata (POb)", "Podocarpus rumphii (PRm)",
            "Samanea saman (SSa)", "Shorea wangtianshuea (SWa)", "Spatheodea camanviata (SCa)",
            "Syzygium grande (SGr)", "Terminalia calamansanai (TCa)", "Terminalia catappa (TCp)"
        ]
        tree_name = st.selectbox("Tree Name", tree_names)
        overall_height = st.text_input("Overall Height (m)")
        dbh = st.text_input("DBH (cm)")
        canopy = st.text_input("Canopy Diameter (cm)")
        iucn_status = st.selectbox("IUCN Status", ["Status 1", "Status 2", "Status 3"])
        classification = st.selectbox("Classification", ["Native", "Non-Native"])
        csp = st.selectbox("CSP", ["0%~20%", "21%~40%", "41%~60%", "61%~80%", "81%~100%"])

        tree_image_a = st.file_uploader("Upload Tree Image A", type=["jpg", "jpeg", "png"], key="tree_a")
        tree_image_b = st.file_uploader("Upload Tree Image B", type=["jpg", "jpeg", "png"], key="tree_b")

        submitted = st.form_submit_button("Add Entry")
        if submitted:
            if not all([id_val, tree_name, overall_height, dbh, canopy, iucn_status, classification, csp, tree_image_a, tree_image_b]):
                st.error("\u274C Please complete all fields.")
            elif st.session_state.latitude is None or st.session_state.longitude is None:
                st.error("\u274C GPS location is missing. Please click 'Get Location' and try again.")
            else:
                safe_tree_name = re.sub(r'[^a-zA-Z0-9_-]', '_', tree_custom_name)

                _, ext_a = os.path.splitext(tree_image_a.name)
                filename_a = f"A_{safe_tree_name}{ext_a}"
                image_url_a = upload_image_to_drive(tree_image_a, filename_a)

                _, ext_b = os.path.splitext(tree_image_b.name)
                filename_b = f"B_{safe_tree_name}{ext_b}"
                image_url_b = upload_image_to_drive(tree_image_b, filename_b)

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
                    "Image A": image_url_a,
                    "Image B": image_url_b,
                    "Latitude": st.session_state.latitude,
                    "Longitude": st.session_state.longitude
                }

                st.session_state.entries.append(entry)
                save_to_gsheet(entry)
                st.success("\u2705 Entry added and images saved!")

                st.write(f"\U0001F4CD Latitude saved: `{st.session_state.latitude}`")
                st.write(f"\U0001F4CD Longitude saved: `{st.session_state.longitude}`")

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
        headers = ["ID", "Tree Name", "Name", "Overall Height", "DBH", "Canopy", "IUCN", "Classification", "CSP", "Image A", "Image B", "Latitude", "Longitude"]
        ws.append(headers)
        for i, entry in enumerate(st.session_state.entries, start=2):
            ws.append([entry.get(k, "") for k in headers])
            ws.cell(row=i, column=10).value = f'=HYPERLINK("{entry.get("Image A", "")}", "View A")'
            ws.cell(row=i, column=11).value = f'=HYPERLINK("{entry.get("Image B", "")}", "View B")'
        wb.save(path)
        with open(path, "rb") as f:
            st.download_button("Download Excel File", f, "tree_data.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
