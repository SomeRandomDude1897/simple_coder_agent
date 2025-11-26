import os
from universal_agent import UniversalAgent
from tools import REPORTTOOL, SEARCHTOOL, RUNCMDTOOL
from prompt import CODER_PROMPT

JWT_TOKEN = os.getenv("JWT_TOKEN")
TAVILY_KEY = os.getenv("TAVILY_API_KEY")
MODEL = "gpt-5-mini"
TEMPERATURE = 0.7

tools = [REPORTTOOL, SEARCHTOOL, RUNCMDTOOL]

prompt = ""


coder_agent = UniversalAgent(
    MODEL,
    TEMPERATURE,
    JWT_TOKEN,
    CODER_PROMPT,
    tools,
)

print(coder_agent.run(prompt))
