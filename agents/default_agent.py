from langgraph.agents import Agent
from langchain.llms import Ollama
from tools.calculator_tool import calculator_tool
from config import MODEL_NAME

llm = Ollama(model="mistral:7b-instruct")

default_agent = Agent(
    llm=llm,
    tools=[calculator_tool],
    name="Default LangGraphAgent",
    description="An AI agent capable of tool usage and complex workflows."
)