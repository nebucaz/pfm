import requests
import asyncio
from tools.spendcast import SPARQLTool

from dotenv import load_dotenv
load_dotenv()

# Minimal tool definition
simple_tool = [{
    "type": "function", 
    "function": {
        "name": "echo",
        "description": "Echo back the input",
        "parameters": {
            "type": "object",
            "properties": {
                "text": {"type": "string"}
            },
            "required": ["text"]
        }
    }
}]

def test_simple_tool():
    response = requests.post('http://localhost:11434/api/chat',
        json={
            "model": "mistral:7b-instruct",
            "messages": [{"role": "user", "content": "Echo 'hello world'"}],
            "tools": simple_tool,
            "stream": False
        }
    )
    
    print("Simple tool test:", response.json())

def test_sparql_tool():
    response = requests.post('http://localhost:11434/api/chat',
        json={
            "model": "mistral:7b-instruct",
            "messages": [
                {"role": "user", "content": "   "}
                ],
            "tools": simple_tool,
            "stream": False
        }
    )
    
    print("SPARQL tool test:", response.json())


tool = SPARQLTool()
async def test():
    args = {"query":"SELECT * WHERE { ?s ?p ?o } LIMIT 10"}
    res = await tool.arun(tool_input=args)
    print(res)

if __name__ == "__main__":
    #test_simple_tool()
    test_sparql_tool()
    #asyncio.run(test())