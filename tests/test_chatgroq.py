import os
from pathlib import Path
from dotenv import load_dotenv
from langchain_groq import ChatGroq

# Load .env from project root
env_path = Path(__file__).resolve().parents[1] / ".env"
load_dotenv(env_path)

api_key = os.getenv("GROQ_API_KEY")

if not api_key:
    raise ValueError("GROQ_API_KEY not found")

llm = ChatGroq(
    model="llama-3.1-8b-instant",
    api_key=api_key,
    temperature=0,
)

response = llm.invoke(
    "Say hello in one short sentence."
)

print(response.content)