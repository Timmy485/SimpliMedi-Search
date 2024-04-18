import json
import os
import logging
import requests
import streamlit as st
from helpers import save_to_dir, upload_file, get_jwt_token, upload_files_in_directory
from dotenv import load_dotenv

load_dotenv()

CUSTOMER_ID = os.environ.get("CUSTOMER_ID")
CORPUS_ID = 6
API_KEY = os.environ.get("API_KEY")
AUTH_URL = os.environ.get("AUTH_URL")
APP_CLIENT_ID = os.environ.get("APP_CLIENT_ID")
APP_CLIENT_SECRET = os.environ.get("APP_CLIENT_SECRET")
IDX_ADDRESS = os.environ.get("IDX_ADDRESS")
load_dotenv()

# Set up the Streamlit interface
st.set_page_config(
    page_title="SimpliMedi-Search",
    # layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    "<h1 style='text-align: center;'>SimpliMedi-Search</h1>", unsafe_allow_html=True
)


# Sidebar Navigation with header background color
st.sidebar.markdown(
    "<h3 style= padding: 10px;'>Navigation</h3>", unsafe_allow_html=True
)


# Use a dropdown menu for feature selection
selected_feature = st.sidebar.selectbox(
    "Select a Feature",
    (
        "Patient Records Chat",
        "Upload new document",
    ),
)


if selected_feature == "Patient Records Chat":
    prompt = st.chat_input("Enter Prompt")


elif selected_feature == "Upload new document":
    # Create a Streamlit file uploader widget
    uploaded_file = st.file_uploader(
        "Upload a PDF, DOCX, or TXT file", type=["pdf", "docx", "txt"]
    )

    
    if uploaded_file is not None:
        file_path = save_to_dir(uploaded_file)
        # Get the absolute path of the temp directory
        # st.write(file_path)

        # Upload the file to vectara server
        upload_msg = upload_files_in_directory(
            customer_id=CUSTOMER_ID,
            corpus_id=CORPUS_ID,
            idx_address="api.vectara.io",
            directory_path="corpus",
        )

        if (upload_msg[0][1]):
            st.success("File Uploaded Successfully")
        else:
            st.warning("Something went wrong, try again")