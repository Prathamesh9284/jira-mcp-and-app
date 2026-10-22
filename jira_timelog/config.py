"""Configuration loaded from environment (.env supported without external deps)."""

import os
from pathlib import Path


def _load_dotenv(path: Path) -> None:
    """Minimal .env loader: KEY=VALUE lines, '#' comments. Does not override real env vars."""
    if not path.exists():
        return
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


class Config:
    """Holds Jira connection settings; validates that required values are present."""

    def __init__(self, base_url: str, email: str, api_token: str,
                 project: str = "PTA", subtask_type_id: str = "", start_date_field: str = "",
                 end_date_field: str = "", acceptance_field: str = "customfield_10046",
                 groq_api_key: str = "", groq_model: str = "llama-3.3-70b-versatile",
                 groq_summary_model: str = "llama-3.1-8b-instant",
                 llm_provider: str = "groq",
                 ollama_base_url: str = "http://localhost:11434",
                 ollama_model: str = "qwen3.5:9b",
                 ollama_summary_model: str = "",
                 ollama_api_key: str = "",
                 worklog_dir: str = "worklogs",
                 epic_type_id: str = "10000", story_type_id: str = "10001",
                 tavily_api_key: str = "", mcp_command: str = "",
                 mcp_args: list | None = None, mcp_enabled: bool = False):
        self.base_url = base_url.rstrip("/")
        self.email = email
        self.api_token = api_token
        self.project = project
        self.subtask_type_id = subtask_type_id
        self.start_date_field = start_date_field
        self.end_date_field = end_date_field
        self.acceptance_field = acceptance_field
        self.field_ids: dict = {}  # populated by JiraClient.resolve_fields() at app startup
        self.groq_api_key = groq_api_key
        self.groq_model = groq_model
        self.groq_summary_model = groq_summary_model
        self.llm_provider = llm_provider.lower()
        self.ollama_base_url = ollama_base_url
        self.ollama_model = ollama_model
        self.ollama_summary_model = ollama_summary_model or ollama_model
        self.ollama_api_key = ollama_api_key
        self.worklog_dir = worklog_dir
        self.epic_type_id = epic_type_id
        self.story_type_id = story_type_id
        self.tavily_api_key = tavily_api_key
        self.mcp_command = mcp_command
        self.mcp_args = mcp_args or []
        self.mcp_enabled = mcp_enabled

    @property
    def llm_ready(self) -> bool:
        """True when the configured LLM provider has enough settings to make a call."""
        if self.llm_provider == "ollama":
            return bool(self.ollama_base_url and self.ollama_model)
        return bool(self.groq_api_key)

    def llm(self, *, summary: bool = False, temperature: float = 0.0):
        """Return a LangChain chat model for the configured provider.

        summary=True picks the cheaper/smaller model when available (Groq summary model
        or Ollama summary model).  temperature overrides the default 0.
        """
        if self.llm_provider == "ollama":
            from langchain_ollama import ChatOllama
            model = self.ollama_summary_model if summary else self.ollama_model
            headers = ({"Authorization": f"Bearer {self.ollama_api_key}"}
                       if self.ollama_api_key else None)
            return ChatOllama(model=model, base_url=self.ollama_base_url,
                              temperature=temperature,
                              **({"client_kwargs": {"headers": headers}} if headers else {}))
        # default: groq
        from langchain_groq import ChatGroq
        model = (self.groq_summary_model if summary else self.groq_model) or self.groq_model
        return ChatGroq(model=model, api_key=self.groq_api_key, temperature=temperature)

    @classmethod
    def from_env(cls, env_path: Path | None = None) -> "Config":
        _load_dotenv(env_path or Path(__file__).resolve().parent.parent / ".env")
        return cls(
            base_url=os.environ.get("JIRA_BASE_URL", ""),
            email=os.environ.get("JIRA_EMAIL", ""),
            api_token=os.environ.get("JIRA_API_TOKEN", ""),
            project=os.environ.get("JIRA_PROJECT", ""),
            subtask_type_id=os.environ.get("JIRA_SUBTASK_TYPE_ID", ""),
            start_date_field=os.environ.get("JIRA_START_DATE_FIELD", ""),
            end_date_field=os.environ.get("JIRA_END_DATE_FIELD", ""),
            acceptance_field=os.environ.get("JIRA_ACCEPTANCE_FIELD", "customfield_10046"),
            groq_api_key=os.environ.get("GROQ_API_KEY", ""),
            groq_model=os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile"),
            groq_summary_model=os.environ.get("GROQ_SUMMARY_MODEL", "llama-3.1-8b-instant"),
            llm_provider=os.environ.get("LLM_PROVIDER", "groq"),
            ollama_base_url=os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434"),
            ollama_model=os.environ.get("OLLAMA_MODEL", "qwen3.5:9b"),
            ollama_summary_model=os.environ.get("OLLAMA_SUMMARY_MODEL", ""),
            ollama_api_key=os.environ.get("OLLAMA_API_KEY", ""),
            worklog_dir=os.environ.get("JIRA_WORKLOG_DIR", "worklogs"),
            epic_type_id=os.environ.get("JIRA_EPIC_TYPE_ID", "10000"),
            story_type_id=os.environ.get("JIRA_STORY_TYPE_ID", "10001"),
            tavily_api_key=os.environ.get("TAVILY_API_KEY", ""),
            mcp_command=os.environ.get("MCP_CODE_COMMAND", ""),
            mcp_args=os.environ.get("MCP_CODE_ARGS", "").split() if os.environ.get("MCP_CODE_ARGS") else [],
            mcp_enabled=os.environ.get("MCP_CODE_ENABLED", "").lower() == "true",
        )

    def missing(self) -> list[str]:
        """Return names of required settings that are empty."""
        need = {"JIRA_BASE_URL": self.base_url, "JIRA_EMAIL": self.email, "JIRA_API_TOKEN": self.api_token}
        return [k for k, v in need.items() if not v]
