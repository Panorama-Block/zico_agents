from src.agents.database.agent import DatabaseAgent
from src.agents.config import Config
from langchain_google_genai import ChatGoogleGenerativeAI

query = "Liste as tabelas que tem algum dado e as tabelas que não tem"

def test_database_agent():
    llm = ChatGoogleGenerativeAI(
        model=Config.GEMINI_MODEL,
        api_key=Config.GEMINI_API_KEY,
        temperature=0.0,
    )
    agent = DatabaseAgent(llm)
    history = agent.create_history()
    response = agent.ask(query, history)
    print(response)

if __name__ == "__main__":
    test_database_agent()