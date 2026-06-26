"""News Summarizer crew — scrape a news site, write a markdown brief.

Two-agent sequential crew:
    researcher (owns NewsScraperTool) → summarizer (writes the brief)

This crew is dispatched by the ``news`` subcommand in
``crewai_jobs.cli``. To add a *different* job, copy this folder to a new
``crews/<name>/`` and register a new subcommand — see README.
"""

from __future__ import annotations

from crewai import Agent, Crew, LLM, Process, Task
from crewai.project import CrewBase, agent, crew, task

from crewai_jobs.config import get_api_key, get_base_url, get_model
from crewai_jobs.tools import NewsScraperTool


def build_llm() -> LLM:
    """Construct the opencode-go LLM shared by both agents.

    The ``openai/`` prefix tells LiteLLM (CrewAI delegates to it) to use
    the OpenAI-compatible request shape; ``base_url`` reroutes the call
    to opencode.ai/zen instead of api.openai.com.
    """
    api_key = get_api_key()
    if not api_key:
        raise RuntimeError(
            "No opencode-go API key found. Set OPENCODE_API_KEY in .env "
            "or add one to ~/.pi/agent/auth.json."
        )
    return LLM(
        model=f"openai/{get_model()}",
        base_url=get_base_url(),
        api_key=api_key,
        temperature=0.7,
    )


@CrewBase
class NewsCrew:
    """Two-agent crew: researcher (scrapes) → summarizer (writes brief)."""

    # Resolved relative to this file → crews/news_summarizer/config/
    agents_config = "config/agents.yaml"
    tasks_config = "config/tasks.yaml"

    def __init__(self, quiet: bool = False) -> None:
        self.llm = build_llm()
        self.quiet = quiet

    # ── agents ───────────────────────────────────────────────────────────────

    @agent
    def researcher(self) -> Agent:
        return Agent(
            config=self.agents_config["researcher"],
            tools=[NewsScraperTool()],
            llm=self.llm,
            allow_delegation=False,
            verbose=not self.quiet,
        )

    @agent
    def summarizer(self) -> Agent:
        return Agent(
            config=self.agents_config["summarizer"],
            llm=self.llm,
            allow_delegation=False,
            verbose=not self.quiet,
        )

    # ── tasks ────────────────────────────────────────────────────────────────

    @task
    def research_task(self) -> Task:
        return Task(config=self.tasks_config["research_task"])

    @task
    def summarize_task(self) -> Task:
        return Task(config=self.tasks_config["summarize_task"])

    # ── crew ─────────────────────────────────────────────────────────────────

    @crew
    def crew(self) -> Crew:
        return Crew(
            agents=self.agents,
            tasks=self.tasks,
            process=Process.sequential,
            verbose=not self.quiet,
        )
