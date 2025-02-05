import json
import os
import sys
import asyncio  # Import asyncio

from langchain_core.messages import AIMessage, HumanMessage
from backend.graph import graph_runnable

from backend.db import load_chat_history,  save_message, get_cart_by_msg_id, get_last_message_and_cart

def format_cart_to_bullets(cart_json):
    """
    Convierte cualquier JSON del carrito en un texto formateado con bullet points,
    independientemente de su estructura
    """
    def process_dict(d, indent=0):
        if not d:  # Si el diccionario está vacío
            return ""
            
        result = ""
        for key, value in d.items():
            # Ignorar llaves vacías
            if not value:
                continue
                
            # Formatear el key para mejor visualización
            formatted_key = key.replace("_", " ").capitalize()
            
            # Si el valor es un diccionario, procesarlo recursivamente
            if isinstance(value, dict):
                result += "  " * indent + f"{formatted_key}:\n" + process_dict(value, indent + 1)

            # Si el valor es una lista, procesar cada elemento
            elif isinstance(value, list):
                result += "  " * indent + f"{formatted_key}:\n"
                for item in value:
                    if isinstance(item, dict):
                        result += process_dict(item, indent + 1) 
                    else:
                        result += "\n" + "  " * (indent + 1) + f"• {item}"
            # Si es un valor simple, mostrarlo directamente
            else:
                result += "  " * indent + f"• {formatted_key}: {value}\n"
        return result
    try:
        if not cart_json:  # Si el JSON está vacío
            return ""
        return process_dict(cart_json)
    except Exception as e:
        return f"Error al formatear el carrito: {str(e)}"

async def invoke_our_graph(state): 
    final_text = ""  # Accumulates the text from the model's response
    raw_text = ""  # Accumulates the text from the model's response
    final_response = {"messages": []}
    final_raw_response = {"messages": []}
    is_json_mode = False
    has_json = False
    carrito = {}

    async for event in graph_runnable.astream_events(state, version="v2"):
        kind = event["event"]  
        if kind == "on_chat_model_stream":
            chunk = event["data"]["chunk"].content  
            
            raw_text += chunk
            # Detectar inicio del bloque JSON
            if "``" in chunk and not is_json_mode:
                is_json_mode = True
                has_json = True
                parts = chunk.split("json", 1)
                final_text += parts[0]  # Añadir el texto antes del JSON
                final_text = final_text.replace("`", "")

                #print(f"text 1: {final_text}")
                json_text = parts[1] if len(parts) > 1 else ""

            # Detectar fin del bloque JSON
            elif "``" in chunk and is_json_mode:
                is_json_mode = False
                parts = chunk.split("```", 1)
                json_text += parts[0]
                
                start_index = json_text.find('{')
                if start_index != -1:
                    json_text = json_text[start_index:]
                    end_index = json_text.rfind('}')
                    if end_index != -1:
                        json_text = json_text[:end_index + 1]

                #print(f"json text: {json_text}")
                try:
                    json_text = json.loads(json_text)
                    carrito = json_text #guardo el carrito en formato json
                    json_text = format_cart_to_bullets(json_text)

                except json.JSONDecodeError as e:
                    print(f"Error decoding JSON: {str(e)}")
                    json_text = f"Error processing cart data: {str(e)}" 

                final_text += json_text  # Append json_text to final_text

            # Si estamos en modo JSON, acumulamos en json_text
            elif is_json_mode:
                json_text += chunk

            # Si no estamos en modo JSON, acumulamos en final_text
            else:
                final_text += chunk

        if kind == 'on_chain_end':
            if event['name'] == 'product_selection':
                final_text = final_text.replace("`", "")
                final_response["messages"] = final_text
                node = "product_selection"
                final_raw_response["messages"] = raw_text # esto es para guardar el msje con el formato json porque quiero que el input de msjes anteriores esten en formato json.

            if event['name'] == 'final_product_lookup':
                final_response["messages"] = final_text
                node = "product_lookup"
            
            if event['name'] == 'change_cart':
                final_response["messages"] = final_text
                node = "change_cart"

    return final_response, has_json, carrito, node, final_raw_response


def generate_response(message_body, wa_id, msg_id,name, parent_msg_id):
    state_messages = []
    print(f"generate response : meesage body: {message_body}")

    if message_body == "Busca en Jumbo":
        node = "product_lookup"
        carrito = get_cart_by_msg_id(parent_msg_id)  # Don't convert to str here
            
    elif message_body == "Modificar Carrito":
        node = "change_cart"
        carrito = get_cart_by_msg_id(parent_msg_id)  
        save_message(wa_id, "user", message_body, msg_id, json.dumps(carrito), node)
        return "Que quieres modificar?", False, carrito, node, ""
        
    elif message_body == "Comprar Carrito":
        node = "add_location"
        carrito = get_cart_by_msg_id(parent_msg_id)  
        save_message(wa_id, "user", message_body, msg_id, json.dumps(carrito), node)
        carrito_dict = json.loads(carrito)  if isinstance(carrito, str) else carrito
        total = carrito_dict["total"]
        response = f"Para comprar tu carrito, primero debes escribir tu dirección. A continuación escribe tu dirección:"
        return response, False, carrito, node, ""
    else:
        result = get_last_message_and_cart(wa_id)
        if result and result['content'] == 'Que quieres modificar?':
            node = "change_cart"
            carrito = result['carrito']
        if result and result['node'] == 'add_location':
            node = 'buy_cart'
            carrito = result['carrito']
            carrito_dict = json.loads(carrito)  if isinstance(carrito, str) else carrito
            total = carrito_dict["total"]
            cart_link = "link.mercadopago.com.ar/frisbee"  
            response = f"Aquí está el link para comprar tu carrito: {cart_link}\nEl valor total a pagar es {total}"
            return response, False, carrito, node, "" 
        else:
            node = "product_selection"
            carrito = {}
            messages = load_chat_history(wa_id)
            if len(messages) > 20:
                messages = messages[-20:]
            messages.append(HumanMessage(content=message_body))
            state_messages = messages

    print(f"input node: {node}")
    print(f"input carrito: {carrito}")

    save_message(wa_id, "user", message_body, msg_id, json.dumps(carrito), node)
    
    state = {
        "messages": state_messages if state_messages else [HumanMessage(content=message_body)],
        "user_id": wa_id,
        "name": name,
        "carrito": str(carrito),
        "node": node
    }
    print(f"generate_resposne : state: {state}")

    # if nodo es producto lookup hacer invoke_graph_product_lookup
    response, has_json, carrito, node, raw_response = asyncio.run(invoke_our_graph(state))
    new_message = response["messages"]
    raw_response = raw_response["messages"] 
    print(f"new_message: {new_message}")

    return new_message, has_json, carrito, node, raw_response 