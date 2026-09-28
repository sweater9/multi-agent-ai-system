# Multi-Agent AI System

A small, hackable multi-agent pipeline built on Google Gemini. Give it a task and five specialized agents work through it in sequence: research, analysis, architecture, code, and review. Run it from a web UI or the command line.

<!-- TODO: add a screenshot or short GIF of the web UI here -->
<!-- ![Web UI](docs/screenshot.png) -->

## How it works

```
Task → Research → Analysis → Development → Coding → QA → Result
```

| Agent | Role |
|-------|------|
| 🔍 Research | Gathers background information for the task |
| 📊 Analysis | Analyzes the research findings |
| 🏗️ Development | Plans the architecture and approach |
| 💻 Coding | Writes the code |
| ✅ QA | Reviews and tests the output |

Each agent receives the previous agent's output as context.

## Quick start

**Prerequisites**

- Python 3.10+
- A Google Gemini API key (free tier available at [ai.google.dev](https://ai.google.dev/))

**Setup**

```bash
git clone https://github.com/sweater9/multi-agent-ai-system.git
cd multi-agent-ai-system

python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

pip install -r gemini_requirements.txt

cp gemini.env.example .env
# Edit .env and add your Gemini API key
```

## Usage

**Web interface**

```bash
python3 gemini_web_server.py
```

Then open <http://localhost:5000>.

**Command line**

```bash
python3 gemini_agents_working.py
```

## Project structure

```
.
├── gemini_agents_working.py   # Agent definitions and CLI entry point
├── gemini_web_server.py       # Flask web server
├── gemini_requirements.txt    # Python dependencies
├── gemini.env.example         # Example environment config
└── templates/                 # Web UI templates
```

## Configuration

Settings live in `.env` (copied from `gemini.env.example`). Never commit your real `.env` file or API key.

## Limitations

- Agents run sequentially, so a full run takes several model calls.
- Output quality depends on the Gemini model and on how clearly the task is described.
- Generated code is not executed or verified automatically. Review it before use.

## Roadmap

- [ ] Add tests
- [ ] Add CI (lint + tests)
- [ ] Stream agent progress to the web UI
- [ ] Make agents and model configurable
- [ ] Reorganize code into a package

## Related projects

- [multi-agent-workspace](https://github.com/sweater9/multi-agent-workspace) – dashboard built on Google ADK with streamed agent events
- [multi-agent-build](https://github.com/sweater9/multi-agent-build) – secure, hosted multi-agent build workflow

## Contributing

Issues and pull requests are welcome.

## License

MIT
