# Import relevant functionality
# from langchain.chat_models import init_chat_model
#from langchain_tavily import TavilySearch

import os
import logging
import getpass
from langchain_community.tools import DuckDuckGoSearchRun
from langgraph.checkpoint.memory import MemorySaver
#from langgraph.prebuilt import create_react_agent
from langchain.agents import create_agent
from langchain.agents.middleware import wrap_tool_call
from langchain_core.messages import ToolMessage

#from langchain_ollama import ChatOllama
from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI
#from langchain_core.messages import HumanMessage
from langchain_core.callbacks.base import AsyncCallbackHandler

from tools.spendcast import SPARQLTool
from dotenv import load_dotenv

load_dotenv()

# Configure logging for the whole app
logging.basicConfig(
    filename='agent.log',       # log file name
    filemode='a',             # append mode ('w' to overwrite each run)
    level=logging.INFO,       # or DEBUG for more verbosity
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)


@wrap_tool_call
def handle_tool_errors(request, handler):
    """Handle tool execution errors with custom messages."""
    try:
        return handler(request)
    except Exception as e:
        # Return a custom error message to the model
        return ToolMessage(
            content=f"Tool error: Please check your input and try again. ({str(e)})",
            tool_call_id=request.tool_call["id"]
        )

class ToolLogger(AsyncCallbackHandler):
    async def on_tool_start(self, serialized, input_str, **kwargs):
        print("Tool start:", serialized["name"], "input:", input_str)

    async def on_tool_end(self, output, **kwargs):
        print("Tool output:", output)

# def get_weather(city: str) -> str:
#     """Get weather for a given city."""
#     return f"It's always sunny in {city}!"



#if not os.environ.get("GOOGLE_API_KEY"):
#  os.environ["GOOGLE_API_KEY"] = getpass.getpass("Enter API key for Google Gemini: ")

#model = ChatGoogleGenerativeAI(model="gemini-2.5-flash", google_api_key=os.environ["GOOGLE_API_KEY"])
#model = ChatOllama(model="mistral:7b-instruct", temperature=0, verbose=True)

# use with LM Studio
model: ChatOpenAI = ChatOpenAI(model="openai/gpt-oss-20b", base_url="http://localhost:9393/v1", temperature=0, api_key="not-needed")

# Create the agent
memory = MemorySaver()
#model = init_chat_model("anthropic:claude-3-5-sonnet-latest")
#search = TavilySearch(max_results=2)

search = DuckDuckGoSearchRun()
tools = [SPARQLTool(), search]
agent = create_agent(
    model, 
    tools, 
    middleware=[handle_tool_errors],
    #system_prompt="You are a helpful assistant. Be concise and accurate."
    checkpointer=memory)


# Use the agent
config = {"configurable": {"thread_id": "abc123"}}

# input_message = {
#     "role": "user",
#     "content": "Hi, I'm Bob and I live in SF.",
# }

# alternativ
# message = HumanMessage(
#     content=[
#         {
#             "type": "text",
#             "text": "What's in this image?",
#         },
#         {"type": "image_url", "image_url": "https://picsum.photos/seed/picsum/200/300"},
#     ]
# result = llm.invoke([message])

for chunk in agent.stream(  
    {"messages": [
        #{"role": "system", "content":"Your are a helpful assistant that helps the user understand her financial situation. Comprehensive information about the user's accounts, transactions are stored in the financial graph accessible by 'SPARQLtool'"},
        # {"role": "user", "content": "What is the weather in SF?"}
        {"role": "user", "content": "Please provide a list of my banking accounts with account name and current balance."}
    ]},
    config,
    stream_mode="updates",
    ):
    for step, data in chunk.items():
        print(f"step: {step}")
        print(f"content: {data['messages'][-1].content_blocks}")


# for step in agent_executor.stream(
#     {"messages": [input_message]}, config, stream_mode="values"
# ):
#     step["messages"][-1].pretty_print()

# input_message = {
#     "role": "user",
#     "content": "What's the weather where I live?",
# }

# for step in agent_executor.stream(
#     {"messages": [input_message]}, config, stream_mode="values"
# ):
#     step["messages"][-1].pretty_print()