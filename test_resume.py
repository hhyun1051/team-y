#!/usr/bin/env python
"""
Test resume functionality
"""

import sys
from pathlib import Path

# 프로젝트 루트를 sys.path에 추가
sys.path.insert(0, str(Path(__file__).parent))

def test_delivery_resume():
    """Test delivery workflow with resume"""
    print("="*60)
    print("Testing Delivery Workflow with Resume")
    print("="*60)

    try:
        from agents import OfficeAutomationGraph

        print("\n[1/4] Initializing OfficeAutomationGraph...")
        graph = OfficeAutomationGraph(
            model_name="gpt-4o-mini",
            temperature=0.0,
            use_langfuse=False
        )

        print("\n[2/4] Testing delivery input (trigger interrupt)...")
        test_input = "호깅텍 01050322853 경기도 김포 아크플레이스 오른쪽, 선불"
        thread_id = "test_resume_delivery"

        result = graph.invoke(
            raw_input=test_input,
            input_type="text",
            thread_id=thread_id
        )

        # Check interrupt
        state = graph.get_state(thread_id=thread_id)
        print(f"\n  - State.next: {state.next}")

        if state.next and "delivery_subgraph" in str(state.next):
            print(f"  ✅ Interrupt detected correctly")

            # Get subgraph state
            if state.tasks and len(state.tasks) > 0:
                task = state.tasks[0]
                subgraph_state = graph.graph.get_state(task.state)
                if subgraph_state and subgraph_state.values:
                    approval_msg = subgraph_state.values.get("approval_message", "")
                    print(f"  - Approval message: {approval_msg[:100]}...")
        else:
            print(f"  ❌ No interrupt detected!")
            return False

        print("\n[3/4] Resuming with approval...")
        result = graph.resume(
            decision_type="approve",
            thread_id=thread_id
        )

        print(f"\n[4/4] Resume result:")
        print(f"  - Result keys: {result.keys() if isinstance(result, dict) else 'N/A'}")

        if "messages" in result:
            print(f"  - Messages count: {len(result['messages'])}")
            for i, msg in enumerate(result["messages"]):
                msg_type = type(msg).__name__
                if hasattr(msg, "content"):
                    content = msg.content
                else:
                    content = str(msg)
                print(f"    [{i}] {msg_type}: {content[:120]}...")

        if "pdf_path" in result and result["pdf_path"]:
            print(f"  ✅ PDF generated: {result['pdf_path']}")
        else:
            print(f"  ❌ No PDF generated!")

        # Check final state
        final_state = graph.get_state(thread_id=thread_id)
        print(f"\n  - Final state.next: {final_state.next}")

        print("\n" + "="*60)
        print("✅ Test completed!")
        print("="*60)

        return True

    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_delivery_resume()
    sys.exit(0 if success else 1)
