"""
Office Automation Agents Module

리팩토링된 모듈 구조:
- graph/: State, 그래프 정의 및 워크플로우
  - utils/: 유틸리티 (tools, parsers, document_generator, intent_classifier)
- middleware/: 로깅 및 에러 핸들링
- prompts/: 프롬프트 템플릿
"""

# Main workflow
from .graph.graph import OfficeAutomationGraph

# Graph components
from .graph import (
    OfficeAutomationState,
    IntentClassification,
    DeliveryInfo,
    ProductOrderInfo,
)

# Tools
from .graph.utils.tools import (
    request_approval_delivery,
    request_approval_product,
    generate_delivery_document,
    generate_product_document,
)

# Parsers
from .graph.utils.parsers import DeliveryParser, ProductOrderParser

# Intent Classifier
from .graph.utils.intent_classifier import IntentClassifier

# Document Generator
from .graph.utils.document_generator import DocumentGenerator

# Middleware
from .middleware import (
    LangfuseToolLoggingMiddleware,
    ToolErrorHandlerMiddleware,
)

__all__ = [
    # Main
    "OfficeAutomationGraph",

    # State
    "OfficeAutomationState",
    "IntentClassification",
    "DeliveryInfo",
    "ProductOrderInfo",

    # Tools
    "request_approval_delivery",
    "request_approval_product",
    "generate_delivery_document",
    "generate_product_document",

    # Parsers
    "DeliveryParser",
    "ProductOrderParser",
    "IntentClassifier",

    # Generators
    "DocumentGenerator",

    # Middleware
    "LangfuseToolLoggingMiddleware",
    "ToolErrorHandlerMiddleware",
]
