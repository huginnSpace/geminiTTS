import base64
import mimetypes
import os
import re
import struct
from dotenv import load_dotenv

load_dotenv()
# Your original Gemini imports
from google import genai
from google.genai import types

# Imports for FastAPI
from fastapi import FastAPI, HTTPException, Body
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import io

# --- Your original helper functions (NO CHANGES) ---
def save_binary_file(file_name, data):
    f = open(file_name, "wb")
    f.write(data)
    f.close()
    print(f"File saved to to: {file_name}")

def parse_audio_mime_type(mime_type: str) -> dict[str, int | None]:
    bits_per_sample = 16
    rate = 24000

    if mime_type: # Make sure mime_type is not None
        parts = mime_type.split(";")
        for param in parts: 
            param = param.strip()
            if param.lower().startswith("rate="):
                try:
                    rate_str = param.split("=", 1)[1]
                    rate = int(rate_str)
                except (ValueError, IndexError):
                    pass 
            # In your original code this was elif param.startswith("audio/L"):
            # To make it work for "audio/L16", you need to consider the case or use .lower()
            elif param.lower().startswith("audio/l"): 
                try:
                    # Extract the number after 'L'
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
        raise ValueError("Failed to determine bits_per_sample or rate from MIME type for WAV conversion.")

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

# --- API key configuration ---
# The key will be taken from the environment variable GEMINI_API_KEY.
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
 # Your key from the example

if not GEMINI_API_KEY:
    # If the key is not found, raise an error. The application will not start.
    # This is better than failing later when trying to use a None key.
    raise ValueError(
        "ERROR: The GEMINI_API_KEY environment variable is not set. "
        "Please set it before running the application. "
        "For example, when running a Docker container via the -e GEMINI_API_KEY=\"YOUR_KEY\" flag"
    )

# --- Adapted function for generating audio, using your style ---
async def generate_audio_for_api(text_input: str, voice_input: str):
   # Initialize the client, as in your code
    client = genai.Client(api_key=GEMINI_API_KEY)

    model = "gemini-2.5-flash-preview-tts" # Model from your code
    contents = [
        types.Content(
            role="user",
            parts=[
                types.Part.from_text(text=text_input), # Use the passed text
            ],
        ),
    ]
    # Configuration, as in your code (save temperature=1, if this is important to you)
    generate_content_config = types.GenerateContentConfig(
        temperature=1, # As in your original code
        response_modalities=["audio"],
        speech_config=types.SpeechConfig(
            voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfig(
                    voice_name=voice_input # Use the passed voice
                )
            )
        ),
    )

    accumulated_audio_data = bytearray()
    source_audio_mime_type = None

    try:
        # Your original way of calling streaming
        for chunk in client.models.generate_content_stream(
            model=model,
            contents=contents,
            config=generate_content_config, # Parameter name 'config' as in your code
        ):
            if (
                chunk.candidates is None
                or not chunk.candidates[0].content # Check that content exists
                or chunk.candidates[0].content.parts is None
            ):
                continue
            
            if chunk.candidates[0].content.parts: # Check that the parts list is not empty
                part = chunk.candidates[0].content.parts[0]
                if part.inline_data and part.inline_data.data:
                    inline_data_obj = part.inline_data # Renamed for clarity
                    current_chunk_audio_data = inline_data_obj.data
                    
                    if source_audio_mime_type is None:
                        source_audio_mime_type = inline_data_obj.mime_type
                    elif source_audio_mime_type != inline_data_obj.mime_type:
                        # This warning is useful, but for the API we usually continue with the first type
                        print(f"Warning: MIME type changed in stream from {source_audio_mime_type} to {inline_data_obj.mime_type}")
                    
                    # Accumulate raw audio data from each chunk
                    accumulated_audio_data.extend(current_chunk_audio_data)
                # Your original code also printed chunk.text, if it was
                # elif hasattr(chunk, 'text') and chunk.text:
                # print(chunk.text) # Uncomment if you need to log text parts
    
    except Exception as e:
        # import traceback # Uncomment for detailed debugging
        # traceback.print_exc() # Uncomment for detailed debugging
        print(f"Error during Gemini API call: {e}")
        raise HTTPException(status_code=500, detail=f"TTS generation error: {str(e)}")

    if not accumulated_audio_data:
        raise HTTPException(status_code=500, detail="No audio data received from TTS service")

    final_audio_data_bytes = bytes(accumulated_audio_data)
    output_media_type_for_response = "audio/wav" # By default we want to return WAV

    # Conversion to WAV is performed ONCE after collecting ALL chunks, if necessary
    if source_audio_mime_type:
        # Original logic assumed conversion if mimetypes.guess_extension returned None
        # It is more reliable to check if the source type is already WAV
        if "wav" not in source_audio_mime_type.lower():
            try:
                print(f"Collected data has MIME type: {source_audio_mime_type}. Converting to WAV.")
                final_audio_data_bytes = convert_to_wav(final_audio_data_bytes, source_audio_mime_type)
            except Exception as e:
                print(f"Error converting collected audio data to WAV: {e}")
                raise HTTPException(status_code=500, detail=f"Error converting audio to WAV: {str(e)}")
        else:
            # If the source type is already WAV, use it
            output_media_type_for_response = source_audio_mime_type
            print(f"Collected data is already in WAV format (MIME type: {source_audio_mime_type}). Conversion not required.")
    else:
        # This should not happen if accumulated_audio_data is not empty
        raise HTTPException(status_code=500, detail="MIME type of audio data was not determined, although data exists.")
        
    return final_audio_data_bytes, output_media_type_for_response

# --- FastAPI application ---
app = FastAPI()

class TTSRequest(BaseModel):
    text: str
    voice_name: str = "Zephyr" # Default voice from your example

@app.post("/generate-tts/") # You can change the endpoint name if you wish
async def api_generate_tts_endpoint(request: TTSRequest = Body(...)):
    if not request.text:
        raise HTTPException(status_code=400, detail="The 'text' field cannot be empty.")

    try:
        audio_bytes, media_type = await generate_audio_for_api(
            request.text, 
            request.voice_name
        )
        
        # Determine the file extension for Content-Disposition
        filename_extension = "wav" # Default wav
        if media_type and "/" in media_type:
            possible_ext = media_type.split("/")[-1]
            # Simple list of common audio extensions
            if possible_ext in ["wav", "mp3", "ogg", "aac", "opus", "flac", "mpeg"]: 
                 filename_extension = possible_ext
        
        return StreamingResponse(
            io.BytesIO(audio_bytes), 
            media_type=media_type,
            headers={"Content-Disposition": f"attachment; filename=\"speech.{filename_extension}\""}
        )
    except HTTPException:
        raise # Re-raise HTTPException from FastAPI or our logic
    except Exception as e:
        print(f"Unexpected error in the /generate-tts/ endpoint: {e}")
        raise HTTPException(status_code=500, detail="Internal server error while processing TTS request.")

# Your original if __name__ == "__main__": generate() is replaced by running Uvicorn
# Example launch: uvicorn main:app --reload (where main.py is the name of your file)
