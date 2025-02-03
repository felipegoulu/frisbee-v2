import logging
from flask import current_app, jsonify
import json
import requests

# from app.services.openai_service import generate_response
import re

def log_http_response(response):
    logging.info(f"Status: {response.status_code}")
    logging.info(f"Content-type: {response.headers.get('content-type')}")
    logging.info(f"Body: {response.text}")

def get_text_message_input(recipient, text):
    return json.dumps(
        {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": recipient,
            "type": "text",
            "text": {"preview_url": False, "body": text},
        }
    )

def get_text_message_input_modify_cart(recipient, text):
    return json.dumps(
        {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": recipient,
            "type": "interactive",
            "interactive": {
                "type": "button", 
                "body": {
                    "text": text
                },
                "action": {
                    "buttons": [
                        {
                            "type": "reply",
                            "reply": {
                                "id": "confirm_order",
                                "title": "Modificar Carrito"
                            }
                        },
                                              {
                            "type": "reply",
                            "reply": {
                                "id": "buy_cart",
                                "title": "Comprar Carrito"
                            }
                        }
                    ]
                }
            }
        })

def get_text_message_input_search_jumbo(recipient, text, reply_text = "Busca en Jumbo"):
    return json.dumps(
        {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": recipient,
            "type": "interactive",
            "interactive": {
                "type": "button", 
                "body": {
                    "text": text
                },
                "action": {
                    "buttons": [
                        {
                            "type": "reply",
                            "reply": {
                                "id": "confirm_order",
                                "title": reply_text
                            }
                        }
                    ]
                }
            }
        })

def send_message(data, wa_id, response_text, carrito, node, raw_response):
    ''' manda mensaje y tambien lo guarda en la base de datos'''

    headers = {
        "Content-type": "application/json",
        "Authorization": f"Bearer {current_app.config['ACCESS_TOKEN']}",
    }

    url = f"https://graph.facebook.com/{current_app.config['VERSION']}/{current_app.config['PHONE_NUMBER_ID']}/messages"

    try:
        response = requests.post(
            url, data=data, headers=headers, timeout=10
        )  # 10 seconds timeout as an example
              # Log para debug

        # Imprime la respuesta completa para debugging
        ##print("Response status:", response.status_code)
        #print("Response text:", response.text)

        response.raise_for_status()  # Raises an HTTPError if the HTTP request returned an unsuccessful status code

        # Extraer el message_id de la respuesta
        response_data = response.json()
        message_id = response_data.get('messages', [{}])[0].get('id')

        from backend.db import save_message
        carrito = json.dumps(carrito)

        print(f"raw response: {raw_response}")
       
        message_content = raw_response if raw_response else response_text

        print(f"saving... {message_content}")

        save_message(wa_id, "assistant", message_content, message_id, carrito, node)
        
        return message_id, response

    except requests.Timeout:
        logging.error("Timeout occurred while sending message")
        return None, jsonify({"status": "error", "message": "Request timed out"}), 408
    except requests.RequestException as e:
        logging.error(f"Request failed due to: {e}")
        return None, jsonify({"status": "error", "message": "Failed to send message"}), 500

def process_text_for_whatsapp(text):
    # Remove brackets
    pattern = r"\【.*?\】"
    # Substitute the pattern with an empty string
    text = re.sub(pattern, "", text).strip()

    # Pattern to find double asterisks including the word(s) in between
    pattern = r"\*\*(.*?)\*\*"

    # Replacement pattern with single asterisks
    replacement = r"*\1*"

    # Substitute occurrences of the pattern with the replacement
    whatsapp_style_text = re.sub(pattern, replacement, text)

    return whatsapp_style_text

def process_whatsapp_message(body):
    ''' Agarra el mensaje del usuario, lo procesa, y luego genera mensaje y responde'''

    wa_id = body["entry"][0]["changes"][0]["value"]["contacts"][0]["wa_id"]
    name = body["entry"][0]["changes"][0]["value"]["contacts"][0]["profile"]["name"]
    message = body["entry"][0]["changes"][0]["value"]["messages"][0]
    
    if "text" in message:
        message_body = message["text"]["body"]
        parent_msg_id = ""
    elif "interactive" in message:
        message_body = message["interactive"]["button_reply"]["title"]
        # Obtener el ID del mensaje original (al que se respondió)
        parent_msg_id = message.get("context", {}).get("id")
        logging.info(f"Respuesta al mensaje: {parent_msg_id}")
    else:
        logging.error(f"Tipo de mensaje no soportado: {message}")
        return 'tipo de mensaje no soportado'

    from app.services.openai_service import generate_response  # Add this import

    msg_id = message["id"]

    # antes de generate_response debo verificar que msg_id no exista, si ya existe debo hacer nada.
    from backend.db import check_duplicated
    is_duplicated = check_duplicated(wa_id, msg_id)

    if is_duplicated:
        return 'duplicado'
    else:
        print("generating reponse...")
        response, has_json, carrito, node, raw_response = generate_response(message_body, wa_id,msg_id,name, parent_msg_id)
        print("response generated")
        response = process_text_for_whatsapp(response)
        data = get_text_message_input(wa_id, response)
        
        send_message(data, wa_id, response, carrito, node, raw_response)

        if has_json:
            if node == "product_selection":
                response = "Si quieres buscar los productos en Jumbo..."
                raw_response = ""
                data = get_text_message_input_search_jumbo(wa_id, response) 
                send_message(data, wa_id, response, carrito, node,  raw_response)
            if node =="change_cart" or node=="product_lookup":
                response = "Para modificar o comprar el carrito en jumbo..."
                raw_response = ""
                data = get_text_message_input_modify_cart(wa_id, response) 
                send_message(data, wa_id, response, carrito, node, raw_response)

def is_valid_whatsapp_message(body):
    """
    Check if the incoming webhook event has a valid WhatsApp message structure.
    """
    return (
        body.get("object")
        and body.get("entry")
        and body["entry"][0].get("changes")
        and body["entry"][0]["changes"][0].get("value")
        and body["entry"][0]["changes"][0]["value"].get("messages")
        and body["entry"][0]["changes"][0]["value"]["messages"][0]
    )