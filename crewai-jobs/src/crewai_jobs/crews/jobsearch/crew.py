"""Job Search crew — search job boards, verify listings, analyze fit, produce reports.

Two-agent sequential crew:
    researcher (4 tools) → report_writer (no tools, formats + JSON for n8n)

Dispatched by the ``jobsearch`` subcommand in ``crewai_jobs.cli``.
"""

from __future__ import annotations

from crewai import Agent, Crew, LLM, Process, Task
from crewai.project import CrewBase, agent, crew, task

from crewai_jobs.config import get_api_key, get_base_url, get_model
from crewai_jobs.tools import (
    JobSearchTool,
    JobTrackerTool,
    JobVerifierTool,
    ResumeLoaderTool,
)


def build_llm() -> LLM:
    """Construct the opencode-go LLM shared by both agents."""
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
class JobSearchCrew:
    """Two-agent crew: researcher → report_writer."""

    agents_config = "config/agents.yaml"
    tasks_config = "config/tasks.yaml"

    def __init__(self, quiet: bool = False) -> None:
        self.llm = build_llm()
        self.quiet = quiet

    # ── agents ───────────────────────────────────────────────────────────

    @agent
    def researcher(self) -> Agent:
        return Agent(
            config=self.agents_config["researcher"],
            tools=[
                ResumeLoaderTool(),
                JobSearchTool(),
                JobTrackerTool(),
                JobVerifierTool(),
            ],
            llm=self.llm,
            allow_delegation=False,
            verbose=not self.quiet,
        )

    @agent
    def report_writer(self) -> Agent:
        return Agent(
            config=self.agents_config["report_writer"],
            llm=self.llm,
            allow_delegation=False,
            verbose=not self.quiet,
        )

    # ── tasks ────────────────────────────────────────────────────────────

    @task
    def research_task(self) -> Task:
        return Task(config=self.tasks_config["research_task"])

    @task
    def write_report_task(self) -> Task:
        return Task(config=self.tasks_config["write_report_task"])

    # ── crew ─────────────────────────────────────────────────────────────

    @crew
    def crew(self) -> Crew:
        return Crew(
            agents=self.agents,
            tasks=self.tasks,
            process=Process.sequential,
            verbose=not self.quiet,
        )
