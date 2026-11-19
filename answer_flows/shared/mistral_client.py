"""
Builds the Mistral client every caller uses (the app and the run script), with one retry setting.

Use:
    mistral_client = build_mistral_client(settings)
"""

from mistralai.client import Mistral
from mistralai.client.utils import BackoffStrategy, RetryConfig

from settings import Settings


# Constants
## The SDK's own retry on a rate limit (429) or a server error: wait 2 s, doubling up to 60 s, for at
## most 5 minutes. Without it, a run with the top 15 clauses hit Mistral's rate limit and was lost at question 15
MISTRAL_RETRY = RetryConfig("backoff", BackoffStrategy(2_000, 60_000, 2.0, 300_000), retry_connection_errors=True)


# ===== The client =====

def build_mistral_client(settings: Settings) -> Mistral:
    """Returns a Mistral client with the API key from the settings and the shared retry setting."""
    return Mistral(api_key=settings.mistral_api_key.get_secret_value(), retry_config=MISTRAL_RETRY)
