from functools import wraps
from flask import current_app, jsonify, request
import logging
import hashlib
import hmac


def validate_signature(payload, signature, source):
    """
    Validate the incoming payload's signature against our expected signature
    """
    if source == 'whatsapp':
        # Use the App Secret to hash the payload
        expected_signature = hmac.new(
            bytes(current_app.config["APP_SECRET"], "latin-1"),
            msg=payload.encode("utf-8"),
            digestmod=hashlib.sha256,
        ).hexdigest()

        # Check if the signature matches
        return hmac.compare_digest(expected_signature, signature)
    elif source == 'mercadopago':
        return True

def signature_required(f):
    """
    Decorator to ensure that the incoming requests to our webhook are valid and signed with the correct signature.
    Handles both WhatsApp and Mercado Pago webhooks.
    """

    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Check if it's a Mercado Pago webhook
        if request.args.get('topic') == 'merchant_order' or request.args.get('type') == 'payment':
            if validate_signature(request.data.decode("utf-8"), '', source='mercadopago'):
                return f(*args, **kwargs)
            return jsonify({"status": "error", "message": "Invalid signature"}), 403
        # WhatsApp signature verification
        signature = request.headers.get("X-Hub-Signature-256", "")[7:]  # Removing 'sha256='
        if not validate_signature(request.data.decode("utf-8"), signature, source='whatsapp'):
            logging.info("Signature verification failed!")
            return jsonify({"status": "error", "message": "Invalid signature"}), 403
        return f(*args, **kwargs)

    return decorated_function