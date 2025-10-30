import chainlit as cl
from uuid import uuid4
from chainlit.logger import logger
import traceback

from realtime import RealtimeClient

from dotenv import load_dotenv
load_dotenv(override=True)

async def setup_openai_realtime():
    """Instantiate and configure the OpenAI Realtime Client"""
    

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
    
    
    openai_realtime.on('conversation.updated', handle_conversation_updated)
    openai_realtime.on('conversation.item.completed', handle_item_completed)
    openai_realtime.on('conversation.interrupted', handle_conversation_interrupt)
    openai_realtime.on('server.response.done', handle_response_done)
    openai_realtime.on('error', handle_error)

    cl.user_session.set("openai_realtime", openai_realtime)
    

@cl.on_chat_start # 앱 시작 : setup_openai_realtime 호출 및 연결 (Realtime 세션을 초기화하고 WebSocket연결)
async def start():
    logger.info("Chat session started")
    try:
        await setup_openai_realtime()
        
        openai_realtime: RealtimeClient = cl.user_session.get("openai_realtime") # 성공하면 세션에 클라이언트를 저장
        if not openai_realtime:
            logger.error("Failed to get openai_realtime from session")
            await cl.ErrorMessage(content="Failed to initialize OpenAI realtime client").send()
            return False
            
        await openai_realtime.connect()
        logger.info("Connected to OpenAI realtime")
        return True
    except Exception as e:
        logger.error(f"Error in start function: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        await cl.ErrorMessage(content=f"Failed to connect to OpenAI realtime: {e}").send()
        return False


@cl.on_message # 사용자의 텍스트를 입력받음
async def on_message(message: cl.Message):
    try:
        openai_realtime: RealtimeClient = cl.user_session.get("openai_realtime")
        
        if not openai_realtime:
            logger.error("OpenAI realtime client not found in session")
            await cl.ErrorMessage(content="OpenAI realtime client not initialized").send()
            return
            
        if not openai_realtime.is_connected():
            logger.error("OpenAI realtime client not connected")
            await cl.ErrorMessage(content="OpenAI realtime client not connected").send()
            return
            
        # Set flag to indicate this is text input, not audio
        cl.user_session.set("is_text_input", True)
        
        # Configure for text-only response (no audio output for text input)
        await openai_realtime.update_session(modalities=["text"])
        
        await openai_realtime.send_user_message_content([{ "type": 'input_text', "text": message.content}]) # 사용자의 메시지를 RealtimeClient로 전송
        
    except Exception as e:
        logger.error(f"Error in on_message: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        await cl.ErrorMessage(content=f"Error processing message: {str(e)}").send()

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