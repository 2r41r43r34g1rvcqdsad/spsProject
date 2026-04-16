# SPARC Project - Virtual Environment Setup

Previous fixes (logging, pyproject.toml, tests) complete.

**Venv Steps (user request):**
1. ✅ Created `.venv` with `python3 -m venv .venv`.
2. ~~Activate: `source .venv/bin/activate` (run manually).~~
3. ~~Sync deps: `pip install -e .` (no runtime deps needed).~~
4. ~~Add [project.optional-dependencies.dev] for pytest/hatchling.~~
5. ~~Verify tests and run in venv.~~

Next: User activate venv, then run `pip install -e .` for editable install.

