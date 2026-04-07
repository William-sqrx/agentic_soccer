import os
from typing import Callable
import redis, pickle
import traceback
import json
from flask import Flask, jsonify, request
from graph import graph as graph
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
        data = request.get_json()
        state, is_interrupt, config = get_state(data)

        if is_interrupt:
            # previus interrupt will finish and update the state
            # Command() will pass chatstate and populate the state with user reply's react_state
            result = await graph.ainvoke(Command(resume=state), config)

        else:
            previous_state = get_chat_state(config["configurable"]["user_id"])
            # for getting started
            messages = [*previous_state.messages, HumanMessage(content=state["evaluation"])]
            updated_state = ChatState(messages=messages)
            result = await graph.ainvoke(updated_state, config)


        messages = extract_chatstate(result)

        save_chat_state(config["configurable"]["user_id"], ChatState(messages=messages))

        ai_messages = [m for m in messages if isinstance(m, AIMessage)]

        return jsonify({
            "response": ai_messages[-1].content,
        })

    except Exception as e:
        print(f"Error in chat endpoint: {str(e)}")
        print(traceback.format_exc())
        return jsonify({"error": "Internal error", "details": str(e)}), 500
