# ChangeGuard AI

AI-powered code change risk analysis for safer software development.

ChangeGuard AI analyzes a Git diff and identifies potential security, reliability, and code-quality risks. It provides a risk score, affected files, detailed findings, suggested fixes, safer alternatives, and recommended tests.

## Key Features

- Git diff-based code change analysis
- High / Medium / Low risk classification
- Overall risk score
- Security and reliability findings
- Affected file detection
- Suggested fixes for each finding
- Safer alternatives
- Recommended tests
- Analysis history
- Persistent SQLite storage
- IBM watsonx.ai-powered analysis

## Quick Start

### Backend

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS/Linux

pip install -r requirements.txt
uvicorn main:app --reload --port 8000
