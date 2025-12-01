"""
Multi-turn input test for Office Automation workflow

This script tests the multi-turn conversation feature where users can provide
incomplete information initially, then add missing details in subsequent messages.

Example flow:
1. User: "호깅텍 경기도 김포 아크플레이스 오른쪽, 선불" (missing contact)
2. AI: "연락처가 누락되었습니다"
3. User: "01071152853"
4. AI: Should parse all messages together and proceed with approval
"""

import asyncio
from pathlib import Path
from langchain_core.messages import HumanMessage

# Add project root to path
import sys
sys.path.insert(0, str(Path(__file__).parent))

from agents.graph.graph import OfficeAutomationGraph


async def test_multiturn_delivery():
    """Test multi-turn conversation for delivery scenario"""
    print("\n" + "="*80)
    print("TEST: Multi-turn Delivery Input")
    print("="*80 + "\n")

    # Initialize graph
    workflow_graph = OfficeAutomationGraph()
    print("[✅] Graph initialized\n")

    # Test Case 1: Incomplete input (missing contact)
    print("-" * 80)
    print("Step 1: User provides incomplete delivery info (missing contact)")
    print("-" * 80)

    thread_id = "test_multiturn_delivery"
    config = {"configurable": {"thread_id": thread_id}}

    incomplete_input = "호깅텍 경기도 김포시 통진읍 김포대로 1938번길 48-1 아크플레이스 오른쪽, 선불, 오후 3시전 도착"

    result1 = workflow_graph.invoke(incomplete_input, thread_id=thread_id)
    print(f"\n[📤] Input: {incomplete_input}")
    print(f"\n[📥] Result 1:")

    if "messages" in result1:
        for msg in result1["messages"]:
            if hasattr(msg, "content"):
                print(f"    {msg.content}\n")

    # Check if parsing failed due to missing contact
    state1 = workflow_graph.get_state(thread_id=thread_id)
    print(f"\n[🔍] State after step 1:")
    print(f"    - scenario: {state1.values.get('scenario')}")
    print(f"    - parsing_error: {state1.values.get('parsing_error')}")
    print(f"    - delivery_info: {state1.values.get('delivery_info')}")
    print(f"    - messages count: {len(state1.values.get('messages', []))}")

    # Test Case 2: Provide missing contact
    print("\n" + "-" * 80)
    print("Step 2: User provides missing contact")
    print("-" * 80)

    missing_contact = "01071152853"

    result2 = workflow_graph.invoke(missing_contact, thread_id=thread_id)
    print(f"\n[📤] Input: {missing_contact}")
    print(f"\n[📥] Result 2:")

    if "messages" in result2:
        for msg in result2["messages"]:
            if hasattr(msg, "content"):
                print(f"    {msg.content}\n")

    # Check if parsing succeeded with combined inputs
    state2 = workflow_graph.get_state(thread_id=thread_id)
    print(f"\n[🔍] State after step 2:")
    print(f"    - scenario: {state2.values.get('scenario')}")
    print(f"    - parsing_error: {state2.values.get('parsing_error')}")
    print(f"    - delivery_info (main): {state2.values.get('delivery_info')}")
    print(f"    - approval_message (main): {state2.values.get('approval_message')}")
    print(f"    - awaiting_approval (main): {state2.values.get('awaiting_approval')}")
    print(f"    - messages count: {len(state2.values.get('messages', []))}")
    print(f"    - next: {state2.next}")

    # Check subgraph state (where delivery_info actually is during interrupt)
    delivery_info = None
    approval_message = None
    if state2.tasks and len(state2.tasks) > 0:
        task = state2.tasks[0]
        print(f"\n[🔍] Subgraph task found: {task.name}")
        subgraph_state = workflow_graph.graph.get_state(task.state)
        if subgraph_state and subgraph_state.values:
            delivery_info = subgraph_state.values.get("delivery_info")
            approval_message = subgraph_state.values.get("approval_message")
            print(f"    - delivery_info (subgraph): {delivery_info}")
            print(f"    - approval_message (subgraph): {approval_message}")

    # Verify multi-turn parsing
    if delivery_info:
        print(f"\n[✅] MULTI-TURN PARSING SUCCESS!")
        print(f"    - Unloading site: {delivery_info.unloading_site}")
        print(f"    - Address: {delivery_info.address}")
        print(f"    - Contact: {delivery_info.contact}")
        print(f"    - Payment type: {delivery_info.payment_type}")
        print(f"    - Notes: {delivery_info.notes}")

        # Verify it's waiting for approval
        if approval_message:
            print(f"\n[✅] System is correctly waiting for approval")
            print(f"\n[📋] Approval message:")
            print(approval_message)
        else:
            print(f"\n[❌] ERROR: Should be awaiting approval but isn't")
            return False
    else:
        print(f"\n[❌] MULTI-TURN PARSING FAILED")
        print(f"    Parsing error: {state2.values.get('parsing_error')}")
        return False

    print("\n" + "="*80)
    print("✅ Multi-turn test PASSED!")
    print("="*80 + "\n")
    return True


