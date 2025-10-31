import chainlit as cl
from uuid import uuid4
from chainlit.logger import logger
from chainlit.input_widget import TextInput, Switch
import traceback

from realtime import RealtimeClient

from dotenv import load_dotenv
load_dotenv(override=True)

DAYS = [
    ("mon", "월요일"), ("tue", "화요일"), ("wed", "수요일"),
    ("thu", "목요일"), ("fri", "금요일"), ("sat", "토요일"), ("sun", "일요일")
]

def make_week_table_props(weekly_meals: dict) -> dict:
    rows = []
    for key, label in DAYS:
        d = (weekly_meals or {}).get(key, {})
        rows.append({
            "dayKey": key, "dayLabel": label,
            "what": d.get("what", ""), "where": d.get("where", ""),
            "time": d.get("time", ""), "note": d.get("note", "")
        })
    return {"rows": rows, "timeout": 600}

def rows_to_weekly_meals(rows: list[dict]) -> dict:
    out = {}
    for r in rows:
        out[r["dayKey"]] = {
            "what":  (r.get("what")  or "").strip(),
            "where": (r.get("where") or "").strip(),
            "time":  (r.get("time")  or "").strip(),
            "note":  (r.get("note")  or "").strip(),
        }
    return out

def format_meal_table(meals: dict) -> str:
    # meals = {"mon": {"what":"파스타","where":"성수","time":"12:30","note":"맵지X"}, ...}
    header = "| 요일 | 먹은 것 | 장소 | 시간 | 메모 |\n|---|---|---|---|---|\n"
    rows = []
    for key, label in DAYS:
        d = meals.get(key, {})
        rows.append(f"| {label} | {d.get('what','')} | {d.get('where','')} | {d.get('time','')} | {d.get('note','')} |")
    return header + "\n".join(rows)


def summarize_meals_for_prompt(meals: dict) -> str:
    # 프롬프트에 넣기 좋은 1~2줄 요약 (최근일/핵심만)
    picks = []
    for key, label in DAYS:
        d = meals.get(key, {})
        if any(d.get(k) for k in ("what","where","time")):
            picks.append(f"{label}:{d.get('what','?')}@{d.get('where','?')}")
    return " / ".join(picks)[:500]

