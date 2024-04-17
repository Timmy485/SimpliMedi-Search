import os
import requests
import http.client
import json
import logging
import mimetypes
import os
from typing import Tuple

import requests
from authlib.integrations.requests_client import OAuth2Session



def create_corpus(api_key , customer_id ,corpus_name,corpus_description):
    conn = http.client.HTTPSConnection("api.vectara.io")
    payload = json.dumps({
        "corpus": {
            "name": corpus_name,  # Replace with your actual corpus name
            "description": corpus_description,  # Optional
            "enabled": True,  # Optional
            "swapQenc": False,  # Optional
            "swapIenc": False,  # Optional
            "textless": False,  # Optional
            "encrypted": True,  # Optional
            "encoderId": 1,  # Optional, use integer
            "metadataMaxBytes": 0,  # Optional, use integer
            "customDimensions": [],  # Optional
            "filterAttributes": []  # Optional
        }
    })
    headers = {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        'customer-id': customer_id,  # Your customer ID
        'x-api-key': api_key  # Your API Key
    }
    conn.request("POST", "/v1/create-corpus", payload, headers)
    res = conn.getresponse()
    data = res.read()
    print(data.decode("utf-8"))
    data_dict = json.loads(data.decode("utf-8"))
    corpus_number = data_dict["corpusId"]
    success_message = data_dict["status"]["statusDetail"]

    return corpus_number, success_message


def save_to_dir(uploaded_file):
  if uploaded_file is not None:
      temp_dir = "temp"
      os.makedirs(temp_dir, exist_ok=True)
      file_path = os.path.join(temp_dir, uploaded_file.name)

      with open(file_path, "wb") as f:
          f.write(uploaded_file.getbuffer())

      return file_path
  

def upload_file(api_key, customer_id, corpus_number, file_path):
  url = f"https://api.vectara.io/v1/upload?c={customer_id}&o={corpus_number}"

  with open(file_path, "rb") as f:
      files = {
          "file": (os.path.basename(file_path), f),
      }

      headers = {"Accept": "application/json", "x-api-key": api_key}

      response = requests.post(url, headers=headers, files=files)

  return response.text



# class based methods
class Indexing:
    def __init__(self):
        self.auth_url = os.getenv('AUTH_URL')
        self.app_client_id = os.getenv('APP_CLIENT_ID')
        self.app_client_secret = os.getenv('APP_CLIENT_SECRET')
        self.jwt_token = self._get_jwt_token()

        def _get_jwt_token(self) -> str:
            """Connect to the server and get a JWT token."""
            token_endpoint = f"{self.auth_url}/oauth2/token"
            session = OAuth2Session(self.app_client_id, self.app_client_secret, scope="")
            token = session.fetch_token(token_endpoint, grant_type="client_credentials")
            return token["access_token"]
        
        def upload_file(self, customer_id: int, corpus_id: int, idx_address: str, uploaded_file, file_title: str) -> Tuple[requests.Response, bool]:
            """Uploads a file to the corpus."""
            # Determine the MIME type based on the file extension
            extension_to_mime_type = {
                '.txt': 'text/plain',
                '.pdf': 'application/pdf',
                '.doc': 'application/msword',
                '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                # ... add more mappings as needed
            }
            file_extension = os.path.splitext(uploaded_file.name)[-1]
            mime_type = extension_to_mime_type.get(file_extension, 'application/octet-stream')
            # mime_type = mimetypes.guess_type(uploaded_file.name)[0] or 'application/octet-stream'

            post_headers = {
                "Authorization": f"Bearer {self.jwt_token}"
            }
            
            try:
                file = uploaded_file.read()  
                files = {"file": (file_title, file, mime_type)}
                response = requests.post(
                    f"https://{idx_address}/v1/upload?c={customer_id}&o={corpus_id}",
                    files=files,
                    headers=post_headers
                )
            
                if response.status_code != 200:
                    logging.error("REST upload failed with code %d, reason %s, text %s",
                                response.status_code,
                                response.reason,
                                response.text)
                    return response, False
                return response, True
            except Exception as e:
                logging.error("An error occurred while uploading the file: %s", str(e))
                return None, False
            

class Searching:
    def __init__(self):
        self.customer_id = os.getenv('CUSTOMER_ID')
        self.api_key = os.getenv('API_KEY')


        def send_query(self, corpus_id, query_text, num_results, summarizer_prompt_name, response_lang, max_summarized_results):
            api_key_header = {
                "customer-id": self.customer_id,
                "x-api-key": self.api_key,
                "Content-Type": "application/json"
            }

            data_dict = {
                "query": [
                    {
                        "query": query_text,
                        "num_results": num_results,
                        "corpus_key": [{"customer_id": self.customer_id, "corpus_id": corpus_id}],
                        'summary': [
                            {
                                'summarizerPromptName': summarizer_prompt_name,
                                'responseLang': response_lang,
                                'maxSummarizedResults': max_summarized_results
                            }
                        ]
                    }
                ]
            }

            payload = json.dumps(data_dict)

            response = requests.post(
                "https://api.vectara.io/v1/query",
                data=payload,
                verify=True,
                headers=api_key_header
            )

            if response.status_code == 200:
                print("Request was successful!")
                data = response.json()
                texts = [item['text'] for item in data['responseSet'][0]['response'] if 'text' in item]
                return texts
            else:
                print("Request failed with status code:", response.status_code)
                print("Response:", response.text)
                return None