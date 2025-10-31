import re
import os
import json
import time
import traceback

from uuid import uuid4
from datetime import datetime
from dotenv import load_dotenv
from typing import Optional, Tuple

import chainlit as cl
from chainlit.logger import logger
from chainlit.input_widget import TextInput, Switch

from realtime import RealtimeClient  # 외부 모듈 가정

load_dotenv(override=True)

# =========================
# Constants & Config
# =========================
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
os.makedirs(DATA_DIR, exist_ok=True)

DAYS = [
    ("mon", "월요일"), ("tue", "화요일"), ("wed", "수요일"),
    ("thu", "목요일"), ("fri", "금요일"), ("sat", "토요일"), ("sun", "일요일"),
]

BASE_SYSTEM_PROMPT = (
    "당신은 맞벌이 하시는 부모님을 둔 고등학교 친구들의 저녁을 책임지는 음식 전문가입니다. "
    "한국어로 대화형 톤으로 답하세요. 건강을 생각한 답변을 하세요. "
    "오디오를 사용해서 말할 수 있으므로 대화형에 맞게 응답하세요. 불릿/번호 매기기는 피합니다."
    "위치 정보에 대해서 물어볼 때는 naver-maps-mcp 툴을 사용하여 장소를 추천하세요."
    "그리고 응답을 할 때는 반드시 출처 정보를 포함하세요."
)

FILENAME_PREFIX = "user_state_"
FILENAME_REGEX = re.compile(r"^user_state_([a-f0-9\-]{6,})\.json$")

user_state_info_id = "user_state_d06b5981-2262-4f39-9157-1308e57740a7"

def _render_provenance_footer(prov_or_list) -> str:
    """단일 혹은 복수 provenance를 Markdown 풋터로 변환."""
    if not prov_or_list:
        return ""
    if isinstance(prov_or_list, dict):
        provs = [prov_or_list]
    else:
        provs = [p for p in (prov_or_list or []) if p]

    lines = ["\n\n---", "**출처**"]
    for p in provs:
        server = p.get("server", "?")
        tool = p.get("tool", "?")
        trace_id = p.get("trace_id", "?")
        lines.append(f"- `{server}` → `{tool}`  (trace: `{trace_id}`)")
    return "\n".join(lines)

def list_state_files() -> list[str]:
    """data/ 내 user_state_*.json 전부 나열"""
    return [
        os.path.join(DATA_DIR, f)
        for f in os.listdir(DATA_DIR)
        if f.startswith(FILENAME_PREFIX) and f.endswith(".json")
    ]

def _extract_state_id_from_path(path: str) -> Optional[str]:
    """파일 경로에서 state id 추출"""
    name = os.path.basename(path)
    m = FILENAME_REGEX.match(name)
    return m.group(1) if m else None

def _read_updated_at(path: str) -> int:
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f) or {}
            return int(data.get("updated_at", 0) or 0)
    except Exception:
        return 0

def pick_latest_state_id() -> Optional[str]:
    """가장 최근 updated_at 의 파일을 대표 state id로 선택"""
    files = list_state_files()
    if not files:
        return None
    latest: Tuple[int, str] = (0, "")
    for p in files:
        ts = _read_updated_at(p)
        if ts >= latest[0]:
            latest = (ts, p)
    return _extract_state_id_from_path(latest[1]) if latest[1] else None

def render_state_as_table(state: dict) -> str:
    ui = state.get("ui_settings", {})
    ts = state.get("updated_at")

    # 1️⃣ ui_settings 표
    label_map = {
        "prefs_food": "선호 음식",
        "prefs_allowance": "용돈",
        "prefs_location": "거주",
        "prefs_body": "신체",
        "prefs_mbti": "MBTI",
        "prefs_you": "자기소개",
    }

    ui_rows = []
    for key, label in label_map.items():
        val = ui.get(key)
        apply_flag = ui.get("apply_" + key.split("prefs_")[-1])
        if val:
            ui_rows.append(f"| {label} | {val} |")
        else:
            ui_rows.append(f"| {label} | {'활성' if apply_flag else '비활성'} |")

    ui_table = "| 항목 | 값 |\n|------|------|\n" + "\n".join(ui_rows)

    # 3️⃣ 업데이트 시간
    try:
        updated = datetime.fromtimestamp(int(ts)).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        updated = "알 수 없음"

    return (
        "## 📦 저장된 사용자 상태\n\n"
        "### ⚙️ 설정 정보\n"
        f"{ui_table}\n\n"
        f"🕒 **마지막 업데이트:** {updated}"
    )

