# Jira Automation

A FastAPI + Next.js tool for Jira time-logging and issue management.

## Features

- Dashboard — worklog heatmap and issue counts
- Timelog — create subtasks, log time, transition issues, link issues
- MCP server — Claude-compatible tools for Jira (list epics/stories/bugs/tasks, create, log time, transition)

## Stack

- **Backend**: FastAPI (Python 3.12), uvicorn
- **Frontend**: Next.js 16
- **MCP**: FastMCP (stdio)

## Setup

1. Copy `.env.example` to `.env` and fill in your values:

```
JIRA_BASE_URL=https://your-org.atlassian.net
JIRA_EMAIL=you@example.com
JIRA_API_TOKEN=your_api_token
JIRA_PROJECT=YOUR_PROJECT_KEY
GROQ_API_KEY=your_groq_key   # optional, for LLM features
LLM_PROVIDER=groq
```

2. Run with Docker:

```bash
docker compose up --build
```

Frontend: http://localhost:3000  
Backend: http://localhost:8000

## MCP Server

```bash
python mcp_server.py
```

Configure in Claude Code as a stdio MCP server pointing to `mcp_server.py`.
