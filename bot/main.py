"""
Discord Bot Main Entry Point

디스코드 봇으로 사무 자동화를 처리하는 메인 파일
- LangGraph 기반 workflow
- Human-in-the-loop 처리
- Whisper API를 통한 음성 메시지 처리
"""

import os
import sys
import asyncio
import discord
from discord.ext import commands
from dotenv import load_dotenv
from pathlib import Path
import tempfile
import re
from typing import Optional, Dict, Any

# 프로젝트 루트를 sys.path에 추가
sys.path.insert(0, str(Path(__file__).parent.parent))

# 환경 변수 로드
load_dotenv()

# 워크플로우 임포트
from agents.workflow import OfficeAutomationGraph

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

    def __init__(self, thread_id: str, timeout: float = 300):
        super().__init__(timeout=timeout)
        self.thread_id = thread_id
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
        edited_args: Optional[Dict[str, Any]] = None,
        reject_message: Optional[str] = None
    ):
        """워크플로우 재개"""
        global workflow_graph

        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                lambda: workflow_graph.resume(
                    decision_type=decision_type,
                    edited_args=edited_args,
                    reject_message=reject_message,
                    thread_id=self.thread_id
                )
            )

            # 세션 정리
            active_sessions.pop(self.thread_id, None)

            print(f"[🔍] Resume result keys: {result.keys() if isinstance(result, dict) else 'not a dict'}")

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

    # 편집 입력 필드
    edited_info = discord.ui.TextInput(
        label="수정된 정보를 입력하세요",
        style=discord.TextStyle.paragraph,
        placeholder="예: 이름: 김철수\n전화번호: 010-9876-5432\n주소: 서울시 서초구",
        required=True,
        max_length=1000,
    )

    async def on_submit(self, interaction: discord.Interaction):
        """모달 제출"""
        edited_text = self.edited_info.value

        # 버튼 비활성화
        for item in self.approval_view.children:
            item.disabled = True

        await interaction.response.edit_message(view=self.approval_view)
        await interaction.followup.send(f"🔄 편집된 정보로 처리 중...\n```\n{edited_text}\n```", ephemeral=False)

        # 워크플로우 재개 (edit)
        await self.approval_view._resume_workflow(
            interaction,
            "edit",
            edited_args={"parsed_info": edited_text}
        )


@bot.event
async def on_ready():
    """봇이 준비되면 실행"""
    global workflow_graph

    # 워크플로우 그래프 초기화
    workflow_graph = OfficeAutomationGraph(
        model_name="gpt-4o-mini",
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
    print(f"[ℹ️] Bot mentioned: {bot.user in message.mentions}")

    # DM 또는 멘션된 메시지만 처리
    if not isinstance(message.channel, discord.DMChannel) and bot.user not in message.mentions:
        print(f"[⏭️] Skipping message (not DM and not mentioned)")
        return

    # 명령어 처리
    await bot.process_commands(message)

    # 명령어가 아닌 일반 메시지 처리
    if not message.content.startswith(bot.command_prefix):
        print(f"[🔄] Processing message...")
        await handle_message(message)


async def handle_message(message: discord.Message):
    """메시지 처리 (텍스트 또는 음성)"""
    try:
        # 음성 메시지 체크
        if message.attachments:
            for attachment in message.attachments:
                # 음성 파일 확인 (ogg, mp3, m4a, wav 등)
                if attachment.content_type and attachment.content_type.startswith("audio"):
                    await handle_voice_message(message, attachment)
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

    # 멘션 제거
    content = message.content.replace(f"<@{bot.user.id}>", "").strip()

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

        # Interrupt 발생 체크 (HumanInTheLoopMiddleware)
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

                    # UI 버튼 생성
                    view = ApprovalView(thread_id=thread_id)

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


async def handle_voice_message(message: discord.Message, attachment: discord.Attachment):
    """음성 메시지 처리 (Whisper API 사용)"""
    global workflow_graph, user_sessions, active_sessions

    processing_msg = await message.channel.send("🎤 음성을 텍스트로 변환 중입니다...")

    try:
        # 임시 파일에 음성 저장
        with tempfile.NamedTemporaryFile(delete=False, suffix=Path(attachment.filename).suffix) as tmp_file:
            await attachment.save(tmp_file.name)
            tmp_path = tmp_file.name

        # Whisper API로 transcribe
        from openai import OpenAI
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

        with open(tmp_path, "rb") as audio_file:
            transcription = client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                language="ko"  # 한국어 지정
            )

        transcribed_text = transcription.text

        # 임시 파일 삭제
        os.unlink(tmp_path)

        await processing_msg.edit(content=f"✅ 음성 변환 완료:\n```{transcribed_text}```")
        await message.channel.send("📝 변환된 텍스트로 처리 중...")

        # 사용자별 세션 키
        user_channel_key = f"{message.channel.id}_{message.author.id}"

        # 현재 활성 세션이 있는지 확인
        current_thread_id = user_sessions.get(user_channel_key)

        # HITL 승인 대기 중이면 무시
        if current_thread_id and active_sessions.get(current_thread_id):
            await message.channel.send("⏸️ 승인 대기 중입니다. 위의 버튼을 사용해주세요.")
            return

        # 새 세션 ID 생성 (타임스탬프 기반)
        import time
        thread_id = f"{user_channel_key}_{int(time.time())}"

        # 세션 매핑 업데이트
        user_sessions[user_channel_key] = thread_id

        print(f"[🆕] New voice session created: {thread_id}")

        # 워크플로우 실행 (invoke 모드)
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            lambda: workflow_graph.invoke(
                raw_input=transcribed_text,
                input_type="voice",
                discord_user_id=str(message.author.id),
                discord_channel_id=str(message.channel.id),
                thread_id=thread_id
            )
        )

        print(f"[🔍] Voice result keys: {result.keys() if isinstance(result, dict) else 'not a dict'}")

        # Interrupt 발생 체크 (HumanInTheLoopMiddleware)
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

                    # UI 버튼 생성
                    view = ApprovalView(thread_id=thread_id)

                    # 승인 메시지와 버튼 전송
                    await message.channel.send(approval_msg, view=view)

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
                await message.channel.send(content)
            else:
                await message.channel.send("✅ 처리 완료")
        else:
            await message.channel.send("✅ 처리 완료")

        # PDF 파일 전송
        if result.get("pdf_path"):
            pdf_path = Path(result["pdf_path"])
            if pdf_path.exists():
                await message.channel.send(file=discord.File(str(pdf_path)))

    except Exception as e:
        await processing_msg.edit(content=f"❌ 음성 변환 실패: {str(e)}")
        # 임시 파일이 남아있으면 삭제
        try:
            if 'tmp_path' in locals():
                os.unlink(tmp_path)
        except:
            pass
        raise


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

📝 **텍스트 메시지**: 봇을 멘션하고 내용을 입력하세요
🎤 **음성 메시지**: 음성 파일을 첨부하면 자동으로 텍스트로 변환됩니다

**명령어:**
- `!start` - 새로운 워크플로우 시작
- `!guide` - 이 가이드 표시
- `!status` - 현재 워크플로우 상태 확인

**예시:**
```
@office_worker 홍길동, 010-1234-5678, 서울시 강남구 테헤란로 123
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
