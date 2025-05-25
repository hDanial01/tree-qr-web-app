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

# Global Tree Species List
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
    return [
        dict(zip(["ID", "Tree Name", "Name", "Overall Height", "DBH", "Canopy", "Image A", "Image B", "Latitude", "Longitude"], row))
        for row in rows if len(row) >= 10
    ]

def save_to_gsheet(entry):
    sheet = get_worksheet()
    sheet.append_row([entry[k] for k in ["ID", "Tree Name", "Name", "Overall Height", "DBH", "Canopy", "Image A", "Image B", "Latitude", "Longitude"]])

def delete_file_from_drive(file_url):
    try:
        match = re.search(r'id=([a-zA-Z0-9_-]+)', file_url)
        if match:
            drive.CreateFile({'id': match.group(1)}).Delete()
    except Exception as e:
        st.warning(f"Could not delete image from Drive: {e}")

def upload_image_to_drive(image_file, filename):
    with open(filename, "wb") as f:
        f.write(image_file.read())
    for f in drive.ListFile({'q': f"'{GOOGLE_DRIVE_FOLDER_ID}' in parents and title = '{filename}' and trashed = false"}).GetList():
        f.Delete()
    file_drive = drive.CreateFile({"title": filename, "parents": [{"id": GOOGLE_DRIVE_FOLDER_ID}]})
    file_drive.SetContentFile(filename)
    file_drive.Upload()
    file_drive.InsertPermission({'type': 'anyone', 'value': 'anyone', 'role': 'reader'})
    os.remove(filename)
    return f"https://drive.google.com/uc?id={file_drive['id']}"

# Session state setup
if "entries" not in st.session_state:
    st.session_state.entries = load_entries_from_gsheet()
    for e in st.session_state.entries:
        for k in ["ID", "Tree Name", "Name", "Overall Height", "DBH", "Canopy", "Image A", "Image B", "Latitude", "Longitude"]:
            e.setdefault(k, "")

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
    data, bbox, _ = cv2.QRCodeDetector().detectAndDecode(img)
    if data:
        ids = [e["ID"] for e in load_entries_from_gsheet()]
        if data in ids:
            st.error(f"\u274C QR Code '{data}' already exists.")
        else:
            st.success(f"\u2705 QR Code Found: {data}")
            st.session_state.qr_result = data
    else:
        st.error("\u274C No QR code detected.")

# GPS Capture
st.header("2. Fill Tree Details")
st.header("\U0001F4CD Capture Your GPS Location")
if st.button("Get Location"):
    location = get_geolocation()
    if location:
        st.session_state.latitude = location["coords"]["latitude"]
        st.session_state.longitude = location["coords"]["longitude"]
        st.success("\U0001F4E1 Location captured!")
if st.session_state.latitude:
    st.write(f"Latitude: `{st.session_state.latitude}`")
    st.write(f"Longitude: `{st.session_state.longitude}`")

# Add Entry Form
if st.session_state.qr_result:
    names = [e["Tree Name"] for e in st.session_state.entries]
    with st.form("add_form"):
        id_val = st.text_input("Tree ID", value=st.session_state.qr_result)
        suffix = st.text_input("Tree Name (Suffix only)", value="1")
        full_name = f"GGN/25/{suffix}"
        st.markdown(f"**Full Tree Name:** `{full_name}`")
        if full_name in names:
            st.warning("Tree Name already exists.")
        tree = st.selectbox("Species Name", tree_names)
        height = st.text_input("Overall Height (m)")
        dbh = st.text_input("DBH (cm)")
        canopy = st.text_input("Canopy Diameter (cm)")
        img_a = st.file_uploader("Tree Image (Overall)", type=["jpg", "jpeg", "png"])
        img_b = st.file_uploader("Tree Image (Canopy)", type=["jpg", "jpeg", "png"])
        submit = st.form_submit_button("Add Entry")
        if submit and full_name not in names and all([id_val, tree, height, dbh, canopy, img_a, img_b]):
            safe = re.sub(r'[^a-zA-Z0-9_-]', '_', full_name)
            img_url_a = upload_image_to_drive(img_a, f"{safe}_A{os.path.splitext(img_a.name)[1]}")
            img_url_b = upload_image_to_drive(img_b, f"{safe}_B{os.path.splitext(img_b.name)[1]}")
            entry = dict(ID=id_val, Tree Name=full_name, Name=tree, Overall Height=height, DBH=dbh,
                         Canopy=canopy, Image A=img_url_a, Image B=img_url_b,
                         Latitude=st.session_state.latitude, Longitude=st.session_state.longitude)
            st.session_state.entries.append(entry)
            save_to_gsheet(entry)
            st.success("\u2705 Entry added!")

