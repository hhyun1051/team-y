# Agent Middlewares

확장 가능한 LangChain 에이전트 middleware 컬렉션입니다.

## 📁 구조

```
agents/middlewares/
├── __init__.py              # 패키지 진입점
├── langfuse_logging.py      # Langfuse 로깅 middleware
├── error_handler.py         # Tool 에러 처리 middleware
└── README.md                # 이 파일
```

## 🚀 사용법

```python
from agents.middlewares import LangfuseToolLoggingMiddleware, ToolErrorHandlerMiddleware

# 필요한 middleware를 직접 조합
middlewares = [
    LangfuseToolLoggingMiddleware(verbose=True),
    ToolErrorHandlerMiddleware(include_error_details=True)
]

# Agent에 적용
from agents import ManagerM

manager = ManagerM(
    middleware=middlewares,
    # ... other params
)
```

## 📦 포함된 Middleware

### 1. LangfuseToolLoggingMiddleware

모든 tool call을 Langfuse에 자동으로 로깅합니다.

**기능:**
- Tool call input/output 추적
- 실행 시간 측정
- 에러 로깅
- Trace context 자동 중첩

**옵션:**
- `langfuse_client`: Langfuse 클라이언트 (None이면 자동 초기화)
- `verbose`: 콘솔 로그 출력 여부
- `log_errors`: 에러 로깅 여부

### 2. ToolErrorHandlerMiddleware

Tool 실행 에러를 graceful하게 처리합니다.

**기능:**
- 예외를 catch하여 ToolMessage로 변환
- 모델이 이해할 수 있는 에러 메시지 생성
- Agent 실행 중단 방지

**옵션:**
- `error_message_template`: 커스텀 에러 메시지 템플릿
- `include_error_details`: 상세 에러 정보 포함 여부


## 🔧 새로운 Middleware 추가하기

### 1. 새 파일 생성

```bash
touch agents/middlewares/my_middleware.py
```

### 2. Middleware 클래스 구현

```python
from typing import Callable
from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import ToolMessage
from langgraph.prebuilt.tool_node import ToolCallRequest
from langgraph.types import Command


class MyCustomMiddleware(AgentMiddleware):
    """
    My custom middleware description
    """

    def __init__(self, **kwargs):
        """초기화"""
        self.config = kwargs

    def wrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], ToolMessage | Command],
    ) -> ToolMessage | Command:
        """
        Tool call wrapper

        Args:
            request: Tool call request
            handler: Next handler in the chain

        Returns:
            ToolMessage or Command
        """
        # 전처리 로직
        print(f"Before: {request.tool_call['name']}")

        # 실제 tool 실행
        result = handler(request)

        # 후처리 로직
        print(f"After: {result.content}")

        return result
```

### 3. __init__.py에 추가

```python
from .my_middleware import MyCustomMiddleware

__all__ = [
    "LangfuseToolLoggingMiddleware",
    "ToolErrorHandlerMiddleware",
    "MyCustomMiddleware",  # ← 추가
]
```

### 4. 사용

```python
from agents.middlewares import MyCustomMiddleware

middleware = MyCustomMiddleware(option="value")
```

## 💡 Middleware 작성 가이드

### 원칙

1. **Single Responsibility**: 하나의 middleware는 하나의 책임만 가져야 함
2. **Composable**: 다른 middleware와 조합 가능해야 함
3. **Non-intrusive**: 에러를 숨기지 말고 전파해야 함
4. **Configurable**: 생성자를 통한 설정 주입

### 체이닝 순서

Middleware는 **리스트 순서대로** 실행됩니다:

```python
middlewares = [
    MiddlewareA(),  # 1. 가장 먼저 실행 (outer wrapper)
    MiddlewareB(),  # 2. 두 번째 실행
    MiddlewareC(),  # 3. 마지막 실행 (inner wrapper)
]

# 실행 순서:
# A.wrap_tool_call 시작
#   → B.wrap_tool_call 시작
#     → C.wrap_tool_call 시작
#       → 실제 tool 실행
#     ← C.wrap_tool_call 종료
#   ← B.wrap_tool_call 종료
# ← A.wrap_tool_call 종료
```

### 에러 처리

```python
def wrap_tool_call(self, request, handler):
    try:
        # 전처리
        result = handler(request)
        # 후처리
        return result
    except Exception as e:
        # 로깅만 하고 에러 전파
        self.log_error(e)
        raise  # ← 중요: 에러를 숨기지 말 것
```

## 🎯 Use Cases

### 인증/권한 체크

```python
class AuthorizationMiddleware(AgentMiddleware):
    def wrap_tool_call(self, request, handler):
        tool_name = request.tool_call["name"]
        user_id = request.state.get("user_id")

        if not self.check_permission(user_id, tool_name):
            return ToolMessage(
                content="Permission denied",
                tool_call_id=request.tool_call["id"]
            )

        return handler(request)
```

### Rate Limiting

```python
class RateLimitMiddleware(AgentMiddleware):
    def wrap_tool_call(self, request, handler):
        if not self.rate_limiter.allow(request.tool_call["name"]):
            return ToolMessage(
                content="Rate limit exceeded, please try again later",
                tool_call_id=request.tool_call["id"]
            )

        return handler(request)
```

### Caching

```python
class CachingMiddleware(AgentMiddleware):
    def wrap_tool_call(self, request, handler):
        cache_key = self.get_cache_key(request)

        if cache_key in self.cache:
            return self.cache[cache_key]

        result = handler(request)
        self.cache[cache_key] = result

        return result
```

## 📚 참고 자료

- [LangChain Middleware 문서](https://python.langchain.com/docs/modules/agents/middleware)
- [LangGraph Tool Node](https://langchain-ai.github.io/langgraph/reference/prebuilt/#toolnode)
- [Langfuse 통합 가이드](https://langfuse.com/docs/integrations/langchain)
