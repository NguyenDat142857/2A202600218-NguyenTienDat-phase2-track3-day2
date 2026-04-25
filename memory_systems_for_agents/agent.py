from typing import TypedDict, List, Dict, Any
from langgraph.graph import StateGraph, END
from langchain_openai import ChatOpenAI
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage

from memory_backends import ShortTermMemory, LongTermProfile, EpisodicMemory, SemanticMemory
import config


# ================= STATE =================
class MemoryState(TypedDict):
    messages: List[BaseMessage]
    user_input: str
    user_profile: Dict[str, Any]
    episodes: List[Dict[str, Any]]
    semantic_hits: List[str]
    response: str
    memory_budget: int


# ================= INIT MEMORY =================
st_memory = ShortTermMemory()
lt_profile = LongTermProfile(config.USER_PROFILE_PATH)
ep_memory = EpisodicMemory(config.EPISODES_PATH)
sem_memory = SemanticMemory(config.CHROMA_DB_DIR)

llm = ChatOpenAI(
    model=config.MODEL_NAME,
    base_url=config.OPENAI_API_BASE,
    api_key=config.OPENAI_API_KEY,
    default_headers={
        "HTTP-Referer": "http://localhost",
        "X-Title": "lab17"
    }
)

# ================= UTIL =================
def trim_text(text: str, max_chars: int):
    return text[-max_chars:]


# ================= NODE 1: RETRIEVE =================
def retrieve_memory_node(state: MemoryState):
    user_input = state["user_input"]

    return {
        "user_profile": lt_profile.get(),
        "episodes": ep_memory.get(),
        "semantic_hits": sem_memory.search(user_input)
    }


# ================= NODE 2: AGENT =================
def agent_node(state: MemoryState):
    # ===== BUILD MEMORY SECTIONS =====
    profile_str = "\n".join([f"{k}: {v}" for k, v in state["user_profile"].items()]) or "None"

    episodic_str = "\n".join([
        f"- {e['summary']} → {e['outcome']}"
        for e in state["episodes"]
    ]) or "None"

    semantic_str = "\n".join([
        f"- {hit}" for hit in state["semantic_hits"]
    ]) or "None"

    # ===== SHORT TERM FROM MEMORY =====
    history = st_memory.get()

    history_str = "\n".join([
        f"{m['role']}: {m['content']}" for m in history
    ]) or "None"

    # ===== TOKEN TRIM =====
    budget = state["memory_budget"]
    history_str = trim_text(history_str, budget // 2)
    episodic_str = trim_text(episodic_str, budget // 4)
    semantic_str = trim_text(semantic_str, budget // 4)

    # ===== PROMPT =====
    system_prompt = f"""
You are a multi-memory AI assistant.

=== USER PROFILE ===
{profile_str}

=== RECENT CONVERSATION ===
{history_str}

=== EPISODIC MEMORY ===
{episodic_str}

=== SEMANTIC KNOWLEDGE ===
{semantic_str}

=== INSTRUCTIONS ===
- Use relevant memory to answer.
- If user corrects a fact → use newest.
- Be natural and helpful.
"""

    messages = [SystemMessage(content=system_prompt)]

    for m in history:
        if m["role"] == "user":
            messages.append(HumanMessage(content=m["content"]))
        else:
            messages.append(AIMessage(content=m["content"]))

    messages.append(HumanMessage(content=state["user_input"]))

    response = llm.invoke(messages)

    # ===== UPDATE SHORT TERM =====
    st_memory.add("user", state["user_input"])
    st_memory.add("assistant", response.content)

    return {"response": response.content}


# ================= NODE 3: UPDATE =================
def update_memory_node(state: MemoryState):
    user_input = state["user_input"]
    response = state["response"]

    # ===== PROFILE EXTRACTION =====
    extract_prompt = f"""
Extract user facts from this message:

"{user_input}"

Return format:
key: value

Keys:
- name
- project
- health
- preference

If none → return NONE
"""

    try:
        extraction = llm.invoke(extract_prompt).content

        if "NONE" not in extraction:
            for line in extraction.split("\n"):
                if ":" in line:
                    key, val = line.split(":", 1)
                    lt_profile.update(key.strip().lower(), val.strip())

    except Exception:
        pass  # fail-safe

    # ===== EPISODIC MEMORY =====
    if any(k in user_input.lower() for k in ["xong", "hoàn thành", "done"]):
        ep_memory.add(
            summary=f"User task: {user_input[:50]}",
            outcome=response[:100]
        )

    return state


# ================= BUILD GRAPH =================
workflow = StateGraph(MemoryState)

workflow.add_node("retrieve", retrieve_memory_node)
workflow.add_node("agent", agent_node)
workflow.add_node("update", update_memory_node)

workflow.set_entry_point("retrieve")
workflow.add_edge("retrieve", "agent")
workflow.add_edge("agent", "update")
workflow.add_edge("update", END)

app = workflow.compile()


# ================= RUN =================
def run_agent(user_input: str):
    state: MemoryState = {
        "messages": [],
        "user_input": user_input,
        "user_profile": {},
        "episodes": [],
        "semantic_hits": [],
        "response": "",
        "memory_budget": 2000
    }

    final_state = app.invoke(state)
    return final_state["response"]