# Display & Manage
if st.session_state.entries:
    st.header("3. Manage Entries")
    df = pd.DataFrame(st.session_state.entries)
    st.dataframe(df)

    # Delete
    delete_map = {e["Tree Name"]: e["ID"] for e in st.session_state.entries}
    selected_tree = st.selectbox("Select a tree to delete", list(delete_map))
    if st.checkbox("Confirm delete") and st.button("Delete Entry"):
        sheet = get_worksheet()
        all_rows = sheet.get_all_values()
        for i, row in enumerate(all_rows[1:], 2):
            if row[0] == delete_map[selected_tree]:
                delete_file_from_drive(row[6])
                delete_file_from_drive(row[7])
                sheet.delete_rows(i)
                break
        st.session_state.entries = [e for e in st.session_state.entries if e["ID"] != delete_map[selected_tree]]
        st.success(f"Deleted entry: {selected_tree}")

    # Edit
    st.subheader("\U0001F4C2 Edit Entry")
    edit_map = {e["Tree Name"]: e for e in st.session_state.entries}
    edit_tree = st.selectbox("Select a tree to edit", list(edit_map))
    if st.button("✏️ Enable Edit Mode"):
        st.session_state.edit_mode = edit_tree

    if st.session_state.get("edit_mode") == edit_tree:
        e = edit_map[edit_tree]
        with st.form("edit_form"):
            new_id = st.text_input("Tree ID", value=e["ID"])
            new_name = st.text_input("Tree Name", value=e["Tree Name"])
            new_species = st.selectbox("Species Name", tree_names, index=tree_names.index(e["Name"]))
            new_height = st.text_input("Overall Height", value=e["Overall Height"])
            new_dbh = st.text_input("DBH", value=e["DBH"])
            new_canopy = st.text_input("Canopy", value=e["Canopy"])
            new_a = st.file_uploader("New Image A (optional)", type=["jpg", "jpeg", "png"])
            new_b = st.file_uploader("New Image B (optional)", type=["jpg", "jpeg", "png"])
            edit_submit = st.form_submit_button("Save Changes")
            if edit_submit:
                sheet = get_worksheet()
                all_rows = sheet.get_all_values()
                for i, row in enumerate(all_rows[1:], 2):
                    if row[0] == e["ID"]:
                        sheet.delete_rows(i)
                        break
                safe = re.sub(r'[^a-zA-Z0-9_-]', '_', new_name)
                url_a = e["Image A"]
                url_b = e["Image B"]
                if new_a:
                    delete_file_from_drive(url_a)
                    url_a = upload_image_to_drive(new_a, f"{safe}_A{os.path.splitext(new_a.name)[1]}")
                if new_b:
                    delete_file_from_drive(url_b)
                    url_b = upload_image_to_drive(new_b, f"{safe}_B{os.path.splitext(new_b.name)[1]}")
                updated = dict(ID=new_id, Tree Name=new_name, Name=new_species,
                               Overall Height=new_height, DBH=new_dbh, Canopy=new_canopy,
                               Image A=url_a, Image B=url_b, Latitude=e["Latitude"], Longitude=e["Longitude"])
                save_to_gsheet(updated)
                st.session_state.entries = load_entries_from_gsheet()
                st.success("Entry updated.")

# Export
if st.session_state.entries:
    st.header("4. Export Data")
    csv = pd.DataFrame(st.session_state.entries).to_csv(index=False).encode("utf-8")
    st.download_button("Download CSV", csv, "tree_data.csv", "text/csv")
    if st.button("Download Excel with Images"):
        path = os.path.join(EXPORT_DIR, "tree_data.xlsx")
        wb = Workbook()
        ws = wb.active
        cols = ["ID", "Tree Name", "Name", "Overall Height", "DBH", "Canopy", "Image A", "Image B", "Latitude", "Longitude"]
        ws.append(cols)
        for i, e in enumerate(st.session_state.entries, 2):
            ws.append([e[k] for k in cols])
            ws.cell(i, 7).value = f'=HYPERLINK("{e["Image A"]}", "View A")'
            ws.cell(i, 8).value = f'=HYPERLINK("{e["Image B"]}", "View B")'
        wb.save(path)
        with open(path, "rb") as f:
            st.download_button("Download Excel File", f, "tree_data.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
