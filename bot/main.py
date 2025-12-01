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

            # 세션 정리
            active_sessions.pop(self.thread_id, None)

            print(f"[🔍] Resume result keys: {result.keys() if isinstance(result, dict) else 'not a dict'}", flush=True)

            # 최종 메시지 전송 및 PDF 파일 추출
            message_content = ""
            pdf_path = None

            if "messages" in result and result["messages"]:
                latest_msg = result["messages"][-1]
                # 메시지가 dict 또는 object일 수 있음
                if isinstance(latest_msg, dict):
                    message_content = latest_msg.get("content", "")
                else:
                    message_content = getattr(latest_msg, "content", "")

                if message_content:
                    # PDF 경로 추출 (정규식으로 "- PDF: /tmp/..." 패턴 찾기)
                    pdf_match = re.search(r'- PDF:\s*(/tmp/[^\s]+\.pdf)', message_content)
                    if pdf_match:
                        pdf_path = Path(pdf_match.group(1))
                        print(f"[📄] Found PDF path: {pdf_path}")

                    await interaction.channel.send(message_content)
                else:
                    await interaction.channel.send("✅ 처리 완료")
            else:
                await interaction.channel.send("✅ 처리 완료")

            # PDF 파일 전송
            if pdf_path and pdf_path.exists():
                print(f"[📤] Sending PDF file: {pdf_path}")
                await interaction.channel.send(file=discord.File(str(pdf_path)))
            elif pdf_path:
                print(f"[⚠️] PDF file not found: {pdf_path}")

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

        # 편집된 텍스트 파싱 (간단한 key: value 형식)
        edited_data = {}
        for line in edited_text.split('\n'):
            line = line.strip()
            if ':' in line:
                key, value = line.split(':', 1)
                key = key.strip().lower()
                value = value.strip()

                # Delivery 키 매핑 (새 스키마)
                if '하차지' in key or 'unloading' in key:
                    edited_data['unloading_site'] = value
                elif '주소' in key and '상차지' not in key:
                    edited_data['address'] = value
                elif '연락처' in key or 'contact' in key:
                    edited_data['contact'] = value
                elif '상차지' in key and '주소' not in key and '전화' not in key:
                    edited_data['loading_site'] = value
                elif '상차지주소' in key or 'loading_address' in key:
                    edited_data['loading_address'] = value
                elif '상차지전화' in key or 'loading_phone' in key:
                    edited_data['loading_phone'] = value
                elif '지불방법' in key or 'payment' in key:
                    if '착불' in value:
                        edited_data['payment_type'] = '착불'
                    elif '선불' in value:
                        edited_data['payment_type'] = '선불'
                elif '운송비' in key or 'freight' in key:
                    # 숫자만 추출
                    numbers = re.findall(r'\d+', value.replace(',', ''))
                    if numbers:
                        edited_data['freight_cost'] = int(numbers[0])
                # Product 키 매핑
                elif '거래처' in key or 'client' in key:
                    edited_data['client'] = value
                elif '품목' in key or 'product' in key:
                    edited_data['product_name'] = value
                elif '수량' in key or 'quantity' in key:
                    # 숫자만 추출
                    numbers = re.findall(r'\d+', value)
                    if numbers:
                        edited_data['quantity'] = int(numbers[0])
                elif '단가' in key or 'unit_price' in key or 'price' in key:
                    # 숫자만 추출
                    numbers = re.findall(r'\d+', value.replace(',', ''))
                    if numbers:
                        edited_data['unit_price'] = int(numbers[0])

        print(f"[📝] Parsed edited data: {edited_data}")

        # 편집된 데이터로 직접 문서 생성 (워크플로우 우회)
        try:
            from agents.graph.utils.document_generator import DocumentGenerator
            from pathlib import Path

            # 시나리오 판별
            if 'unloading_site' in edited_data:
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

            elif 'client' in edited_data:
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
                message = "❌ 편집된 데이터에서 시나리오를 판별할 수 없습니다."
                pdf_path = None

            # 결과 전송
            await interaction.channel.send(message)

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


@bot.event
async def on_ready():
    """봇이 준비되면 실행"""
    global workflow_graph

    # 워크플로우 그래프 초기화
    workflow_graph = OfficeAutomationGraph(
        model_name=os.getenv("OPENAI_MODEL_NAME", "gpt-4o-mini"),
        temperature=0.0,
        use_langfuse=True
    )

    print(f"[✅] {bot.user} has connected to Discord!")
    print(f"[ℹ️] Bot is ready to process office automation tasks")


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

    print(f"[⏭️] Skipping message (not DM, not mentioned, and not starting with !)")


async def handle_message(message: discord.Message):
    """메시지 처리"""
    try:
        # 텍스트 메시지 처리
        if message.content:
            await handle_text_message(message)

    except Exception as e:
        await message.channel.send(f"⚠️ 오류가 발생했습니다: {str(e)}")
        print(f"[❌] Error handling message: {e}")


async def handle_text_message(message: discord.Message):
    """텍스트 메시지 처리"""
    global workflow_graph, user_sessions, active_sessions

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

    # 현재 활성 세션이 있는지 확인
    current_thread_id = user_sessions.get(user_channel_key)

    # HITL 승인 대기 중이면 무시 (버튼으로만 응답)
    if current_thread_id and active_sessions.get(current_thread_id):
        await message.channel.send("⏸️ 승인 대기 중입니다. 위의 버튼을 사용해주세요.")
        return

    # 새 세션 ID 생성 (타임스탬프 기반)
    import time
    thread_id = f"{user_channel_key}_{int(time.time())}"

    # 세션 매핑 업데이트
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

        if state and state.next and "approval" in str(state.next):
            # Interrupt 발생 - approval 노드 전에 중단됨
            print(f"[⏸️] Interrupt detected: next={state.next}")

            # 승인 메시지 가져오기 (state.values에서)
            approval_msg = state.values.get("approval_message", "승인이 필요합니다")

            # 원래 데이터 추출 (delivery_info 또는 product_order_info)
            original_data = {}

            # Delivery 정보
            if state.values.get("delivery_info"):
                info = state.values["delivery_info"]
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
            # Product 정보
            elif state.values.get("product_order_info"):
                info = state.values["product_order_info"]
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


def main():
    """봇 실행"""
    token = os.getenv("DISCORD_BOT_TOKEN")

    if not token:
        raise ValueError("DISCORD_BOT_TOKEN이 설정되지 않았습니다. .env 파일을 확인해주세요.")

    print("[🤖] Starting Discord Bot...")
    bot.run(token)


if __name__ == "__main__":
    main()
