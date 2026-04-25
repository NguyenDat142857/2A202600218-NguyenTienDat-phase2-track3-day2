import json
import os
import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional

from chromadb import PersistentClient
from langchain_openai import OpenAIEmbeddings


# ================= SHORT-TERM MEMORY =================
class ShortTermMemory:
    """Sliding window of recent messages."""

    def __init__(self, capacity: int = 10):
        self.capacity = capacity
        self.messages: List[Dict[str, str]] = []

    def add(self, role: str, content: str):
        self.messages.append({"role": role, "content": content})
        if len(self.messages) > self.capacity:
            self.messages = self.messages[-self.capacity:]

    def get(self) -> List[Dict[str, str]]:
        return self.messages


# ================= LONG-TERM PROFILE =================
class LongTermProfile:
    """KV store for user attributes with conflict overwrite."""

    def __init__(self, file_path: str = "user_profile.json"):
        self.file_path = file_path
        self.profile = self._load()

    def _load(self) -> Dict[str, Any]:
        if os.path.exists(self.file_path):
            with open(self.file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}

    def _save(self):
        with open(self.file_path, "w", encoding="utf-8") as f:
            json.dump(self.profile, f, indent=4, ensure_ascii=False)

    def update(self, key: str, value: Any):
        # Overwrite → conflict handling (new fact wins)
        self.profile[key] = value
        self._save()

    def get(self) -> Dict[str, Any]:
        return self.profile

    def clear(self):
        self.profile = {}
        self._save()


# ================= EPISODIC MEMORY =================
class EpisodicMemory:
    """Stores meaningful past events (NOT raw chat)."""

    def __init__(self, file_path: str = "episodes.json"):
        self.file_path = file_path
        self.episodes = self._load()

    def _load(self) -> List[Dict[str, Any]]:
        if os.path.exists(self.file_path):
            with open(self.file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        return []

    def _save(self):
        with open(self.file_path, "w", encoding="utf-8") as f:
            json.dump(self.episodes, f, indent=4, ensure_ascii=False)

    def add(self, summary: str, outcome: str):
        # Only store meaningful events
        if not summary or not outcome:
            return

        self.episodes.append({
            "summary": summary,
            "outcome": outcome,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
        self._save()

    def get(self, limit: int = 5) -> List[Dict[str, Any]]:
        return self.episodes[-limit:]

    def clear(self):
        self.episodes = []
        self._save()


# ================= SEMANTIC MEMORY =================
class SemanticMemory:
    """Vector DB (Chroma) + fallback keyword search."""

    def __init__(self, persist_directory: str = "./chroma_db"):
        self.client = PersistentClient(path=persist_directory)
        self.collection = self.client.get_or_create_collection(name="facts")

        try:
            self.embeddings = OpenAIEmbeddings()
            self.use_embedding = True
        except Exception:
            self.use_embedding = False

    def add(self, text: str, metadata: Optional[Dict[str, Any]] = None):
        doc_id = str(uuid.uuid4())

        if self.use_embedding:
            try:
                embedding = self.embeddings.embed_query(text)
                self.collection.add(
                    ids=[doc_id],
                    embeddings=[embedding],
                    documents=[text],
                    metadatas=[metadata] if metadata else None
                )
                return
            except Exception:
                pass  # fallback below

        # Fallback: store without embedding
        self.collection.add(
            ids=[doc_id],
            documents=[text],
            metadatas=[metadata] if metadata else None
        )

    def search(self, query: str, limit: int = 3) -> List[str]:
        # Try embedding search
        if self.use_embedding:
            try:
                embedding = self.embeddings.embed_query(query)
                results = self.collection.query(
                    query_embeddings=[embedding],
                    n_results=limit
                )
                if results and results.get("documents"):
                    return results["documents"][0]
            except Exception:
                pass

        # Fallback keyword search
        try:
            all_docs = self.collection.get().get("documents", [])
            return [
                doc for doc in all_docs
                if query.lower() in doc.lower()
            ][:limit]
        except Exception:
            return []

    def clear(self):
        self.client.delete_collection("facts")
        self.collection = self.client.get_or_create_collection(name="facts")