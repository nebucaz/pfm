import os

MODEL_NAME = "mistral:7b-instruct"
OLLAMA_API_KEY = os.getenv("OLLAMA_API_KEY")

TOOLS = {
    "calculator": True,
    "search": True,
}