async def test_multiturn_product():
    """Test multi-turn conversation for product order scenario"""
    print("\n" + "="*80)
    print("TEST: Multi-turn Product Order Input")
    print("="*80 + "\n")

    # Initialize graph
    workflow_graph = OfficeAutomationGraph()
    print("[✅] Graph initialized\n")

    # Test Case 1: Incomplete input (missing unit price)
    print("-" * 80)
    print("Step 1: User provides incomplete product order (missing unit price)")
    print("-" * 80)

    thread_id = "test_multiturn_product"
    config = {"configurable": {"thread_id": thread_id}}

    incomplete_input = "삼성전자 알루미늄 원파이프 10개"

    result1 = workflow_graph.invoke(incomplete_input, thread_id=thread_id)
    print(f"\n[📤] Input: {incomplete_input}")
    print(f"\n[📥] Result 1:")

    if "messages" in result1:
        for msg in result1["messages"]:
            if hasattr(msg, "content"):
                print(f"    {msg.content}\n")

    # Check state
    state1 = workflow_graph.get_state(thread_id=thread_id)
    print(f"\n[🔍] State after step 1:")
    print(f"    - scenario: {state1.values.get('scenario')}")
    print(f"    - parsing_error: {state1.values.get('parsing_error')}")
    print(f"    - messages count: {len(state1.values.get('messages', []))}")

    # Test Case 2: Provide missing unit price
    print("\n" + "-" * 80)
    print("Step 2: User provides missing unit price")
    print("-" * 80)

    missing_price = "개당 50000원"

    result2 = workflow_graph.invoke(missing_price, thread_id=thread_id)
    print(f"\n[📤] Input: {missing_price}")
    print(f"\n[📥] Result 2:")

    if "messages" in result2:
        for msg in result2["messages"]:
            if hasattr(msg, "content"):
                print(f"    {msg.content}\n")

    # Check if parsing succeeded
    state2 = workflow_graph.get_state(thread_id=thread_id)
    print(f"\n[🔍] State after step 2:")
    print(f"    - scenario: {state2.values.get('scenario')}")
    print(f"    - product_order_info (main): {state2.values.get('product_order_info')}")
    print(f"    - awaiting_approval (main): {state2.values.get('awaiting_approval')}")
    print(f"    - next: {state2.next}")

    # Check subgraph state
    product_info = None
    if state2.tasks and len(state2.tasks) > 0:
        task = state2.tasks[0]
        print(f"\n[🔍] Subgraph task found: {task.name}")
        subgraph_state = workflow_graph.graph.get_state(task.state)
        if subgraph_state and subgraph_state.values:
            product_info = subgraph_state.values.get("product_order_info")
            print(f"    - product_order_info (subgraph): {product_info}")
    if product_info:
        print(f"\n[✅] MULTI-TURN PARSING SUCCESS!")
        print(f"    - Client: {product_info.client}")
        print(f"    - Product: {product_info.product_name}")
        print(f"    - Quantity: {product_info.quantity}")
        print(f"    - Unit price: {product_info.unit_price:,}원")
        return True
    else:
        print(f"\n[❌] MULTI-TURN PARSING FAILED")
        print(f"    Parsing error: {state2.values.get('parsing_error')}")
        return False


async def main():
    """Run all multi-turn tests"""
    print("\n" + "="*80)
    print("MULTI-TURN INPUT TESTS")
    print("="*80)

    results = []

    # Test 1: Delivery multi-turn
    try:
        result = await test_multiturn_delivery()
        results.append(("Delivery Multi-turn", result))
    except Exception as e:
        print(f"\n[❌] Delivery multi-turn test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        results.append(("Delivery Multi-turn", False))

    # Test 2: Product multi-turn
    try:
        result = await test_multiturn_product()
        results.append(("Product Multi-turn", result))
    except Exception as e:
        print(f"\n[❌] Product multi-turn test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        results.append(("Product Multi-turn", False))

    # Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)

    for test_name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {test_name}")

    all_passed = all(passed for _, passed in results)
    print("\n" + "="*80)
    if all_passed:
        print("🎉 ALL TESTS PASSED!")
    else:
        print("❌ SOME TESTS FAILED")
    print("="*80 + "\n")

    return all_passed


if __name__ == "__main__":
    asyncio.run(main())
