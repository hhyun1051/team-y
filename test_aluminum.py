"""
알루미늄 계산 멀티턴 테스트

시나리오 1: 완전한 정보 입력 (단일턴)
시나리오 2: 불완전한 정보 → 추가 입력 (멀티턴)
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from agents.graph.graph import OfficeAutomationGraph


def test_aluminum_single_turn():
    """시나리오 1: 완전한 정보로 단일턴 계산"""
    print("\n" + "="*80)
    print("TEST 1: 알루미늄 계산 - 단일턴 (완전한 정보)")
    print("="*80)

    workflow_graph = OfficeAutomationGraph(
        model_name="gpt-4o-mini",
        temperature=0.0,
        use_langfuse=False
    )

    # 완전한 정보 입력: 원파이프 50mm 두께 3t 길이 6m 10개
    user_input = "원파이프 50x3t 6m 10개"

    result = workflow_graph.invoke(
        raw_input=user_input,
        input_type="text",
        thread_id="test_aluminum_single"
    )

    print(f"\n[결과] Messages:")
    for msg in result.get("messages", []):
        print(f"  - {msg.content[:200]}")

    print(f"\n[상태] aluminum_calculation_info: {result.get('aluminum_calculation_info')}")
    print(f"[상태] parsing_error: {result.get('parsing_error')}")
    print(f"[상태] active_scenario: {result.get('active_scenario')}")

    assert result.get("aluminum_calculation_info") is not None, "알루미늄 정보 파싱 실패"
    assert result.get("parsing_error") is None, "파싱 에러 발생"
    print("\n✅ Test 1 passed: 단일턴 계산 성공")


def test_aluminum_multi_turn():
    """시나리오 2: 불완전한 정보 → 멀티턴"""
    print("\n" + "="*80)
    print("TEST 2: 알루미늄 계산 - 멀티턴 (불완전한 정보)")
    print("="*80)

    workflow_graph = OfficeAutomationGraph(
        model_name="gpt-4o-mini",
        temperature=0.0,
        use_langfuse=False
    )

    thread_id = "test_aluminum_multi"

    # 첫 번째 입력: 두께 누락
    print("\n[입력 1] 원파이프 50 6m")
    result1 = workflow_graph.invoke(
        raw_input="원파이프 50 6m",
        input_type="text",
        thread_id=thread_id
    )

    print(f"\n[결과 1] Messages:")
    for msg in result1.get("messages", []):
        print(f"  - {msg.content[:200]}")

    print(f"\n[상태 1] parsing_error: {result1.get('parsing_error')}")
    print(f"[상태 1] active_scenario: {result1.get('active_scenario')}")

    # 파싱 실패 확인
    assert result1.get("parsing_error") is not None, "파싱 에러가 없음 (있어야 함)"
    assert result1.get("active_scenario") == "aluminum_calculation", "시나리오 잠금 실패"

    # 두 번째 입력: 두께 추가
    print("\n[입력 2] 두께 3t")
    result2 = workflow_graph.invoke(
        raw_input="두께 3t",
        input_type="text",
        thread_id=thread_id
    )

    print(f"\n[결과 2] Messages:")
    for msg in result2.get("messages", [])[-3:]:  # 마지막 3개만
        print(f"  - {msg.content[:200]}")

    print(f"\n[상태 2] aluminum_calculation_info: {result2.get('aluminum_calculation_info')}")
    print(f"[상태 2] parsing_error: {result2.get('parsing_error')}")
    print(f"[상태 2] active_scenario: {result2.get('active_scenario')}")

    # 파싱 성공 및 계산 완료 확인
    assert result2.get("aluminum_calculation_info") is not None, "알루미늄 정보 파싱 실패"
    assert result2.get("parsing_error") is None, "파싱 에러 발생"
    assert result2.get("active_scenario") is None, "시나리오 잠금 해제 실패"

    print("\n✅ Test 2 passed: 멀티턴 계산 성공")


def test_aluminum_angle():
    """시나리오 3: 앵글 계산"""
    print("\n" + "="*80)
    print("TEST 3: 알루미늄 계산 - 앵글")
    print("="*80)

    workflow_graph = OfficeAutomationGraph(
        model_name="gpt-4o-mini",
        temperature=0.0,
        use_langfuse=False
    )

    user_input = "앵글 40x40x3t 5m 20개"

    result = workflow_graph.invoke(
        raw_input=user_input,
        input_type="text",
        thread_id="test_aluminum_angle"
    )

    print(f"\n[결과] Messages:")
    for msg in result.get("messages", []):
        print(f"  - {msg.content[:300]}")

    assert result.get("aluminum_calculation_info") is not None, "앵글 정보 파싱 실패"
    assert result.get("aluminum_calculation_info").product_type == "angle", "제품 타입 불일치"
    print("\n✅ Test 3 passed: 앵글 계산 성공")


if __name__ == "__main__":
    try:
        test_aluminum_single_turn()
        test_aluminum_multi_turn()
        test_aluminum_angle()
        print("\n" + "="*80)
        print("✅ ALL TESTS PASSED")
        print("="*80)
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ UNEXPECTED ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