def _load_state_file(path: str) -> dict:
    """단일 상태 파일 로드(없거나 파싱 실패 시 빈 기본값)."""
    if not os.path.exists(path):
        return {"ui_settings": {}, "weekly_meals": {}, "updated_at": 0}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f) or {}
            return {
                "ui_settings": data.get("ui_settings", {}) or {},
                "weekly_meals": data.get("weekly_meals", {}) or {},
                "updated_at": int(data.get("updated_at", 0) or 0),
            }
    except Exception:
        return {"ui_settings": {}, "weekly_meals": {}, "updated_at": 0}

def _merge_weekly_meals(a: dict, b: dict) -> dict:
    """요일별로 필드 단위 머지. b 가 a 를 덮어씀."""
    out = dict(a or {})
    for day, bval in (b or {}).items():
        aval = out.get(day, {})
        merged = {
            "what":  (bval.get("what")  if bval.get("what")  not in (None, "") else aval.get("what", "")),
            "where": (bval.get("where") if bval.get("where") not in (None, "") else aval.get("where", "")),
            "time":  (bval.get("time")  if bval.get("time")  not in (None, "") else aval.get("time", "")),
            "note":  (bval.get("note")  if bval.get("note")  not in (None, "") else aval.get("note", "")),
        }
        out[day] = merged
    return out

def _merge_states(base: dict, override: dict) -> dict:
    """ui_settings/weekly_meals 단위로 병합. override 가 base 를 덮어씀."""
    merged_ui = dict(base.get("ui_settings", {}) or {})
    merged_ui.update(override.get("ui_settings", {}) or {})  # 뒤가 우선

    merged_meals = _merge_weekly_meals(base.get("weekly_meals", {}) or {},
                                       override.get("weekly_meals", {}) or {})

    return {
        "ui_settings": merged_ui,
        "weekly_meals": merged_meals,
        "updated_at": max(int(base.get("updated_at", 0) or 0),
                          int(override.get("updated_at", 0) or 0)),
    }

def load_user_state_combined() -> dict:
    """
    data/의 user_state_*.json을 모두 병합해 반환.
    (뒤에 처리되는 파일이 우선. 파일 나열 순서는 OS에 따라 다를 수 있으므로
     updated_at 기준 정렬을 적용해도 좋습니다.)
    """
    files = list_state_files()
    state = {"ui_settings": {}, "weekly_meals": {}, "updated_at": 0}
    # updated_at 오름차순으로 정렬 후 병합 → 나중(최근) 파일이 우선
    files_sorted = sorted(files, key=_read_updated_at)
    for p in files_sorted:
        state = _merge_states(state, _load_state_file(p))
    return state

# =========================
# Persistence (user state)
# =========================
def _get_user_id() -> str:
    """
    저장/로드에 사용할 '대표 state id'.
    - 세션에 active_user_state_id 가 있으면 그것을 사용
    - 없으면 data/ 에서 최신 파일의 id 선택
    - 그것도 없으면 (완전 신규) 새 UUID 생성 후 세션에 저장
    """
    sid = cl.user_session.get("active_user_state_id")
    if sid:
        return sid

    latest = pick_latest_state_id()
    if latest:
        cl.user_session.set("active_user_state_id", latest)
        return latest

    # 완전 신규
    new_id = str(uuid4())
    cl.user_session.set("active_user_state_id", new_id)
    return new_id

def _user_state_path(uid: str) -> str:
    return os.path.join(DATA_DIR, f"user_state_{uid}.json")

def load_user_state() -> dict:
    """디스크에서 사용자 상태 복원."""
    path = _user_state_path(_get_user_id())
    if not os.path.exists(path):
        return {"ui_settings": {}, "weekly_meals": {}, "updated_at": 0}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"ui_settings": {}, "weekly_meals": {}, "updated_at": 0}

def save_user_state(ui_settings: dict | None = None, weekly_meals: dict | None = None) -> None:
    """사용자 상태 저장(부분 업데이트 가능, 원자적 저장)."""
    path = _user_state_path(_get_user_id())
    state = load_user_state()
    if ui_settings is not None:
        state["ui_settings"] = ui_settings
    if weekly_meals is not None:
        state["weekly_meals"] = weekly_meals
    state["updated_at"] = int(time.time())

    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)

