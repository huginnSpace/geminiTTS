# Gemini TTS API (Text-to-Speech)

This application is a FastAPI service wrapped in a Docker container that provides an API for converting text to speech (TTS) using the Google Gemini API.

## Features

*   Text-to-speech conversion via Google Gemini.
*   Voice selection (e.g., "Zephyr").
*   Returns audio file in MP3/WAV format (or in the original format if it is already WAV).
*   Easily deployable with Docker.

## Prerequisites

1.  **Docker**: Ensure that Docker is installed and running on your computer. ([Docker Installation Guide](https://docs.docker.com/get-docker/))
2.  **Google Gemini API Key**: You need a valid API key from Google to access the Gemini API. You can get it from [Google AI Studio](https://aistudio.google.com/app/apikey) or Google Cloud Console.

## Project Structure

*   .
*   ├── Dockerfile        # Instructions for building the Docker image
*   ├── main.py           # Main code for the FastAPI application
*   ├── README.md         # This file
*   └── requirements.txt  # List of Python dependencies

## Setup and Installation

1.  **Clone the repository** (if applicable) or ensure you have all project files (`main.py`, `Dockerfile`, `requirements.txt`).

2.  **Gemini API Key**:
    The application requires `GEMINI_API_KEY` to be set as an environment variable. **Without this key, the application will not start.**

## Building the Docker Image

Navigate to the root directory of the project in your terminal and run the following command to build the Docker image:

```bash
docker build -t gemini-tts-api .
```

*   -t gemini-tts-api: Sets the name (tag) for your image. You can choose a different name.
*   .: Specifies that the Dockerfile and build context are in the current directory.

### Running the Docker Container

After successfully building the image, run the Docker container:

```bash
docker run -d -p 8000:8000 -e GEMINI_API_KEY="YOUR_VALID_API_KEY" --name my-tts-container gemini-tts-api
```

## Using the API

After starting the container, the API will be available on the port you specified (e.g., `8000`).

### Endpoint

*   **URL:** `/generate-tts/`
*   **Method:** `POST`

### Request Body

The request must be in **JSON** format and contain the following fields:

*   `text` (`string`, **required**) — The text to convert to speech.
*   `voice_name` (`string`, optional) — The name of the voice for speech synthesis.
    The default is `"Zephyr"`. A list of available voices can be found in the **Google Gemini** documentation.

```json
{
  "text": "Hello, this is Gemini voice assistant!",
  "voice_name": "Zephyr"
}
```

### Example Request using `curl`

Replace `8001` with your host port if you used a different one.

#### Bash

```bash
curl -X POST "http://localhost:8000/generate-tts/" \
     -H "Content-Type: application/json" \
     -d '{"text": "This is a test message for Gemini TTS.", "voice_name": "Zephyr"}' \
     --output speech_output.wav
```

## Description

This command will send a request and save the received audio file as `speech_output.wav` in the current directory.

---

## Successful Response

*   **Status code:** `200 OK`
*   **Response body:** Binary data of the audio file.
*   **Headers:**
    *   `Content-Type`: e.g., `audio/wav`
    *   `Content-Disposition`: e.g., `attachment; filename="speech.wav"`

---

## Errors

*   **400 Bad Request**
    Occurs if the `text` field is empty or the request is invalid.

*   **422 Unprocessable Entity**
    If the request body does not conform to the Pydantic model (e.g., incorrect data types).

*   **500 Internal Server Error**
    Server-side errors, including:
    *   Problems with the Gemini API (invalid key, service failure, etc.)
    *   Audio conversion errors.
    Check the container logs for diagnostics.

---

## Important

If the `GEMINI_API_KEY` variable is not set at startup, the container will not start correctly. You will see an error in the Docker logs or when trying to start.
