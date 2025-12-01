try:
    from langchain.agents.middleware import AgentMiddleware
    print("AgentMiddleware found in langchain.agents.middleware")
except ImportError:
    print("AgentMiddleware NOT found in langchain.agents.middleware")

try:
    from langchain.agents.middleware.types import AgentMiddleware, ModelCallResult, ModelRequest, ModelResponse
    print("Types found in langchain.agents.middleware.types")
except ImportError:
    print("Types NOT found in langchain.agents.middleware.types")

try:
    from langchain.chat_models.base import init_chat_model
    print("init_chat_model found in langchain.chat_models.base")
except ImportError:
    print("init_chat_model NOT found in langchain.chat_models.base")
