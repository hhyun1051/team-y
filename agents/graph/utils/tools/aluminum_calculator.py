"""
알루미늄 제품 단가 계산 도구

다양한 형상의 알루미늄 제품(사각파이프, 원파이프, 앵글, 평철, 환봉, 찬넬)의
단면적, 중량, 단가를 계산합니다.
"""

import math
from typing import Tuple
from langchain_core.tools import tool


def calculate_square_pipe_area(width: float, height: float, thickness: float) -> float:
    """
    사각파이프 단면적 계산

    Args:
        width: 외경 폭 (mm)
        height: 외경 높이 (mm)
        thickness: 두께 (mm)

    Returns:
        단면적 (cm²)
    """
    outer_area = width * height
    inner_area = (width - 2 * thickness) * (height - 2 * thickness)
    area_mm2 = outer_area - inner_area
    return area_mm2 / 100  # mm² → cm²


def calculate_round_pipe_area(diameter: float, thickness: float) -> float:
    """
    원파이프 단면적 계산

    Args:
        diameter: 외경 (mm)
        thickness: 두께 (mm)

    Returns:
        단면적 (cm²)
    """
    outer_diameter = diameter
    inner_diameter = diameter - 2 * thickness
    area_mm2 = (math.pi / 4) * (outer_diameter**2 - inner_diameter**2)
    return area_mm2 / 100  # mm² → cm²


def calculate_angle_area(width_a: float, width_b: float, thickness: float) -> float:
    """
    앵글(ㄱ자) 단면적 계산

    Args:
        width_a: 폭 A (mm)
        width_b: 폭 B (mm)
        thickness: 두께 (mm)

    Returns:
        단면적 (cm²)
    """
    area_mm2 = (width_a * thickness) + (width_b * thickness) - (thickness * thickness)
    return area_mm2 / 100  # mm² → cm²


def calculate_flat_bar_area(width: float, thickness: float) -> float:
    """
    평철 단면적 계산

    Args:
        width: 폭 (mm)
        thickness: 두께 (mm)

    Returns:
        단면적 (cm²)
    """
    area_mm2 = width * thickness
    return area_mm2 / 100  # mm² → cm²


def calculate_round_bar_area(diameter: float) -> float:
    """
    환봉 단면적 계산

    Args:
        diameter: 지름 (mm)

    Returns:
        단면적 (cm²)
    """
    area_mm2 = math.pi * (diameter / 2) ** 2
    return area_mm2 / 100  # mm² → cm²


def calculate_channel_area(height: float, width: float, thickness: float) -> float:
    """
    찬넬(C형강) 단면적 계산 (간단 버전)

    Args:
        height: 웹 높이 (mm)
        width: 플랜지 폭 (mm)
        thickness: 두께 (mm)

    Returns:
        단면적 (cm²)
    """
    # 플랜지 2개 + 웹
    flange_area = width * thickness * 2
    web_area = (height - 2 * thickness) * thickness
    area_mm2 = flange_area + web_area
    return area_mm2 / 100  # mm² → cm²


def calculate_price_from_area(
    area_cm2: float,
    length_m: float,
    density: float,
    price_per_kg: int,
    quantity: int = 1
) -> Tuple[float, float, float]:
    """
    단면적으로부터 중량과 단가를 계산하는 공통 함수

    Args:
        area_cm2: 단면적 (cm²)
        length_m: 길이 (m)
        density: 비중 (g/cm³)
        price_per_kg: kg당 단가 (원)
        quantity: 수량 (개)

    Returns:
        (단위중량(kg), 단위가격(원), 총가격(원))
    """
    length_cm = length_m * 100
    unit_weight_kg = area_cm2 * length_cm * (density / 1000)
    unit_price = unit_weight_kg * price_per_kg
    total_price = unit_price * quantity
    return unit_weight_kg, unit_price, total_price


