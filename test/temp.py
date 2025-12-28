"""
맥북에서 Windows ERP API 테스트용 클라이언트
인터랙티브하게 함수 하나씩 실행하면서 테스트
"""

import httpx

# Windows 서버 주소 (본인 환경에 맞게 수정)
BASE_URL = "http://localhost:8011"  # ← 여기에 Windows 서버 IP 입력!


def health_check():
    """서버 상태 확인"""
    print("\n=== Health Check ===")
    try:
        r = httpx.get(f"{BASE_URL}/health", timeout=10)
        print(f"Status Code: {r.status_code}")
        print(f"Response: {r.json()}")
        return r.json()
    except Exception as e:
        print(f"Error: {e}")
        return None


def get_menu_status():
    """현재 활성화된 메뉴 버튼 확인"""
    print("\n=== 현재 메뉴 상태 확인 ===")
    try:
        r = httpx.get(f"{BASE_URL}/menu/status", timeout=30)
        print(f"Status Code: {r.status_code}")
        data = r.json()
        print(f"Active Button: {data.get('active_button')}")
        print(f"Message: {data.get('message')}")
        print(f"Success: {data.get('success')}")
        return data
    except Exception as e:
        print(f"Error: {e}")
        return None


def click_button(button_name: str):
    """버튼 클릭 (거래 또는 기초)"""
    print(f"\n=== '{button_name}' 버튼 클릭 ===")
    try:
        r = httpx.post(
            f"{BASE_URL}/menu/click",
            json={"button_name": button_name},
            timeout=30
        )
        print(f"Status Code: {r.status_code}")
        data = r.json()
        print(f"Clicked: {data.get('clicked_button')}")
        print(f"Current Active: {data.get('current_active_button')}")
        print(f"Message: {data.get('message')}")
        print(f"Success: {data.get('success')}")
        return data
    except Exception as e:
        print(f"Error: {e}")
        return None


def debug_locate(button_name: str):
    """버튼 위치 디버깅"""
    print(f"\n=== '{button_name}' 버튼 위치 찾기 ===")
    try:
        r = httpx.get(f"{BASE_URL}/debug/locate/{button_name}", timeout=30)
        print(f"Status Code: {r.status_code}")
        data = r.json()
        print(f"Confidence: {data.get('confidence')}")
        for state, result in data.get('results', {}).items():
            print(f"  [{state}] found={result.get('found')}", end="")
            if result.get('found'):
                print(f" center={result.get('center')}")
            else:
                print(f" error={result.get('error')}")
        return data
    except Exception as e:
        print(f"Error: {e}")
        return None


def interactive_menu():
    """인터랙티브 메뉴"""
    print("\n" + "=" * 50)
    print("ERP Automation Test Client")
    print(f"Server: {BASE_URL}")
    print("=" * 50)
    
    while True:
        print("\n[메뉴]")
        print("1. Health Check (서버 상태)")
        print("2. 현재 메뉴 상태 확인")
        print("3. '거래' 버튼 클릭")
        print("4. '기초' 버튼 클릭")
        print("5. '거래' 버튼 위치 디버그")
        print("6. '기초' 버튼 위치 디버그")
        print("q. 종료")
        
        choice = input("\n선택: ").strip()
        
        if choice == "1":
            health_check()
        elif choice == "2":
            get_menu_status()
        elif choice == "3":
            click_button("거래")
        elif choice == "4":
            click_button("기초")
        elif choice == "5":
            debug_locate("거래")
        elif choice == "6":
            debug_locate("기초")
        elif choice.lower() == "q":
            print("종료합니다.")
            break
        else:
            print("잘못된 선택입니다.")


if __name__ == "__main__":
    # 서버 IP 설정 안내
    if "xxx" in BASE_URL:
        print("!" * 50)
        print("먼저 BASE_URL을 수정하세요!")
        print("파일 상단의 BASE_URL에 Windows 서버 IP를 입력하세요.")
        print("예: BASE_URL = \"http://192.168.0.100:8000\"")
        print("!" * 50)
        
        ip = input("\nWindows 서버 IP 입력 (예: 192.168.0.100): ").strip()
        if ip:
            BASE_URL = f"http://{ip}:8000"
    
    interactive_menu()