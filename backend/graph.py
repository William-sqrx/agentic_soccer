from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode          # ← new
from langgraph.types import interrupt
from langchain_core.tools import tool            # ← new
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from state import ChatState
from flask import Flask, jsonify, request
from langgraph.types import Command
import os, redis, pickle, traceback, json
from typing import Callable
from openai import APIConnectionError
from dotenv import load_dotenv
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from tools.pat_runner import pat_runner
from tools.team_lookup import team_lookup
from model.team import Team


load_dotenv()

# ─── 1. Define the weather tool ───────────────────────────────────────────────

@tool
def run_pat_analysis(
    team_a_name: str,
    team_b_name: str,
) -> str:
    """Run PAT model checking to analyse pressure dynamics between two football teams.

    Args:
        team_a_name: The name of the team whose pressure aggression is being analysed.
        team_b_name: The name of the opponent team.
    """
    team_a = team_lookup(team_a_name)
    team_b = team_lookup(team_b_name)
    return pat_runner(team_a, team_b)

tools = [run_pat_analysis]

# ─── 2. Bind tools to the model ───────────────────────────────────────────────

MODEL = ChatOpenAI(
    model="gpt-4.1-mini",
    openai_api_key=os.getenv("OPEN_AI_API_KEY")
).bind_tools(tools)  # ← bind_tools so the LLM knows about get_weather

# ─── 3. Prompt & invokeAI (unchanged, just uses the tool-aware MODEL) ─────────

def prompt_generator(state: ChatState, **kwargs) -> SystemMessage:
    return SystemMessage(content="""You are an AI football tactics coach that uses formal probabilistic model checking (PAT) to give precise, data-backed tactical advice.

When a user asks about pressing tactics or how aggressively a team should press:
1. Call run_pat_analysis multiple times with pressure_aggression_a values of 20, 40, 60, and 80
2. Compare the win probabilities returned from each run
3. Recommend the aggression level with the highest win probability, citing the exact numbers

NEVER give generic advice. ALWAYS call run_pat_analysis first.""")

async def invokeAI(
    system_prompt_fn: Callable,
    state: ChatState,
    n_history: int = 3,
    **kwargs
):
    try:
        system = system_prompt_fn(state, **kwargs)
        prompt = [system, *state.messages[-n_history:]]
        print("prompt is", prompt)
        response = await MODEL.ainvoke(prompt)
        return response
    except APIConnectionError as e:
        print("OpenAI API connection failed:", e)
        return AIMessage(content="Sorry, I couldn't reach the AI service right now.")

# ─── 4. Nodes ─────────────────────────────────────────────────────────────────

async def start_node(state: ChatState) -> dict:
    print("in start_node")
    reply = await invokeAI(prompt_generator, state)
    return {"messages": [reply]}  # add_messages appends automatically

async def reply_node(state: ChatState) -> dict:
    last = state.messages[-1]

    # Only interrupt for human input if we didn't just come from a tool call
    if not isinstance(last, ToolMessage):
        user_reply = interrupt(state)
        # add_messages reducer will merge this in
        new_human = HumanMessage(user_reply["evaluation"])
    else:
        new_human = None

    # Build prompt from current state + optional new human message
    prompt_messages = state.messages + ([new_human] if new_human else [])
    system = SystemMessage(content="You are a helpful AI.")
    reply = await MODEL.ainvoke([system, *prompt_messages[-3:]])
    print("reply is", reply)

    return {
        "messages": ([new_human] if new_human else []) + [reply]
    }

# ─── 5. Conditional edge: route to tool node if the LLM made a tool call ──────

def should_use_tool(state: ChatState) -> str:
    last = state.messages[-1]
    if isinstance(last, AIMessage) and getattr(last, "tool_calls", None):
        return "tool_node"
    return "reply_node"

# ─── 6. Build the graph ───────────────────────────────────────────────────────

tool_node = ToolNode(tools)   # handles execution of get_weather calls

builder = StateGraph(ChatState)

builder.add_node("start_node", start_node)
builder.add_node("reply_node", reply_node)
builder.add_node("tool_node", tool_node)     # ← new node

builder.set_entry_point("start_node")

# After start_node: go to tool_node if tool was called, else reply_node
builder.add_conditional_edges(
    "start_node",
    should_use_tool,
    {"tool_node": "tool_node", "reply_node": "reply_node"},
)

# After reply_node: same conditional check
builder.add_conditional_edges(
    "reply_node",
    should_use_tool,
    {"tool_node": "tool_node", "reply_node": "reply_node"},
)

# After tool execution, loop back to reply_node so the model can use the result
builder.add_edge("tool_node", "reply_node")

memory = MemorySaver()
graph = builder.compile(checkpointer=memory)

# ─── 7. Helpers ───────────────────────────────────────────────────────────────

def updated_state(state: ChatState, **kwargs) -> ChatState:
    return ChatState(
        messages=kwargs.get("messages", state.messages),
    )