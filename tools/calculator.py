from langchain.tools import Tool

def calculator(input_text: str):
    try:
        return str(eval(input_text, {"__builtins__": {}}))
    except Exception as e:
        return f"Error: {e}"

calculator_tool = Tool(
    name="Calculator",
    func=calculator,
    description="Performs basic arithmetic calculations."
)