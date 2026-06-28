import os
from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain.chat_models import init_chat_model

load_dotenv()

# Step 1: Define a tool
# In LangChain, any Python function with type hints + docstring can be a tool
def get_weather(city: str) -> str:
    """Get the current weather for a given city.

    Args:
        city: The name of the city to get weather for.
    """
    weather_data = {
        "beijing": "sunny, 25°C, humidity 40%",
        "shanghai": "cloudy, 28°C, humidity 65%",
        "tokyo": "light rain, 22°C, humidity 80%",
    }
    return weather_data.get(city.lower(), f"No weather data for {city}")

# Step 2: Initialize the model (DeepSeek via OpenAI-compatible protocol)
model = init_chat_model(
    "openai:deepseek-chat",
    temperature=0,
    openai_api_key=os.environ["DEEPSEEK_API_KEY"],
    openai_api_base=os.environ["DEEPSEEK_BASE_URL"],
)

# Step 3: Create the agent
agent = create_agent(
    model=model,
    tools=[get_weather],
    system_prompt="You are a friendly weather assistant. Answer in Chinese.",
)

# Step 4: Run the agent
result = agent.invoke(
    {"messages": [{"role": "user", "content": "what's the weather like in Beijing today?"}]}
)

# Step 5: Inspect the message history
print("=== Full message history ===")
for msg in result["messages"]:
    content_preview = str(msg.content)[:200]
    print(f"[{msg.type}] {content_preview}...")
