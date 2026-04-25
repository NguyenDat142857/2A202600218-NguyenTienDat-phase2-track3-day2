import json
import tiktoken
from agent import run_agent, sem_memory, lt_profile, st_memory, ep_memory
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage
import config


llm_no_mem = ChatOpenAI(
    model=config.MODEL_NAME,
    base_url=config.OPENAI_API_BASE,
    api_key=config.OPENAI_API_KEY,
    default_headers={
        "HTTP-Referer": "http://localhost",
        "X-Title": "lab17"
    }
)

# ================= UTILS =================
def count_tokens(text: str):
    enc = tiktoken.get_encoding("cl100k_base")
    return len(enc.encode(text))


def run_no_memory(user_input: str):
    res = llm_no_mem.invoke([HumanMessage(content=user_input)])
    return res.content


def reset_memory():
    st_memory.messages = []
    lt_profile.clear()
    ep_memory.clear()
    sem_memory.clear()


# ================= MULTI-TURN SCENARIOS =================
scenarios = [
    {
        "id": 1,
        "name": "Profile Recall",
        "turns": [
            "Tôi tên là Dat",
            "Tôi đang học AI",
            "Tên tôi là gì?"
        ],
        "expected": "Dat"
    },
    {
        "id": 2,
        "name": "Conflict Update",
        "turns": [
            "Tôi dị ứng sữa bò",
            "À nhầm, tôi dị ứng đậu nành",
            "Tôi dị ứng gì?"
        ],
        "expected": "đậu nành"
    },
    {
        "id": 3,
        "name": "Preference Recall",
        "turns": [
            "Tôi thích câu trả lời có code Python",
            "Giải thích quicksort",
        ],
        "expected": "python"
    },
    {
        "id": 4,
        "name": "Episodic Memory",
        "turns": [
            "Hôm trước bạn giúp tôi debug docker xong việc",
            "Bạn nhớ tôi đã làm gì không?"
        ],
        "expected": "docker"
    },
    {
        "id": 5,
        "name": "Semantic Retrieval",
        "turns": [
            "Docker AI optimization là gì?"
        ],
        "expected": "docker"
    },
    {
        "id": 6,
        "name": "Long Context",
        "turns": [
            "Tôi tên Linh",
            "Tôi học backend",
            "Tôi thích NodeJS",
            "Hãy nhắc lại thông tin của tôi"
        ],
        "expected": "linh"
    },
    {
        "id": 7,
        "name": "Multi Session",
        "turns": [
            "Tôi làm project microservices",
            "Project của tôi là gì?"
        ],
        "expected": "microservices"
    },
    {
        "id": 8,
        "name": "Task Continuation",
        "turns": [
            "Giúp tôi setup docker",
            "tiếp tục đi"
        ],
        "expected": "docker"
    },
    {
        "id": 9,
        "name": "Profile Overwrite",
        "turns": [
            "Tôi thích Java",
            "Không, tôi thích Python hơn",
            "Tôi thích gì?"
        ],
        "expected": "python"
    },
    {
        "id": 10,
        "name": "Token Trim",
        "turns": [
            "A" * 2000,
            "Tóm tắt lại"
        ],
        "expected": "tóm"
    }
]


# ================= SEED SEMANTIC =================
def seed_semantic():
    sem_memory.add("Docker optimization uses multi-stage builds")
    sem_memory.add("Use --gpus all for AI containers")


# ================= RUN =================
def run_benchmark():
    seed_semantic()

    results = []

    for s in scenarios:
        print(f"Running {s['name']}")

        reset_memory()

        # WITH MEMORY
        last_response = ""
        for turn in s["turns"]:
            last_response = run_agent(turn)

        # NO MEMORY (only last turn)
        no_mem_response = run_no_memory(s["turns"][-1])

        # CHECK PASS
        passed = s["expected"].lower() in last_response.lower()

        results.append({
            "id": s["id"],
            "scenario": s["name"],
            "no_memory": no_mem_response,
            "with_memory": last_response,
            "pass": passed
        })

    save_markdown(results)


# ================= SAVE MD =================
def save_markdown(results):
    with open("BENCHMARK.md", "w", encoding="utf-8") as f:
        f.write("# Benchmark Results\n\n")
        f.write("| # | Scenario | No-memory | With-memory | Pass |\n")
        f.write("|---|----------|----------|-------------|------|\n")

        for r in results:
            f.write(f"| {r['id']} | {r['scenario']} | {r['no_memory'][:30]}... | {r['with_memory'][:30]}... | {'✅' if r['pass'] else '❌'} |\n")


# ================= MAIN =================
if __name__ == "__main__":
    run_benchmark()