async def setup_openai_realtime():
    system_prompt = """
        당신은 도움이 되는 AI 어시스턴트입니다. 
        사용자의 질문에 정확하고 유용한 답변을 제공하세요.
        한국어로 답변해주세요. 오디오를 사용해서 말할 수 있으므로 대화형에 맞게 응답하세요. Bullet이나 1. 2, 등의 형식을 피해주세요. 
    """
    max_tokens = 4096
             
    openai_realtime = RealtimeClient(system_prompt=system_prompt, max_tokens=max_tokens)
    cl.user_session.set("track_id", str(uuid4())) # 오디오 재생 트랙 ID 설정
    # Initialize the flag to track input type (text vs audio)
    cl.user_session.set("is_text_input", True) # 입력값이 텍스트인지 오디오인지 추적하는 플래그 초기화

    def get_user_context():
        return {
            "ui_settings": cl.user_session.get("ui_settings") or {},
            "weekly_meals": cl.user_session.get("weekly_meals") or {},
        }
    openai_realtime._ui_settings_injector = get_user_context
    
    def get_ui_settings():  # ← 동기 함수
        return cl.user_session.get("ui_settings") or {}
    openai_realtime._ui_settings_injector = get_ui_settings

    async def handle_conversation_updated(event):
        item = event.get("item")
        delta = event.get("delta")
        """Currently used to stream audio back to the client."""
        
        try:
            if event:
                # Skip handling input_audio_transcription events when text is typed (not audio)
                # This prevents duplicate messages for non-Latin scripts
                if item and "input_audio_transcription" in item.get("type", "") and cl.user_session.get("is_text_input", False):
                    pass  # Skip for text input
                elif item and "input_audio_transcription" in item.get("type", "") and delta and "transcript" in delta:
                    msg = cl.Message(content=delta["transcript"], author="user")
                    msg.type = "user_message"
                    await msg.send()
                    
            if delta:
                # Only one of the following will be populated for any given event
                if 'audio' in delta:
                    audio = delta['audio']  # Int16Array, audio added
                    await cl.context.emitter.send_audio_chunk(cl.OutputAudioChunk(mimeType="pcm16", data=audio, track=cl.user_session.get("track_id")))
                if 'transcript' in delta:
                    transcript = delta['transcript']  # string, transcript added
                    # Display realtime audio transcription in chat
                    if item and item.get("role") == "assistant":
                        # Get or create message for streaming transcript
                        transcript_msg = cl.user_session.get("current_transcript_msg")
                        if not transcript_msg:
                            logger.info("Audio response started")
                            transcript_msg = cl.Message(content="", author="assistant")
                            cl.user_session.set("current_transcript_msg", transcript_msg)
                            await transcript_msg.send()
                        
                        # Update transcript content
                        transcript_msg.content += transcript
                        await transcript_msg.update()
                if 'text' in delta:
                    text = delta['text']  # string, text added
                    # Display realtime text response in chat
                    if item and item.get("role") == "assistant":
                        # Get or create message for streaming text
                        text_msg = cl.user_session.get("current_text_msg")
                        if not text_msg:
                            logger.info("Text response started")
                            text_msg = cl.Message(content="", author="assistant")
                            cl.user_session.set("current_text_msg", text_msg)
                            await text_msg.send()
                        
                        # Update text content
                        text_msg.content += text
                        await text_msg.update()
                if 'arguments' in delta:
                    # Arguments added but not used in this context
                    pass
        except Exception as e:
            logger.error(f"Error in handle_conversation_updated: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise e
            
    async def handle_item_completed(item):
        """Used to populate the chat context with transcription once an item is completed."""
        
        try:
            if item["item"]["type"] == "message":
                content = item["item"]["content"][0]
                if content["type"] == "audio":
                    logger.info("Audio response completed")
                    # Get the current streaming transcript message
                    transcript_msg = cl.user_session.get("current_transcript_msg")
                    
                    # Clear the streaming transcript message since the item is completed
                    cl.user_session.set("current_transcript_msg", None)
                    
                    # Always send the completed transcript message for audio responses
                    # regardless of whether the input was text or audio
                    if transcript_msg and transcript_msg.content:
                        # Update the final message content with the complete transcript
                        transcript_msg.content = content.get("transcript", transcript_msg.content)
                        await transcript_msg.update()
                    else:
                        # If no streaming message exists, create a new one with the complete transcript
                        final_msg = cl.Message(content=content.get("transcript", ""), author="assistant")
                        await final_msg.send()
                        
                elif content["type"] == "text":
                    logger.info("Text response completed")
                    # Get the current streaming text message
                    text_msg = cl.user_session.get("current_text_msg")
                    
                    # Clear the streaming text message since the item is completed
                    cl.user_session.set("current_text_msg", None)
                    
                    # Finalize the text message
                    if text_msg and text_msg.content:
                        # Update the final message content with the complete text
                        text_msg.content = content.get("text", text_msg.content)
                        await text_msg.update()
                    else:
                        # If no streaming message exists, create a new one with the complete text
                        final_msg = cl.Message(content=content.get("text", ""), author="assistant")
                        await final_msg.send()
                        
            elif item["item"]["type"] == "function_call":
                logger.info("Function call completed")
                # Clear transcript and text messages for function calls too
                cl.user_session.set("current_transcript_msg", None)
                cl.user_session.set("current_text_msg", None)
        except Exception as e:
            logger.error(f"Error in handle_item_completed: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise e
    
    async def handle_conversation_interrupt(event):
        """Used to cancel the client previous audio playback."""
        cl.user_session.set("track_id", str(uuid4()))
        # NOTE this will only work starting from version 2.0.0
        await cl.context.emitter.send_audio_interrupt()
        
    async def handle_response_done(event):
        """Handle when a response is completely done"""
        # Reset the input type flag when response is completely done
        cl.user_session.set("is_text_input", False)
        # Also clear any remaining streaming messages
        cl.user_session.set("current_transcript_msg", None)
        cl.user_session.set("current_text_msg", None)
        
    async def handle_error(event):
        logger.error(f"Realtime connection error: {event}")
        # Send error message to user
        await cl.ErrorMessage(content=f"Realtime connection error: {event}").send()
        
    async def get_ui_settings():
        return cl.user_session.get("ui_settings") or {}

    openai_realtime._ui_settings_injector = get_ui_settings
    
    openai_realtime.on('conversation.updated', handle_conversation_updated)
    openai_realtime.on('conversation.item.completed', handle_item_completed)
    openai_realtime.on('conversation.interrupted', handle_conversation_interrupt)
    openai_realtime.on('server.response.done', handle_response_done)
    openai_realtime.on('error', handle_error)

    cl.user_session.set("openai_realtime", openai_realtime)
    
async def ensure_realtime_connected():
    openai_realtime: RealtimeClient = cl.user_session.get("openai_realtime")
    if not openai_realtime:
        await setup_openai_realtime()
        openai_realtime = cl.user_session.get("openai_realtime")
    if not openai_realtime.is_connected():
        await openai_realtime.connect()
        # 세션 생성 이벤트를 기다리도록 구현되어 있다면 호출
        if hasattr(openai_realtime, "wait_for_session_created"):
            await openai_realtime.wait_for_session_created()
    return openai_realtime

@cl.on_audio_start # 음성 입력
async def on_audio_start():
    logger.info("Audio recording started")
    return True

@cl.on_audio_chunk # 오디오 청크를 수신
async def on_audio_chunk(chunk: cl.InputAudioChunk):
    try:
        openai_realtime: RealtimeClient = cl.user_session.get("openai_realtime")
        if not openai_realtime:
            logger.error("OpenAI realtime client not found in audio chunk handler")
            return
            
        if openai_realtime.is_connected():
            # Set flag to indicate this is audio input, not text
            cl.user_session.set("is_text_input", False)
            
            # Configure for audio + text response (audio output with transcript for audio input)
            await openai_realtime.update_session(modalities=["text", "audio"])
            
            await openai_realtime.append_input_audio(chunk.data)
        else:
            logger.warning("RealtimeClient is not connected when processing audio chunk")
    except Exception as e:
        logger.error(f"Error in on_audio_chunk: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")

@cl.on_audio_end
async def on_audio_end():
    logger.info("Audio recording ended")
    return True
@cl.on_chat_end
@cl.on_stop
async def on_end():
    logger.info("Chat session ending")
    
    try:
        openai_realtime: RealtimeClient = cl.user_session.get("openai_realtime")
        if openai_realtime and openai_realtime.is_connected():
            await openai_realtime.disconnect()
            logger.info("OpenAI realtime client disconnected")
    except Exception as e:
        logger.error(f"Error during disconnect: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")


def build_prefs_text(settings: dict) -> str:
    if not settings:
        return ""
    parts = []
    if settings.get("apply_food")      and settings.get("prefs_food"):      parts.append(f"선호 음식: {settings['prefs_food']}")
    if settings.get("apply_allowance") and settings.get("prefs_allowance"): parts.append(f"용돈: {settings['prefs_allowance']}")
    if settings.get("apply_location")  and settings.get("prefs_location"):  parts.append(f"거주: {settings['prefs_location']}")
    if settings.get("apply_body")      and settings.get("prefs_body"):      parts.append(f"신체: {settings['prefs_body']}")
    if settings.get("apply_mbti")      and settings.get("prefs_mbti"):      parts.append(f"MBTI: {settings['prefs_mbti']}")
    return " | ".join(parts)

# 사용자가 고르는 값 → 시스템 프롬프트에 섞을 “라벨”들
def build_freeform_prefs_text(settings: dict) -> str:
    raw = (settings or {}).get("freeform_prefs", "").strip()
    # 1~2줄 요약용 (너무 길면 잘라 쓰는 등 가볍게 가공)
    return raw[:500]

@cl.on_chat_start
async def start():
    await cl.ChatSettings(
        [
            TextInput(id="prefs_food",      label="어떤 음식을 좋아해?",      placeholder="예) 비건, 견과류 알레르기, 매운맛 선호..."),
            Switch(   id="apply_food",      label="이 선호를 자동 첨부",     initial=True),

            TextInput(id="prefs_allowance", label="일주일에 용돈이 얼마야?",  placeholder="예) 안받아ㅠ, 일주일에 만원..."),
            Switch(   id="apply_allowance", label="이 정보 자동 첨부",      initial=True),

            TextInput(id="prefs_location",  label="어디 살아?",             placeholder="예) 서울 강남구, 마포구..."),
            Switch(   id="apply_location",  label="이 정보 자동 첨부",      initial=True),

            TextInput(id="prefs_body",      label="키하고 몸무게 알려줘",    placeholder="예) 170cm, 60kg"),
            Switch(   id="apply_body",      label="이 정보 자동 첨부",      initial=True),

            TextInput(id="prefs_mbti",      label="MBTI도 알려줄래?",       placeholder="예) INFP, ENTP"),
            Switch(   id="apply_mbti",      label="이 정보 자동 첨부",      initial=True),

            TextInput(id="prefs_you",      label="너에 대해 알려줄래?",       placeholder="예) 난 헬충이야"),
            Switch(   id="apply_you",      label="이 정보 자동 첨부",      initial=True),
        ]
    ).send()

    cl.user_session.set("ui_settings", {})  # 초기값

    try:
        await setup_openai_realtime()
        await ensure_realtime_connected()
        logger.info("Connected to OpenAI realtime")
    except Exception as e:
        logger.error(f"Error in start: {e}")
        await cl.ErrorMessage(content=f"Failed to connect to OpenAI realtime: {e}").send()
    await cl.Message("안녕하세요! 이번 주 식사 기록을 입력하려면 `/week` 를 입력하세요. 현재 저장된 기록은 `/meals` 로 확인할 수 있어요.").send()
    
@cl.on_settings_update
async def on_settings_update(settings: dict):
    # 1) 세션에 저장
    cl.user_session.set("ui_settings", settings)

    # 2) 시스템 프롬프트 즉시 갱신
    openai_realtime = cl.user_session.get("openai_realtime")
    if openai_realtime and openai_realtime.is_connected():
        base = "당신은 도움이 되는 AI 어시스턴트입니다. 한국어로 대화형 톤으로 답하세요. 불릿/번호 매기기는 피합니다."
        prefs_line = build_prefs_text(settings)
        merged = base + (f"\n\n[사용자 사전 설정]\n{prefs_line}" if prefs_line else "")
        await openai_realtime.update_system_prompt(merged)
        await cl.Message("설정이 적용되었습니다. 다음 답변부터 반영돼요.").send()

@cl.on_message
async def on_message(message: cl.Message):
    content = (message.content or "").strip()

    # ① /week : 주간 식사 입력 폼 띄우기
    if content == "/week":
        current = cl.user_session.get("weekly_meals") or {}

        element = cl.CustomElement(
            name="WeeklyMeals",          # 프론트 컴포넌트 파일명과 동일 (WeeklyMeals.tsx/tsx)
            display="inline",
            props=make_week_table_props(current),
        )

        res = await cl.AskElementMessage(
            content="이번 주 식사를 표에 입력하고 제출하세요.",
            element=element,
            timeout=600,
        ).send()

        if not res or not res.get("submitted"):
            return  # 사용자가 취소/시간초과

        # 제출된 rows → 백엔드 포맷으로 변환하여 저장
        weekly_meals = rows_to_weekly_meals(res["rows"])
        cl.user_session.set("weekly_meals", weekly_meals)

        # 표 미리보기
        await cl.Message(content="### 이번 주 식사 기록이 저장됐어요!\n" + format_meal_table(weekly_meals)).send()

        # 시스템 프롬프트 갱신 (기존 코드 재사용)
        openai_realtime = cl.user_session.get("openai_realtime")
        if openai_realtime and openai_realtime.is_connected():
            base = "당신은 도움이 되는 AI 어시스턴트입니다. 한국어로 대화형 톤으로 답하세요. 불릿/번호 매기기는 피합니다."
            summary = summarize_meals_for_prompt(weekly_meals)
            merged = base + (f"\n\n[사용자 주간 식사 요약] {summary}" if summary else "")
            await openai_realtime.update_system_prompt(merged)
            await cl.Message("이제부터 추천/답변에 방금 입력한 식사 기록을 참고할게요.").send()
        return

    # ② /meals : 현재 저장본 보기
    if content == "/meals":
        weekly = cl.user_session.get("weekly_meals") or {}
        md = format_meal_table(weekly) if weekly else "아직 기록이 없어요. `/week`로 입력해 주세요."
        return await cl.Message(content="### 현재 저장된 식사 기록\n" + md).send()

    # ③ /meals reset : 초기화
    if content == "/meals reset":
        cl.user_session.set("weekly_meals", {})
        return await cl.Message("주간 식사 기록을 초기화했어요. `/week`로 다시 입력해 주세요.").send()

    # ④ 일반 메시지: 설정 + 식사요약을 프리앰블로 붙여 모델에 전달
    openai_realtime = cl.user_session.get("openai_realtime")
    if not openai_realtime or not openai_realtime.is_connected():
        return await cl.ErrorMessage("Realtime client not connected").send()

    await openai_realtime.update_session(modalities=["text"])

    settings = cl.user_session.get("ui_settings") or {}
    prefs_line = build_prefs_text(settings)

    weekly_meals = cl.user_session.get("weekly_meals") or {}
    meals_line = summarize_meals_for_prompt(weekly_meals)

    bits = []
    if prefs_line: bits.append(prefs_line)
    if meals_line: bits.append(f"최근 일주일 식사: {meals_line}")
    preamble = f"(참고: {' | '.join(bits)})\n" if bits else ""

    await openai_realtime.send_user_message_content([
        {"type": "input_text", "text": preamble + message.content}
    ])
