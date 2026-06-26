"""Allow `python -m crewai_jobs ...` by delegating to the CLI dispatcher."""

from crewai_jobs.cli import main

raise SystemExit(main())
