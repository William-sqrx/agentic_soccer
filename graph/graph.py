from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import StateGraph
from langgraph.types import interrupt

from langchain_core.messages import AIMessage
from langchain_core.messages import HumanMessage
from state import ChatState

from langgraph.graph import StateGraph, START, END

import os
from typing import Callable
import redis, pickle
import traceback
import json
from flask import Flask, jsonify, request
from langchain_core.messages import HumanMessage, AIMessage
from langgraph.types import Command
from state import ChatState

import os
from dotenv import load_dotenv
from openai import APIConnectionError

from langchain_core.messages import SystemMessage
from state import ChatState
from langchain_openai import ChatOpenAI
from typing import Callable

load_dotenv()


MODEL = ChatOpenAI(
    model="gpt-4.1-mini",
    openai_api_key=os.getenv("OPEN_AI_API_KEY")
)

def prompt_generator(result):
    message = f"""you are an AI. User said {result}"""
    return message

async def invokeAI(
    system_prompt_fn: Callable[..., SystemMessage],
    state: ChatState,
    n_history: int = 3,
    use_fine_tune: bool = False,
    **kwargs
):
    try:
        model = MODEL
        system = system_prompt_fn(state, **kwargs)
        prompt = [system, *state.messages[-n_history:]]
        print("prompt is", prompt)
        response = await model.ainvoke(prompt)
        return response
    except APIConnectionError as e:
        print("OpenAI API connection failed:", e)
        return {"error": "connection_failure"}

async def start_node(state: ChatState) -> ChatState:
    print("in start node")
    reply = await invokeAI(prompt_generator, state)

    return updated_state(
        state,
        messages=[*state.messages, reply],
    )

async def reply_node(state: ChatState):
    user_reply = interrupt(state)
    state.messages.append(HumanMessage(user_reply['evaluation']))
    reply = await invokeAI(prompt_generator, state)
    print("reply is", reply)

    return updated_state(
        state,
        messages=[*state.messages, reply],
    )

builder = StateGraph(ChatState)
builder.set_entry_point("start_node") 

builder.add_node("start_node", start_node)
builder.add_node("reply_node", reply_node)

builder.add_edge("start_node", "reply_node")

memory = MemorySaver()
graph = builder.compile(checkpointer=memory)

def updated_state(state: ChatState, **kwargs) -> ChatState:
    return ChatState(
        messages=kwargs.get("messages", state.messages),
    )