import json
import os
import logging
import requests
import streamlit as st
from helpers import save_to_dir, get_jwt_token, upload_files_in_directory, query_corpus
from dotenv import load_dotenv

load_dotenv()

CORPUS_ID = 6
CUSTOMER_ID = st.secrets.get("CUSTOMER_ID", os.environ.get("CUSTOMER_ID"))
API_KEY = st.secrets.get("API_KEY", os.environ.get("API_KEY"))
AUTH_URL = st.secrets.get("AUTH_URL", os.environ.get("AUTH_URL"))
APP_CLIENT_ID = st.secrets.get("APP_CLIENT_ID", os.environ.get("APP_CLIENT_ID"))
APP_CLIENT_SECRET = st.secrets.get("APP_CLIENT_SECRET", os.environ.get("APP_CLIENT_SECRET"))
IDX_ADDRESS = st.secrets.get("IDX_ADDRESS", os.environ.get("IDX_ADDRESS"))

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
    # Dictionary mapping language names to their lowercase initials
    language_initials = {
        "English": "eng",
        "German": "deu",
        "French": "fra",
        "Chinese": "zho",
        "Korean": "kor",
        "Arabic": "ara",
        "Russian": "rus",
        "Thai": "tha",
        "Dutch": "nld",
        "Italian": "ita",
        "Portuguese": "por",
        "Spanish": "spa",
        "Japanese": "jpn",
        "Polish": "pol",
        "Turkish": "tur",
        "Vietnamese": "vie",
        "Indonesian": "ind",
        "Czech": "ces",
        "Ukrainian": "ukr",
        "Greek": "ell",
        "Hebrew": "heb",
        "Farsi/Persian": "fas",
        "Hindi": "hin",
        "Urdu": "urd",
        "Swedish": "swe",
        "Bengali": "ben",
        "Malay": "msa",
        "Romanian": "ron",
    }

    models = {
        "GPT-3.5-Turbo": "vectara-summary-ext-v1.2.0",
        "GPT-4-Turbo": "vectara-summary-ext-v1.3.0",
    }

    # Create a column layout for the dropdowns
    col1, col2 = st.columns(2)

    # Dropdown for selecting language
    with col1:
        selected_language = st.selectbox(
            "Select Language:", options=list(language_initials.keys()), index=0
        )

    # Dropdown for selecting model
    with col2:
        selected_model = st.selectbox(
            "Select Model:", options=list(models.keys()), index=0
        )

    # Access selected values
    if selected_language and selected_model:
        selected_language_initial = language_initials[selected_language]
        selected_model_value = models[selected_model]

        st.write(f"Utilizing Model: {selected_model_value}")

        # Initialize chat history
        if "messages" not in st.session_state:
            st.session_state.messages = []

        # Display chat messages from history on app rerun
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

        # React to user input
        if prompt := st.chat_input("Input your query"):
            # Display user message in chat message container
            st.chat_message("user").markdown(prompt)
            # Add user message to chat history
            st.session_state.messages.append({"role": "user", "content": prompt})

            results, summary, score, documents = query_corpus(
                CUSTOMER_ID, 
                CORPUS_ID, 
                IDX_ADDRESS, 
                get_jwt_token(), 
                prompt,
                model=selected_model_value,
                language=selected_language_initial,
            )
            response = f"SimpliMedi-Search: {summary}\n\nFactual Consistency Score: {score}"
            # Display assistant response in chat message container
            with st.chat_message("assistant"):
                st.markdown(response)
            # Add assistant response to chat history
            st.session_state.messages.append({"role": "assistant", "content": response})


elif selected_feature == "Upload new document":
    st.write("Upload Patient medical record here")
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

        if upload_msg[0][1]:
            st.success("File Uploaded Successfully")
        else:
            st.warning("Something went wrong, try again")
