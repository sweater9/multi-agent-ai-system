# Multi-Agent AI System

An AI-powered system using Google Gemini with 5 specialized agents.

## Features

- 🔍 Research Agent - Gathers information
- 📊 Analysis Agent - Analyzes findings
- 🏗️ Development Agent - Plans architecture
- 💻 Coding Agent - Writes code
- ✅ QA Agent - Reviews and tests

## Quick Start

1. Clone this repo
2. Install dependencies: `pip3 install -r gemini_requirements.txt`
3. Copy config: `cp gemini.env.example .env`
4. Add your Gemini API key to `.env`
5. Run: `python3 gemini_web_server.py`
6. Open: http://localhost:5000

## Requirements

- Python 3.8+
- Google Gemini API key (get free at https://ai.google.dev/)
- Flask

## Usage

### Web Interface
```bash
python3 gemini_web_server.py
```
Open http://localhost:5000 in your browser

### Command Line
```bash
python3 gemini_agents_working.py
```

## License

MIT - Feel free to use and modify!
