import base64
import os
import logging
from typing import Optional, Dict, Any

import requests
from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
from twilio.rest import Client
from dotenv import load_dotenv

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

load_dotenv()

app = Flask(__name__)

# Twilio configuration
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_NUMBER = os.getenv("TWILIO_NUMBER")
twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

# Azure OpenAI configuration
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
AZURE_OPENAI_KEY = os.getenv("AZURE_OPENAI_KEY")
GPT_MODEL = os.getenv("GPT_MODEL")
GPT_RESPONSE_CHARACTER_LIMIT = 1500

# Temporary storage for image URL
temporary_image_storage: Dict[str, str] = {}


def download_and_encode_image(media_url: str) -> Optional[str]:
    """Download and encode image to base64."""
    try:
        response = requests.get(
            media_url,
            auth=(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN),
            headers={"Accept": "image/*"},
        )
        response.raise_for_status()
        base64_image = base64.b64encode(response.content).decode("utf-8")
        logger.info("Image saved as base64")
        return base64_image
    except requests.RequestException as e:
        logger.exception(f"Error downloading or encoding image: {str(e)}")
        return None


def get_gpt_response(query: str, whatsapp_number: str) -> Optional[str]:
    """Get response from GPT model."""
    logger.info(f"Requesting ChatGPT data for query: {query}")

    gpt_query_body = {
        "model": GPT_MODEL,
        "max_tokens": 100,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": f"Limit your response to {GPT_RESPONSE_CHARACTER_LIMIT} characters for this query: {query}",
                    }
                ],
            }
        ],
    }

    if whatsapp_number in temporary_image_storage:
        logger.info(f"Saved image found, adding to query")
        gpt_query_body["messages"][0]["content"].append(
            {
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/jpeg;base64,{temporary_image_storage[whatsapp_number]}"
                },
            }
        )
        del temporary_image_storage[whatsapp_number]

    try:
        response = requests.post(
            AZURE_OPENAI_ENDPOINT,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {AZURE_OPENAI_KEY}",
            },
            json=gpt_query_body,
        )
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"] if "choices" in data else None
    except requests.RequestException as e:
        logger.exception(f"Error getting GPT response: {str(e)}")
        return None


@app.route("/webhook", methods=["POST"])
def webhook():
    """Handle incoming WhatsApp messages."""
    incoming_msg = request.values.get("Body", "").lower()
    whatsapp_number = request.values.get("From", "").split("whatsapp:")[-1]
    logger.info("Incoming request: %s", request.values)

    resp = MessagingResponse()

    if "MediaUrl0" in request.values:
        handle_image_message(request.values["MediaUrl0"], whatsapp_number, resp)
    else:
        handle_text_message(incoming_msg, whatsapp_number, resp)

    return str(resp)


def handle_image_message(media_url: str, whatsapp_number: str, resp: MessagingResponse):
    """Handle incoming image messages."""
    base64_image = download_and_encode_image(media_url)
    if base64_image:
        temporary_image_storage[whatsapp_number] = base64_image
        resp.message("Image received. What would you like to know about this image?")
    else:
        resp.message(
            "Sorry, I couldn't process the image. Please try sending it again."
        )


def handle_text_message(
    incoming_msg: str, whatsapp_number: str, resp: MessagingResponse
):
    """Handle incoming text messages."""
    response = get_gpt_response(incoming_msg, whatsapp_number)
    if response:
        send_chunked_response(response, resp)
    else:
        resp.message("I'm ready for your question about the image.")


def send_chunked_response(response: str, resp: MessagingResponse):
    """Send response in chunks if it's too long."""
    message_parts = [response[i : i + 1590] for i in range(0, len(response), 1590)]
    for part in message_parts:
        resp.message(f"AI: {part}")


@app.route("/", methods=["GET"])
def index():
    """Health check endpoint."""
    return {"msg": "working"}


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
