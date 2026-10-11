from tavily import TavilyClient
import os

client = TavilyClient(
    api_key=os.getenv("TAVILY_API_KEY")
)

result = client.search(
    "latest financial results of Infosys",
    search_depth="advanced"
)

print(result)