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
from tools.team_lookup import team_lookup, get_team_names
from model.team import Team


load_dotenv()

# ─── 1. Define the tools ───────────────────────────────────────────────

@tool
def get_team_names_in_data() -> str:
    """Retrieve all available team names from the historic dataset.

    Returns:
        A comma-separated string of all team names available in the data.
    """
    team_names = get_team_names()
    return ", ".join(team_names)

@tool
def get_team_stats(team_name: str) -> dict:
    """Retrieve a soccer team's statistics from the precomputed CSV.

    Args:
        team_name: The name of the team to look up (case-insensitive).

    Returns:
        A dictionary containing the team's stats (pass_reliability, shot_conversion, etc.)
        if the team exists. Otherwise returns {"msg": "team does not exist"}.
    """
    available_teams = [name.lower() for name in get_team_names()]
    if team_name.lower() not in available_teams:
        return {"msg": "team does not exist"}

    team: Team = team_lookup(team_name)
    return team.toDict()

@tool
def run_pat_analysis(
    pass_reliability_a: int,
    pass_under_pressure_a: int,
    shot_conversion_a: int,
    xg_per_shot_a: int,
    ball_retention_a: int,
    pressure_success_a: int,
    pressure_aggression_a: int,
    pass_reliability_b: int,
    pass_under_pressure_b: int,
    shot_conversion_b: int,
    xg_per_shot_b: int,
    ball_retention_b: int,
    pressure_success_b: int,
    pressure_aggression_b: int,
) -> str:
    """Run PAT probabilistic model checking to simulate a match between two teams.

    Returns the raw PAT3 verification output containing win/draw/loss
    probabilities. You can call this multiple times with different
    pressure_aggression_a values (e.g. 20, 40, 60, 80) to find the
    optimal pressing intensity for team A.

    All parameters are integers in the range 1-100.

    Args:
        pass_reliability_a (int): How often team A completes passes successfully.
        pass_under_pressure_a (int): How well team A maintains passing accuracy when pressed by the opponent.
        shot_conversion_a (int): How often team A converts shots into goals.
        xg_per_shot_a (int): Average expected-goals value per shot for team A (quality of chances created).
        ball_retention_a (int): How well team A keeps possession after receiving the ball.
        pressure_success_a (int): How often team A's pressing wins the ball back from the opponent.
        pressure_aggression_a (int): How aggressively team A presses (higher = more intense pressing). This is the main parameter to sweep.
        pass_reliability_b (int): How often team B completes passes successfully.
        pass_under_pressure_b (int): How well team B maintains passing accuracy when pressed.
        shot_conversion_b (int): How often team B converts shots into goals.
        xg_per_shot_b (int): Average expected-goals value per shot for team B.
        ball_retention_b (int): How well team B keeps possession after receiving the ball.
        pressure_success_b (int): How often team B's pressing wins the ball back.
        pressure_aggression_b (int): How aggressively team B presses.

    Returns:
        str: Raw PAT3 verification output containing win/draw/loss probabilities.
    """
    team_a = Team(
        pass_reliability=pass_reliability_a,
        pass_under_pressure=pass_under_pressure_a,
        shot_conversion=shot_conversion_a,
        xg_per_shot=xg_per_shot_a,
        ball_retention=ball_retention_a,
        pressure_success=pressure_success_a,
        pressure_aggression=pressure_aggression_a,
    )
    team_b = Team(
        pass_reliability=pass_reliability_b,
        pass_under_pressure=pass_under_pressure_b,
        shot_conversion=shot_conversion_b,
        xg_per_shot=xg_per_shot_b,
        ball_retention=ball_retention_b,
        pressure_success=pressure_success_b,
        pressure_aggression=pressure_aggression_b,
    )
    return pat_runner(team_a, team_b)

