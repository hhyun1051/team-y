"""
알루미늄 중량 및 가격 계산기

8가지 계산 공식:
1. 원파이프 중량 계산
2. 평철 중량 계산
3. 찬넬 중량 계산
4. 사각파이프 중량 계산
5. 앵글 중량 계산
6. 봉 중량 계산
7. kg당 가격 계산
8. 단가 계산
"""

import math
from typing import Dict, Any


def calculate_round_pipe_weight(
    diameter: float,
    thickness: float,
    length: float,
    quantity: int,
    density: float = 2.7
) -> Dict[str, Any]:
    """
    원파이프 중량 계산

    공식: (지름-두께) x 두께 x 3.14 x 기장 x 수량 x 비중 / 1000 = 중량(kg)

    Args:
        diameter: 지름 (mm)
        thickness: 두께 (mm)
        length: 기장/길이 (m)
        quantity: 수량 (개)
        density: 비중 (기본값: 2.7 g/cm³)

    Returns:
        계산 결과 딕셔너리
    """
    weight = (diameter - thickness) * thickness * 3.14 * length * quantity * density / 1000

    return {
        "type": "원파이프",
        "specs": f"Ø{diameter}×{thickness}t",
        "length": length,
        "quantity": quantity,
        "density": density,
        "weight_kg": round(weight, 2),
        "formula": f"({diameter}-{thickness}) × {thickness} × 3.14 × {length} × {quantity} × {density} / 1000"
    }


def calculate_flat_bar_weight(
    width: float,
    thickness: float,
    density: float,
    length: float,
    quantity: int
) -> Dict[str, Any]:
    """
    평철 중량 계산

    공식: 폭 x 두께 x 비중 x 기장 x 수량 / 1000 = 중량(kg)

    Args:
        width: 폭 (mm)
        thickness: 두께 (mm)
        density: 비중 (g/cm³)
        length: 기장/길이 (m)
        quantity: 수량 (개)

    Returns:
        계산 결과 딕셔너리
    """
    weight = width * thickness * density * length * quantity / 1000

    return {
        "type": "평철",
        "specs": f"{width}×{thickness}t",
        "length": length,
        "quantity": quantity,
        "density": density,
        "weight_kg": round(weight, 2),
        "formula": f"{width} × {thickness} × {density} × {length} × {quantity} / 1000"
    }


def calculate_channel_weight(
    width: float,
    height: float,
    thickness: float,
    density: float,
    length: float,
    quantity: int
) -> Dict[str, Any]:
    """
    찬넬 중량 계산

    공식: ((가로+2×세로)-(2×두께)) x 두께 x 비중 x 기장 x 수량 / 1000 = 중량(kg)

    Args:
        width: 가로 (mm)
        height: 세로 (mm)
        thickness: 두께 (mm)
        density: 비중 (g/cm³)
        length: 기장/길이 (m)
        quantity: 수량 (개)

    Returns:
        계산 결과 딕셔너리
    """
    weight = ((width + 2 * height) - (2 * thickness)) * thickness * density * length * quantity / 1000

    return {
        "type": "찬넬",
        "specs": f"{width}×{height}×{thickness}t",
        "length": length,
        "quantity": quantity,
        "density": density,
        "weight_kg": round(weight, 2),
        "formula": f"(({width}+2×{height})-(2×{thickness})) × {thickness} × {density} × {length} × {quantity} / 1000"
    }


def calculate_square_pipe_weight(
    width: float,
    height: float,
    thickness: float,
    density: float,
    length: float,
    quantity: int
) -> Dict[str, Any]:
    """
    사각파이프 중량 계산

    공식: ((가로+세로)×2-4×두께) x 두께 x 비중 x 기장 x 수량 / 1000 = 중량(kg)

    Args:
        width: 가로 (mm)
        height: 세로 (mm)
        thickness: 두께 (mm)
        density: 비중 (g/cm³)
        length: 기장/길이 (m)
        quantity: 수량 (개)

    Returns:
        계산 결과 딕셔너리
    """
    weight = ((width + height) * 2 - 4 * thickness) * thickness * density * length * quantity / 1000

    return {
        "type": "사각파이프",
        "specs": f"{width}×{height}×{thickness}t",
        "length": length,
        "quantity": quantity,
        "density": density,
        "weight_kg": round(weight, 2),
        "formula": f"(({width}+{height})×2-4×{thickness}) × {thickness} × {density} × {length} × {quantity} / 1000"
    }


