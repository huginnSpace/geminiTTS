import base64
import mimetypes
import os
import re
import struct
from dotenv import load_dotenv

load_dotenv()
# Ваши оригинальные импорты Gemini
from google import genai
from google.genai import types

# Импорты для FastAPI
from fastapi import FastAPI, HTTPException, Body
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import io

# --- Ваши оригинальные вспомогательные функции (БЕЗ ИЗМЕНЕНИЙ) ---
def save_binary_file(file_name, data):
    f = open(file_name, "wb")
    f.write(data)
    f.close()
    print(f"File saved to to: {file_name}")

def parse_audio_mime_type(mime_type: str) -> dict[str, int | None]:
    bits_per_sample = 16
    rate = 24000

    if mime_type: # Убедимся, что mime_type не None
        parts = mime_type.split(";")
        for param in parts: 
            param = param.strip()
            if param.lower().startswith("rate="):
                try:
                    rate_str = param.split("=", 1)[1]
                    rate = int(rate_str)
                except (ValueError, IndexError):
                    pass 
            # В вашем оригинальном коде это было elif param.startswith("audio/L"):
            # Чтобы это работало для "audio/L16", нужно учесть регистр или использовать .lower()
            elif param.lower().startswith("audio/l"): 
                try:
                    # Извлекаем число после 'L'
                    bps_str = param.split("L", 1)[1] if "L" in param else param.split("l", 1)[1]
                    bits_per_sample = int(bps_str)
                except (ValueError, IndexError, AttributeError):
                    pass

    return {"bits_per_sample": bits_per_sample, "rate": rate}

def convert_to_wav(audio_data: bytes, mime_type: str) -> bytes:
    parameters = parse_audio_mime_type(mime_type)
    bits_per_sample = parameters.get("bits_per_sample", 16)
    sample_rate = parameters.get("rate", 24000)
    
    if bits_per_sample is None or sample_rate is None:
        raise ValueError("Не удалось определить bits_per_sample или rate из MIME-типа для конвертации в WAV.")

    num_channels = 1
    data_size = len(audio_data)
    bytes_per_sample = bits_per_sample // 8
    block_align = num_channels * bytes_per_sample
    byte_rate = sample_rate * block_align
    chunk_size = 36 + data_size

    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF", chunk_size, b"WAVE", b"fmt ",
        16, 1, num_channels, sample_rate,
        byte_rate, block_align, bits_per_sample,
        b"data", data_size
    )
    return header + audio_data

# --- Конфигурация API ключа ---
# Ключ будет браться из переменной окружения GEMINI_API_KEY.
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
 # Ваш ключ из примера

if not GEMINI_API_KEY:
    # Если ключ не найден, возбуждаем ошибку. Приложение не запустится.
    # Это лучше, чем падать позже при попытке использовать None ключ.
    raise ValueError(
        "ОШИБКА: Переменная окружения GEMINI_API_KEY не установлена. "
        "Пожалуйста, установите ее перед запуском приложения. "
        "Например, при запуске Docker-контейнера через флаг -e GEMINI_API_KEY=\"ВАШ_КЛЮЧ\""
    )

