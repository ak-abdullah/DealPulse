# Sentinel

Sentinel watches your HubSpot pipeline for deals that have gone quiet, drafts a short follow-up with Groq, sends it through Gmail, and leaves a note on the deal so your team can see what happened.

It is built as a fixed LangGraph workflow, not an open-ended LLM agent. Python decides when to call HubSpot and Gmail. Groq only writes text.

## How it runs

Each invocation walks the same path:

```
monitor → researcher → writer → executor → error_handler
```

| Step | What happens |
|------|----------------|
| monitor | Pull open deals from HubSpot. Filter by `STALE_DEAL_DAYS`. |
| researcher | One deal per pass. Optional website fetch, then Groq research and hot/warm/cold score. |
| writer | One draft per deal. Groq produces subject and body. |
| executor | Send via Gmail if the deal has no prior Sentinel note. Write HubSpot note on success. |
| error_handler | Review the send outcome for that deal. Log failures in one place. |

Deals are processed in a loop inside researcher, writer, and executor until each stalled deal has been handled for that step.

## Requirements

- Python 3.11 or newer
- HubSpot private app token with deal, contact, and company read access (and deal write for notes)
- Groq API key
- Google Cloud OAuth client for Gmail send (`credentials.json`)

## Setup

Clone the repo and create a virtual environment:

```bash
git clone https://github.com/ak-abdullah/Sentinel.git
cd Sentinel
python -m venv .venv
```

Windows:

```powershell
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

macOS / Linux:

```bash
source .venv/bin/activate
pip install -r requirements.txt
```

Copy the example env file and fill in your values:

```bash
cp .env.example .env
```

You also need `credentials.json` from Google Cloud Console (Gmail API enabled, OAuth desktop client). Place it in the project root or set `GMAIL_CREDENTIALS_PATH`.

On first real send, Gmail opens a browser for OAuth. The refresh token is stored in `token.json`. Both files are gitignored.

### HubSpot app

The `hubspot-app/` directory is a HubSpot developer project for the private app. Deploy it with the HubSpot CLI if you need to change scopes. Day-to-day pipeline runs only need `HUBSPOT_API_KEY` in `.env`.

For deduplication to work reliably, the token should be able to read notes on deals. If skip logic fails open (allows a resend), check that your app can list and read note objects associated with deals.

## Configuration

| Variable | Purpose |
|----------|---------|
| `HUBSPOT_API_KEY` | Private app access token |
| `STALE_DEAL_DAYS` | Days without HubSpot activity before a deal is stalled. Use `7` in production. `0` marks every open deal as stalled (testing only). |
| `GROQ_API_KEY` | Groq API key |
| `GROQ_MODEL` | Model id. Default `llama-3.3-70b-versatile` |
| `SENDER_EMAIL` | From address on outbound mail |
| `SENDER_NAME` | Display name on outbound mail |
| `GMAIL_CREDENTIALS_PATH` | Path to OAuth client JSON |
| `GMAIL_TOKEN_PATH` | Path to saved OAuth token |
| `HUBSPOT_USE_MOCK` | `true` returns fixture deals, no HubSpot calls |
| `GMAIL_USE_MOCK` | `true` logs sends without calling Gmail |
| `SCHEDULER_ENABLED` | `true` allows `run_worker.py --daemon`. Default `false`. |
| `SCHEDULER_HOUR` | Hour for built-in daily run (with `--daemon`) |
| `SCHEDULER_MINUTE` | Minute for built-in daily run |
| `SCHEDULER_TIMEZONE` | IANA timezone, e.g. `UTC` or `Asia/Karachi` |

## Running

### Manual (default)

```bash
python main.py
```

Same pipeline, explicit entry point for local use.

### One shot worker

```bash
python run_worker.py --once
```

Use this for cron, Windows Task Scheduler, or CI. It runs the same code path as `main.py`.

### Built-in daily scheduler

Off unless you opt in. Requires both:

1. `SCHEDULER_ENABLED=true` in `.env`
2. `python run_worker.py --daemon`

The process stays up and triggers the pipeline once per day at the configured time. Stop it with Ctrl+C. It does not start on machine boot unless you configure the OS to launch it.

For production on Windows, the usual pattern is to keep `SCHEDULER_ENABLED=false` and let Task Scheduler call `run_worker.py --once` on a timetable.

### Email formatting check

```bash
python test_email.py --preview-only
python test_email.py --to you@example.com
```

## Duplicate sends

Before Gmail delivery, the executor checks HubSpot notes on the deal for the marker `DealPulse automated follow-up sent`. If found, the run records `skipped_duplicate` and does not send again.

Research and drafting still run on every invocation. Only the send step is skipped.

## Project layout

```
agents/           LangGraph nodes (monitor, research, write, send, errors)
graph/            State model, routers, compiled pipeline
tools/            HubSpot, Gmail, browser integrations
prompts/          Groq system prompts
config/           Settings from environment
scheduler/        --once and --daemon worker
runner.py         Shared pipeline entry used by main and worker
main.py           Manual CLI
run_worker.py     Scheduled / one-shot CLI
hubspot-app/      HubSpot developer project for the CRM app
```

## Mock mode

Set `HUBSPOT_USE_MOCK=true` and/or `GMAIL_USE_MOCK=true` to exercise the graph without live API calls. Useful for local development and future automated tests.

## Exit codes

`main.py` and `run_worker.py --once` return `0` when the run finishes with no errors on state. They return `1` if any node recorded an error (check the printed list and logs).

## Tests

Install dev dependencies and run the suite (no live HubSpot, Groq, or Gmail calls):

```bash
pip install -r requirements-dev.txt
pytest
```

Mock modes are enabled in `tests/conftest.py`. Coverage includes routers, email normalization, HubSpot dedup, monitor fixtures, and executor skip/send paths.

## LangSmith (optional)

Tracing is **off by default**. Nothing is sent to LangSmith until you opt in.

1. Create an account at [smith.langchain.com](https://smith.langchain.com)
2. Create an API key under Settings
3. Add to `.env`:

```env
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=lsv2_pt_...
LANGCHAIN_PROJECT=sentinel
```

4. Run the pipeline as usual:

```bash
python main.py
```

5. Open LangSmith, project `sentinel`, and inspect the trace for that run. You should see LangGraph nodes and Groq LLM calls under researcher and writer.

Traces may include deal and contact fields from prompts. Turn tracing off with `LANGCHAIN_TRACING_V2=false` when you do not need it.

## What this repo does not include yet

- Hosted deployment manifests

The core pipeline is complete. Scheduling is your responsibility via Task Scheduler, cron, or `--daemon`.

## License

Private project. Add a license file if you plan to open-source it.
