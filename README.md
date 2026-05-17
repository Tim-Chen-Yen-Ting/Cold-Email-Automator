# Cold Email Automator

Automated cold email pipeline powered by Claude AI. Researches targets, verifies emails, drafts personalized outreach, sends via Gmail, and syncs everything to Google Sheets.

## How It Works

```
Claude AI research → Email verification (Reoon) → Claude AI drafting → Gmail send → Google Sheets dashboard
```

Each cycle Claude searches the web to find contacts matching your target profile, guesses and verifies their emails, writes a personalized email using a specific hook (recent news, product launch, etc.), then sends and tracks everything.

## Features

- AI-driven contact research — no database subscription needed
- Email verification via Reoon API (~$0.001/email)
- Personalized email drafting with tracked appeal angles
- Gmail API sending with daily limits and scheduling
- Bounce detection via Gmail inbox polling
- Reply detection via Gmail thread monitoring
- Google Sheets live dashboard (auto-created on first run)
- SQLite database with full contact + email history
- Blocklist support

## Cost Estimate

Costs vary by provider. All figures are approximate per sent email.

| Component | Anthropic | OpenAI | Gemini |
|---|---|---|---|
| Research (web search + tokens) | ~$0.25 / run | ~$0.30 / run | ~$0.10 / run |
| Draft (per email) | ~$0.002 | ~$0.002 | ~$0.001 |
| Email verification (Reoon) | ~$0.001 | ~$0.001 | ~$0.001 |
| Gmail API | Free | Free | Free |
| **Total per sent email** | **~$0.03** | **~$0.04** | **~$0.01** |

Research cost is per run (e.g. 10 contacts), not per email. Gemini is cheapest overall; Anthropic has the most reliable native web search.

## Setup

### 1. Clone and install dependencies

```bash
git clone <your-repo-url>
cd cold-email
pip install -r requirements.txt
```

### 2. Create your config

```bash
cp config.example.json config.json
```

Edit `config.json` with your details:
- `sender` — your name, email, role, pitch, signature
- `targeting` — who you want to reach (industries, roles, keywords)
- `email` — subject template and goal of the outreach
- `scheduling` — when and how often to send

### 3. Choose your AI provider

Set `"provider"` in `config.json` to one of:

| Provider | `"provider"` value | Web search | Notes |
|---|---|---|---|
| Anthropic Claude | `"anthropic"` | Native (best) | Default |
| OpenAI GPT-4o | `"openai"` | `gpt-4o-search-preview` | Use if you have an existing key |
| Google Gemini | `"gemini"` | Google Search grounding | Cheapest per token |

### 4. Create your `.env`

```bash
cp .env.example .env
```

Fill in only the key(s) for your chosen provider:
```
ANTHROPIC_API_KEY=your_key_here   # anthropic
OPENAI_API_KEY=your_key_here      # openai
GEMINI_API_KEY=your_key_here      # gemini
REOON_API_KEY=your_key_here       # always required
```

- Anthropic API: [console.anthropic.com](https://console.anthropic.com)
- OpenAI API: [platform.openai.com](https://platform.openai.com)
- Gemini API: [aistudio.google.com](https://aistudio.google.com)
- Reoon: [emailverifier.reoon.com](https://emailverifier.reoon.com)

### 4. Set up Gmail + Google Sheets

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a project
3. Enable **Gmail API** and **Google Sheets API**
4. OAuth consent screen → External → add your Gmail as a test user
5. Credentials → Create OAuth 2.0 Client ID → Desktop app → Download JSON
6. Save the downloaded file as `credentials.json` in this folder
7. Run the authorization flow:

```bash
python setup_gmail.py
```

A browser window will open. Authorize access. A `token.json` will be saved automatically.

### 5. Test manually

```bash
python main.py status        # show database stats
python main.py research 3    # research 3 contacts and draft emails (no send)
python main.py send          # send pending drafts
python main.py run           # full cycle: research + draft + send
```

### 6. Start the scheduler

```bash
python scheduler.py
```

Runs the full pipeline at the time set in `config.json`, then repeats on the configured interval. Bounce and reply checks run every 6 hours. Google Sheets syncs after every run.

## Project Structure

```
├── main.py                      # manual control CLI
├── scheduler.py                 # auto-runs on interval
├── pipeline.py                  # orchestrates each cycle
├── research.py                  # delegates to provider for contact research
├── drafter.py                   # delegates to provider for email drafting
├── models.py                    # Pydantic schemas (Contact, EmailDraft)
├── providers/
│   ├── __init__.py              # provider factory
│   ├── anthropic_client.py      # Claude + native web search
│   ├── openai_client.py         # GPT-4o + search preview
│   └── gemini_client.py         # Gemini + Google Search grounding
├── verify.py                    # Reoon API verifies emails
├── gmail_sender.py              # sends via Gmail API
├── bounce_reply.py              # detects bounces and replies from Gmail
├── sheets_sync.py               # syncs database to Google Sheets
├── database.py                  # SQLite — contacts, emails, blocklist
├── setup_gmail.py               # run once to authorize Gmail + Sheets
├── config.example.json
├── .env.example
└── requirements.txt
```

## Google Sheets Dashboard

On first run a spreadsheet is auto-created and its ID is saved to your `config.json`. It tracks:

| Column | Description |
|---|---|
| Name, Email, Company, Role | Contact info |
| Appeal Angle | What hook Claude used to personalize |
| Campaign | Which targeting run found this contact |
| Status | `researched` → `drafted` → `sent` → `replied` / `bounced` |
| Sent At | Timestamp of send |
| Bounced / Replied | Yes/No, with detection timestamp |

## Blocklist

To stop emailing someone, add their address to the `blocklist` table:

```bash
python -c "import database as db; db.init_db(); db.add_to_blocklist('email@example.com', 'requested removal')"
```

## Sensitive Files (gitignored)

These files are never committed:

```
.env                ← API keys
config.json         ← your personal info and targeting
credentials.json    ← Google OAuth credentials
token.json          ← Gmail session token
cold_email.db       ← all contacts and email history
```

## Legal

Cold email is subject to CAN-SPAM (US) and GDPR (EU). Ensure your emails include a clear way for recipients to opt out, and honor all removal requests promptly.
