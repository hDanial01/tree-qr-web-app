import streamlit as st
import streamlit.components.v1 as components
from PIL import Image
import pandas as pd
import os
import re
import json

import gspread
from oauth2client.service_account import ServiceAccountCredentials
from openpyxl import Workbook
from openpyxl.drawing.image import Image as XLImage

import cv2
import numpy as np
from PIL import Image

# Setup directories
IMAGE_DIR = "tree_images"
EXPORT_DIR = "exports"
os.makedirs(IMAGE_DIR, exist_ok=True)
os.makedirs(EXPORT_DIR, exist_ok=True)

# Google Sheets Setup
SHEET_NAME = "TreeQRDatabase"

# Load Google Sheets credentials from Streamlit secrets
creds_dict = json.loads(st.secrets["CREDS_JSON"])

def get_worksheet():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    return client.open(SHEET_NAME).sheet1

def load_entries_from_gsheet():
    sheet = get_worksheet()
    rows = sheet.get_all_values()[1:]  # Skip header
    entries = []
    for row in rows:
        if len(row) >= 8:
            entry = {
                "ID": row[0],
                "Type": row[1],
                "Height": row[2],
                "Canopy": row[3],
                "IUCN": row[4],
                "Classification": row[5],
                "CSP": row[6],
                "Image": row[7],
            }
            entries.append(entry)
    return entries

def save_to_gsheet(entry):
    sheet = get_worksheet()
    row = [
        entry["ID"], entry["Type"], entry["Height"], entry["Canopy"],
        entry["IUCN"], entry["Classification"], entry["CSP"], entry["Image"]
    ]
    sheet.append_row(row)

# Initialize session state
if "entries" not in st.session_state:
    st.session_state.entries = load_entries_from_gsheet()

if "qr_result" not in st.session_state:
    st.session_state.qr_result = ""

st.title("🌳 GAMUDA")

def decode_qr_with_opencv():
    st.subheader("🖼️ Upload QR Code Image")
    uploaded_file = st.file_uploader("Upload an image with a QR Code", type=["png", "jpg", "jpeg"], key="qr-upload")

    if uploaded_file:
        try:
            # Convert uploaded file to OpenCV image
            image = Image.open(uploaded_file).convert('RGB')
            st.image(image, caption="Uploaded QR Image", use_column_width=True)

            image_np = np.array(image)
            image_bgr = cv2.cvtColor(image_np, cv2.COLOR_RGB2BGR)

            detector = cv2.QRCodeDetector()
            data, bbox, _ = detector.detectAndDecode(image_bgr)

            if data:
                st.success(f"✅ QR Code Decoded: `{data}`")
                st.session_state.qr_result = data  # Save result to session state
            else:
                st.error("❌ No QR code detected in this image.")

        except Exception as e:
            st.error(f"Error processing image: {e}")

# QR toggle button
if "show_camera" not in st.session_state:
    st.session_state.show_camera = False

if st.button("📷 Open Camera to Scan QR"):
    st.session_state.show_camera = True

if st.session_state.get("show_camera", False):
    st.markdown("### Camera Scanner")
    components.html(
        f"""
        <script src="https://unpkg.com/html5-qrcode@2.3.8/minified/html5-qrcode.min.js"></script>
        <div id="reader" style="width: 400px;"></div>
        <script>
        function onScanSuccess(decodedText, decodedResult) {{
            window.parent.postMessage({{ type: 'qr_scanned', data: decodedText }}, '*');
        }}
        const config = {{
            fps: 10,
            qrbox: 400,
            aspectRatio: 1.7777778,
            videoConstraints: {{
                facingMode: "environment"
            }}
        }};
        new Html5QrcodeScanner("reader", config).render(onScanSuccess);
        </script>
        """,
        height=380,
    )

# JS listener to update the QR result
components.html(
    """
    <script>
    window.addEventListener("message", (event) => {
        if (event.data.type === "qr_scanned") {
            const input = window.parent.document.querySelector('input[id$="qr-result"]');
            if (input) {
                input.value = event.data.data;
                input.dispatchEvent(new Event("input", { bubbles: true }));
            }
        }
    });
    </script>
    """,
    height=0
)

# Call image upload QR scanner
decode_qr_with_opencv()

# Then show input box populated by scan result
qr_input = st.text_input("Scanned QR Result", value=st.session_state.qr_result, key="qr-result")

# Data Entry Form
st.header("2. Fill Tree Details")
with st.form("tree_form"):
    id_val = st.text_input("Tree ID", value=qr_input, key="tree-id")
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
                "ID": id_val,
                "Type": tree_type,
                "Height": height,
                "Canopy": canopy,
                "IUCN": iucn_status,
                "Classification": classification,
                "CSP": csp,
                "Image": new_filename
            }

            st.session_state.entries.append(entry)
            save_to_gsheet(entry)
            st.success(f"✅ Entry added and saved to Google Sheet! Image: {new_filename}")
            st.session_state.qr_result = ""

# Display Table
if st.session_state.entries:
    st.header("3. Current Entries")
    df = pd.DataFrame(st.session_state.entries)
    st.dataframe(df)

# Export
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
