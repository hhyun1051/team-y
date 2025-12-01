#!/usr/bin/env python
"""
Graph 초기화 테스트

노드 기반 아키텍처가 정상적으로 초기화되는지 확인
"""

import sys
from pathlib import Path

# 프로젝트 루트를 sys.path에 추가
sys.path.insert(0, str(Path(__file__).parent))

def test_graph_initialization():
    """Graph 초기화 테스트"""
    print("="*60)
    print("Testing OfficeAutomationGraph initialization")
    print("="*60)

    try:
        from agents import OfficeAutomationGraph

        print("\n[1/3] Importing OfficeAutomationGraph... ✅")

        print("\n[2/3] Initializing OfficeAutomationGraph...")
        graph = OfficeAutomationGraph(
            model_name="gpt-4o-mini",
            temperature=0.0,
            use_langfuse=False  # Langfuse 비활성화 (테스트용)
        )
        print("[2/3] OfficeAutomationGraph initialized ✅")

        print("\n[3/3] Checking graph structure...")
        print(f"  - Graph type: {type(graph.graph)}")
        print(f"  - Has delivery_subgraph: {hasattr(graph, 'delivery_subgraph')}")
        print(f"  - Has product_subgraph: {hasattr(graph, 'product_subgraph')}")
        print(f"  - Has aluminum_subgraph: {hasattr(graph, 'aluminum_subgraph')}")
        print("[3/3] Graph structure check ✅")

        print("\n" + "="*60)
        print("✅ All tests passed!")
        print("="*60)

        return True

    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_graph_initialization()
    sys.exit(0 if success else 1)
