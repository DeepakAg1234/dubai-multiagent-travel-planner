"""Runtime settings. Missing keys turn a provider off instead of raising."""

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _repo_root() -> Path:
    """Source-tree root when the package lives in ``src/``.

    A deployed install copies the package into site-packages. In that case the
    project root is the process working directory, which is where prompts and
    ``data/seed`` are checked out.
    """

    source_tree = Path(__file__).resolve().parents[2]
    if (source_tree / "prompts").is_dir():
        return source_tree
    cwd = Path.cwd()
    for candidate in (cwd, *cwd.parents):
        if (candidate / "prompts").is_dir() and (candidate / "data" / "seed").is_dir():
            return candidate
    return source_tree


REPO_ROOT = _repo_root()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Every LLM node uses Claude. Ollama and Groq are not called.
    llm_provider: str = "anthropic"
    groq_api_key: str = ""
    groq_model: str = "openai/gpt-oss-20b"
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-opus-5-5"
    llm_api_key: str = ""
    llm_model: str = ""
    gemini_api_key: str = ""
    # Kept for an old Gemini key. Review does not read these.
    gemini_model: str = "gemini-2.5-flash-lite"
    ollama_api_key: str = ""
    ollama_base_url: str = "https://ollama.com"
    ollama_model: str = "nemotron-3-nano"
    ors_api_key: str = ""
    use_live_apis: bool = False
    max_revisions: int = Field(default=3, ge=0)
    buffer_pct: float = Field(default=10, ge=0)
    api_call_budget: int = Field(default=40, ge=0)
    # Empty disables runtime cache. Local dev may use memory:// or sqlite:///path.
    # Do not point this at the Vercel filesystem.
    cache_store_url: str = ""
    checkpoint_store_url: str = ""
    data_db_path: str = ""

    @property
    def resolved_gemini_key(self) -> str:
        return self.gemini_api_key.strip() or self.llm_api_key.strip()

    @property
    def resolved_gemini_model(self) -> str:
        return self.gemini_model.strip() or self.llm_model.strip()

    @property
    def groq_enabled(self) -> bool:
        return bool(self.groq_api_key.strip() and self.groq_model.strip())

    @property
    def anthropic_enabled(self) -> bool:
        return bool(self.anthropic_api_key.strip() and self.anthropic_model.strip())

    @property
    def gemini_enabled(self) -> bool:
        return bool(self.resolved_gemini_key and self.resolved_gemini_model)

    @property
    def ollama_is_cloud(self) -> bool:
        return "ollama.com" in self.ollama_base_url.strip().lower()

    @property
    def ollama_enabled(self) -> bool:
        if not self.ollama_model.strip():
            return False
        if self.ollama_is_cloud:
            return bool(self.ollama_api_key.strip())
        return True

    @property
    def llm_enabled(self) -> bool:
        """True when Claude can be called. Other provider keys are ignored."""
        return self.anthropic_enabled

    @property
    def ors_enabled(self) -> bool:
        return self.use_live_apis and bool(self.ors_api_key.strip())

    @property
    def live_apis_enabled(self) -> bool:
        return self.use_live_apis

    @property
    def cache_enabled(self) -> bool:
        return bool(self.cache_store_url.strip())

    @property
    def checkpoint_enabled(self) -> bool:
        return bool(self.checkpoint_store_url.strip())

    @property
    def sqlite_path(self) -> Path:
        if self.data_db_path.strip():
            return Path(self.data_db_path)
        return REPO_ROOT / "data" / "dubai.sqlite"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
