"""Resume loader tool — reads the resume file and returns role-specific sections.

Loads the markdown resume at the given path and extracts the profile
section relevant to the requested role (kdb, go, or python) plus the
"Quick Reference for Agent" section (keywords, experience, preferences).
"""

from __future__ import annotations

from pathlib import Path
from typing import Type

from crewai.tools import BaseTool
from pydantic import BaseModel, Field


class ResumeLoaderInput(BaseModel):
    path: str = Field(
        default="../agents/jobsearch/references/resume.md",
        description="Path to the resume markdown file.",
    )
    role: str = Field(
        default="kdb",
        description="Role key: 'kdb', 'go', or 'python'.",
    )


class ResumeLoaderTool(BaseTool):
    """Read the resume file and return role-specific profile sections."""

    name: str = "Resume Loader"
    description: str = (
        "Reads the resume markdown file and extracts the relevant profile "
        "section for a given role ('kdb', 'go', or 'python') plus search "
        "keywords, experience level, and job preferences. "
        "Input: path (string) and role (string). Call this at the start of "
        "every job search run."
    )
    args_schema: Type[BaseModel] = ResumeLoaderInput

    def _run(self, path: str = "../agents/jobsearch/references/resume.md", role: str = "kdb") -> str:
        file_path = Path(path)
        if not file_path.is_absolute():
            # Resolve relative to the project root (crewai-jobs/)
            here = Path(__file__).resolve()
            project_root = here.parent.parent.parent.parent
            file_path = (project_root / path).resolve()

        if not file_path.exists():
            return (
                f"Resume file not found at {file_path}. "
                "Provide a valid path to resume.md."
            )

        try:
            content = file_path.read_text(encoding="utf-8")
        except OSError as e:
            return f"Error reading resume: {e}"

        # Extract the Quick Reference section (always useful)
        quick_ref = self._extract_section(content, "Quick Reference for Agent")

        # Extract the role-specific profile
        role_profile = self._extract_role_profile(content, role)

        sections = [f"## Resume — {role.upper()} Role Profile\n{role_profile}"]
        if quick_ref:
            sections.append(f"\n## Quick Reference\n{quick_ref}")

        return "\n".join(sections)

    @staticmethod
    def _extract_section(content: str, heading: str) -> str:
        """Extract everything from ## heading to the next ## heading or EOF."""
        marker = f"## {heading}"
        idx = content.find(marker)
        if idx == -1:
            return ""

        start = idx + len(marker)
        # Find the next ## heading
        rest = content[start:]
        next_heading = rest.find("\n## ")
        if next_heading != -1:
            return rest[:next_heading].strip()
        return rest.strip()

    @staticmethod
    def _extract_role_profile(content: str, role: str) -> str:
        """Return the profile section matching the requested role."""
        if role == "kdb":
            section = ResumeLoaderTool._extract_section(content, "KDB+/q Profile")
            if section:
                return section
        elif role == "go":
            section = ResumeLoaderTool._extract_section(content, "Go/Golang Profile")
            if section:
                return section
        elif role == "python":
            # No dedicated Python profile in the resume — return the
            # "All Skills" and "Experience" sections as a proxy.
            skills = ResumeLoaderTool._extract_section(content, "All Skills")
            exp = ResumeLoaderTool._extract_section(content, "Experience")
            parts = []
            if skills:
                parts.append(f"### All Skills\n{skills}")
            if exp:
                parts.append(f"\n### Experience\n{exp}")
            if parts:
                return "\n".join(parts)
            # Fallback: return whole resume
            return content

        # Fallback: return the entire resume if specific section not found
        return content
