"""
Discord Bot Main Entry Point

디스코드 봇으로 사무 자동화를 처리하는 메인 파일
- LangGraph 기반 workflow
- Human-in-the-loop 처리
"""

import os
import sys
import asyncio
import discord
from discord.ext import commands
from dotenv import load_dotenv
from pathlib import Path
import re
from typing import Optional, Dict, Any

# 프로젝트 루트를 sys.path에 추가
sys.path.insert(0, str(Path(__file__).parent.parent))

# 환경 변수 로드
load_dotenv()

# 워크플로우 임포트
from agents import OfficeAutomationGraph

# 봇 설정
intents = discord.Intents.default()
intents.message_content = True
intents.messages = True
intents.guilds = True
bot = commands.Bot(command_prefix="!", intents=intents)

# 워크플로우 그래프 (전역)
workflow_graph: Optional[OfficeAutomationGraph] = None

# 전역 상태 관리
active_sessions: Dict[str, bool] = {}  # thread_id -> awaiting_approval 매핑
user_sessions: Dict[str, str] = {}  # user_channel_key -> current_thread_id 매핑


# HITL 승인 UI 버튼
class ApprovalView(discord.ui.View):
    """승인/거절/편집 버튼 UI"""

    def __init__(self, thread_id: str, original_data: Dict[str, Any] = None, timeout: float = 300):
        super().__init__(timeout=timeout)
        self.thread_id = thread_id
        self.original_data = original_data or {}  # 원래 데이터 저장
        self.decision = None
        self.edited_text = None

        # 사업자등록증인 경우 승인 버튼 제거 (편집 필수)
        scenario = original_data.get("scenario") if original_data else None
        if scenario == "business_registration":
            # 승인 버튼 제거 - children에서 찾아서 제거
            self.remove_item(self.approve_button)

    @discord.ui.button(label="✅ 승인", style=discord.ButtonStyle.success, custom_id="approve")
    async def approve_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """승인 버튼"""
        self.decision = "approve"

        # 버튼 비활성화
        for item in self.children:
            item.disabled = True

        await interaction.response.edit_message(view=self)
        await interaction.followup.send("🔄 승인 처리 중...", ephemeral=False)

        # 워크플로우 재개
        await self._resume_workflow(interaction, "approve")

    @discord.ui.button(label="❌ 거절", style=discord.ButtonStyle.danger, custom_id="reject")
    async def reject_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """거절 버튼"""
        self.decision = "reject"

        # 버튼 비활성화
        for item in self.children:
            item.disabled = True

        await interaction.response.edit_message(view=self)
        await interaction.followup.send("❌ 거절되었습니다.", ephemeral=False)

        # 워크플로우 재개
        await self._resume_workflow(interaction, "reject", reject_message="사용자가 거절했습니다.")

    @discord.ui.button(label="✏️ 편집", style=discord.ButtonStyle.primary, custom_id="edit")
    async def edit_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """편집 버튼 - Modal 띄우기"""
        modal = EditModal(self.thread_id, self)
        await interaction.response.send_modal(modal)

    async def _resume_workflow(
        self,
        interaction: discord.Interaction,
        decision_type: str,
        reject_message: Optional[str] = None
    ):
        """워크플로우 재개 (승인/거절만, 편집은 직접 처리)"""
        global workflow_graph

        try:
            loop = asyncio.get_event_loop()
            print(f"[🔄] Calling resume with decision_type={decision_type}", flush=True)
            try:
                result = await asyncio.wait_for(
                    loop.run_in_executor(
                        None,
                        lambda: workflow_graph.resume(
                            decision_type=decision_type,
                            reject_message=reject_message,
                            thread_id=self.thread_id
                        )
                    ),
                    timeout=120.0  # 120초 타임아웃
                )
                print(f"[✅] Resume completed, result type: {type(result)}", flush=True)
            except asyncio.TimeoutError:
                print(f"[⏰] Resume timed out after 120 seconds!", flush=True)
                await interaction.channel.send("⏰ 처리 시간 초과 (120초)")
                active_sessions.pop(self.thread_id, None)
                return

            print(f"[🔍] Resume result keys: {result.keys() if isinstance(result, dict) else 'not a dict'}", flush=True)

            # 추가 interrupt 체크 (인쇄 승인)
            state_after_resume = workflow_graph.get_state(thread_id=self.thread_id)
            print(f"[🔍] state_after_resume: next={state_after_resume.next if state_after_resume else None}")

            if state_after_resume and state_after_resume.next:
                print(f"[⏸️] Another interrupt detected after resume: next={state_after_resume.next}")
                print(f"[🔍] Tasks count: {len(state_after_resume.tasks) if state_after_resume.tasks else 0}")

                # Subgraph state 접근
                subgraph_state_values = None
                if state_after_resume.tasks and len(state_after_resume.tasks) > 0:
                    task = state_after_resume.tasks[0]
                    print(f"[🔍] Task name: {task.name}, has state: {task.state is not None}")

                    if task.state:
                        try:
                            subgraph_state = workflow_graph.graph.get_state(task.state)
                            print(f"[🔍] Subgraph state retrieved: {subgraph_state is not None}")

                            if subgraph_state and subgraph_state.values:
                                subgraph_state_values = subgraph_state.values
                                print(f"[✅] Subgraph state after resume: {list(subgraph_state_values.keys())}")
                                print(f"[🔍] pdf_path in subgraph: {subgraph_state_values.get('pdf_path')}")
                                print(f"[🔍] image_paths in subgraph: {len(subgraph_state_values.get('image_paths', []))} images")
                        except Exception as e:
                            print(f"[⚠️] Failed to get subgraph state: {e}")
                            import traceback
                            traceback.print_exc()

                # 인쇄 승인 체크
                if subgraph_state_values and subgraph_state_values.get("awaiting_print_approval"):
                    print(f"[🖨️] Print approval interrupt detected")
                    approval_msg = subgraph_state_values.get("print_approval_message", "🖨️ 인쇄하시겠습니까?")

                    # PrintApprovalView 표시
                    print_view = PrintApprovalView(thread_id=self.thread_id)
                    active_sessions[self.thread_id] = True

                    # 먼저 문서 생성 메시지와 파일 전송
                    if "messages" in result and result["messages"]:
                        latest_msg = result["messages"][-1]
                        if isinstance(latest_msg, dict):
                            message_content = latest_msg.get("content", "")
                        else:
                            message_content = getattr(latest_msg, "content", "")

                        if message_content:
                            await interaction.channel.send(message_content)

                    # 이미지 파일 전송 (subgraph state에서)
                    if subgraph_state_values.get("image_paths"):
                        image_paths = [Path(p) for p in subgraph_state_values["image_paths"]]
                        for img_path in image_paths:
                            if img_path.exists():
                                print(f"[📤] Sending image file: {img_path}")
                                await interaction.channel.send(file=discord.File(str(img_path)))

                    # PDF 파일 전송 (subgraph state에서)
                    if subgraph_state_values.get("pdf_path"):
                        pdf_path = Path(subgraph_state_values["pdf_path"])
                        if pdf_path.exists():
                            print(f"[📤] Sending PDF file: {pdf_path}")
                            await interaction.channel.send(file=discord.File(str(pdf_path)))

                    # 인쇄 승인 UI 표시
                    await interaction.channel.send(approval_msg, view=print_view)
                    print(f"[✅] Print approval request sent")
                    return

            # 세션 정리 (더 이상 interrupt 없음)
            active_sessions.pop(self.thread_id, None)

            # 최종 메시지 전송 및 PDF 파일 추출
            message_content = ""
            pdf_path = None
            image_paths = []

            # PDF 경로를 result에서 직접 가져오기 (더 신뢰성 있음)
            if "pdf_path" in result and result["pdf_path"]:
                pdf_path = Path(result["pdf_path"])
                print(f"[📄] Found PDF path in result: {pdf_path}")

            # 이미지 경로 가져오기
            if "image_paths" in result and result["image_paths"]:
                image_paths = [Path(p) for p in result["image_paths"]]
                print(f"[🖼️] Found {len(image_paths)} image(s) in result")

            if "messages" in result and result["messages"]:
                latest_msg = result["messages"][-1]
                # 메시지가 dict 또는 object일 수 있음
                if isinstance(latest_msg, dict):
                    message_content = latest_msg.get("content", "")
                else:
                    message_content = getattr(latest_msg, "content", "")

                if message_content:
                    await interaction.channel.send(message_content)
                else:
                    await interaction.channel.send("✅ 처리 완료")
            else:
                await interaction.channel.send("✅ 처리 완료")

            # 이미지 파일 전송 (미리보기)
            if image_paths:
                for img_path in image_paths:
                    if img_path.exists():
                        print(f"[📤] Sending image file: {img_path}")
                        await interaction.channel.send(file=discord.File(str(img_path)))
                    else:
                        print(f"[⚠️] Image file not found: {img_path}")

            # PDF 파일 전송
            if pdf_path and pdf_path.exists():
                print(f"[📤] Sending PDF file: {pdf_path}")
                await interaction.channel.send(file=discord.File(str(pdf_path)))
            elif pdf_path:
                print(f"[⚠️] PDF file not found: {pdf_path}")
            else:
                print(f"[⚠️] No PDF path found in result")

        except Exception as e:
            await interaction.channel.send(f"❌ 재개 실패: {str(e)}")
            active_sessions.pop(self.thread_id, None)
            import traceback
            traceback.print_exc()