@tool
def find_optimal_aggression(
    pass_reliability_a: int,
    pass_under_pressure_a: int,
    shot_conversion_a: int,
    xg_per_shot_a: int,
    ball_retention_a: int,
    pressure_success_a: int,
    pressure_aggression_a: int,
    pass_reliability_b: int,
    pass_under_pressure_b: int,
    shot_conversion_b: int,
    xg_per_shot_b: int,
    ball_retention_b: int,
    pressure_success_b: int,
    pressure_aggression_b: int,
    ) -> str:

    """Run PAT probabilistic model checking 10 times using varying pressure aggression for team a

    Returns the raw 10 PAT3 verification output containing win/draw/loss
    probabilities from 10 to 100. This is a convenience function for calling
    the `pat_analysis` multiple times with different
    pressure_aggression_a values to find the
    optimal pressing intensity for team A.

    All parameters are integers in the range 1-100.

    Args:
        pass_reliability_a (int): How often team A completes passes successfully.
        pass_under_pressure_a (int): How well team A maintains passing accuracy when pressed by the opponent.
        shot_conversion_a (int): How often team A converts shots into goals.
        xg_per_shot_a (int): Average expected-goals value per shot for team A (quality of chances created).
        ball_retention_a (int): How well team A keeps possession after receiving the ball.
        pressure_success_a (int): How often team A's pressing wins the ball back from the opponent.
        pressure_aggression_a (int): How aggressively team A presses (higher = more intense pressing). This is the main parameter to sweep.
        pass_reliability_b (int): How often team B completes passes successfully.
        pass_under_pressure_b (int): How well team B maintains passing accuracy when pressed.
        shot_conversion_b (int): How often team B converts shots into goals.
        xg_per_shot_b (int): Average expected-goals value per shot for team B.
        ball_retention_b (int): How well team B keeps possession after receiving the ball.
        pressure_success_b (int): How often team B's pressing wins the ball back.
        pressure_aggression_b (int): How aggressively team B presses.

    Returns:
        str: Concatenation of 10 Raw PAT3 verification output containing win/draw/loss probabilities, starting
        with result when pressure aggression of team A set 10 to 90.
    """

    team_a = Team(
        pass_reliability=pass_reliability_a,
        pass_under_pressure=pass_under_pressure_a,
        shot_conversion=shot_conversion_a,
        xg_per_shot=xg_per_shot_a,
        ball_retention=ball_retention_a,
        pressure_success=pressure_success_a,
        pressure_aggression=pressure_aggression_a,
    )
    team_b = Team(
        pass_reliability=pass_reliability_b,
        pass_under_pressure=pass_under_pressure_b,
        shot_conversion=shot_conversion_b,
        xg_per_shot=xg_per_shot_b,
        ball_retention=ball_retention_b,
        pressure_success=pressure_success_b,
        pressure_aggression=pressure_aggression_b,
    )

    result = ""

    for i in range(10, 100, 10):
        result += "Pressure aggression of team A set to i\n\n"
        team_a.pressure_aggression = i
        result += pat_runner(team_a, team_b)


    return result


tools = [get_team_names_in_data,  get_team_stats, run_pat_analysis, find_optimal_aggression]


# ─── 2. Bind tools to the model ───────────────────────────────────────────────

MODEL = ChatOpenAI(
    model="gpt-4.1-mini",
    openai_api_key=os.getenv("OPEN_AI_API_KEY")
).bind_tools(tools)  # ← bind_tools so the LLM knows about get_weather

# ─── 3. Prompt & invokeAI (unchanged, just uses the tool-aware MODEL) ─────────

