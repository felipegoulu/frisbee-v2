import os
from dotenv import load_dotenv
load_dotenv()

from langchain_openai import OpenAIEmbeddings

EMBEDDINGS_DIMENSIONS = 512

OPENAI_API_KEY = os.environ.get('OPEN_AI_API_KEY')

embedding_client = OpenAIEmbeddings(api_key=OPENAI_API_KEY,
    model="text-embedding-3-small", dimensions=EMBEDDINGS_DIMENSIONS)

from pinecone import Pinecone
from pinecone_text.sparse import BM25Encoder

# initialize connection to pinecone
api_key = os.environ.get('PINECONE_API_KEY') 

# connect to index
pc = Pinecone(api_key=api_key)

codigo = os.environ.get('CODIGO') 

index_name = f"jumbo-index-{codigo}"
pinecone_index = pc.Index(index_name)

import asyncio
import pickle

async def load_bm25_model():
    environment = os.environ.get('ENVIRONMENT', 'local')
    if environment == 'server':
        base_path = "/home/ubuntu/frisbee-v2"
    else:
        base_path = "/Users/felipegoulu/projects/activos/frizbee-v2"

    model_path = os.path.join(base_path, f"backend/tools/bm25_model_{codigo}.pkl")
    with open(model_path, 'rb') as f:
        bm25 = pickle.load(f)
    return bm25

import asyncio
from langchain_core.tools import tool

@tool("product_lookup_tool")
async def product_lookup_tool(query):
    """
    Busco dentro de la base de datos del supermercado 'jumbo'
    """
    # Check if the bm25 model is loaded
    bm25 = await load_bm25_model()  # Ensure the model is loaded
    sparse = bm25.encode_queries(query)
    dense = await asyncio.to_thread(embedding_client.embed_query, query)

    result = await asyncio.to_thread(
        pinecone_index.query,
        top_k =5 ,
        vector = dense,
        sparse_vector = sparse,
        include_metadata = True
    )

    result_matches = result['matches']
    final_result = []
    for i in range(len(result_matches)):
        final_result.append({
            'nombre_producto': result_matches[i]['metadata']['product_name'],
            'price_with_discount': result_matches[i]['metadata']['price_with_discount'],
            'original_price': result_matches[i]['metadata']['original_price'],
            'discount': result_matches[i]['metadata']['discount_percentage'],
            'regular_price': result_matches[i]['metadata']['regular_price'],
            'link_producto': result_matches[i]['metadata']['link']
#            'link_imagen': result_matches[i]['metadata']['image'],
        })
            
    # Convert the list of dictionaries to a JSON string
    import json
    json_string = json.dumps(final_result)

    return json_string