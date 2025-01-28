from typing import Annotated, TypedDict, Literal, List

from langgraph.graph import START, END, StateGraph
from langgraph.graph.message import AnyMessage, add_messages
from langchain_openai import ChatOpenAI
from langchain_core.messages import ToolMessage, SystemMessage, AIMessage

from backend.tools.tool import product_lookup_tool

import os
from dotenv import load_dotenv

load_dotenv()

os.environ["OPENAI_API_KEY"] = os.getenv("OPEN_AI_API_KEY")
os.environ["LANGSMITH_API_KEY"] = os.getenv("LANGCHAIN_API_KEY")
os.environ["LANGCHAIN_PROJECT"] = os.getenv("LANGCHAIN_PROJECT")
os.environ["LANGCHAIN_TRACING_V2"] = os.getenv("LANGCHAIN_TRACING_V2")

class GraphsState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]
    user_id: str
    name: str
    carrito: str
    node: str

graph = StateGraph(GraphsState)

# Shopping tools (main flow)
tools = [product_lookup_tool]
tools_by_name = {tool.name: tool for tool in tools}

model = ChatOpenAI(model="gpt-4o-mini")
llm = model.bind_tools(tools)

import asyncio

async def handle_shopping_tools(state: dict):
    result = []
    tasks = []

    # Crear todas las tareas primero para ejecución paralela
    for tool_call in state["messages"][-1].tool_calls:
        tool_name = tool_call["name"]
        tool = tools_by_name[tool_name]
        task = asyncio.create_task(tool.ainvoke(tool_call["args"]))
        tasks.append((task, tool_call["id"], tool_name))

    # Esperar todas las tareas y procesar resultados
    for task, tool_call_id, tool_name in tasks:
        observation = await task
        result.append(ToolMessage(content=observation, tool_call_id=tool_call_id, type='tool'))
   
    return {"messages": result}

def determine_tool_node(state: GraphsState) -> Literal["handle_shopping_tools", "__end__"]:
    if not state["messages"][-1].tool_calls:
        return "__end__"
    
    tool_name = state["messages"][-1].tool_calls[0]["name"]
    
    shopping_tools = {
        "product_lookup_tool",
    }

    if tool_name in shopping_tools: 
        return "handle_shopping_tools"
    else:
        return "__end__"  # End the conversation if no tool is needed

def determine_initial_node(state: GraphsState):
    node = state["node"]
    if node == "product_lookup":
        return "product_lookup"

    elif node == "change_cart":
        return "product_lookup"

    elif node == "product_selection":
        return "product_selection"  # End the conversation if no tool is needed

from backend.prompts import get_product_selection_prompt

def product_selection(state: GraphsState):
    user_id = state["user_id"]
    name= state["name"]

    prompt_content = get_product_selection_prompt(user_id, name)

    system_prompt = SystemMessage(content=prompt_content)
    conversation = [system_prompt] + state["messages"][-20:] 
    response = model.invoke(conversation)

    return {"messages": [AIMessage(content=response.content)]}

from backend.prompts import get_product_lookup_prompt, get_change_cart_prompt

def product_lookup(state: GraphsState):
    user_id = state["user_id"]
    name= state["name"]
    carrito = state["carrito"] 
    node = state["node"] 
    
    if node =="product_lookup":
        prompt_content = get_product_lookup_prompt(user_id, name, carrito) 
    else:
        prompt_content = get_change_cart_prompt(user_id, name, carrito) 
  
    system_prompt = SystemMessage(content=prompt_content)
    conversation = [system_prompt] + state["messages"]
    response = llm.invoke(conversation)

    # If it has tool_calls, return the response directly. I need all the answer because it has the tool call name.
    if hasattr(response, 'tool_calls') and response.tool_calls:
        return {
            "messages": [response]  # Return the original message with tool_calls
        }
    
    else:
        return {"messages": [AIMessage(content=response.content)]}

graph.add_node("product_selection", product_selection)
graph.add_node("handle_shopping_tools", handle_shopping_tools)
graph.add_node("product_lookup", product_lookup)

graph.add_conditional_edges(
    "product_lookup",
    determine_tool_node,  # This function will decide the flow of execution
)

graph.add_conditional_edges(
    START,
    determine_initial_node,  # This function will decide the flow of execution
)

graph.add_edge("product_selection", END)
graph.add_edge("handle_shopping_tools", "product_lookup")

graph_runnable = graph.compile()