# =========================
# UI helpers
# =========================
def build_prefs_text(settings: dict) -> str:
    """체크된 항목만 라벨로 압축."""
    if not settings:
        return ""
    parts = []
    if settings.get("apply_food") and settings.get("prefs_food"):
        parts.append(f"선호 음식: {settings['prefs_food']}")
    if settings.get("apply_allowance") and settings.get("prefs_allowance"):
        parts.append(f"용돈: {settings['prefs_allowance']}")
    if settings.get("apply_location") and settings.get("prefs_location"):
        parts.append(f"거주: {settings['prefs_location']}")
    if settings.get("apply_body") and settings.get("prefs_body"):
        parts.append(f"신체: {settings['prefs_body']}")
    if settings.get("apply_mbti") and settings.get("prefs_mbti"):
        parts.append(f"MBTI: {settings['prefs_mbti']}")
    return " | ".join(parts)

def summarize_meals_for_prompt(meals: dict) -> str:
    """프롬프트에 넣기 좋은 1~2줄 요약."""
    picks = []
    for key, label in DAYS:
        d = meals.get(key, {})
        if any(d.get(k) for k in ("what", "where", "time")):
            picks.append(f"{label}:{d.get('what','?')}@{d.get('where','?')}")
    return " / ".join(picks)[:500]

def make_week_table_props(weekly_meals: dict) -> dict:
    rows = []
    for key, label in DAYS:
        d = (weekly_meals or {}).get(key, {})
        rows.append({
            "dayKey": key, "dayLabel": label,
            "what": d.get("what", ""), "where": d.get("where", ""),
            "time": d.get("time", ""), "note": d.get("note", ""),
        })
    return {"rows": rows, "timeout": 600}

def rows_to_weekly_meals(rows: list[dict]) -> dict:
    out = {}
    for r in rows:
        out[r["dayKey"]] = {
            "what": (r.get("what") or "").strip(),
            "where": (r.get("where") or "").strip(),
            "time": (r.get("time") or "").strip(),
            "note": (r.get("note") or "").strip(),
        }
    return out

def format_meal_table(meals: dict) -> str:
    header = "| 요일 | 먹은 것 | 장소 | 시간 | 메모 |\n|---|---|---|---|---|\n"
    rows = []
    for key, label in DAYS:
        d = meals.get(key, {})
        rows.append(
            f"| {label} | {d.get('what','')} | {d.get('where','')} | {d.get('time','')} | {d.get('note','')} |"
        )
    return header + "\n".join(rows)

# =========================
# Realtime setup & helpers
# =========================
async def _update_system_prompt_from_context() -> None:
    """세션의 settings/weekly_meals를 기반으로 시스템 프롬프트 갱신."""
    openai_realtime: RealtimeClient = cl.user_session.get("openai_realtime")
    if not (openai_realtime and openai_realtime.is_connected()):
        return

    settings = cl.user_session.get("ui_settings") or {}
    meals = cl.user_session.get("weekly_meals") or {}

    prefs_line = build_prefs_text(settings)
    meals_line = summarize_meals_for_prompt(meals)

    extra = []
    if prefs_line:
        extra.append(f"[사용자 사전 설정]\n{prefs_line}")
    if meals_line:
        extra.append(f"[사용자 주간 식사 요약] {meals_line}")

    merged = BASE_SYSTEM_PROMPT + ("\n\n" + "\n".join(extra) if extra else "")
    await openai_realtime.update_system_prompt(merged)

