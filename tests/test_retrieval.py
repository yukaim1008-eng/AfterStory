from afterstory.conversation import ConversationService
from afterstory.memory import MemoryService
from afterstory.repository import Repository
from afterstory.retrieval import MemoryIndexService, RetrievalService


class Embeddings:
    @staticmethod
    def embed(texts):
        return [
            [
                float("夜空" in text or "星星" in text),
                float("茶" in text),
                float(len(text) % 7) / 7,
            ]
            for text in texts
        ]


def test_hybrid_retrieval_is_bounded_and_instance_isolated(database):
    _, sessions = database
    repo = Repository(sessions)
    first = repo.create_instance("alice", "test-lan-v1")["instance_id"]
    second = repo.create_instance("alice", "test-lan-v1")["instance_id"]
    memories = MemoryService(sessions)
    sky = memories.create("alice", first, "sky", "用户喜欢在夜里看星星")
    memories.create("alice", first, "tea", "用户喜欢无糖茶")
    memories.create("alice", second, "private", "另一实例的星星秘密")

    index = MemoryIndexService(sessions, Embeddings(), "fake-v1")
    index.sync(sky["memory_id"])
    retrieval = RetrievalService(
        sessions,
        embedding_provider=Embeddings(),
        max_items=1,
        max_tokens=100,
    )
    prepared = retrieval.prepare(first, "还记得我看星星吗")
    assert prepared.instance_id == first
    assert prepared.selected_ids == [sky["memory_id"]]
    assert prepared.memory_items[0]["content"] == "用户喜欢在夜里看星星"
    assert all("另一实例" not in item["content"] for item in prepared.memory_items)


def test_prepared_runtime_context_reaches_provider(database):
    _, sessions = database
    retrieval = RetrievalService(sessions, embedding_provider=Embeddings())
    repo = Repository(sessions, retrieval=retrieval)
    instance_id = repo.create_instance("alice", "test-lan-v1")["instance_id"]
    conversation_id = repo.create_conversation("alice", instance_id)["conversation_id"]
    memory = MemoryService(sessions).create("alice", instance_id, "sky", "用户喜欢看夜空")
    MemoryIndexService(sessions, Embeddings(), "fake-v1").sync(memory["memory_id"])

    class Provider:
        calls = []

        def generate(self, messages):
            self.calls.append(messages)
            return "记得"

    provider = Provider()
    ConversationService(repo, provider).send("alice", conversation_id, "ask", "夜空呢")
    assert any("用户喜欢看夜空" in message.content for message in provider.calls[0])
