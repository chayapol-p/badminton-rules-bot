"""
Tests the batched embedding call with a stub client, so no test ever calls the API.
"""

from types import SimpleNamespace

from scripts.build_embeddings import embed_in_batches


# ===== A stub client that records each request =====

class StubEmbeddingClient:
    """Stub: answers each request with one vector per text, [length of the text], and records the batches."""

    def __init__(self):
        self.batches = []
        self.embeddings = SimpleNamespace(create=self.create)

    def create(self, model, inputs):
        self.batches.append(list(inputs))
        data = [SimpleNamespace(embedding=[len(text)]) for text in inputs]
        return SimpleNamespace(data=data)


# ===== Tests =====

def test_vectors_come_back_in_the_same_order_as_the_texts():
    client = StubEmbeddingClient()
    texts = ["a", "bb", "ccc", "dddd", "eeeee"]
    vectors = embed_in_batches(client, "test-model", texts, batch_size=2, pause_seconds=0)
    assert vectors == [[1], [2], [3], [4], [5]]


def test_texts_are_sent_in_batches_of_the_given_size():
    client = StubEmbeddingClient()
    texts = ["a", "bb", "ccc", "dddd", "eeeee"]
    embed_in_batches(client, "test-model", texts, batch_size=2, pause_seconds=0)
    assert client.batches == [["a", "bb"], ["ccc", "dddd"], ["eeeee"]]
