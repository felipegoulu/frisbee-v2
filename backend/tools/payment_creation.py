import mercadopago
from dotenv import load_dotenv
import os
import asyncio 

# Cargar variables de entorno desde .env
load_dotenv()

# Obtener el token desde las variables de entorno
PROD_ACCESS_TOKEN = os.getenv('MP_ACCESS_TOKEN')


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
        description: str
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

    async def handle_message(self, amount: str) -> str:
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
                description=f"Pago de ${amount} a través de Frisbee"
            )
            return f"Aquí está tu link de pago: {payment_link}"
  
        except ValueError:
            return "Por favor, envía el monto en formato correcto."
        except Exception as e:
            return f"Lo siento, hubo un error al procesar tu solicitud: {str(e)}"


#if __name__ == "__main__":
#    PROD_ACCESS_TOKEN = "APP_USR-2292321468702285-012818-6a6136985805585549a92549b07b87f9-303417316"
    
    # Inicializa el bot
#    bot = WhatsAppBot(PROD_ACCESS_TOKEN)

#    async def test_message():
#        response = await bot.handle_message("10")
#        print(response)
    
#    import asyncio 

#    asyncio.run(test_message())


async def create_payment(amount: str) -> str:
    """
    Crea un link de pago usando el bot de WhatsApp
    
    Args:
        amount (str): Monto a cobrar
        
    Returns:
        str: URL del link de pago o mensaje de error
    """
    bot = WhatsAppBot(PROD_ACCESS_TOKEN)
    return await bot.handle_message(amount)

#response = asyncio.run(create_payment("10"))
#print(response)