class EditModal(discord.ui.Modal, title="정보 편집"):
    """편집 모달"""

    def __init__(self, thread_id: str, view: ApprovalView):
        super().__init__()
        self.thread_id = thread_id
        self.approval_view = view

        # 원래 데이터로 placeholder 생성
        original_data = view.original_data
        if 'unloading_site' in original_data:
            # Delivery 정보 (새 스키마)
            placeholder_text = f"하차지: {original_data.get('unloading_site', '')}\n주소: {original_data.get('address', '')}\n연락처: {original_data.get('contact', '')}"
            placeholder_text += f"\n상차지: {original_data.get('loading_site', '유진알루미늄')}"
            if original_data.get('loading_address'):
                placeholder_text += f"\n상차지주소: {original_data.get('loading_address')}"
            if original_data.get('loading_phone'):
                placeholder_text += f"\n상차지전화: {original_data.get('loading_phone')}"
            placeholder_text += f"\n지불방법: {original_data.get('payment_type', '선불')}"
            if original_data.get('freight_cost'):
                placeholder_text += f"\n운송비: {original_data.get('freight_cost')}"
        elif 'client' in original_data:
            # Product 정보
            placeholder_text = f"거래처: {original_data.get('client', '')}\n품목: {original_data.get('product_name', '')}\n수량: {original_data.get('quantity', '')}\n단가: {original_data.get('unit_price', '')}"
        elif 'business_name' in original_data:
            # Business Registration 정보 (전체 필드)
            # None 값을 빈 문자열로 변환 (placeholder에서 "None" 문자열 표시 방지)
            def fmt(val):
                return val if val is not None else ''

            placeholder_text = f"거래처명: {fmt(original_data.get('client_name'))}\n상호: {fmt(original_data.get('business_name'))}"
            placeholder_text += f"\n대표자명: {fmt(original_data.get('representative_name'))}\n사업자번호: {fmt(original_data.get('business_number'))}"
            placeholder_text += f"\n종사업자번호: {fmt(original_data.get('branch_number'))}\n우편번호: {fmt(original_data.get('postal_code'))}"
            placeholder_text += f"\n주소1: {fmt(original_data.get('address1'))}\n주소2: {fmt(original_data.get('address2'))}"
            placeholder_text += f"\n업태: {fmt(original_data.get('business_type'))}\n종목: {fmt(original_data.get('business_item'))}"
            placeholder_text += f"\n전화1: {fmt(original_data.get('phone1'))}\n전화2: {fmt(original_data.get('phone2'))}"
            placeholder_text += f"\n팩스: {fmt(original_data.get('fax'))}"
            placeholder_text += f"\n담당자1: {fmt(original_data.get('contact_person1'))}\n휴대폰1: {fmt(original_data.get('mobile1'))}"
            placeholder_text += f"\n담당자2: {fmt(original_data.get('contact_person2'))}\n휴대폰2: {fmt(original_data.get('mobile2'))}"
            placeholder_text += f"\n거래처구분: {fmt(original_data.get('client_type'))}\n출고가등급: {fmt(original_data.get('price_grade'))}"
            placeholder_text += f"\n기초잔액: {original_data.get('initial_balance', 0)}\n적정잔액: {original_data.get('optimal_balance', 0)}"
            placeholder_text += f"\n메모: {fmt(original_data.get('memo'))}"
        else:
            placeholder_text = "예: 하차지: 삼성전자\n주소: 서울시 강남구\n연락처: 010-1234-5678\n상차지: 유진알루미늄\n지불방법: 착불"

        # 편집 입력 필드
        self.edited_info = discord.ui.TextInput(
            label="수정된 정보를 입력하세요",
            style=discord.TextStyle.paragraph,
            placeholder=placeholder_text[:100],  # Discord placeholder 길이 제한
            default=placeholder_text,  # 기본값으로 원래 데이터 표시
            required=True,
            max_length=1000,
        )
        self.add_item(self.edited_info)

    async def on_submit(self, interaction: discord.Interaction):
        """모달 제출"""
        edited_text = self.edited_info.value

        # 버튼 비활성화
        for item in self.approval_view.children:
            item.disabled = True

        await interaction.response.edit_message(view=self.approval_view)
        await interaction.followup.send(f"🔄 편집된 정보로 처리 중...\n```\n{edited_text}\n```", ephemeral=False)

        # 시나리오 확인 (state에서 이미 기록됨)
        scenario = self.approval_view.original_data.get("scenario")
        print(f"[📝] Scenario from original_data: {scenario}")

        # 편집된 텍스트 파싱 (간단한 key: value 형식)
        edited_data = {}
        for line in edited_text.split('\n'):
            line = line.strip()
            if ':' in line:
                key, value = line.split(':', 1)
                key = key.strip().lower()
                value = value.strip()

                # 빈 값 또는 "None", "N/A" 문자열은 건너뛰기 (원본 값 유지)
                if not value or value.strip().lower() in ['none', 'n/a']:
                    continue  # 이 필드는 건너뛰고 원본 값 유지

                # 시나리오별 키 매핑
                if scenario == "delivery":
                    # Delivery 키 매핑 (if 문 유지 - 한 라인에 여러 조건 매칭 가능)
                    if '하차지' in key or 'unloading' in key:
                        edited_data['unloading_site'] = value
                    if '주소' in key and '상차지' not in key:
                        edited_data['address'] = value
                    if '연락처' in key or 'contact' in key:
                        edited_data['contact'] = value
                    if '상차지' in key and '주소' not in key and '전화' not in key:
                        edited_data['loading_site'] = value
                    if '상차지주소' in key or 'loading_address' in key:
                        edited_data['loading_address'] = value
                    if '상차지전화' in key or 'loading_phone' in key:
                        edited_data['loading_phone'] = value
                    if '지불방법' in key or 'payment' in key:
                        if value and '착불' in value:
                            edited_data['payment_type'] = '착불'
                        elif value and '선불' in value:
                            edited_data['payment_type'] = '선불'
                    if '운송비' in key or 'freight' in key:
                        if value:
                            numbers = re.findall(r'\d+', value.replace(',', ''))
                            if numbers:
                                edited_data['freight_cost'] = int(numbers[0])

                elif scenario == "product_order":
                    # Product 키 매핑
                    if '거래처' in key or 'client' in key:
                        edited_data['client'] = value
                    elif '품목' in key or 'product' in key:
                        edited_data['product_name'] = value
                    elif '수량' in key or 'quantity' in key:
                        if value:
                            numbers = re.findall(r'\d+', value)
                            if numbers:
                                edited_data['quantity'] = int(numbers[0])
                    elif '단가' in key or 'unit_price' in key or 'price' in key:
                        if value:
                            numbers = re.findall(r'\d+', value.replace(',', ''))
                            if numbers:
                                edited_data['unit_price'] = int(numbers[0])

                elif scenario == "business_registration":
                    # Business Registration 키 매핑 (elif로 변경하여 중복 매칭 방지)
                    if '거래처명' in key or 'client_name' in key:
                        edited_data['client_name'] = value
                    elif '상호' in key or 'business_name' in key:
                        edited_data['business_name'] = value
                    elif '대표자' in key or 'representative' in key:
                        edited_data['representative_name'] = value
                    elif '사업자번호' in key or 'business_number' in key:
                        edited_data['business_number'] = value
                    elif '종사업자번호' in key or 'branch_number' in key:
                        edited_data['branch_number'] = value
                    elif '우편번호' in key or 'postal' in key:
                        edited_data['postal_code'] = value
                    elif '주소1' in key or 'address1' in key:
                        edited_data['address1'] = value
                    elif '주소2' in key or 'address2' in key:
                        edited_data['address2'] = value
                    elif '업태' in key or 'business_type' in key:
                        edited_data['business_type'] = value
                    elif '종목' in key or 'business_item' in key:
                        edited_data['business_item'] = value
                    elif '전화1' in key or 'phone1' in key:
                        edited_data['phone1'] = value
                    elif '전화2' in key or 'phone2' in key:
                        edited_data['phone2'] = value
                    elif '팩스' in key or 'fax' in key:
                        edited_data['fax'] = value
                    elif '담당자1' in key or 'contact_person1' in key:
                        edited_data['contact_person1'] = value
                    elif '휴대폰1' in key or 'mobile1' in key:
                        edited_data['mobile1'] = value
                    elif '담당자2' in key or 'contact_person2' in key:
                        edited_data['contact_person2'] = value
                    elif '휴대폰2' in key or 'mobile2' in key:
                        edited_data['mobile2'] = value
                    elif '거래처구분' in key or 'client_type' in key:
                        edited_data['client_type'] = value
                    elif '출고가등급' in key or 'price_grade' in key:
                        edited_data['price_grade'] = value
                    elif '기초잔액' in key or 'initial_balance' in key:
                        if value:
                            numbers = re.findall(r'\d+', value.replace(',', ''))
                            if numbers:
                                edited_data['initial_balance'] = int(numbers[0])
                    elif '적정잔액' in key or 'optimal_balance' in key:
                        if value:
                            numbers = re.findall(r'\d+', value.replace(',', ''))
                            if numbers:
                                edited_data['optimal_balance'] = int(numbers[0])
                    elif '메모' in key or 'memo' in key:
                        edited_data['memo'] = value

        print(f"[📝] Parsed edited data: {edited_data}")

        # 시나리오별 처리
        try:
            from agents.graph.utils.document_generator import DocumentGenerator
            from pathlib import Path

            # business_registration은 워크플로우를 통해 DB 저장
            if scenario == "business_registration":
                # BusinessRegistrationInfo 객체 재생성 (편집된 데이터로)
                from agents.graph.state import BusinessRegistrationInfo

                # 먼저 기존 state에서 원본 데이터 가져오기
                config = {"configurable": {"thread_id": self.approval_view.thread_id}}
                state = workflow_graph.get_state(thread_id=self.approval_view.thread_id)

                # 원본 데이터와 편집된 데이터 병합 (edited_data가 우선)
                original_info = self.approval_view.original_data.copy()
                original_info.pop('scenario', None)  # scenario 필드 제거
                merged_data = {**original_info, **edited_data}  # 편집된 필드만 덮어씀

                print(f"[🔧] Original data fields: {list(original_info.keys())}")
                print(f"[🔧] Edited data fields: {list(edited_data.keys())}")
                print(f"[🔧] Merged data business_number: {merged_data.get('business_number')}")

                # 병합된 데이터로 BusinessRegistrationInfo 생성
                updated_info = BusinessRegistrationInfo(**merged_data)

                if state and state.tasks and len(state.tasks) > 0:
                    task = state.tasks[0]
                    print(f"[🔧] Updating business_registration_info with edited data")

                    # Subgraph state 업데이트
                    workflow_graph.graph.update_state(
                        task.state,
                        {
                            "business_registration_info": updated_info,
                            "approval_decision": "approve"  # 편집 완료 = 승인
                        }
                    )
                    print(f"[✅] State updated, resuming workflow...")

                # 워크플로우 재개 (save 노드 실행 → DB 저장)
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(
                    None,
                    lambda: workflow_graph.graph.invoke(None, config)
                )

                # 결과 메시지 전송
                if "messages" in result and result["messages"]:
                    latest_msg = result["messages"][-1]
                    if isinstance(latest_msg, dict):
                        message_content = latest_msg.get("content", "")
                    else:
                        message_content = getattr(latest_msg, "content", "")

                    await interaction.channel.send(message_content)
                else:
                    await interaction.channel.send("✅ 처리 완료")

                # 세션 정리
                active_sessions.pop(self.approval_view.thread_id, None)
                return

            elif scenario == "delivery":
                # Delivery 문서 생성
                result = DocumentGenerator.generate_delivery_document(
                    unloading_site=edited_data.get('unloading_site'),
                    address=edited_data.get('address'),
                    contact=edited_data.get('contact'),
                    payment_type=edited_data.get('payment_type', '선불'),
                    loading_site=edited_data.get('loading_site', '유진알루미늄'),
                    loading_address=edited_data.get('loading_address'),
                    loading_phone=edited_data.get('loading_phone'),
                    freight_cost=edited_data.get('freight_cost')
                )

                freight_info = f"{edited_data.get('freight_cost'):,}원" if edited_data.get('freight_cost') else "미정"
                message = f"""✅ 운송장 생성 완료!

**생성된 파일:**
- DOCX: {result['docx']}
- PDF: {result['pdf']}

**문서 내용:**
- 하차지: {edited_data.get('unloading_site')}
- 주소: {edited_data.get('address')}
- 연락처: {edited_data.get('contact')}
- 상차지: {edited_data.get('loading_site', '유진알루미늄')}
- 운송비: {edited_data.get('payment_type', '선불')} ({freight_info if edited_data.get('payment_type') == '착불' else '해당없음'})"""

                pdf_path = Path(result['pdf'])

            elif scenario == "product_order":
                # Product 문서 생성
                result = DocumentGenerator.generate_product_order_document(
                    client=edited_data.get('client'),
                    product_name=edited_data.get('product_name'),
                    quantity=edited_data.get('quantity'),
                    unit_price=edited_data.get('unit_price')
                )

                total_price = edited_data.get('quantity', 0) * edited_data.get('unit_price', 0)
                message = f"""✅ 거래명세서 생성 완료!

**생성된 파일:**
- DOCX: {result['docx']}
- PDF: {result['pdf']}

**문서 내용:**
- 거래처: {edited_data.get('client')}
- 품목: {edited_data.get('product_name')}
- 수량: {edited_data.get('quantity')}개
- 단가: {edited_data.get('unit_price'):,}원
- 합계: {total_price:,}원"""

                pdf_path = Path(result['pdf'])

            else:
                message = f"❌ 알 수 없는 시나리오입니다: {scenario}"
                pdf_path = None
                result = {}

            # 결과 전송
            await interaction.channel.send(message)

            # 이미지 파일 전송 (미리보기)
            if 'images' in result and result['images']:
                image_paths = [Path(p) for p in result['images']]
                for img_path in image_paths:
                    if img_path.exists():
                        print(f"[📤] Sending image file: {img_path}")
                        await interaction.channel.send(file=discord.File(str(img_path)))

            # PDF 파일 전송
            if pdf_path and pdf_path.exists():
                print(f"[📤] Sending PDF file: {pdf_path}")
                await interaction.channel.send(file=discord.File(str(pdf_path)))

            # 세션 정리
            active_sessions.pop(self.approval_view.thread_id, None)

        except Exception as e:
            await interaction.channel.send(f"❌ 문서 생성 실패: {str(e)}")
            import traceback
            traceback.print_exc()