def calculate_angle_weight(
    width: float,
    height: float,
    thickness: float,
    density: float,
    length: float,
    quantity: int
) -> Dict[str, Any]:
    """
    앵글 중량 계산

    공식: (가로+세로-두께) x 두께 x 비중 x 기장 x 수량 / 1000 = 중량(kg)

    Args:
        width: 가로 (mm)
        height: 세로 (mm)
        thickness: 두께 (mm)
        density: 비중 (g/cm³)
        length: 기장/길이 (m)
        quantity: 수량 (개)

    Returns:
        계산 결과 딕셔너리
    """
    weight = (width + height - thickness) * thickness * density * length * quantity / 1000

    return {
        "type": "앵글",
        "specs": f"{width}×{height}×{thickness}t",
        "length": length,
        "quantity": quantity,
        "density": density,
        "weight_kg": round(weight, 2),
        "formula": f"({width}+{height}-{thickness}) × {thickness} × {density} × {length} × {quantity} / 1000"
    }


def calculate_round_bar_weight(
    diameter: float,
    density: float,
    length: float,
    quantity: int
) -> Dict[str, Any]:
    """
    봉 중량 계산

    공식: (지름/2)² x 3.14 x 비중 x 기장 x 수량 / 1000 = 중량(kg)

    Args:
        diameter: 지름 (mm)
        density: 비중 (g/cm³)
        length: 기장/길이 (m)
        quantity: 수량 (개)

    Returns:
        계산 결과 딕셔너리
    """
    radius = diameter / 2
    weight = (radius ** 2) * 3.14 * density * length * quantity / 1000

    return {
        "type": "봉",
        "specs": f"Ø{diameter}",
        "length": length,
        "quantity": quantity,
        "density": density,
        "weight_kg": round(weight, 2),
        "formula": f"({diameter}/2)² × 3.14 × {density} × {length} × {quantity} / 1000"
    }


def calculate_price_per_kg(
    unit_price: float,
    weight_per_unit: float
) -> Dict[str, Any]:
    """
    kg당 가격 계산

    공식: 제품 단가 / 개당 중량 = kg당 가격(원)

    Args:
        unit_price: 제품 단가 (원)
        weight_per_unit: 개당 중량 (kg)

    Returns:
        계산 결과 딕셔너리
    """
    if weight_per_unit <= 0:
        raise ValueError("개당 중량은 0보다 커야 합니다")

    price_per_kg = unit_price / weight_per_unit

    return {
        "type": "kg당 가격 계산",
        "unit_price": unit_price,
        "weight_per_unit": weight_per_unit,
        "price_per_kg": round(price_per_kg, 2),
        "formula": f"{unit_price} ÷ {weight_per_unit}"
    }


def calculate_unit_price(
    weight_per_unit: float,
    price_per_kg: float
) -> Dict[str, Any]:
    """
    단가 계산

    공식: 개당 중량 x kg당 가격 = 단가(원)

    Args:
        weight_per_unit: 개당 중량 (kg)
        price_per_kg: kg당 가격 (원)

    Returns:
        계산 결과 딕셔너리
    """
    unit_price = weight_per_unit * price_per_kg

    return {
        "type": "단가 계산",
        "weight_per_unit": weight_per_unit,
        "price_per_kg": price_per_kg,
        "unit_price": round(unit_price, 2),
        "formula": f"{weight_per_unit} × {price_per_kg}"
    }


def format_result(result: Dict[str, Any]) -> str:
    """
    계산 결과를 사용자에게 보여줄 형식으로 포맷팅

    Args:
        result: 계산 결과 딕셔너리

    Returns:
        포맷팅된 문자열
    """
    calc_type = result.get("type", "")

    # 중량 계산 결과
    if "weight_kg" in result:
        output = f"""✅ **{calc_type} 중량 계산**

📏 규격: {result['specs']}
📐 길이: {result['length']}m
🔢 수량: {result['quantity']}개
⚖️ 비중: {result['density']} g/cm³

**중량: {result['weight_kg']:.4f} kg**

계산식: {result['formula']}"""

    # kg당 가격 계산
    elif "price_per_kg" in result and "unit_price" in result:
        output = f"""✅ **kg당 가격 계산**

💰 제품 단가: ₩{result['unit_price']:,.0f}
⚖️ 개당 중량: {result['weight_per_unit']:.4f} kg

**kg당 가격: ₩{result['price_per_kg']:,.2f}**

계산식: {result['formula']}"""

    # 단가 계산
    elif "unit_price" in result and "weight_per_unit" in result:
        output = f"""✅ **단가 계산**

⚖️ 개당 중량: {result['weight_per_unit']:.4f} kg
💰 kg당 가격: ₩{result['price_per_kg']:,.2f}

**단가: ₩{result['unit_price']:,.2f}**

계산식: {result['formula']}"""

    else:
        output = str(result)

    return output
