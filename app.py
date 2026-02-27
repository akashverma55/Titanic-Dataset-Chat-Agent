import base64
import requests
import streamlit as st 

st.set_page_config(
    page_title="Titanic Chat Agent",
    page_icon="🚢",
    layout="centered",
)

BACKEND_URL = st.secrets.get("BACKEND_URL", "http://localhost:8000")

EXAMPLE_QUESTIONS = [
    "What percentage of passengers were male?",
    "Show me a histogram of passenger ages",
    "What was the average ticket fare?",
    "How many passengers embarked from each port?",
    "Show survival rate by passenger class",
    "What was the survival rate for women vs men?",
]

if "messages" not in st.session_state:
    st.session_state.messages = []

if "pending_question" not in st.session_state:
    st.session_state.pending_question = None


@st.cache_data(ttl=300)
def fetch_dataset_info() -> dict:
    """Fetch basic dataset stats from the backend."""
    try:
        resp = requests.get(f"{BACKEND_URL}/dataset-info", timeout=10)
        resp.raise_for_status()
        return resp.json()
    except Exception:
        return {}
    
def send_question(question: str) -> dict:
    """Send a question to the FastAPI backend and return the response."""
    try:
        resp = requests.post(
            f"{BACKEND_URL}/chat",
            json={"question": question},
            timeout=60,
        )
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.ConnectionError:
        return {"answer": "Cannot connect to the backend. Make sure FastAPI is running."}
    except requests.exceptions.Timeout:
        return {"answer": "Request timed out. Try a simpler question."}
    except Exception as e:
        return {"answer": f"Error: {str(e)}"}
    
def process_question(question: str):
    """Add user message, call backend, display assistant response."""
    st.session_state.messages.append({"role": "user", "content": question})

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            result = send_question(question)

        answer = result.get("answer", "No answer returned.")
        chart_image_b64 = result.get("chart_image_b64")

        st.write(answer)

        if chart_image_b64:
            img_bytes = base64.b64decode(chart_image_b64)
            st.image(img_bytes, use_column_width=True)

    st.session_state.messages.append({
        "role": "assistant",
        "content": answer,
        "chart_image_b64": chart_image_b64,
    })

st.title("Titanic Passenger Chat")
st.caption("Ask questions about the Titanic dataset in plain English.")

# Render chat history
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])
        if msg.get("chart_image_b64"):
            img_bytes = base64.b64decode(msg["chart_image_b64"])
            st.image(img_bytes, use_column_width=True)

# Handle sidebar button clicks
if st.session_state.pending_question:
    q = st.session_state.pending_question
    st.session_state.pending_question = None
    process_question(q)
    st.rerun()

# Chat input
if user_input := st.chat_input("Ask about Titanic passengers..."):
    process_question(user_input)
    st.rerun()