# --- Адаптированная функция для генерации аудио, использующая ваш стиль ---
async def generate_audio_for_api(text_input: str, voice_input: str):
   # Инициализация клиента, как в вашем коде
    client = genai.Client(api_key=GEMINI_API_KEY)

    model = "gemini-2.5-flash-preview-tts" # Модель из вашего кода
    contents = [
        types.Content(
            role="user",
            parts=[
                types.Part.from_text(text=text_input), # Используем переданный текст
            ],
        ),
    ]
    # Конфигурация, как в вашем коде (сохраняем temperature=1, если это важно для вас)
    generate_content_config = types.GenerateContentConfig(
        temperature=1, # Как в вашем оригинальном коде
        response_modalities=["audio"],
        speech_config=types.SpeechConfig(
            voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfig(
                    voice_name=voice_input # Используем переданный голос
                )
            )
        ),
    )

    accumulated_audio_data = bytearray()
    source_audio_mime_type = None

    try:
        # Ваш оригинальный способ вызова стриминга
        for chunk in client.models.generate_content_stream(
            model=model,
            contents=contents,
            config=generate_content_config, # Имя параметра 'config' как в вашем коде
        ):
            if (
                chunk.candidates is None
                or not chunk.candidates[0].content # Проверка, что content существует
                or chunk.candidates[0].content.parts is None
            ):
                continue
            
            if chunk.candidates[0].content.parts: # Проверка, что список parts не пуст
                part = chunk.candidates[0].content.parts[0]
                if part.inline_data and part.inline_data.data:
                    inline_data_obj = part.inline_data # Переименовал для ясности
                    current_chunk_audio_data = inline_data_obj.data
                    
                    if source_audio_mime_type is None:
                        source_audio_mime_type = inline_data_obj.mime_type
                    elif source_audio_mime_type != inline_data_obj.mime_type:
                        # Это предупреждение полезно, но для API мы обычно продолжаем с первым типом
                        print(f"Предупреждение: MIME-тип изменился в потоке с {source_audio_mime_type} на {inline_data_obj.mime_type}")
                    
                    # Накапливаем сырые аудиоданные из каждого чанка
                    accumulated_audio_data.extend(current_chunk_audio_data)
                # Ваш оригинальный код также печатал chunk.text, если он был
                # elif hasattr(chunk, 'text') and chunk.text:
                # print(chunk.text) # Раскомментируйте, если нужно логировать текстовые части
    
    except Exception as e:
        # import traceback # Раскомментируйте для детальной отладки
        # traceback.print_exc() # Раскомментируйте для детальной отладки
        print(f"Ошибка во время вызова Gemini API: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка генерации TTS: {str(e)}")

    if not accumulated_audio_data:
        raise HTTPException(status_code=500, detail="Не были получены аудиоданные от сервиса TTS")

    final_audio_data_bytes = bytes(accumulated_audio_data)
    output_media_type_for_response = "audio/wav" # По умолчанию мы хотим вернуть WAV

    # Конвертация в WAV выполняется ОДИН РАЗ после сбора ВСЕХ чанков, если необходимо
    if source_audio_mime_type:
        # Оригинальная логика предполагала конвертацию, если mimetypes.guess_extension вернул None
        # Более надежно проверить, является ли исходный тип уже WAV
        if "wav" not in source_audio_mime_type.lower():
            try:
                print(f"Собранные данные имеют MIME-тип: {source_audio_mime_type}. Конвертация в WAV.")
                final_audio_data_bytes = convert_to_wav(final_audio_data_bytes, source_audio_mime_type)
            except Exception as e:
                print(f"Ошибка конвертации собранных аудиоданных в WAV: {e}")
                raise HTTPException(status_code=500, detail=f"Ошибка конвертации аудио в WAV: {str(e)}")
        else:
            # Если исходный тип уже WAV, используем его
            output_media_type_for_response = source_audio_mime_type
            print(f"Собранные данные уже в формате WAV (MIME-тип: {source_audio_mime_type}). Конвертация не требуется.")
    else:
        # Этого не должно произойти, если accumulated_audio_data не пусто
        raise HTTPException(status_code=500, detail="MIME-тип аудиоданных не был определен, хотя данные есть.")
        
    return final_audio_data_bytes, output_media_type_for_response

# --- FastAPI приложение ---
app = FastAPI()

class TTSRequest(BaseModel):
    text: str
    voice_name: str = "Zephyr" # Голос по умолчанию из вашего примера

@app.post("/generate-tts/") # Можно изменить имя эндпоинта при желании
async def api_generate_tts_endpoint(request: TTSRequest = Body(...)):
    if not request.text:
        raise HTTPException(status_code=400, detail="Поле 'text' не может быть пустым.")

    try:
        audio_bytes, media_type = await generate_audio_for_api(
            request.text, 
            request.voice_name
        )
        
        # Определяем расширение файла для Content-Disposition
        filename_extension = "wav" # По умолчанию wav
        if media_type and "/" in media_type:
            possible_ext = media_type.split("/")[-1]
            # Простой список распространенных аудио расширений
            if possible_ext in ["wav", "mp3", "ogg", "aac", "opus", "flac", "mpeg"]: 
                 filename_extension = possible_ext
        
        return StreamingResponse(
            io.BytesIO(audio_bytes), 
            media_type=media_type,
            headers={"Content-Disposition": f"attachment; filename=\"speech.{filename_extension}\""}
        )
    except HTTPException:
        raise # Перебрасываем HTTPException от FastAPI или нашей логики
    except Exception as e:
        print(f"Неожиданная ошибка в эндпоинте /generate-tts/: {e}")
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера при обработке TTS запроса.")

# Ваш оригинальный if __name__ == "__main__": generate() заменяется запуском Uvicorn
# Пример запуска: uvicorn main:app --reload (где main.py - имя вашего файла)
