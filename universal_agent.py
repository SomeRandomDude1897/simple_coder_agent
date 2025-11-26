from langchain.agents import AgentType, initialize_agent
from langchain.memory import ConversationBufferWindowMemory
from custom_model import CustomCloudLLM


class UniversalAgent:
    def __init__(self, model, temp, jwt_token, prompt, tools):
        self.model = model
        self.temp = temp
        self.jwt_token = jwt_token
        self.prompt = prompt
        self.tools = tools
        self.memory = ConversationBufferWindowMemory(
            memory_key="chat_history", return_messages=True, k=100
        )
        self.answer = ""
        self.reasoning = ""

    def update_memory(self, memory):
        self.memory = memory

    def get_answer(self):
        return self.answer

    def get_reasoning(self):
        return self.reasoning

    def run(self, user_prompt):

        llm = CustomCloudLLM(
            model=self.model,
            temperature=self.temp,
            prompt=self.prompt,
            jwt_token=self.jwt_token,
        )

        agent = initialize_agent(
            self.tools,
            llm,
            agent=AgentType.CHAT_CONVERSATIONAL_REACT_DESCRIPTION,
            verbose=True,
            handle_parsing_errors=True,
            max_iterations=100,  # лимит итераций # лимит времени (в секундах)
            memory=self.memory,
            # profanity_check=False
        )

        self.answer = agent.run(input=user_prompt)
