import os
from pathlib import Path
from dotenv import load_dotenv
from groq import Groq

# Load .env from project root
env_path = Path(__file__).resolve().parents[1] / ".env"
load_dotenv(env_path)

api_key = os.getenv("GROQ_API_KEY")

if not api_key:
    raise ValueError(f"GROQ_API_KEY not found. Checked: {env_path}")

client = Groq(api_key=api_key)

response = client.chat.completions.create(
    model="llama-3.3-70b-versatile",
    messages=[
        {
            "role": "user",
            "content": "Say hello in one short sentence."
        }
    ],
)

print(response.choices[0].message.content)