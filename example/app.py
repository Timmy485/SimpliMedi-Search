import os
import time
import json
import logging
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import streamlit as st
from streamlit_chat import message
from ingest import create_corpus, upload_file, save_to_dir
from dotenv import load_dotenv
load_dotenv()


# Configure logging for better tracking
logging.basicConfig(format="\n%(asctime)s\n%(message)s", level=logging.INFO, force=True)

def get_latest_conversation_id(api_key, customer_id):
    """Retrieves the latest conversation ID from Vectara."""
    response = requests.post(
        "https://api.vectara.io/v1/list-conversations",
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "customer-id": customer_id,
            "x-api-key": api_key,
        },
        data=json.dumps({"numResults": 0, "pageKey": ""}),
    )
    response_data = response.json()
    return (
        response_data["conversation"][-1]["conversationId"]
        if response_data and "conversation" in response_data
        else None
    )


def research_and_update_corpus(
    query, serper_api_key, vectara_api_key, vectara_customer_id, corpus_number
):
    """Conducts research and updates the corpus based on the query."""
    with st.status("Updating corpus...") as status:
        status.write("Sending request to Serper.dev API...")
        response = requests.post(
            "https://google.serper.dev/search",
            headers={"X-API-KEY": serper_api_key, "Content-Type": "application/json"},
            data=json.dumps({"q": query}),
        )

        search_results = json.loads(response.text)
        top_links = [result["link"] for result in search_results["organic"][:5]]

        consolidated_content = "\n".join(
            [fetch_url_content(link) for link in top_links]
        )
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_path = os.path.join("", f"serper_response_{timestamp}.txt")

        with open(file_path, "w", encoding="utf-8") as file:
            file.write(consolidated_content)

        status.write("Uploading consolidated file to update corpus...")
        upload_response = upload_file(
            vectara_api_key, vectara_customer_id, corpus_number, file_path
        )
        status.update(label="Corpus updated successfully!", state="complete")
        time.sleep(1)

        return upload_response
    

def fetch_url_content(url):
    """Fetches content from a URL."""
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return response.text
    except requests.RequestException as e:
        logging.error(f"Error fetching {url}: {e}")
        return ""
    




# Streamlit page configuration
st.set_page_config(page_title="Vectara Chat Essentials", page_icon="💬")

# Displaying the title with an emoji
st.title("Vectara Chat Essentials 🤖")

# Using markdown for a welcoming message with emojis for visual appeal
st.markdown("""
    Welcome to 'Vectara Chat Essentials: A Developer's Guide to Next-Gen Chatbots' 🌟.
    This tutorial offers a deep dive into building and enhancing chatbots using the innovative Vectara platform,
    equipped with the latest in AI and conversational intelligence. 🧠💬
    Whether you are a beginner or an advanced developer, this guide will take you through all the steps
    from creating your first chatbot to deploying sophisticated AI-driven conversational agents.
    Let's embark on this exciting journey! 🚀
    """)

# Adding an interactive element

if st.button("Start Using Now!"):
    st.snow()
    st.write(
        "Great! Let's dive into the world of conversational AI with Vectara Chat. 🎉"
    )


# Ensure corpus_number is stored across sessions
if "corpus_number" not in st.session_state:
    st.session_state["corpus_number"] = None

# Sidebar setup for user inputs

with st.sidebar:
    st.session_state["vectara_api_key"] = st.text_input("Vectara API Key")
    st.session_state["serper_api_key"] = st.text_input("Serper API Key (for research)") # Optional
    vectara_customer_id = st.text_input("Vectara Customer ID")
    corpus_name = st.text_input("Corpus Name (optional)")
    corpus_description = st.text_input("Corpus Description (optional)")
    file = st.file_uploader("Upload a file (optional)", type=["text", "pdf"])

    if st.button("Submit") and file:
        corpus_number, _ = create_corpus(
            st.session_state["vectara_api_key"],
            vectara_customer_id,
            corpus_name,
            corpus_description,
        )

        if corpus_number is not None:
            st.session_state["corpus_number"] = corpus_number
            file_path = save_to_dir(file)
            upload_file(
                st.session_state["vectara_api_key"],
                vectara_customer_id,
                corpus_number,
                file_path,
            )
            st.success("File uploaded successfully!")
        else:
            st.error("Failed to create corpus. Please check your inputs.")


# Chat message handling
if "messages" not in st.session_state:
    st.session_state["messages"] = []

with st.form("chat_input", clear_on_submit=True):
    user_prompt = st.text_input("Your message:", label_visibility="collapsed")

    if st.form_submit_button("Send"):
        st.session_state.messages.append({"role": "user", "content": user_prompt})


if user_prompt and st.session_state["vectara_api_key"]:
    conversation_id = get_latest_conversation_id(
        st.session_state["vectara_api_key"], vectara_customer_id
    )
    response = requests.post(
        "https://api.vectara.io/v1/query",
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "customer-id": vectara_customer_id,
            "x-api-key": st.session_state["vectara_api_key"],
        },
        data=json.dumps(
            {
                "query": [
                    {
                        "query": user_prompt,
                        "start": 0,
                        "numResults": 3,
                        "contextConfig": {
                            "sentences_before": 3,
                            "sentences_after": 3,
                            "start_tag": "<response>",
                            "end_tag": "</response>",
                        },
                        "corpusKey": [{"corpus_id": st.session_state["corpus_number"]}],
                        "summary": [
                            {"max_summarized_results": 3, "response_lang": "en"}
                        ],
                        "chat": {"store": True, "conversationId": conversation_id},
                    }
                ]
            }
        ),
    )
    query_response = response.json()

    if query_response["responseSet"] and query_response["responseSet"][0]["response"]:
        score = query_response["responseSet"][0]["response"][0]["score"]
        first_response = query_response["responseSet"][0]["summary"][0]["text"]

        if (
            score < 0.65
            or "The returned results did not contain sufficient information"
            in first_response
        ):
            st.write("Conversation paused. Updating corpus...")
            if st.session_state["corpus_number"] is not None:
                upload_response = research_and_update_corpus(
                    user_prompt,
                    st.session_state["serper_api_key"],
                    st.session_state["vectara_api_key"],
                    vectara_customer_id,
                    st.session_state["corpus_number"],
                )
                st.write(f"Corpus update response: {upload_response}")
            else:
                st.error("Corpus number is not set. Cannot update the corpus.")

        st.session_state.messages.append(
            {"role": "assistant", "content": first_response}
        )

# Display chat messages
for idx, msg in enumerate(st.session_state.messages):
    message(msg["content"], is_user=msg["role"] == "user", key=f"chat_message_{idx}")


















#tutorial link: https://lablab.ai/t/vectara-chat-essentials-harness-ai-for-next-gen-hackathon-chatbot