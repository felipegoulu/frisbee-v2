import os
import logging
import json

from flask import Blueprint, request, jsonify, current_app

from .decorators.security import signature_required
from .utils.whatsapp_utils import (
    process_whatsapp_message,
    is_valid_whatsapp_message,
)
import mercadopago

webhook_blueprint = Blueprint("webhook", __name__)

from dotenv import load_dotenv

load_dotenv()

access_token=os.environ.get("PROD_ACCESS_TOKEN")

def verify_payment(payment_id):
    sdk = mercadopago.SDK(access_token)

    try:
        response = sdk.payment().get(payment_id)
        payment = response["response"]
        return payment
    
    except Exception as e:
        print(f"Error al verificar el pago: {str(e)}")
        raise e

def handle_message():
    """
    Handle incoming webhook events from the WhatsApp API.

    This function processes incoming WhatsApp messages and other events,
    such as delivery statuses. If the event is a valid message, it gets
    processed. If the incoming payload is not a recognized WhatsApp event,
    an error is returned.

    Every message send will trigger 4 HTTP requests to your webhook: message, sent, delivered, read.

    Returns:
        response: A tuple containing a JSON response and an HTTP status code.
    """
    body = request.get_json()
    #logging.info(f"request body: {body}")

    # Check if it's a WhatsApp status update
    if (
        body.get("entry", [{}])[0]
        .get("changes", [{}])[0]
        .get("value", {})
        .get("statuses")
    ):
        logging.info("Received a WhatsApp status update.")
        return jsonify({"status": "ok"}), 200

    print(f"body: {body}")

    #if body.get("type")== "payment":    
    #    payment_id =  body.get("data",{}).get('id')
    #    if payment_id:
    #        print(f"pago recibido: {payment_id}")
    #    else:
    #        print("Pago recibido pero sin ID")

    #    return jsonify({"status": "ok"}), 200

    # Handle both types of Mercado Pago webhooks
    if request.args.get('topic') == 'merchant_order' or request.args.get('topic') == 'payment' or request.args.get('type') == 'payment':
        if request.args.get('topic') == 'payment':
            payment_id = body['resource']
            payment = verify_payment(payment_id)

            print(payment["status"]) 
            if payment["status"] == "approved":
                status = payment["status"]
                monto = f"{payment['transaction_amount']} {payment['currency_id']}"
                fecha_creacion = payment['date_created']
                metodo_de_pago = payment['payment_method_id'] 
                # id_usuario = 
                # insertar pago a tabla payments. Si el id de pago ya existe salir del loop y no insertar nada.
                # tambien necesito obtener el id del usuario (nro de telefono) y ponerlo en la tabla payments.
                # la tabla payments deberia tener una columna llamada estado de delivery que en ppio está en nulo y yo la voy modificando.
                # mandar mensaje a cliente diciendo que ya nos llego el pago

        return jsonify({"status": "ok"}), 200

    try:
        if is_valid_whatsapp_message(body):
            process_whatsapp_message(body)
            return jsonify({"status": "ok"}), 200
        else:
            # if the request is not a WhatsApp API event, return an error
            return (
                jsonify({"status": "error", "message": "Not a WhatsApp API event"}),
                404,
            )
    except json.JSONDecodeError:
        logging.error("Failed to decode JSON")
        return jsonify({"status": "error", "message": "Invalid JSON provided"}), 400


# Required webhook verifictaion for WhatsApp
def verify():
    # Parse params from the webhook verification request
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")
    # Check if a token and mode were sent
    if mode and token:
        # Check the mode and token sent are correct
        if mode == "subscribe" and token == current_app.config["VERIFY_TOKEN"]:
            # Respond with 200 OK and challenge token from the request
            logging.info("WEBHOOK_VERIFIED")
            return challenge, 200
        else:
            # Responds with '403 Forbidden' if verify tokens do not match
            logging.info("VERIFICATION_FAILED")
            return jsonify({"status": "error", "message": "Verification failed"}), 403
    else:
        # Responds with '400 Bad Request' if verify tokens do not match
        logging.info("MISSING_PARAMETER")
        return jsonify({"status": "error", "message": "Missing parameters"}), 400


@webhook_blueprint.route("/webhook", methods=["GET"])
def webhook_get():
    return verify()

@webhook_blueprint.route("/webhook", methods=["POST"])
@signature_required
def webhook_post():
    return handle_message()