def prompt_generator(state: ChatState, **kwargs) -> SystemMessage:
    return SystemMessage(content="""You are an AI football tactics coach that uses formal probabilistic model checking (PAT) to give precise, data-backed tactical advice.

## How this system works

You have access to processed data generated from historic StatsBomb match events. Each team in the dataset is summarised by seven numeric metrics, all on a 0-100 scale. These metrics are fed into a parametric PCSP# model which the PAT model checker verifies to compute match-outcome probabilities. You do NOT compute probabilities yourself — you call tools that run PAT and then interpret the output.

## Team metrics and their football meaning

When you retrieve team stats via `get_team_stats`, each team has the following fields. Understanding these is essential for explaining results to the user:

- **pass_reliability** (0-100): Percentage of the team's passes that are successfully completed. High values indicate a possession-oriented team that rarely gives the ball away via misplaced passes.

- **pass_under_pressure** (0-100): Percentage of passes completed specifically when the passer was being pressed by an opponent. Compare this to `pass_reliability` — a small gap means the team is press-resistant (e.g., 82 vs 78), while a large gap means they struggle when pressed (e.g., 82 vs 55).

- **shot_conversion** (0-100): Percentage of shots that result in goals. This is the team's clinical finishing rate.

- **xg_per_shot** (0-100): Average expected goals per shot, scaled by 100 (so 11 means 0.11 xG per shot). This measures the *quality* of chances the team creates, independent of whether they finished them. Compare to `shot_conversion`: if conversion > xg_per_shot, the team finishes better than their chances deserve (clinical); if lower, they are wasteful.

- **ball_retention** (0-100): How well the team keeps the ball. 100 means they almost never lose it cheaply to dispossessions or miscontrols; low values mean they lose the ball carelessly.

- **pressure_success** (0-100): When the team applies pressure, how often it results in winning the ball back (via interception or recovery). High values mean their press is genuinely effective at regaining possession.

- **pressure_aggression** (0-100): How aggressively the team presses when the opponent has the ball. This is computed from two signals: how often they apply pressure (frequency) and how high up the pitch they do so (average pressure x-coordinate). A value near 100 means a frequent, high press (e.g., Liverpool under Klopp). A value near 0 means a deep block that rarely engages. A value near 50 is a balanced mid-block.

## About the underlying data

The StatsBomb Open Data dataset covers men's and women's football across major competitions including the FIFA World Cup (1958–2022), UEFA Euro (through 2024), Champions League (1970s–2019), La Liga (2004/05–2020/21), Premier League (2003/04 and 2015/16), Serie A, Ligue 1, Bundesliga, MLS 2023, NWSL, FA Women's Super League, Women's World Cup, UEFA Women's Euro, Copa America 2024, and African Cup of Nations 2023. Each match is broken down into a detailed event-by-event log (passes, shots, pressures, ball receipts, dispossessions, etc.) with pitch coordinates. A team's metrics in `get_team_stats` are aggregated across every match of every season that team appears in within this dataset — so a team with few matches in the data will have noisier statistics than one with many. You can only answer questions about teams that actually appear in this dataset; confirm availability with `get_team_names_in_data` before attempting analysis.
## Interpreting aggression values specifically

When the user asks questions about pressure aggression, remember:
- Each team has a **historical** `pressure_aggression` extracted from data — this is what they actually do.
- The model lets you ask "what if this team were MORE or LESS aggressive than usual?" by varying this value in the simulation.
- Higher aggression = more chances to win the ball back, but also leaves more space behind the defensive line if the press is beaten.
- The optimal value depends on the matchup: against a team with low `pass_under_pressure`, aggressive pressing is more likely to pay off.

## Tool usage workflow

You have access to processed data that is generated from historic football data from StatsBomb. You can access the data as needed using `get_team_names_in_data` and `get_team_stats`.

Common scenario 1:
When user asks questions on the winning, draw, or losing probability of a particular team against another particular team:
1. Check that data on both soccer teams are available via `get_team_names_in_data`
    - if not, explain that you cannot calculate it
2. Retrieve the team stats of both teams using `get_team_stats` for both teams
3. Pass the team stats as parameters to `run_pat_analysis` which will return a string of PAT output
4. Interpret the PAT output on the probabilities. Explain it to the user quoting figures, and connect the numbers to the relevant team metrics (e.g., "Liverpool's 42% win probability reflects their high pass_under_pressure of 78, which handles Arsenal's aggressive 72 pressure_aggression well").

Common scenario 2:
When user asks questions on the best pressure aggression that a particular team should have against another particular team:
1. Check that data on both soccer teams are available via `get_team_names_in_data`
    - if not, explain that you cannot calculate it
2. Retrieve the team stats of both teams using `get_team_stats` for both teams
3. Use `find_optimal_aggression`
4. Give advice on how aggressive the team should be. Compare the recommended value against the team's historical `pressure_aggression` — if the recommendation is 70 but they historically press at 50, explain that they should press more than usual for this particular opponent, and why (referencing the opponent's weaknesses in the relevant metrics).

When a user wants probability analysis on teams that are not available in the data,
Explain that user can provide the necessary figures required to describe a team, since it is possible to run_pat_analysis or find_optimal_aggression, with the user supplied value.
Explain that in this case the user should provide pass_reliability, pass_under_pressure, shot_conversion, xg_per_shot, ball_retention, pressure_success, pressure_aggression and
all values should be between 1 to 100 inclusive, and should be an integer(not float). Elaborate on what each properties mean.
By accepting data from user this way, scenario 1 and 2 can stil work when one or both of the soccer teams at stake are not available in the historic data.

NEVER give generic advice. ALWAYS call `run_pat_analysis` or `find_optimal_aggression` first. When interpreting results, always ground your explanations in the specific metric values retrieved from `get_team_stats`, not in general football knowledge.""")

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
    system = prompt_generator(ChatState(messages=[]))
    reply = await MODEL.ainvoke([system, *prompt_messages])
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