class PrintApprovalView(discord.ui.View):
    """인쇄 승인/거절 버튼 UI"""

    def __init__(self, thread_id: str, timeout: float = 300):
        super().__init__(timeout=timeout)
        self.thread_id = thread_id
        self.decision = None

    @discord.ui.button(label="🖨️ 인쇄", style=discord.ButtonStyle.success, custom_id="print_approve")
    async def print_approve_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """인쇄 승인 버튼"""
        self.decision = "approve"

        # 버튼 비활성화
        for item in self.children:
            item.disabled = True

        await interaction.response.edit_message(view=self)
        await interaction.followup.send("🖨️ 인쇄 요청 중...", ephemeral=False)

        # 워크플로우 재개 (print_approval_decision)
        await self._resume_print_workflow(interaction, "approve")

    @discord.ui.button(label="🚫 인쇄 안함", style=discord.ButtonStyle.secondary, custom_id="print_reject")
    async def print_reject_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """인쇄 거절 버튼"""
        self.decision = "reject"

        # 버튼 비활성화
        for item in self.children:
            item.disabled = True

        await interaction.response.edit_message(view=self)
        await interaction.followup.send("🚫 인쇄를 건너뜁니다.", ephemeral=False)

        # 워크플로우 재개 (print_approval_decision)
        await self._resume_print_workflow(interaction, "reject")

    async def _resume_print_workflow(
        self,
        interaction: discord.Interaction,
        decision_type: str
    ):
        """인쇄 승인 워크플로우 재개"""
        global workflow_graph

        try:
            loop = asyncio.get_event_loop()
            print(f"[🔄] Calling resume with print_approval_decision={decision_type}", flush=True)

            # resume 호출 (print_approval_decision 파라미터 전달)
            result = await asyncio.wait_for(
                loop.run_in_executor(
                    None,
                    lambda: workflow_graph.resume(
                        decision_type=decision_type,
                        reject_message=None,
                        thread_id=self.thread_id,
                        is_print_approval=True  # 인쇄 승인임을 표시
                    )
                ),
                timeout=120.0
            )

            print(f"[✅] Print resume completed", flush=True)

            # 세션 정리
            active_sessions.pop(self.thread_id, None)

            # 최종 메시지 전송
            if "messages" in result and result["messages"]:
                latest_msg = result["messages"][-1]
                if isinstance(latest_msg, dict):
                    content = latest_msg.get("content", "")
                else:
                    content = getattr(latest_msg, "content", "")

                if content:
                    await interaction.channel.send(content)
                else:
                    await interaction.channel.send("✅ 처리 완료")
            else:
                await interaction.channel.send("✅ 처리 완료")

        except asyncio.TimeoutError:
            print(f"[⏰] Print resume timed out!", flush=True)
            await interaction.channel.send("⏰ 인쇄 처리 시간 초과")
            active_sessions.pop(self.thread_id, None)
        except Exception as e:
            await interaction.channel.send(f"❌ 인쇄 처리 실패: {str(e)}")
            active_sessions.pop(self.thread_id, None)
            import traceback
            traceback.print_exc()