async def setup_openai_realtime():
    """Realtime 클라이언트 초기화 및 이벤트 핸들러 등록."""
    openai_realtime = RealtimeClient(system_prompt=BASE_SYSTEM_PROMPT, max_tokens=4096)
    
    cl.user_session.set("openai_realtime", openai_realtime)
    cl.user_session.set("track_id", str(uuid4()))
    cl.user_session.set("is_text_input", True)  # 텍스트/오디오 입력 구분 플래그
    cl.user_session.set("current_transcript_msg", None)
    cl.user_session.set("current_text_msg", None)

    async def handle_mcp_tool_completed(event):
        prov = (event or {}).get("provenance")
        if not prov:
            return
        lst = cl.user_session.get("last_provenances") or []
        lst.append(prov)
        cl.user_session.set("last_provenances", lst)
        
        openai_realtime.on("mcp.tool.completed", handle_mcp_tool_completed)
        
    # --- Event handlers ---
    async def handle_conversation_updated(event):
        """오디오/텍스트 스트리밍 업데이트."""
        try:
            item = event.get("item")
            delta = event.get("delta") or {}

            # 텍스트 입력 중에는 음성 인식 이벤트를 생략
            if item and "input_audio_transcription" in item.get("type", "") and cl.user_session.get("is_text_input", False):
                return

            if item and "input_audio_transcription" in item.get("type", "") and "transcript" in delta:
                msg = cl.Message(content=delta["transcript"], author="user")
                msg.type = "user_message"
                await msg.send()

            # 오디오 스트림
            if "audio" in delta:
                await cl.context.emitter.send_audio_chunk(
                    cl.OutputAudioChunk(mimeType="pcm16", data=delta["audio"], track=cl.user_session.get("track_id"))
                )

            # 어시스턴트 음성 답변의 실시간 텍스트 전사
            if "transcript" in delta and item and item.get("role") == "assistant":
                transcript_msg = cl.user_session.get("current_transcript_msg")
                if not transcript_msg:
                    logger.info("Audio response started")
                    transcript_msg = cl.Message(content="", author="assistant")
                    cl.user_session.set("current_transcript_msg", transcript_msg)
                    await transcript_msg.send()
                transcript_msg.content += delta["transcript"]
                await transcript_msg.update()

            # 어시스턴트 텍스트 답변 스트림
            if "text" in delta and item and item.get("role") == "assistant":
                text_msg = cl.user_session.get("current_text_msg")
                if not text_msg:
                    logger.info("Text response started")
                    text_msg = cl.Message(content="", author="assistant")
                    cl.user_session.set("current_text_msg", text_msg)
                    await text_msg.send()
                text_msg.content += delta["text"]
                await text_msg.update()

        except Exception as e:
            logger.error(f"Error in handle_conversation_updated: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise e

    async def handle_item_completed(item):
        """아이템 단위 스트림 완료 처리."""
        try:
            it = item.get("item", {})
            content = (it.get("content") or [{}])[0]
            ctype = content.get("type")

            if it.get("type") == "message" and ctype == "audio":
                logger.info("Audio response completed")
                transcript_msg = cl.user_session.get("current_transcript_msg")
                cl.user_session.set("current_transcript_msg", None)
                final_text = content.get("transcript", transcript_msg.content if transcript_msg else "")
                if transcript_msg:
                    transcript_msg.content = final_text
                    await transcript_msg.update()
                elif final_text:
                    await cl.Message(content=final_text, author="assistant").send()

                provs = cl.user_session.get("last_provenances")
                if provs:
                    footer = _render_provenance_footer(provs)
                    if transcript_msg:
                        transcript_msg.content = (transcript_msg.content or "") + footer
                        transcript_msg.metadata = {"provenance": provs}
                        await transcript_msg.update()
                    elif final_text:
                        await cl.Message(content=final_text + footer, author="assistant", metadata={"provenance": provs}).send()
                    # 한 턴 끝났으니 초기화
                    cl.user_session.set("last_provenances", None)
                
            elif it.get("type") == "message" and ctype == "text":
                logger.info("Text response completed")
                text_msg = cl.user_session.get("current_text_msg")
                cl.user_session.set("current_text_msg", None)
                final_text = content.get("text", text_msg.content if text_msg else "")
                if text_msg:
                    text_msg.content = final_text
                    await text_msg.update()
                elif final_text:
                    await cl.Message(content=final_text, author="assistant").send()
                provs = cl.user_session.get("last_provenances")
                if provs:
                    footer = _render_provenance_footer(provs)
                    if text_msg:
                        text_msg.content = (text_msg.content or "") + footer
                        text_msg.metadata = {"provenance": provs}
                        await text_msg.update()
                    elif final_text:
                        await cl.Message(content=final_text + footer, author="assistant", metadata={"provenance": provs}).send()
                    cl.user_session.set("last_provenances", None)

            elif it.get("type") == "function_call":
                logger.info("Function call completed")
                cl.user_session.set("current_transcript_msg", None)
                cl.user_session.set("current_text_msg", None)

        except Exception as e:
            logger.error(f"Error in handle_item_completed: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise e

    async def handle_conversation_interrupt(_event):
        """이전 오디오 재생 중단."""
        cl.user_session.set("track_id", str(uuid4()))
        await cl.context.emitter.send_audio_interrupt()

    async def handle_response_done(_event):
        """응답 완료 후 정리."""
        cl.user_session.set("is_text_input", False)
        cl.user_session.set("current_transcript_msg", None)
        cl.user_session.set("current_text_msg", None)

    async def handle_error(event):
        logger.error(f"Realtime connection error: {event}")
        await cl.ErrorMessage(content=f"Realtime connection error: {event}").send()

    # 이벤트 바인딩
    openai_realtime.on("conversation.updated", handle_conversation_updated)
    openai_realtime.on("conversation.item.completed", handle_item_completed)
    openai_realtime.on("conversation.interrupted", handle_conversation_interrupt)
    openai_realtime.on("server.response.done", handle_response_done)
    openai_realtime.on("error", handle_error)

async def ensure_realtime_connected() -> RealtimeClient:
    """Realtime 연결 보장."""
    openai_realtime: RealtimeClient = cl.user_session.get("openai_realtime")
    if not openai_realtime:
        await setup_openai_realtime()
        openai_realtime = cl.user_session.get("openai_realtime")
    if not openai_realtime.is_connected():
        await openai_realtime.connect()
        if hasattr(openai_realtime, "wait_for_session_created"):
            await openai_realtime.wait_for_session_created()
    return openai_realtime

# =========================
# Chainlit hooks
# =========================
@cl.on_audio_start
async def on_audio_start():
    logger.info("Audio recording started")
    return True

@cl.on_audio_chunk
async def on_audio_chunk(chunk: cl.InputAudioChunk):
    try:
        openai_realtime: RealtimeClient = cl.user_session.get("openai_realtime")
        if openai_realtime and openai_realtime.is_connected():
            cl.user_session.set("is_text_input", False)
            await openai_realtime.update_session(modalities=["text", "audio"])
            await openai_realtime.append_input_audio(chunk.data)
        else:
            logger.warning("RealtimeClient is not connected when processing audio chunk")
    except Exception as e:
        logger.error(f"Error in on_audio_chunk: {e}")
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
        logger.error(f"Error during disconnect: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")

@cl.on_chat_start
async def start():
    # 🔍 data/ 폴더에 user_state_*.json 파일 존재 여부 확인
    has_state_files = any(
        f.startswith("user_state_") and f.endswith(".json")
        for f in os.listdir(DATA_DIR)
    )

    if has_state_files:
        # ✅ 기존 사용자: 병합 로드 + 최신 파일을 대표로
        state = load_user_state_combined()
        cl.user_session.set("ui_settings", state.get("ui_settings") or {})
        cl.user_session.set("weekly_meals", state.get("weekly_meals") or {})
        # 대표 파일 id를 최신 파일로 설정
        latest_id = pick_latest_state_id()
        if latest_id:
            cl.user_session.set("active_user_state_id", latest_id)
        first_time = False
    else:
        # 🆕 신규 사용자: 완전 초기 상태 + 새 파일명(새 ID) 부여
        cl.user_session.set("ui_settings", {})
        cl.user_session.set("weekly_meals", {})
        cl.user_session.set("active_user_state_id", str(uuid4()))  # ⭐ 새 파일명용 ID
        first_time = True

    await cl.ChatSettings([
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

        TextInput(id="prefs_you",       label="너에 대해 알려줄래?",      placeholder="예) 난 헬충이야"),
        Switch(   id="apply_you",       label="이 정보 자동 첨부",      initial=True),
    ]).send()

    try:
        await setup_openai_realtime()
        await ensure_realtime_connected()
        await _update_system_prompt_from_context()
        logger.info("Connected to OpenAI realtime")
    except Exception as e:
        logger.error(f"Error in start: {e}")
        await cl.ErrorMessage(content=f"Failed to connect to OpenAI realtime: {e}").send()
    if first_time:
        await cl.Message(
            "## 👋 처음 오셨네요!\n"
            "🍱 내맘내밥 – 식사 기록 도우미야 😊\n\n"
            "지금부터 너에 대해서 알려줘!\n"
            "`/week`로 이번 주 식사도 기록해볼 수 있어요.\n"
            "• `/week` → 이번 주 식사 기록하기\n"
            "• `/info` → 내 정보 보기\n"
        ).send()
    else:
        await cl.Message(
            "## 안녕? 오랜만이야!\n"
            "이전 세션의 **설정**과 **주간 식사 기록**을 불러왔어요.\n\n"
            "• `/week` → 이번 주에 뭘 먹었는지 기록해줘\n"
            "• `/meals` → 이번 주에 너가 뭘 먹었는지 알 수 있어!\n"
            "• `/info` → 너의 정보를 알 수 있어\n"
        ).send()
        
@cl.on_settings_update
async def on_settings_update(settings: dict):
    cl.user_session.set("ui_settings", settings)
    save_user_state(ui_settings=settings, weekly_meals=cl.user_session.get("weekly_meals") or {})
    await _update_system_prompt_from_context()
    await cl.Message("설정이 적용되었습니다. 다음 답변부터 반영돼요.").send()

@cl.on_message
async def on_message(message: cl.Message):
    content = (message.content or "").strip()

    # ① /week : 주간 식사 입력 폼
    if content == "/week":
        current = cl.user_session.get("weekly_meals") or {}
        element = cl.CustomElement(
            name="WeeklyMeals",  # 프런트 컴포넌트명과 일치
            display="inline",
            props=make_week_table_props(current),
        )
        res = await cl.AskElementMessage(
            content="이번 주 식사를 표에 입력하고 제출하세요.",
            element=element,
            timeout=600,
        ).send()
        if not res or not res.get("submitted"):
            return

        weekly_meals = rows_to_weekly_meals(res["rows"])
        cl.user_session.set("weekly_meals", weekly_meals)
        save_user_state(ui_settings=cl.user_session.get("ui_settings") or {}, weekly_meals=weekly_meals)

        await cl.Message(content="### 이번 주 식사 기록이 저장됐어요!\n" + format_meal_table(weekly_meals)).send()
        await _update_system_prompt_from_context()
        await cl.Message("이제부터 추천/답변에 방금 입력한 식사 기록을 참고할게요.").send()
        return

    # ② /meals : 주간 식사 기록 출력
    if content == "/meals":
        meals = cl.user_session.get("weekly_meals") or {}
        if not meals:
            await cl.Message("🍽️ 아직 저장된 식사 기록이 없어요! `/week`로 입력해보세요.").send()
        else:
            table = format_meal_table(meals)
            await cl.Message(f"## 🍱 이번 주 식사 기록\n\n{table}").send()
            # note에 숫자가 있을 경우 합산
            try:
                total = sum(int((d.get("note") or "0").strip() or 0) for d in meals.values())
                if total > 0:
                    await cl.Message(f"이번 주 총 식비 메모 합계: **{total}원**").send()
            except ValueError:
                pass
        return

    # ③ /meals reset : 초기화
    if content == "/meals reset":
        cl.user_session.set("weekly_meals", {})
        save_user_state(ui_settings=cl.user_session.get("ui_settings") or {}, weekly_meals={})
        await _update_system_prompt_from_context()
        return await cl.Message("주간 식사 기록을 초기화했어요. `/week`로 다시 입력해 주세요.").send()

    # /info 명령 처리
    if content == "/info":
        state = load_user_state()  # 또는 load_user_state_combined()
        md = render_state_as_table(state)
        await cl.Message(content=md).send()
        return

    # ④ /save : 현재 상태 저장
    if content == "/save":
        save_user_state(
            ui_settings=cl.user_session.get("ui_settings") or {},
            weekly_meals=cl.user_session.get("weekly_meals") or {},
        )
        await cl.Message("✅ 현재 설정/식사 기록을 디스크에 저장했어요!").send()
        return

    # ⑤ 일반 메시지: 프리앰블 붙여 모델에 전달
    openai_realtime: RealtimeClient = cl.user_session.get("openai_realtime")
    if not openai_realtime or not openai_realtime.is_connected():
        return await cl.ErrorMessage("Realtime client not connected").send()

    await openai_realtime.update_session(modalities=["text"])

    settings = cl.user_session.get("ui_settings") or {}
    weekly_meals = cl.user_session.get("weekly_meals") or {}

    bits = []
    prefs_line = build_prefs_text(settings)
    meals_line = summarize_meals_for_prompt(weekly_meals)
    if prefs_line:
        bits.append(prefs_line)
    if meals_line:
        bits.append(f"최근 일주일 식사: {meals_line}")
    preamble = f"(참고: {' | '.join(bits)})\n" if bits else ""

    await openai_realtime.send_user_message_content([
        {"type": "input_text", "text": preamble + message.content}
    ])
