import streamlit as st
import os
import re
import gspread
from streamlit_js_eval import get_geolocation
from oauth2client.service_account import ServiceAccountCredentials
from openpyxl import Workbook
import pandas as pd
from pydrive.auth import GoogleAuth
from pydrive.drive import GoogleDrive

# Setup
EXPORT_DIR = "exports"
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
        if len(row) >= 7:
            entries.append({
                "Tree Name": row[0], "Name": row[1],
                "Overall Height": row[2], "DBH": row[3], "Canopy": row[4],
                "Latitude": row[5], "Longitude": row[6]
            })
    return entries

def save_to_gsheet(entry):
    sheet = get_worksheet()
    sheet.append_row([
        entry["Tree Name"], entry["Name"],
        entry["Overall Height"], entry["DBH"], entry["Canopy"],
        entry.get("Latitude", ""), entry.get("Longitude", "")
    ])

def upload_image_to_drive(image_file, filename):
    with open(filename, "wb") as f:
        f.write(image_file.getbuffer())
    file_drive = drive.CreateFile({"title": filename, "parents": [{"id": GOOGLE_DRIVE_FOLDER_ID}]})
    file_drive.SetContentFile(filename)
    file_drive.Upload()
    file_drive.InsertPermission({'type': 'anyone', 'value': 'anyone', 'role': 'reader'})
    os.remove(filename)
    return f"https://drive.google.com/uc?id={file_drive['id']}"

# Session state setup
for key in ["qr_image", "image_a", "image_b", "latitude", "longitude", "location_requested", "capture_stage"]:
    if key not in st.session_state:
        st.session_state[key] = None if key != "capture_stage" else "qr"

st.title("🌳 Tree Registration Flow")

# Step-by-step flow
if st.session_state.capture_stage == "qr":
    st.header("Step 1: Capture QR Code")
    st.info("📱 Tip: Tap the camera icon to switch to the rear-facing camera for better quality.")
    qr = st.camera_input("📸 Capture QR Image")
    if qr:
        st.session_state.qr_image = qr
        st.session_state.capture_stage = "image_a"
        st.success("✅ QR image captured. Proceed to Tree Image A.")

elif st.session_state.capture_stage == "image_a":
    st.header("Step 2: Capture Tree Image A (Overall)")
    st.info("📱 Tip: Tap the camera icon to switch to the rear-facing camera for better quality.")
    image_a = st.camera_input("🌳 Capture Tree Image A")
    if image_a:
        st.session_state.image_a = image_a
        st.session_state.capture_stage = "image_b"
        st.success("✅ Tree Image A captured. Proceed to Tree Image B.")

elif st.session_state.capture_stage == "image_b":
    st.header("Step 3: Capture Tree Image B (Canopy)")
    st.info("📱 Tip: Tap the camera icon to switch to the rear-facing camera for better quality.")
    image_b = st.camera_input("🍃 Capture Tree Image B")
    if image_b:
        st.session_state.image_b = image_b
        st.session_state.capture_stage = "form"
        st.success("✅ Tree Image B captured. Proceed to fill the form.")

