import mercadopago
from dotenv import load_dotenv
import os
import asyncio 



class PaymentService:
    def __init__(self, access_token: str):
        """
        Inicializa el servicio de pagos con Mercado Pago
        
        Args:
            access_token (str): Token de acceso de Mercado Pago
        """
        self.sdk = mercadopago.SDK(access_token)

    async def create_payment_link(
        self, 
        amount: float, 
        description: str,
        user_id: str
    ) -> str:
        """
        Crea un link de pago de Mercado Pago
        
        Args:
            amount (float): Monto a cobrar
            description (str): Descripción del pago
            
        Returns:
            str: URL del link de pago
        """
        preference_data = {
            "items": [
                {
                    "title": description,
                    "quantity": 1,
                    "currency_id": "ARS",  # Cambiar según tu país
                    "unit_price": amount
                }
            ],
            "back_urls": {
                "success": "https://frisbee.one",
            },
            "auto_return": "approved",
            "notification_url": "https://specially-elegant-skunk.ngrok-free.app/webhook",
            "external_reference":  user_id
        }

      
        try:
            preference_response = self.sdk.preference().create(preference_data)
            preference = preference_response["response"]
            print(preference_response)
            return preference["init_point"]
        except Exception as e:
            print(f"Error al crear link de pago: {str(e)}")
            raise


# Ejemplo de uso con un bot de WhatsApp (usando python-whatsapp-bot)
class WhatsAppBot:
    def __init__(self, mp_access_token: str):
        self.payment_service = PaymentService(mp_access_token)

    async def handle_message(self, amount: str, user_id: str) -> str:
        """
        Maneja los mensajes recibidos en el bot
        
        Args:
            message (str): Mensaje recibido
            
        Returns:
            str: Respuesta para el usuario
        """
        try:
            amount = float(amount)
            payment_link = await self.payment_service.create_payment_link(
                amount=amount,
                description=f"Pago a través de Frisbee",
                user_id=user_id
            )
            return payment_link
  
        except ValueError:
            return "Por favor, envía el monto en formato correcto."
        except Exception as e:
            return f"Lo siento, hubo un error al procesar tu solicitud: {str(e)}"



async def create_payment(amount: str, user_id) -> str:
    """
    Crea un link de pago usando el bot de WhatsApp
    
    Args:
        amount (str): Monto a cobrar
        
    Returns:
        str: URL del link de pago o mensaje de error
    """
    # Cargar variables de entorno desde .env
    load_dotenv()

    # Obtener el token desde las variables de entorno
    PROD_ACCESS_TOKEN = os.environ.get('PROD_ACCESS_TOKEN')

    if not PROD_ACCESS_TOKEN:
        raise ValueError("MP_ACCESS_TOKEN no está configurado en las variables de entorno")

    bot = WhatsAppBot(PROD_ACCESS_TOKEN)
    return await bot.handle_message(amount, user_id)

#response = asyncio.run(create_payment("10"))
#print(response)
