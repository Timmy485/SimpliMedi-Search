import json
import os
import logging
import requests
from dotenv import load_dotenv
load_dotenv()

CUSTOMER_ID = os.environ.get('CUSTOMER_ID')
CORPUS_ID = os.environ.get('CORPUS_ID')
API_KEY = os.environ.get('API_KEY')
AUTH_URL = os.environ.get('AUTH_URL')
APP_CLIENT_ID = os.environ.get('APP_CLIENT_ID')
APP_CLIENT_SECRET = os.environ.get('APP_CLIENT_SECRET')
IDX_ADDRESS = os.environ.get('IDX_ADDRESS')


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
    "Romanian": "ron"
}

models = {
    "GPT-3.5-Turbo" : "vectara-summary-ext-v1.2.0",
    "GPT-4-Turbo" : "vectara-summary-ext-v1.3.0"
}
def get_jwt_token():
    """Get JWT token from authentication service."""
    auth_url = AUTH_URL
    client_id = APP_CLIENT_ID
    client_secret = APP_CLIENT_SECRET

    data = {
        "grant_type": "client_credentials",
        "client_id": client_id,
        "client_secret": client_secret
    }

    headers = {
        "Content-Type": "application/x-www-form-urlencoded"
    }

    response = requests.post(auth_url, headers=headers, data=data)

    if response.status_code == 200:
        response_data = response.json()
        return response_data.get("access_token")
    else:
        print("Error:", response.text)
        return None
    

def upload_file(customer_id: int, corpus_id: int, idx_address: str, jwt_token: str, file_path: str):
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

    post_headers = {
        "Authorization": f"Bearer {jwt_token}"
    }
    with open(file_path, 'rb') as file:
        response = requests.post(
            f"https://{idx_address}/v1/upload?c={customer_id}&o={corpus_id}",
            files={"file": (file.name, file, "application/octet-stream")},
            data={"doc_metadata": f'{{"filename": "{filename}"}}'},
            verify=True,
            headers=post_headers)

    if response.status_code != 200:
        logging.error("REST upload failed with code %d, reason %s, text %s",
                       response.status_code,
                       response.reason,
                       response.text)
        return response, False

    message = response.json()["response"]
    # An empty status indicates success.
    if message["status"] and message["status"]["code"] not in ("OK", "ALREADY_EXISTS"):
        logging.error("REST upload failed with status: %s", message["status"])
        return message["status"], False

    return message, True


def upload_files_in_directory(customer_id: int, corpus_id: int, idx_address: str, directory_path: str):
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
            response, success = upload_file(customer_id, corpus_id, idx_address, jwt_token, file_path)
            file_uploads.append((response, success))
    return file_uploads




def _get_query_json(
    customer_id: int,
    corpus_id: int,
    query_value: str,
    summarizer_prompt_name,
    response_lang,
    top_k=10,
    max_summarized_results=5,
    lambda_val=0.025
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
                            "lexicalInterpolationConfig": {"lambda":lambda_val},
                        }
                            ],
                "summary": [
                    {
                        "summarizerPromptName": summarizer_prompt_name, #vectara-summary-ext-v1.2.0 (gpt-3.5-turbo) vectara-summary-ext-v1.3.0 (gpt-4.0)
                        "responseLang": response_lang, #auto to auto-detect
                        "maxSummarizedResults": max_summarized_results,
                        "factual_consistency_score": True,
                    }
                ],
            },
        ],
    }
    return json.dumps(query)


def query_corpus(
    customer_id: int, corpus_id: int, query_address: str, jwt_token: str, query: str
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
        data=_get_query_json(customer_id, corpus_id, query, models["GPT-4-Turbo"], language_initials["English"]),
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
    if (message["status"] and
        any(status["code"] != "OK" for status in message["status"])):
        logging.error("Query failed with status: %s", message["status"])
        return message["status"], False


    responses = message["responseSet"][0]["response"]
    documents = message["responseSet"][0]["document"]
    summary = message["responseSet"][0]["summary"][0]["text"]

    res = [[r['text'], r['score']] for r in responses]
    return res, summary
    

def save_to_dir(uploaded_file):
  if uploaded_file is not None:
      temp_dir = "corpus"
      os.makedirs(temp_dir, exist_ok=True)
      file_path = os.path.join(temp_dir, uploaded_file.name)

      with open(file_path, "wb") as f:
          f.write(uploaded_file.getbuffer())

      return file_path