@bot.event
async def on_ready():
    """봇이 준비되면 실행"""
    global workflow_graph

    try:
        # 워크플로우 그래프 초기화 (model_name은 .env의 OPENAI_MODEL_NAME 사용)
        print(f"[🔧] Initializing OfficeAutomationGraph...")
        workflow_graph = OfficeAutomationGraph(
            temperature=0.0,
            use_langfuse=True
        )
        print(f"[✅] OfficeAutomationGraph initialized successfully")
        print(f"[✅] {bot.user} has connected to Discord!")
        print(f"[ℹ️] Bot is ready to process office automation tasks")
    except Exception as e:
        print(f"[❌] CRITICAL: Failed to initialize OfficeAutomationGraph: {e}")
        import traceback
        traceback.print_exc()
        print(f"[⚠️] Bot will not function properly without workflow_graph!")
        # Don't raise - let bot stay online but log the error


@bot.event
async def on_message(message):
    """메시지 수신 이벤트"""
    # 봇 자신의 메시지는 무시
    if message.author == bot.user:
        return

    # 디버깅: 모든 메시지 로깅
    print(f"[📨] Message from {message.author}: {message.content[:50]}...")
    print(f"[ℹ️] Is DM: {isinstance(message.channel, discord.DMChannel)}")
    print(f"[ℹ️] Starts with !: {message.content.startswith('!')}")

    # !로 시작하는 명령어/메시지 처리
    if message.content.startswith("!"):
        # 명령어 처리 (!start, !guide, !status)
        await bot.process_commands(message)

        # !start, !guide, !status 같은 명령어가 아니면 일반 메시지로 처리
        command_names = [f"!{cmd.name}" for cmd in bot.commands]
        if not any(message.content.startswith(cmd) for cmd in command_names):
            print(f"[🔄] Processing ! message as input...")
            await handle_message(message)
        return

    # DM인 경우에도 처리
    if isinstance(message.channel, discord.DMChannel):
        print(f"[🔄] Processing DM message...")
        await handle_message(message)
        return

    # 멘션된 경우 처리
    if bot.user in message.mentions:
        print(f"[🔄] Processing mentioned message...")
        await handle_message(message)
        return

    # 이미지 첨부가 있는 경우 처리
    if message.attachments:
        # 이미지 파일 확인
        image_attachments = [
            att for att in message.attachments
            if att.content_type and att.content_type.startswith('image/')
        ]
        if image_attachments:
            print(f"[🔄] Processing message with image attachment...")
            await handle_message(message)
            return

    print(f"[⏭️] Skipping message (not DM, not mentioned, not starting with !, and no image)")


