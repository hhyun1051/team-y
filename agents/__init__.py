"""
Office Automation Agents Module

리팩토링된 모듈 구조:
- graph/: State 및 그래프 정의
- tools/: HITL 승인 및 문서 생성 도구
- parsers/: 시나리오별 파서
- middleware/: 로깅 및 에러 핸들링
"""

# Main workflow
from .workflow import OfficeAutomationGraph

# Graph components
from .graph import (
    OfficeAutomationState,
    IntentClassification,
    DeliveryInfo,
    ProductOrderInfo,
)

# Tools
from .tools import (
    request_approval_delivery,
    request_approval_product,
    generate_delivery_document,
    generate_product_document,
)

# Parsers
from .parsers import DeliveryParser, ProductOrderParser

# Intent Classifier
from .intent_classifier import IntentClassifier

# Document Generator
from .document_generator import DocumentGenerator

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
]
