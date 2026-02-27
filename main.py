from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
from fastapi.staticfiles import StaticFiles
import pandas as pd
import os
from langchain_experimental.agents import create_pandas_dataframe_agent
from langchain.agents.agent_types import AgentType
from pydantic import BaseModel
from typing import Optional
import base64
import tempfile
import time
import matplotlib
matplotlib.use('Agg')  # Force "Headless" mode (no windows)
import matplotlib.pyplot as plt

CHART_PATH = Path(tempfile.gettempdir()) / "chart.png"
CHART_PATH_STR = str(CHART_PATH).replace("\\", "/")

load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")
app = FastAPI(title='Titanic Chat Agent', version = "1.0.0")

origins = [
    "http://localhost:8501",           
    "https://your-app-name.streamlit.app" 
]
app.add_middleware(
    CORSMiddleware,
    allow_origins = ["*"],
    allow_credentials = True,
    allow_methods = ["*"],
    allow_headers = ["*"]
)

STATIC_PATH  = Path("static")
STATIC_PATH.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(STATIC_PATH)), name="static")

df = pd.read_csv("titanic_cleaned.csv")

llm = ChatGoogleGenerativeAI(model = "gemini-2.5-flash", temperature = 0, google_api_key = api_key)

agent_prefix = f"""
You are a helpful data analyst assistant specializing in the Titanic passenger dataset.
You have access to a pandas DataFrame called `df` with these key columns:
- PassengerId, Survived (0/1), Pclass (1/2/3), Name, Sex, Age, SibSp, Parch
- Ticket, Fare, Cabin, Embarked (C/Q/S)
- PassengerClass (First/Second/Third), Survived_Label, Sex_Label, EmbarkedPort

IMPORTANT RULES:
1. Only answer questions related to the Titanic dataset.
2. If asked for a visualization (histogram, bar chart, pie chart, etc.), generate it using matplotlib/plotly AND save it.
3. For plots: use plt.savefig('{CHART_PATH_STR}', dpi=120, bbox_inches='tight') then include the exact text CHART_SAVED in your response.
4. Always provide a clear, concise text answer alongside any chart.
5. If the question is unrelated to the Titanic, politely redirect the user.
6. Format numbers nicely (e.g., percentages to 1 decimal place).
7. Whenever the user uses keywords like 'plot', 'chart', 'graph', or 'visualize', prioritize generating a visual over a text-only summary
8. ALWAYS end your final response with exactly: Final Answer: <your text here>
    Never use markdown bullets in the Final Answer line. This is required.  
""" 

agent = create_pandas_dataframe_agent(
    llm = llm,
    df = df,
    agent_type= AgentType.ZERO_SHOT_REACT_DESCRIPTION,
    prefix= agent_prefix,
    verbose = True,
    allow_dangerous_code = True,
    handle_parsing_errors = True,
    max_iterations = 10
)

class ChatRequest(BaseModel):
    question: str 

class ChatResponse(BaseModel):
    answer: str
    # chart_data: Optional[dict] = None
    chart_image_b64: Optional[str] = None

@app.get("/")
def root():
    return {"status": "ok", "message": "Titanic Chat Agent is running"}

@app.post("/chat", response_model = ChatResponse)
def chat(request: ChatRequest):
    question = request.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Question cannot be empty.")
    
    answer = ""

    try:
        agent_response = agent.invoke({"input": question})
        print(f"[DEBUG] agent_response = {agent_response}")

        if agent_response is None:
            answer = "Agent returned no response. Chart may still be available."
        elif isinstance(agent_response, dict):
            answer = agent_response.get("output", str(agent_response))
        else:
            answer = str(agent_response)

    except Exception as e:
        print(f"[AGENT ERROR] {type(e).__name__}: {e}")
        error_str = str(e)

        if "Could not parse LLM output:" in error_str:
            extracted = error_str.split("Could not parse LLM output:")[-1].strip()
            extracted = extracted.strip("`").strip()
            answer = extracted
            print(f"[RECOVERED] Answer extracted from parse error: {answer[:200]}")
        else:
            answer = "I had trouble reading the response. Chart may still be available below."

    chart_image_b64 = None
    if CHART_PATH.exists():
        try: 
            time.sleep(1)
            with open(CHART_PATH, "rb") as f:
                chart_image_b64 = base64.b64encode(f.read()).decode()
            CHART_PATH.unlink(missing_ok=True)
            answer = answer.replace("CHART_SAVED", "").strip()
        except Exception:
            pass
    
    return ChatResponse(
        answer = answer,
        chart_image_b64 = chart_image_b64
    )