async def handle_message(message: discord.Message):
    """메시지 처리"""
    try:
        # 이미지 첨부가 있는 경우 우선 처리
        if message.attachments:
            # 이미지 파일 확인
            image_attachments = [
                att for att in message.attachments
                if att.content_type and att.content_type.startswith('image/')
            ]
            if image_attachments:
                await handle_image_message(message, image_attachments[0])
                return

        # 텍스트 메시지 처리
        if message.content:
            await handle_text_message(message)

    except Exception as e:
        await message.channel.send(f"⚠️ 오류가 발생했습니다: {str(e)}")
        print(f"[❌] Error handling message: {e}")


async def handle_text_message(message: discord.Message):
    """텍스트 메시지 처리"""
    global workflow_graph, user_sessions, active_sessions

    # workflow_graph 초기화 확인
    if workflow_graph is None:
        await message.channel.send("❌ 봇이 아직 초기화되지 않았습니다. 잠시 후 다시 시도해주세요.")
        print(f"[❌] workflow_graph is None - bot not initialized properly")
        return

    # 멘션 제거
    content = message.content.replace(f"<@{bot.user.id}>", "").strip()

    # ! prefix 제거 (명령어가 아닌 경우)
    if content.startswith("!"):
        content = content[1:].strip()

    if not content:
        await message.channel.send("메시지를 입력해주세요.")
        return

    # 사용자별 세션 키
    user_channel_key = f"{message.channel.id}_{message.author.id}"
    print(f"[🔑] User channel key: {user_channel_key}")
    print(f"[📍] Channel ID: {message.channel.id}, Author ID: {message.author.id}, Channel type: {type(message.channel)}")

    # 현재 활성 세션이 있는지 확인
    current_thread_id = user_sessions.get(user_channel_key)
    print(f"[🔍] Current thread_id from user_sessions: {current_thread_id}")

    # HITL 승인 대기 중이면 무시 (버튼으로만 응답)
    if current_thread_id and active_sessions.get(current_thread_id):
        await message.channel.send("⏸️ 승인 대기 중입니다. 위의 버튼을 사용해주세요.")
        return

    # 세션 재사용 로직: 기존 세션이 있고 완료되지 않았으면 재사용
    import time

    # 세션 타임아웃 설정 (5분 = 300초)
    SESSION_TIMEOUT = 300

    if current_thread_id:
        # 기존 세션의 상태 확인
        try:
            state = workflow_graph.get_state(thread_id=current_thread_id)
            # 멀티턴 대화 체크: active_scenario가 있으면 진행 중
            active_scenario = state.values.get("active_scenario") if state else None
            active_scenario_timestamp = state.values.get("active_scenario_timestamp", 0) if state else 0

            # 세션 타임아웃 체크
            if active_scenario and active_scenario_timestamp:
                session_age = time.time() - active_scenario_timestamp
                if session_age > SESSION_TIMEOUT:
                    print(f"[⏰] Session expired (age: {session_age:.0f}s), creating new session")
                    thread_id = f"{user_channel_key}_{int(time.time())}"
                    user_sessions[user_channel_key] = thread_id
                    print(f"[🆕] New session created: {thread_id}")
                else:
                    # 타임아웃 전 → 세션 재사용
                    thread_id = current_thread_id
                    print(f"[🔄] Reusing active session (multi-turn): {thread_id}, active_scenario={active_scenario}, age={session_age:.0f}s")
            # state.next가 비어있고 active_scenario도 없으면 완료된 세션
            elif state and not state.next and not active_scenario:
                print(f"[✅] Previous session completed, creating new session")
                thread_id = f"{user_channel_key}_{int(time.time())}"
                user_sessions[user_channel_key] = thread_id
                print(f"[🆕] New session created: {thread_id}")
            else:
                # 진행 중인 세션 → 재사용 (멀티턴 대화)
                thread_id = current_thread_id
                print(f"[🔄] Reusing active session: {thread_id}")
        except Exception as e:
            print(f"[⚠️] Failed to get session state: {e}, creating new session")
            thread_id = f"{user_channel_key}_{int(time.time())}"
            user_sessions[user_channel_key] = thread_id
            print(f"[🆕] New session created: {thread_id}")
    else:
        # 첫 메시지 → 새 세션
        thread_id = f"{user_channel_key}_{int(time.time())}"
        user_sessions[user_channel_key] = thread_id
        print(f"[🆕] New session created: {thread_id}")

    # 처리 중 메시지
    processing_msg = await message.channel.send("🤖 텍스트를 처리 중입니다...")

    try:
        # LangGraph workflow 실행 (invoke 모드 - HITL에서는 stream 대신 invoke 사용)
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            lambda: workflow_graph.invoke(
                raw_input=content,
                input_type="text",
                discord_user_id=str(message.author.id),
                discord_channel_id=str(message.channel.id),
                thread_id=thread_id
            )
        )

        print(f"[🔍] Result keys: {result.keys() if isinstance(result, dict) else 'not a dict'}")

        # Interrupt 발생 체크 (StateGraph interrupt_before)
        # StateGraph에서는 state.next가 None이 아니면 interrupt 발생
        config = {"configurable": {"thread_id": thread_id}}
        state = workflow_graph.get_state(thread_id=thread_id)

        # Subgraph interrupt 체크
        if state and state.next and ("delivery_subgraph" in str(state.next) or "product_subgraph" in str(state.next) or "business_registration_subgraph" in str(state.next)):
            # Interrupt 발생 - subgraph 내부에서 approval 노드 전에 중단됨
            print(f"[⏸️] Interrupt detected: next={state.next}")

            # Subgraph state 접근 (state.tasks를 통해)
            subgraph_state_values = None
            if state.tasks and len(state.tasks) > 0:
                task = state.tasks[0]
                if task.state:
                    try:
                        # Subgraph의 state를 가져옴
                        subgraph_state = workflow_graph.graph.get_state(task.state)
                        if subgraph_state and subgraph_state.values:
                            subgraph_state_values = subgraph_state.values
                            print(f"[✅] Subgraph state accessed: {list(subgraph_state_values.keys())}")
                    except Exception as e:
                        print(f"[⚠️] Failed to get subgraph state: {e}")

            # Subgraph의 다음 노드 확인 (어느 노드 전에 interrupt 되었는지)
            subgraph_next_node = None
            if state.tasks and len(state.tasks) > 0:
                task = state.tasks[0]
                if task.state:
                    try:
                        subgraph_state_obj = workflow_graph.graph.get_state(task.state)
                        if subgraph_state_obj and subgraph_state_obj.next:
                            subgraph_next_node = subgraph_state_obj.next[0] if isinstance(subgraph_state_obj.next, tuple) else subgraph_state_obj.next
                            print(f"[🔍] Subgraph next node: {subgraph_next_node}")
                    except Exception as e:
                        print(f"[⚠️] Failed to get subgraph next node: {e}")

            # wait_for_image interrupt인 경우: 승인 UI 없이 메시지만 표시
            if subgraph_next_node == "wait_for_image":
                print(f"[📸] Wait for image interrupt - showing message only")
                # wait_for_image는 interrupt_before이므로 아직 실행 전 → 하드코딩 메시지 사용
                await processing_msg.edit(content="📄 **사업자등록증 이미지를 업로드해주세요.**\n\n이미지를 첨부하면 자동으로 정보를 추출합니다.")
                return

            # 승인 메시지 가져오기 (subgraph state에서)
            # 인쇄 승인인지 문서 승인인지 체크
            is_print_approval = False
            approval_msg = "승인이 필요합니다"

            if subgraph_state_values:
                # 인쇄 승인 체크
                if subgraph_state_values.get("awaiting_print_approval"):
                    is_print_approval = True
                    approval_msg = subgraph_state_values.get("print_approval_message", "🖨️ 인쇄하시겠습니까?")
                    print(f"[🖨️] Print approval detected")
                # 문서 승인
                elif subgraph_state_values.get("awaiting_approval"):
                    approval_msg = subgraph_state_values.get("approval_message", "승인이 필요합니다")
                    print(f"[📄] Document approval detected")

            # 인쇄 승인인 경우 PrintApprovalView 사용
            if is_print_approval:
                view = PrintApprovalView(thread_id=thread_id)
                active_sessions[thread_id] = True

                try:
                    await processing_msg.delete()
                    await message.channel.send(approval_msg, view=view)
                    print(f"[✅] Print approval request sent")
                except Exception as e:
                    print(f"[❌] Failed to send print approval request: {e}")
                    await message.channel.send(f"❌ 인쇄 승인 요청 전송 실패: {str(e)}")

                return

            # 원래 데이터 추출 (delivery_info 또는 product_order_info)
            original_data = {}

            # Delivery 정보 (subgraph state에서)
            if subgraph_state_values and subgraph_state_values.get("delivery_info"):
                info = subgraph_state_values["delivery_info"]
                original_data = {
                    "unloading_site": info.unloading_site,
                    "address": info.address,
                    "contact": info.contact,
                    "loading_site": info.loading_site,
                    "loading_address": info.loading_address,
                    "loading_phone": info.loading_phone,
                    "payment_type": info.payment_type,
                    "freight_cost": info.freight_cost,
                    "notes": info.notes,
                    "scenario": "delivery"
                }
            # Product 정보 (subgraph state에서)
            elif subgraph_state_values and subgraph_state_values.get("product_order_info"):
                info = subgraph_state_values["product_order_info"]
                original_data = {
                    "client": info.client,
                    "product_name": info.product_name,
                    "quantity": info.quantity,
                    "unit_price": info.unit_price,
                    "notes": info.notes,
                    "scenario": "product_order"
                }

            # 승인 버튼 UI 생성
            view = ApprovalView(thread_id=thread_id, original_data=original_data)
            active_sessions[thread_id] = True

            try:
                # Delete processing message and send approval UI
                await processing_msg.delete()
                await message.channel.send(approval_msg, view=view)
                print(f"[✅] Approval request sent")
            except Exception as e:
                print(f"[❌] Failed to send approval request: {e}")
                await message.channel.send(f"❌ 승인 요청 전송 실패: {str(e)}")

            return

        # 이전 방식 (__interrupt__) 지원 (호환성)
        if "__interrupt__" in result:
            interrupts = result["__interrupt__"]
            print(f"[⏸️] Interrupt detected: {len(interrupts)} interrupt(s)")

            if interrupts and len(interrupts) > 0:
                interrupt_data = interrupts[0].value if hasattr(interrupts[0], 'value') else interrupts[0]
                action_requests = interrupt_data.get("action_requests", [])

                if action_requests:
                    # 첫 번째 action request 처리
                    action = action_requests[0]
                    approval_msg = action.get("description", "승인이 필요합니다")
                    original_args = action.get("args", {})

                    # parsed_info에서 원래 데이터 추출
                    original_data = {}
                    if 'parsed_info' in original_args:
                        info_text = original_args['parsed_info']

                        # Delivery 정보 파싱 (새 스키마)
                        unloading_match = re.search(r'하차지:\s*(.+)', info_text)
                        address_match = re.search(r'(?:^|\n)주소:\s*(.+)', info_text, re.MULTILINE)
                        contact_match = re.search(r'연락처:\s*(.+)', info_text)
                        loading_match = re.search(r'상차지:\s*(.+)', info_text)
                        loading_addr_match = re.search(r'상차지 주소:\s*(.+)', info_text)
                        loading_phone_match = re.search(r'상차지 전화번호:\s*(.+)', info_text)
                        payment_match = re.search(r'지불방법:\s*(.+)', info_text)
                        freight_match = re.search(r'운송비:\s*([\d,]+)', info_text)

                        # Product 정보 파싱
                        client_match = re.search(r'거래처:\s*(.+)', info_text)
                        product_match = re.search(r'품목:\s*(.+)', info_text)
                        quantity_match = re.search(r'수량:\s*(\d+)', info_text)
                        price_match = re.search(r'단가:\s*([\d,]+)', info_text)

                        # Delivery data
                        if unloading_match:
                            original_data['unloading_site'] = unloading_match.group(1).strip()
                        if address_match:
                            original_data['address'] = address_match.group(1).strip()
                        if contact_match:
                            original_data['contact'] = contact_match.group(1).strip()
                        if loading_match:
                            original_data['loading_site'] = loading_match.group(1).strip()
                        if loading_addr_match:
                            original_data['loading_address'] = loading_addr_match.group(1).strip()
                        if loading_phone_match:
                            original_data['loading_phone'] = loading_phone_match.group(1).strip()
                        if payment_match:
                            original_data['payment_type'] = payment_match.group(1).strip()
                        if freight_match:
                            original_data['freight_cost'] = int(freight_match.group(1).replace(',', ''))

                        # Product data
                        if client_match:
                            original_data['client'] = client_match.group(1).strip()
                        if product_match:
                            original_data['product_name'] = product_match.group(1).strip()
                        if quantity_match:
                            original_data['quantity'] = int(quantity_match.group(1))
                        if price_match:
                            original_data['unit_price'] = int(price_match.group(1).replace(',', ''))

                    # UI 버튼 생성 (원래 데이터 포함)
                    view = ApprovalView(thread_id=thread_id, original_data=original_data)

                    # 승인 메시지와 버튼 전송
                    await processing_msg.edit(content=approval_msg, view=view)

                    # 세션 활성화
                    active_sessions[thread_id] = True
                    print(f"[⏸️] Workflow paused for approval: {thread_id}")
                    return

        # Interrupt가 없으면 완료된 것
        # 최종 메시지 전송
        if "messages" in result and result["messages"]:
            latest_msg = result["messages"][-1]
            # 메시지가 dict 또는 object일 수 있음
            if isinstance(latest_msg, dict):
                content = latest_msg.get("content", "")
            else:
                content = getattr(latest_msg, "content", "")

            if content:
                await processing_msg.edit(content=content)
            else:
                await processing_msg.edit(content="✅ 처리 완료")
        else:
            await processing_msg.edit(content="✅ 처리 완료")

        # 이미지 파일 전송 (미리보기)
        if result.get("image_paths"):
            image_paths = [Path(p) for p in result["image_paths"]]
            for img_path in image_paths:
                if img_path.exists():
                    print(f"[📤] Sending image file: {img_path}")
                    await message.channel.send(file=discord.File(str(img_path)))

        # PDF 파일 전송
        if result.get("pdf_path"):
            pdf_path = Path(result["pdf_path"])
            if pdf_path.exists():
                await message.channel.send(file=discord.File(str(pdf_path)))

    except Exception as e:
        await processing_msg.edit(content=f"❌ 처리 실패: {str(e)}")
        print(f"[❌] Error: {e}")
        import traceback
        traceback.print_exc()
        raise