@tool
def calculate_aluminum_price_square_pipe(
    width: float,
    height: float,
    thickness: float,
    length_m: float,
    quantity: int = 1,
    density: float = 2.8,
    price_per_kg: int = 6000
) -> str:
    """
    사각파이프 알루미늄 단가를 계산합니다.

    Args:
        width: 외경 폭 (mm)
        height: 외경 높이 (mm)
        thickness: 두께 (mm)
        length_m: 길이 (m)
        quantity: 수량 (개, 기본값: 1)
        density: 비중 (기본값: 2.8 g/cm³)
        price_per_kg: kg당 단가 (원, 기본값: 6000원)

    Returns:
        계산 결과 문자열
    """
    area_cm2 = calculate_square_pipe_area(width, height, thickness)
    unit_weight, unit_price, total_price = calculate_price_from_area(
        area_cm2, length_m, density, price_per_kg, quantity
    )

    result = f"""📦 사각파이프 {width}×{height}×{thickness}t ({length_m}M)

• 단면적: {area_cm2:.2f} cm²
• 단위중량: {unit_weight:.2f} kg
• 단위가격: ₩{unit_price:,.0f}"""

    if quantity > 1:
        result += f"""
• 수량: {quantity}개
• 총 금액: ₩{total_price:,.0f}"""

    return result


@tool
def calculate_aluminum_price_round_pipe(
    diameter: float,
    thickness: float,
    length_m: float,
    quantity: int = 1,
    density: float = 2.8,
    price_per_kg: int = 6000
) -> str:
    """
    원파이프 알루미늄 단가를 계산합니다.

    Args:
        diameter: 외경 (mm)
        thickness: 두께 (mm)
        length_m: 길이 (m)
        quantity: 수량 (개, 기본값: 1)
        density: 비중 (기본값: 2.8 g/cm³)
        price_per_kg: kg당 단가 (원, 기본값: 6000원)

    Returns:
        계산 결과 문자열
    """
    area_cm2 = calculate_round_pipe_area(diameter, thickness)
    unit_weight, unit_price, total_price = calculate_price_from_area(
        area_cm2, length_m, density, price_per_kg, quantity
    )

    result = f"""⭕ 원파이프 Ø{diameter}×{thickness}t ({length_m}M)

• 단면적: {area_cm2:.2f} cm²
• 단위중량: {unit_weight:.2f} kg
• 단위가격: ₩{unit_price:,.0f}"""

    if quantity > 1:
        result += f"""
• 수량: {quantity}개
• 총 금액: ₩{total_price:,.0f}"""

    return result


@tool
def calculate_aluminum_price_angle(
    width_a: float,
    width_b: float,
    thickness: float,
    length_m: float,
    quantity: int = 1,
    density: float = 2.8,
    price_per_kg: int = 6000
) -> str:
    """
    앵글(ㄱ자) 알루미늄 단가를 계산합니다.

    Args:
        width_a: 폭 A (mm)
        width_b: 폭 B (mm)
        thickness: 두께 (mm)
        length_m: 길이 (m)
        quantity: 수량 (개, 기본값: 1)
        density: 비중 (기본값: 2.8 g/cm³)
        price_per_kg: kg당 단가 (원, 기본값: 6000원)

    Returns:
        계산 결과 문자열
    """
    area_cm2 = calculate_angle_area(width_a, width_b, thickness)
    unit_weight, unit_price, total_price = calculate_price_from_area(
        area_cm2, length_m, density, price_per_kg, quantity
    )

    result = f"""📐 앵글 {width_a}×{width_b}×{thickness}t ({length_m}M)

• 단면적: {area_cm2:.2f} cm²
• 단위중량: {unit_weight:.2f} kg
• 단위가격: ₩{unit_price:,.0f}"""

    if quantity > 1:
        result += f"""
• 수량: {quantity}개
• 총 금액: ₩{total_price:,.0f}"""

    return result


@tool
def calculate_aluminum_price_flat_bar(
    width: float,
    thickness: float,
    length_m: float,
    quantity: int = 1,
    density: float = 2.8,
    price_per_kg: int = 6000
) -> str:
    """
    평철 알루미늄 단가를 계산합니다.

    Args:
        width: 폭 (mm)
        thickness: 두께 (mm)
        length_m: 길이 (m)
        quantity: 수량 (개, 기본값: 1)
        density: 비중 (기본값: 2.8 g/cm³)
        price_per_kg: kg당 단가 (원, 기본값: 6000원)

    Returns:
        계산 결과 문자열
    """
    area_cm2 = calculate_flat_bar_area(width, thickness)
    unit_weight, unit_price, total_price = calculate_price_from_area(
        area_cm2, length_m, density, price_per_kg, quantity
    )

    result = f"""▬ 평철 {width}×{thickness}t ({length_m}M)

• 단면적: {area_cm2:.2f} cm²
• 단위중량: {unit_weight:.2f} kg
• 단위가격: ₩{unit_price:,.0f}"""

    if quantity > 1:
        result += f"""
• 수량: {quantity}개
• 총 금액: ₩{total_price:,.0f}"""

    return result


