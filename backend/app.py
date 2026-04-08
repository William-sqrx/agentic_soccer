import os
from typing import Callable
import redis, pickle
import traceback
import json
from flask import Flask, jsonify, request
from graph import graph as graph, prompt_generator
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
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

load_dotenv()

redis_pool = redis.ConnectionPool.from_url(os.getenv("REDIS_URL"))
redis_client = redis.Redis(connection_pool=redis_pool)

def get_state(data):
    state = data.get("state")
    user_id = data.get("user_id")
    config = build_config(user_id)
    current_state = graph.get_state(config)

    is_interrupt = any(task.interrupts for task in current_state.tasks)

    return state, is_interrupt, config

def save_chat_state(user_id, state):
    redis_client.set(user_id, pickle.dumps(state), ex=3600)

def get_chat_state(user_id):
    data = redis_client.get(user_id)
    return pickle.loads(data) if data else ChatState(messages=[])

def build_config(user_id: str) -> dict:
    return {
        "configurable": {
            "user_id": user_id,
            "model": "gpt-4o-transcribe",
            "model_provider": "openai",
            "thread_id": f"thread-{user_id}",
        },
        "recursion_limit": 25,
    }

def extract_chatstate(result):
    messages = result["messages"]
    return messages

@app.route("/chat", methods=["POST"])
async def chat():
    try:
        print("chat: request received", flush=True)
        data = request.get_json()
        print(f"chat: parsed json keys={list(data.keys()) if data else None}", flush=True)

        state, is_interrupt, config = get_state(data)
        print(
            f"chat: built state user_id={config['configurable']['user_id']} is_interrupt={is_interrupt}",
            flush=True,
        )

        if is_interrupt:
            print("chat: before graph.ainvoke interrupt resume", flush=True)
            # previous interrupt will finish and update the state
            # Command() will pass chatstate and populate the state with user reply's react_state
            result = await graph.ainvoke(Command(resume=state), config)
            print("chat: after graph.ainvoke interrupt resume", flush=True)

        else:
            print("chat: before get_chat_state", flush=True)
            previous_state = get_chat_state(config["configurable"]["user_id"])
            print("chat: after get_chat_state", flush=True)

            # Add system prompt from prompt_generator to maintain soccer coach context
            system_message = prompt_generator(ChatState(messages=[]))
            print("chat: after prompt_generator", flush=True)

            # Include system messages at the start, followed by human messages
            messages = [system_message, *previous_state.messages, HumanMessage(content=state["evaluation"])]
            print(f"chat: assembled messages count={len(messages)}", flush=True)

            updated_state = ChatState(messages=messages)
            print("chat: before graph.ainvoke normal flow", flush=True)
            result = await graph.ainvoke(updated_state, config)
            print("chat: after graph.ainvoke normal flow", flush=True)

        messages = extract_chatstate(result)
        print(f"chat: extracted messages count={len(messages)}", flush=True)

        save_chat_state(config["configurable"]["user_id"], ChatState(messages=messages))
        print("chat: after save_chat_state", flush=True)

        ai_messages = [m for m in messages if isinstance(m, AIMessage)]
        print(f"chat: ai_messages count={len(ai_messages)}", flush=True)

        return jsonify({
            "response": ai_messages[-1].content,
        })

    except Exception as e:
        print(f"Error in chat endpoint: {str(e)}", flush=True)
        print(traceback.format_exc(), flush=True)
        return jsonify({"error": "Internal error", "details": str(e)}), 500