async def handle_image_message(message: discord.Message, attachment: discord.Attachment):
    """이미지 메시지 처리 (사업자등록증 등)"""
    global workflow_graph, user_sessions, active_sessions

    # workflow_graph 초기화 확인
    if workflow_graph is None:
        await message.channel.send("❌ 봇이 아직 초기화되지 않았습니다. 잠시 후 다시 시도해주세요.")
        print(f"[❌] workflow_graph is None - bot not initialized properly")
        return

    print(f"[📸] Image received: {attachment.filename}, size: {attachment.size} bytes")

    # 사용자별 세션 키
    user_channel_key = f"{message.channel.id}_{message.author.id}"
    print(f"[🔑] User channel key: {user_channel_key}")
    print(f"[📍] Channel ID: {message.channel.id}, Author ID: {message.author.id}, Channel type: {type(message.channel)}")

    # 현재 활성 세션 확인
    current_thread_id = user_sessions.get(user_channel_key)
    print(f"[🔍] Current thread_id from user_sessions: {current_thread_id}")
    print(f"[📋] All user_sessions keys: {list(user_sessions.keys())}")

    # HITL 승인 대기 중이면 무시
    if current_thread_id and active_sessions.get(current_thread_id):
        await message.channel.send("⏸️ 승인 대기 중입니다. 위의 버튼을 사용해주세요.")
        return

    # 세션이 없으면 새로 생성
    import time
    if not current_thread_id:
        thread_id = f"{user_channel_key}_{int(time.time())}"
        user_sessions[user_channel_key] = thread_id
        print(f"[🆕] New session created for image: {thread_id}")
    else:
        thread_id = current_thread_id
        print(f"[🔄] Reusing session for image: {thread_id}")

    # 처리 중 메시지
    processing_msg = await message.channel.send("🤖 이미지를 처리 중입니다...")

    try:
        # 이미지 URL 추출
        image_url = attachment.url
        print(f"[🔗] Image URL: {image_url}")

        # 현재 세션 상태 확인
        state = workflow_graph.get_state(thread_id=thread_id)

        # active_scenario는 main graph state에 있음 (subgraph state가 아님)
        # Subgraph가 interrupt 중이면 state.tasks[0].state에서 찾아야 함
        active_scenario = None

        # Main graph state에서 먼저 확인
        if state and state.values:
            active_scenario = state.values.get("active_scenario")
            print(f"[🔍] Active scenario from main state: {active_scenario}")

        # Subgraph state에서도 확인 (fallback)
        if not active_scenario and state and state.tasks and len(state.tasks) > 0:
            task = state.tasks[0]
            if task.state:
                try:
                    subgraph_state = workflow_graph.graph.get_state(task.state)
                    if subgraph_state and subgraph_state.values:
                        active_scenario = subgraph_state.values.get("active_scenario")
                        print(f"[🔍] Active scenario from subgraph state: {active_scenario}")
                except Exception as e:
                    print(f"[⚠️] Failed to get active_scenario from subgraph: {e}")

        print(f"[📊] Final active_scenario: {active_scenario}")

        # active_scenario가 business_registration이고 wait_for_image interrupt 중이면 resume
        if active_scenario == "business_registration":
            print(f"[🔄] Business registration in progress, resuming with image")

            # Interrupt 상태에서 resume하려면:
            # 1. State를 업데이트하여 raw_input에 image_url 설정
            # 2. invoke(None, config)로 재개

            config = {"configurable": {"thread_id": thread_id}}

            # Subgraph state 업데이트 (tasks[0].state를 통해 subgraph에 접근)
            if state and state.tasks and len(state.tasks) > 0:
                task = state.tasks[0]
                print(f"[🔧] Updating subgraph state with image_url: {image_url[:100]}...")

                # Subgraph state 업데이트
                workflow_graph.graph.update_state(
                    task.state,
                    {
                        "raw_input": image_url,
                        "input_type": "image"
                    }
                )
                print(f"[✅] Subgraph state updated")
            else:
                print(f"[⚠️] No tasks found - updating main graph state")
                # Fallback: main graph state 업데이트
                workflow_graph.graph.update_state(
                    config,
                    {
                        "raw_input": image_url,
                        "input_type": "image"
                    }
                )

            # Resume workflow (None을 전달하여 interrupt에서 재개)
            print(f"[🚀] Invoking graph to resume from wait_for_image interrupt...")
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                lambda: workflow_graph.graph.invoke(None, config)
            )

            print(f"[🔍] Result keys: {result.keys() if isinstance(result, dict) else 'not a dict'}")

            # Interrupt 체크 (approval)
            state_after = workflow_graph.get_state(thread_id=thread_id)

            if state_after and state_after.next:
                print(f"[⏸️] Interrupt detected after image parse: next={state_after.next}")

                # Subgraph state 접근
                subgraph_state_values = None
                if state_after.tasks and len(state_after.tasks) > 0:
                    task = state_after.tasks[0]
                    if task.state:
                        try:
                            subgraph_state = workflow_graph.graph.get_state(task.state)
                            if subgraph_state and subgraph_state.values:
                                subgraph_state_values = subgraph_state.values
                                print(f"[✅] Subgraph state after parse: {list(subgraph_state_values.keys())}")
                        except Exception as e:
                            print(f"[⚠️] Failed to get subgraph state: {e}")

                # 승인 메시지 가져오기
                approval_msg = "승인이 필요합니다"
                original_data = {}

                if subgraph_state_values:
                    print(f"[📝] awaiting_approval: {subgraph_state_values.get('awaiting_approval')}")
                    print(f"[📝] business_registration_info exists: {bool(subgraph_state_values.get('business_registration_info'))}")

                    if subgraph_state_values.get("awaiting_approval"):
                        approval_msg = subgraph_state_values.get("approval_message", "승인이 필요합니다")
                        print(f"[📝] Approval message length: {len(approval_msg)}")

                        # BusinessRegistrationInfo 추출
                        if subgraph_state_values.get("business_registration_info"):
                            info = subgraph_state_values["business_registration_info"]
                            original_data = {
                                "client_name": info.client_name,
                                "business_name": info.business_name,
                                "representative_name": info.representative_name,
                                "business_number": info.business_number,
                                "branch_number": info.branch_number,
                                "postal_code": info.postal_code,
                                "address1": info.address1,
                                "address2": info.address2,
                                "business_type": info.business_type,
                                "business_item": info.business_item,
                                "phone1": info.phone1,
                                "phone2": info.phone2,
                                "fax": info.fax,
                                "contact_person1": info.contact_person1,
                                "mobile1": info.mobile1,
                                "contact_person2": info.contact_person2,
                                "mobile2": info.mobile2,
                                "client_type": info.client_type,
                                "price_grade": info.price_grade,
                                "initial_balance": info.initial_balance,
                                "optimal_balance": info.optimal_balance,
                                "memo": info.memo,
                                "scenario": "business_registration"
                            }

                # 승인 버튼 UI 생성
                view = ApprovalView(thread_id=thread_id, original_data=original_data)
                active_sessions[thread_id] = True

                await processing_msg.delete()
                await message.channel.send(approval_msg, view=view)
                print(f"[✅] Approval request sent for business registration")
                return

            # Interrupt 없으면 완료
            if "messages" in result and result["messages"]:
                latest_msg = result["messages"][-1]
                if isinstance(latest_msg, dict):
                    content = latest_msg.get("content", "")
                else:
                    content = getattr(latest_msg, "content", "")

                if content:
                    await processing_msg.edit(content=content)
                else:
                    await processing_msg.edit(content="✅ 처리 완료")
            else:
                await processing_msg.edit(content="✅ 처리 완료")

        else:
            # business_registration이 아닌 경우: 일반 이미지는 무시하거나 안내
            await processing_msg.edit(content="❓ 이미지가 첨부되었지만, 사업자등록증 등록 모드가 아닙니다.\n먼저 '사업자 등록해줘'라고 입력해주세요.")

    except Exception as e:
        await processing_msg.edit(content=f"❌ 이미지 처리 실패: {str(e)}")
        print(f"[❌] Image processing error: {e}")
        import traceback
        traceback.print_exc()


