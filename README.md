# 🧬 Fulcra OpenClaw Skills

[![MIT License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Built with OpenClaw](https://img.shields.io/badge/Built%20with-OpenClaw-blue)](https://openclaw.ai)
[![Powered by Fulcra](https://img.shields.io/badge/Powered%20by-Fulcra-purple)](https://fulcradynamics.com)

**OpenClaw skills that connect your AI agent to real-time personal health data via Fulcra.**

## Skills

### 🌅 Morning Briefing
Personalized morning briefing combining overnight sleep analysis, glucose trends, calendar preview, and weather.
- Sleep stage breakdown with fragmentation analysis
- CGM overnight glucose stability check
- Calendar-aware day planning
- Actionable suggestions based on recovery state

### 🚨 Proactive Health Alerts
Multi-stream anomaly detection — every alert requires data from 2+ biometric streams.
- Recovery deficit detection (sleep + HRV + exercise)
- Sleep-glucose interaction alerts
- Exercise timing impact warnings
- Calendar stress correlation
- Cooldown deduplication (no repeated alerts)

### 📊 Context Dump
Raw biometric data export formatted for LLM reasoning. Dumps all available Fulcra data into a structured prompt for ad-hoc analysis.

## Prerequisites

- [OpenClaw](https://openclaw.ai) agent running
- [Fulcra](https://fulcradynamics.com) account with data collection enabled
- [Context by Fulcra](https://apps.apple.com/us/app/context-by-fulcra/id1633037434) iOS app
- Python 3.10+

## Install

```bash
pip install fulcra-api pandas numpy
```

Run Fulcra CLI commands through `uv tool run` when a workflow needs the CLI:

```bash
uv tool run fulcra-api --help

# Configure Fulcra token
export FULCRA_TOKEN_PATH="~/.config/fulcra/token.json"
```

## Usage

Copy the skill directory into your OpenClaw workspace `skills/` folder. Each skill includes a `SKILL.md` that OpenClaw reads automatically.

### 🌍 Shared Utilities (`shared/`)
Reusable modules used across all skills:

- **`fulcra_timezone.py`** — Dynamic timezone detection from your Fulcra user profile. Handles DST automatically via Python's `ZoneInfo`. Never hardcode timezones again.
- **`fulcra_sleep_utils.py`** — UTC-safe sleep data retrieval. Solves the "PM bug" where querying sleep data after noon local time returns the wrong day's data.

```python
from shared.fulcra_timezone import get_user_tz, now_local, today_local
from shared.fulcra_sleep_utils import get_last_night_sleep

# Timezone is fetched from Fulcra user profile, cached daily
tz = get_user_tz()  # e.g., ZoneInfo('America/New_York')
sleep = get_last_night_sleep()  # DST-aware, correct UTC bucket
```

## Privacy

All data stays local. No cloud processing beyond the Fulcra API. Configurable paths via environment variables.

## License

MIT