@tool
def calculate_aluminum_price_round_bar(
    diameter: float,
    length_m: float,
    quantity: int = 1,
    density: float = 2.8,
    price_per_kg: int = 6000
) -> str:
    """
    환봉 알루미늄 단가를 계산합니다.

    Args:
        diameter: 지름 (mm)
        length_m: 길이 (m)
        quantity: 수량 (개, 기본값: 1)
        density: 비중 (기본값: 2.8 g/cm³)
        price_per_kg: kg당 단가 (원, 기본값: 6000원)

    Returns:
        계산 결과 문자열
    """
    area_cm2 = calculate_round_bar_area(diameter)
    unit_weight, unit_price, total_price = calculate_price_from_area(
        area_cm2, length_m, density, price_per_kg, quantity
    )

    result = f"""● 환봉 Ø{diameter} ({length_m}M)

• 단면적: {area_cm2:.2f} cm²
• 단위중량: {unit_weight:.2f} kg
• 단위가격: ₩{unit_price:,.0f}"""

    if quantity > 1:
        result += f"""
• 수량: {quantity}개
• 총 금액: ₩{total_price:,.0f}"""

    return result


@tool
def calculate_aluminum_price_channel(
    height: float,
    width: float,
    thickness: float,
    length_m: float,
    quantity: int = 1,
    density: float = 2.8,
    price_per_kg: int = 6000
) -> str:
    """
    찬넬(C형강) 알루미늄 단가를 계산합니다.

    Args:
        height: 웹 높이 (mm)
        width: 플랜지 폭 (mm)
        thickness: 두께 (mm)
        length_m: 길이 (m)
        quantity: 수량 (개, 기본값: 1)
        density: 비중 (기본값: 2.8 g/cm³)
        price_per_kg: kg당 단가 (원, 기본값: 6000원)

    Returns:
        계산 결과 문자열
    """
    area_cm2 = calculate_channel_area(height, width, thickness)
    unit_weight, unit_price, total_price = calculate_price_from_area(
        area_cm2, length_m, density, price_per_kg, quantity
    )

    result = f"""🔲 찬넬 {height}H×{width}W×{thickness}t ({length_m}M)

• 단면적: {area_cm2:.2f} cm²
• 단위중량: {unit_weight:.2f} kg
• 단위가격: ₩{unit_price:,.0f}"""

    if quantity > 1:
        result += f"""
• 수량: {quantity}개
• 총 금액: ₩{total_price:,.0f}"""

    return result


@tool
def calculate_price_from_weight_and_price_per_kg(
    weight_kg: float,
    price_per_kg: float,
    quantity: int = 1
) -> str:
    """
    개당 중량과 kg당 가격으로 1개당 가격을 계산합니다.

    계산식: 1개당 가격 = 개당 중량(kg) × kg당 가격(원)

    Args:
        weight_kg: 개당 중량 (kg)
        price_per_kg: kg당 가격 (원)
        quantity: 수량 (개, 기본값: 1)

    Returns:
        계산 결과 문자열
    """
    unit_price = weight_kg * price_per_kg
    total_price = unit_price * quantity

    result = f"""💰 가격 계산 (개당 중량 × kg당 가격)

• 개당 중량: {weight_kg:.2f} kg
• kg당 가격: ₩{price_per_kg:,.0f}
• 1개당 가격: ₩{unit_price:,.0f}"""

    if quantity > 1:
        result += f"""
• 수량: {quantity}개
• 총 금액: ₩{total_price:,.0f}"""

    return result


@tool
def calculate_price_per_kg_from_unit_price_and_weight(
    unit_price: float,
    weight_kg: float
) -> str:
    """
    제품 단가와 개당 중량으로 kg당 가격을 계산합니다.

    계산식: kg당 가격 = 제품 단가(원) ÷ 개당 중량(kg)

    Args:
        unit_price: 제품 단가 (원)
        weight_kg: 개당 중량 (kg)

    Returns:
        계산 결과 문자열
    """
    if weight_kg <= 0:
        return "❌ 오류: 중량은 0보다 커야 합니다."

    price_per_kg = unit_price / weight_kg

    result = f"""💰 kg당 가격 계산 (제품 단가 ÷ 개당 중량)

• 제품 단가: ₩{unit_price:,.0f}
• 개당 중량: {weight_kg:.2f} kg
• kg당 가격: ₩{price_per_kg:,.0f}"""

    return result
