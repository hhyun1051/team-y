#!/usr/bin/env python
"""
Test workflow execution to debug echo issue
"""

import sys
from pathlib import Path

# 프로젝트 루트를 sys.path에 추가
sys.path.insert(0, str(Path(__file__).parent))

def test_delivery_workflow():
    """Test delivery workflow"""
    print("="*60)
    print("Testing Delivery Workflow")
    print("="*60)

    try:
        from agents import OfficeAutomationGraph

        print("\n[1/3] Initializing OfficeAutomationGraph...")
        graph = OfficeAutomationGraph(
            model_name="gpt-4o-mini",
            temperature=0.0,
            use_langfuse=False
        )
        print("[1/3] OfficeAutomationGraph initialized ✅")

        print("\n[2/3] Testing delivery input...")
        test_input = "삼성전자 서울시 강남구 테헤란로 123 상세주소 010-1234-5678 착불"

        result = graph.invoke(
            raw_input=test_input,
            input_type="text",
            thread_id="test_delivery"
        )

        print(f"\n[2/3] Workflow result:")
        print(f"  - Result type: {type(result)}")
        print(f"  - Result keys: {result.keys() if isinstance(result, dict) else 'N/A'}")

        if "messages" in result:
            print(f"  - Messages count: {len(result['messages'])}")
            for i, msg in enumerate(result["messages"]):
                msg_type = type(msg).__name__
                if hasattr(msg, "content"):
                    content = msg.content
                elif isinstance(msg, dict):
                    content = msg.get("content", "")
                else:
                    content = str(msg)
                print(f"    [{i}] {msg_type}: {content[:100]}...")

        if "scenario" in result:
            print(f"  - Scenario: {result['scenario']}")

        if "delivery_info" in result:
            print(f"  - Delivery info parsed: {result['delivery_info'] is not None}")

        if "approval_message" in result:
            print(f"  - Approval message: {result['approval_message'][:100]}...")

        # Check state after interrupt
        print("\n[3/3] Checking state after execution...")
        state = graph.get_state(thread_id="test_delivery")
        if state:
            print(f"  - State.next: {state.next}")
            print(f"  - State.values keys: {state.values.keys() if state.values else 'None'}")

            # Check tasks for subgraph state
            if hasattr(state, 'tasks') and state.tasks:
                print(f"  - State.tasks count: {len(state.tasks)}")
                for i, task in enumerate(state.tasks):
                    print(f"    Task[{i}]: name={task.name}, error={task.error}")
                    # Get subgraph state using the task's config
                    if task.state:
                        try:
                            subgraph_state = graph.graph.get_state(task.state)
                            print(f"      - Subgraph state keys: {subgraph_state.values.keys() if subgraph_state and subgraph_state.values else 'None'}")
                            if subgraph_state and subgraph_state.values:
                                if "approval_message" in subgraph_state.values:
                                    print(f"      - approval_message: {subgraph_state.values['approval_message'][:80]}...")
                                if "delivery_info" in subgraph_state.values:
                                    info = subgraph_state.values['delivery_info']
                                    print(f"      - delivery_info: unloading_site={info.unloading_site if info else 'None'}")
                        except Exception as e:
                            print(f"      - Error getting subgraph state: {e}")

            if state.values:
                if "messages" in state.values:
                    print(f"  - State messages count: {len(state.values['messages'])}")
                if "approval_message" in state.values:
                    approval = state.values["approval_message"]
                    print(f"  - State approval_message: {approval[:100] if approval else 'None'}...")
                if "product_order_info" in state.values:
                    print(f"  - State product_order_info: {state.values['product_order_info']}")
                if "awaiting_approval" in state.values:
                    print(f"  - State awaiting_approval: {state.values['awaiting_approval']}")

        print("\n" + "="*60)
        print("✅ Test completed!")
        print("="*60)

        return True

    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_help_workflow():
    """Test help workflow"""
    print("\n" + "="*60)
    print("Testing Help Workflow")
    print("="*60)

    try:
        from agents import OfficeAutomationGraph

        print("\n[1/2] Initializing OfficeAutomationGraph...")
        graph = OfficeAutomationGraph(
            model_name="gpt-4o-mini",
            temperature=0.0,
            use_langfuse=False
        )

        print("\n[2/2] Testing help input...")
        test_input = "도움말"

        result = graph.invoke(
            raw_input=test_input,
            input_type="text",
            thread_id="test_help"
        )

        print(f"\n  - Result type: {type(result)}")
        print(f"  - Result keys: {result.keys() if isinstance(result, dict) else 'N/A'}")

        if "messages" in result:
            print(f"  - Messages count: {len(result['messages'])}")
            for i, msg in enumerate(result["messages"]):
                msg_type = type(msg).__name__
                if hasattr(msg, "content"):
                    content = msg.content
                elif isinstance(msg, dict):
                    content = msg.get("content", "")
                else:
                    content = str(msg)
                print(f"    [{i}] {msg_type}: {content[:100]}...")

        print("\n" + "="*60)
        print("✅ Help test completed!")
        print("="*60)

        return True

    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    # Test help first (simpler case)
    help_success = test_help_workflow()

    # Test delivery (interrupt case)
    delivery_success = test_delivery_workflow()

    sys.exit(0 if (help_success and delivery_success) else 1)
