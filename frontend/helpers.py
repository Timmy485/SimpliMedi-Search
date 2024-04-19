import json
import os
import logging
import requests
import streamlit as st
import PyPDF2
from docx import Document
from together import Together
from streamlit_pdf_viewer import pdf_viewer
from openai import OpenAI
from dotenv import load_dotenv


load_dotenv()

# Try to get secrets first
CORPUS_ID = 6

CUSTOMER_ID = os.environ.get("CUSTOMER_ID") or st.secrets["CUSTOMER_ID"]
API_KEY = os.environ.get("API_KEY") or st.secrets["API_KEY"]
AUTH_URL = os.environ.get("AUTH_URL") or st.secrets["AUTH_URL"]
APP_CLIENT_ID = os.environ.get("APP_CLIENT_ID") or st.secrets["APP_CLIENT_ID"]
APP_CLIENT_SECRET = os.environ.get("APP_CLIENT_SECRET") or st.secrets["APP_CLIENT_SECRET"]
IDX_ADDRESS = os.environ.get("IDX_ADDRESS") or st.secrets["IDX_ADDRESS"]
TOGETHER_API_KEY = os.environ.get("TOGETHER_API_KEY") or st.secrets["TOGETHER_API_KEY"]
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY") or st.secrets["OPENAI_API_KEY"]

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


def get_jwt_token():
    """Get JWT token from authentication service."""
    auth_url = AUTH_URL
    client_id = APP_CLIENT_ID
    client_secret = APP_CLIENT_SECRET

    data = {
        "grant_type": "client_credentials",
        "client_id": client_id,
        "client_secret": client_secret,
    }

    headers = {"Content-Type": "application/x-www-form-urlencoded"}

    response = requests.post(auth_url, headers=headers, data=data)

    if response.status_code == 200:
        response_data = response.json()
        return response_data.get("access_token")
    else:
        print("Error:", response.text)
        return None


def upload_file(
    customer_id: int, corpus_id: int, idx_address: str, jwt_token: str, file_path: str
):
    """Uploads a file to the corpus.

    Args:
        customer_id: Unique customer ID in vectara platform.
        corpus_id: ID of the corpus to which data needs to be indexed.
        idx_address: Address of the indexing server. e.g., api.vectara.io
        jwt_token: A valid Auth token.
        file_path: Path to the file to be uploaded.

    Returns:
        (response, True) in case of success and returns (error, False) in case of failure.
    """

    # Extract filename from the file path
    filename = os.path.basename(file_path)

    post_headers = {"Authorization": f"Bearer {jwt_token}"}
    with open(file_path, "rb") as file:
        response = requests.post(
            f"https://{idx_address}/v1/upload?c={customer_id}&o={corpus_id}",
            files={"file": (file.name, file, "application/octet-stream")},
            data={"doc_metadata": f'{{"filename": "{filename}"}}'},
            verify=True,
            headers=post_headers,
        )

    if response.status_code != 200:
        logging.error(
            "REST upload failed with code %d, reason %s, text %s",
            response.status_code,
            response.reason,
            response.text,
        )
        return response, False

    message = response.json()["response"]
    # An empty status indicates success.
    if message["status"] and message["status"]["code"] not in ("OK", "ALREADY_EXISTS"):
        logging.error("REST upload failed with status: %s", message["status"])
        return message["status"], False

    return message, True


def upload_files_in_directory(
    customer_id: int, corpus_id: int, idx_address: str, directory_path: str
):
    """Uploads all files in a directory to the corpus.

    Args:
        customer_id: Unique customer ID in Vectara platform.
        corpus_id: ID of the corpus to which data needs to be indexed.
        idx_address: Address of the indexing server. e.g., api.vectara.io
        directory_path: Path to the directory containing files to be uploaded.

    Returns:
        A list of tuples containing (response, success) for each file upload.
    """
    jwt_token = get_jwt_token()
    if not jwt_token:
        return []

    file_uploads = []
    for file_name in os.listdir(directory_path):
        file_path = os.path.join(directory_path, file_name)
        if os.path.isfile(file_path):
            response, success = upload_file(
                customer_id, corpus_id, idx_address, jwt_token, file_path
            )
            file_uploads.append((response, success))
    return file_uploads


def _get_query_json(
    customer_id: int,
    corpus_id: int,
    query_value: str,
    summarizer_prompt_name,
    response_lang,
    top_k=5,
    max_summarized_results=10,
    lambda_val=0.025,
):
    """Returns a query JSON."""
    query = {
        "query": [
            {
                "query": query_value,
                "num_results": top_k,
                "corpus_key": [
                    {
                        "customer_id": customer_id,
                        "corpus_id": corpus_id,
                        "lexicalInterpolationConfig": {"lambda": lambda_val},
                    }
                ],
                "summary": [
                    {
                        "summarizerPromptName": summarizer_prompt_name,  # vectara-summary-ext-v1.2.0 (gpt-3.5-turbo) vectara-summary-ext-v1.3.0 (gpt-4.0)
                        "responseLang": response_lang,  # auto to auto-detect
                        "maxSummarizedResults": max_summarized_results,
                        "factual_consistency_score": True,
                    }
                ],
            },
        ],
    }
    return json.dumps(query)


