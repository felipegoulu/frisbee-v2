"""
Database Connection Manager

Este módulo maneja las conexiones a la base de datos PostgreSQL usando un pool de conexiones.
Proporciona una forma eficiente y segura de compartir conexiones entre diferentes partes de la aplicación.

Características principales:
- Usa ThreadedConnectionPool para manejar múltiples conexiones concurrentes
- Cachea el pool de conexiones usando st.cache_resource
- Implementa context manager para manejo seguro de conexiones
- Configura autocommit para optimizar queries de lectura
"""
import os
from contextlib import contextmanager
import psycopg2
from psycopg2.pool import ThreadedConnectionPool
from psycopg2.extras import RealDictCursor
import json
from psycopg2.extras import Json
from langchain_core.messages import AIMessage, HumanMessage
from datetime import datetime

def init_connection_pool():
    """Initialize and cache the database connection pool"""
    return ThreadedConnectionPool(
        minconn=1,
        maxconn=20,
        dsn=os.getenv('DATABASE_URL')
    )

# Get connection pool on startup
pool = init_connection_pool()

@contextmanager
def get_db_connection():
    """Get a connection from the cached pool"""
    conn = None
    try:
        conn = pool.getconn()
        conn.set_session(autocommit=True)
        yield conn
    finally:
        if conn is not None:
            pool.putconn(conn)

def get_cart_by_msg_id(msg_id):
    """
    Obtiene el carrito asociado a un mensaje específico
    Args:
        msg_id: ID del mensaje
    Returns:
        dict: El carrito encontrado o None si no existe
    """
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT carrito 
                FROM chat_messages 
                WHERE msg_id = %s
                LIMIT 1
            """, (msg_id,))
            
            result = cur.fetchone()
            
            if result and result['carrito']:
                return result['carrito']
            return None

def get_last_message_and_cart(session_id):
    """
    Obtiene el último mensaje y carrito para una sesión específica
    Args:
        session_id: ID de la sesión
    Returns:
        dict: Diccionario con el último mensaje y carrito, o None si no existe
    """
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT content, carrito 
                FROM chat_messages 
                WHERE session_id = %s
                ORDER BY id DESC
                LIMIT 1
            """, (session_id,))
            
            result = cur.fetchone()
            return result if result else None

def save_message(session_id, role, content, msg_id, carrito, node):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO chat_messages (session_id, role, content, created_at, status, msg_id, carrito, node)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (session_id, role, content, datetime.now(), "en_proceso", msg_id, carrito, node))
            conn.commit()

# Database functions
def load_chat_history(session_id):
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT role, content FROM chat_messages 
                WHERE session_id = %s AND node = 'product_selection'
                ORDER BY id DESC LIMIT 20
            """, (session_id,))
            messages = cur.fetchall()

            messages.reverse()
            
            return [
                AIMessage(content=msg['content']) if msg['role'] == 'assistant'
                else HumanMessage(content=msg['content'])
                for msg in messages
            ]

# Database functions
def check_duplicated(session_id, msg_id):
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT session_id FROM chat_messages 
                    WHERE session_id = %s and msg_id = %s 
                """, (session_id,msg_id))
                messages = cur.fetchone()
                
                return messages is not None # Retorna True si hay un duplicado 
                
    except Exception as e:
        st.error(f"Error loading chat history: {e}")
        return []