# handle_approval_response는 더 이상 필요 없음 (UI 버튼이 직접 처리)


@bot.command(name="start")
async def start_workflow(ctx):
    """새로운 사무 자동화 워크플로우 시작"""
    global user_sessions, active_sessions

    user_channel_key = f"{ctx.channel.id}_{ctx.author.id}"

    # 기존 세션 정리
    old_thread_id = user_sessions.get(user_channel_key)
    if old_thread_id:
        active_sessions.pop(old_thread_id, None)
        print(f"[🗑️] Cleared old session: {old_thread_id}")

    # 새 세션 준비 (실제로는 다음 메시지에서 생성됨)
    user_sessions.pop(user_channel_key, None)

    await ctx.send("🚀 새로운 워크플로우를 시작합니다.\n\n봇을 멘션하고 정보를 입력해주세요.\n예: `@office_worker 홍길동, 010-1234-5678, 서울시 강남구 테헤란로 123`")


@bot.command(name="guide")
async def guide_command(ctx):
    """사용 가이드"""
    help_text = """
**사무 자동화 봇 사용 가이드**

📝 **텍스트 메시지**: ! 또는 @멘션으로 봇을 호출하고 내용을 입력하세요

**명령어:**
- `!start` - 새로운 워크플로우 시작
- `!guide` - 이 가이드 표시
- `!status` - 현재 워크플로우 상태 확인
- `!reset` - 현재 세션 초기화 (세션이 꼬였을 때 사용)

**예시:**
```
!운송장 생성 부탁해
홍길동
010-1234-5678
서울시 강남구 테헤란로 123
```
    """
    await ctx.send(help_text)