def query_corpus(
    customer_id: int,
    corpus_id: int,
    query_address: str,
    jwt_token: str,
    query: str,
    model="vectara-summary-ext-v1.2.0",
    language="eng",
):
    """Queries the data.

    Args:
        customer_id: Unique customer ID in vectara platform.
        corpus_id: ID of the corpus to which data needs to be indexed.
        query_address: Address of the querying server. e.g., api.vectara.io
        jwt_token: A valid Auth token.

    Returns:
        (response, True) in case of success and returns (error, False) in case of failure.

    """
    post_headers = {
        "customer-id": f"{customer_id}",
        "Authorization": f"Bearer {jwt_token}",
    }

    response = requests.post(
        f"https://{query_address}/v1/query",
        data=_get_query_json(
            customer_id,
            corpus_id,
            query,
            summarizer_prompt_name=model,
            response_lang=language,
        ),
        verify=True,
        headers=post_headers,
    )

    if response.status_code != 200:
        logging.error(
            "Query failed with code %d, reason %s, text %s",
            response.status_code,
            response.reason,
            response.text,
        )
        return response, False

    message = response.json()
    if message["status"] and any(
        status["code"] != "OK" for status in message["status"]
    ):
        logging.error("Query failed with status: %s", message["status"])
        return message["status"], False

    responses = message["responseSet"][0]["response"]
    documents = message["responseSet"][0]["document"]
    summary = message["responseSet"][0]["summary"][0]["text"]
    factual_consistency_score = message["responseSet"][0]["summary"][0][
        "factualConsistency"
    ]["score"]

    res = [[r["text"], r["score"]] for r in responses]
    return res, summary, factual_consistency_score, documents


def save_to_dir(uploaded_file):
    if uploaded_file is not None:
        temp_dir = "corpus"
        os.makedirs(temp_dir, exist_ok=True)
        file_path = os.path.join(temp_dir, uploaded_file.name)

        with open(file_path, "wb") as f:
            f.write(uploaded_file.getbuffer())

        return file_path


def get_report_summary(uploaded_file):

    file_extension = uploaded_file.name.split(".")[-1]

    if file_extension == "pdf":
        # Extract text from PDF
        pdf_reader = PyPDF2.PdfReader(uploaded_file)
        text = "".join(
            pdf_reader.pages[page_num].extract_text()
            for page_num in range(len(pdf_reader.pages))
        )

        if st.button("View Document Preview"):
            binary_data = uploaded_file.getvalue()  
            pdf_viewer(input=binary_data, width=700)

        # st.markdown("## Medical Report Summary")
        # st.markdown("### Data Preview")
    elif file_extension == "docx":
        # Extract text from DOCX
        docx_document = Document(uploaded_file)
        text = "".join(paragraph.text + "\n" for paragraph in docx_document.paragraphs)
    elif file_extension == "txt":
        # Read text directly from TXT file
        text = uploaded_file.getvalue().decode("utf-8")

    query = f"""
    Assume you are a patient with limited medical knowledge who has received a medical report filled with complex terminology. You are seeking a clearer understanding of this report in two parts:

    1. **Report Explanation**: First, break down the medical report, keeping the original terms but explaining their significance. Detail what each finding or measurement within the report indicates about your health. Include any abnormalities or conditions detected, explaining what each part of the scan or test represents. 

    2. **Simplified Explanation**: Next, provide a simplified explanation of the report's findings as if explaining to a complete layperson or as though you were explaining it to a two-year-old. This should include:
    - A plain English summary of any conditions or abnormalities found.
    - Insights into how these findings relate to your overall health.
    - Suggestions for potential treatment options or further diagnostic tests, based ONLY on the report's findings.
    - Clarification of any complex terms or concepts in very simple language, avoiding medical jargon.

    Please ensure that while simplifying, you do not omit essential medical terms; rather, introduce them with their explanations to ensure the patient fully understands their report.

    Medical report: {text}
    """
    if st.button("Generate document summary"):
        # # Together.AI call
        # client = Together(api_key=TOGETHER_API_KEY)
        # response = client.chat.completions.create(
        #     model="meta-llama/Llama-3-70b-chat-hf",
        #     messages=[
        #         {
        #             "role": "system",
        #             "content": "You are a knowledgeable agent specializing in the medical domain, proficient in interpreting and analyzing medical reports with precision and expertise.",
        #         },
        #         {
        #             "role": "user",
        #             "content": query
        #         }
        #     ],
        # )

        #OpenAI call
        client = OpenAI(api_key=OPENAI_API_KEY,)
        response = client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": "You are a knowledgeable agent specializing in the medical domain, proficient in interpreting and analyzing medical reports with precision and expertise.",
                },
                {
                    "role": "user", 
                    "content": query
                },
            ],
            model="gpt-3.5-turbo",
        )

        st.write(response.choices[0].message.content)