elif st.session_state.capture_stage == "form":
    st.header("Step 4: Fill Tree Details")

    st.subheader("📍 GPS Capture")
    if st.button("📍 Get Location"):
        st.session_state.location_requested = True

    if st.session_state.location_requested:
        location = get_geolocation()
        if location:
            st.session_state.latitude = location["coords"]["latitude"]
            st.session_state.longitude = location["coords"]["longitude"]
            st.success("📡 Location captured!")

    if st.session_state.latitude and st.session_state.longitude:
        st.write(f"Latitude: `{st.session_state.latitude}`")
        st.write(f"Longitude: `{st.session_state.longitude}`")
    else:
        st.info("Click 'Get Location' to capture GPS coordinates.")

    st.subheader("📝 Tree Details")

    entries = load_entries_from_gsheet()
    existing_names = [e["Tree Name"] for e in entries]

    with st.form("tree_form"):
        suffix = st.text_input("Tree Name (Suffix only)")
        tree_custom_name = f"GGN/25/{suffix}"
        st.markdown(f"🔖 Full Tree Name: `{tree_custom_name}`")

        if tree_custom_name in existing_names:
            st.warning("⚠️ This Tree Name already exists.")

        tree_name = st.selectbox("Tree Species", [
            "Alstonia angustiloba", "Aquilaria malaccensis", "Azadirachta indica",
            "Baringtonia acutangula", "Buchanania arborescens", "Callophyllum inophyllum",
            "Cerbera odollam rubra", "Cinnamomum iners", "Coccoloba uvifera",
            "Cratoxylum chochinchinensis", "Dillenia indica", "Diospyros blancoi",
            "Diptercarpus baudi", "Diptercarpus gracilis", "Dyera costulata",
            "Eleocarpus grandiflorus", "Ficus lyrate", "Filicium decipiens",
            "Garcinia hombroniana", "Gardenia carinata", "Heteropanax fragrans",
            "Hopea ferrea", "Hopea odorata", "Leptospermum brachyandrum",
            "Licuala grandis", "Maniltoa browneoides", "Mesua ferrea",
            "Michelia champaka", "Milingtonia hortensis", "Millettia pinnata",
            "Mimusops elengi", "Pentaspadon monteylii", "Podocarpus macrophyllus",
            "Podocarpus polystachyus", "Pometia pinnata", "Saraca thaipingensis",
            "Shorea roxburghii", "Spathodea campanulata", "Sterculia foetida",
            "Sterculia paviflora", "Sygzium polyanthum", "Syzgium grande",
            "Syzgium spicata", "Tabebuia argentea", "Tabebuia rosea",
            "Terminalia calamansanai", "Terminalia catappa", "Tristania obovata",
            "Tristaniopsis whiteana", "Unknown sp", "Mixed sp"
        ])

        height = st.selectbox("Overall Height (m)", ["1", "2", "3", "4", "5", "6", "7"])
        dbh = st.selectbox("DBH (cm)", ["1", "2", "3", "4", "5", "6", "7", "8", "9"])
        canopy = st.text_input("Canopy Diameter (cm)")

        submitted = st.form_submit_button("✅ Submit Tree Entry")

        if submitted:
            if tree_custom_name in existing_names:
                st.error("❌ Tree Name already exists.")
            elif not all([suffix, tree_name, height, dbh, canopy]):
                st.error("❌ Please complete all fields.")
            elif not st.session_state.latitude or not st.session_state.longitude:
                st.error("❌ GPS location missing.")
            else:
                safe_suffix = re.sub(r'\W+', '_', suffix)

                qr_url = upload_image_to_drive(st.session_state.qr_image, f"GGN_25_{safe_suffix}_QR.jpg")
                a_url = upload_image_to_drive(st.session_state.image_a, f"GGN_25_{safe_suffix}_A.jpg")
                b_url = upload_image_to_drive(st.session_state.image_b, f"GGN_25_{safe_suffix}_B.jpg")

                entry = {
                    "Tree Name": tree_custom_name,
                    "Name": tree_name,
                    "Overall Height": height,
                    "DBH": dbh,
                    "Canopy": canopy,
                    "Latitude": st.session_state.latitude,
                    "Longitude": st.session_state.longitude
                }

                save_to_gsheet(entry)
                st.success("🎉 Tree entry saved successfully!")
                st.info("📸 Ready to capture the next tree — starting with the QR code.")
                st.markdown("<script>window.scrollTo(0, 0);</script>", unsafe_allow_html=True)

                # Reset state and go back to QR
                for key in ["qr_image", "image_a", "image_b", "latitude", "longitude", "location_requested"]:
                    st.session_state[key] = None
                st.session_state.capture_stage = "qr"
                st.rerun()

# Show entries
st.header("📋 All Tree Entries")
df = pd.DataFrame(load_entries_from_gsheet())
st.dataframe(df)

# Export
st.header("⬇️ Export Data")
if not df.empty:
    csv_data = df.to_csv(index=False).encode("utf-8")
    st.download_button("Download CSV", csv_data, "tree_data.csv", "text/csv")

    if st.button("Download Excel File"):
        path = os.path.join(EXPORT_DIR, "tree_data.xlsx")
        wb = Workbook()
        ws = wb.active
        headers = ["Tree Name", "Name", "Overall Height", "DBH", "Canopy", "Latitude", "Longitude"]
        ws.append(headers)
        for entry in df.to_dict(orient="records"):
            ws.append([entry.get(k, "") for k in headers])
        wb.save(path)
        with open(path, "rb") as f:
            st.download_button("Download Excel File", f, "tree_data.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
