"""Resume loader tool — reads the resume file and returns role-specific sections."""

from __future__ import annotations

from pathlib import Path


class ResumeLoaderTool:
    """Read the resume file and return role-specific profile sections."""

    @staticmethod
    def load(path: str = "../agents/jobsearch/references/resume.md", role: str = "kdb") -> str:
        file_path = Path(path)
        if not file_path.is_absolute():
            here = Path(__file__).resolve()
            project_root = here.parent.parent.parent.parent
            file_path = (project_root / path).resolve()

        if not file_path.exists():
            return f"Resume file not found at {file_path}. Provide a valid path to resume.md."

        try:
            content = file_path.read_text(encoding="utf-8")
        except OSError as e:
            return f"Error reading resume: {e}"

        quick_ref = ResumeLoaderTool._extract_section(content, "Quick Reference for Agent")
        role_profile = ResumeLoaderTool._extract_role_profile(content, role)

        sections = [f"## Resume — {role.upper()} Role Profile\n{role_profile}"]
        if quick_ref:
            sections.append(f"\n## Quick Reference\n{quick_ref}")

        return "\n".join(sections)

    @staticmethod
    def _extract_section(content: str, heading: str) -> str:
        marker = f"## {heading}"
        idx = content.find(marker)
        if idx == -1:
            return ""
        start = idx + len(marker)
        rest = content[start:]
        next_heading = rest.find("\n## ")
        if next_heading != -1:
            return rest[:next_heading].strip()
        return rest.strip()

    @staticmethod
    def _extract_role_profile(content: str, role: str) -> str:
        if role == "kdb":
            section = ResumeLoaderTool._extract_section(content, "KDB+/q Profile")
            if section:
                return section
        elif role == "go":
            section = ResumeLoaderTool._extract_section(content, "Go/Golang Profile")
            if section:
                return section
        elif role == "python":
            skills = ResumeLoaderTool._extract_section(content, "All Skills")
            exp = ResumeLoaderTool._extract_section(content, "Experience")
            parts = []
            if skills:
                parts.append(f"### All Skills\n{skills}")
            if exp:
                parts.append(f"\n### Experience\n{exp}")
            if parts:
                return "\n".join(parts)
            return content
        return content