@bot.command(name="status")
async def status_command(ctx):
    """현재 워크플로우 상태 확인"""
    global user_sessions, active_sessions

    user_channel_key = f"{ctx.channel.id}_{ctx.author.id}"
    current_thread_id = user_sessions.get(user_channel_key)

    if current_thread_id:
        is_waiting = active_sessions.get(current_thread_id, False)
        status = "⏸️ 승인 대기 중" if is_waiting else "✅ 활성"
        await ctx.send(f"{status}\n세션 ID: `{current_thread_id}`")
    else:
        await ctx.send("ℹ️ 활성 세션이 없습니다.\n`!start` 명령어로 새 세션을 시작하세요.")


@bot.command(name="reset")
async def reset_command(ctx):
    """현재 세션 초기화"""
    global user_sessions, active_sessions

    user_channel_key = f"{ctx.channel.id}_{ctx.author.id}"
    current_thread_id = user_sessions.get(user_channel_key)

    if current_thread_id:
        # 세션 정리
        user_sessions.pop(user_channel_key, None)
        active_sessions.pop(current_thread_id, None)
        print(f"[🗑️] Session reset by user: {current_thread_id}")
        await ctx.send(f"🔄 세션이 초기화되었습니다.\n이전 세션 ID: `{current_thread_id}`\n\n새로운 작업을 시작하려면 봇을 멘션하거나 `!` 로 시작하는 메시지를 입력하세요.")
    else:
        await ctx.send("ℹ️ 초기화할 활성 세션이 없습니다.")


def main():
    """봇 실행"""
    token = os.getenv("DISCORD_BOT_TOKEN")

    if not token:
        raise ValueError("DISCORD_BOT_TOKEN이 설정되지 않았습니다. .env 파일을 확인해주세요.")

    print("[🤖] Starting Discord Bot...")
    bot.run(token)


if __name__ == "__main__":
    main()
