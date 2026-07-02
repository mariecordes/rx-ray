import pytest

# apps.api.main calls load_dotenv() at import time, and several tests import
# from it (directly or via the FastAPI app), which pulls real values from a
# local .env into os.environ for the rest of the process. Tests that want to
# exercise a "configured" LLM path set these explicitly via monkeypatch; every
# other test should run as if no LLM is configured, regardless of what's in a
# developer's local .env.
_LLM_ENV_VARS = (
    "QUERY_EXTRACTION_OPENAI_API_KEY",
    "QUERY_EXTRACTION_OPENAI_MODEL",
    "ANSWER_SYNTHESIS_OPENAI_API_KEY",
    "ANSWER_SYNTHESIS_OPENAI_MODEL",
    "ANSWER_CRITIC_OPENAI_API_KEY",
    "ANSWER_CRITIC_OPENAI_MODEL",
)


@pytest.fixture(autouse=True)
def _clear_llm_env_vars(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in _LLM_ENV_VARS:
        monkeypatch.delenv(name, raising=False)
