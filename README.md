<div align="center">

# 🎬 CineRequestBot

**A Pyrogram-based Telegram bot that delivers movie & series search results via a private results channel — Locaflix-style.**

Users search in the group → results go to a **private channel** → group only gets a button link.  
No movie links ever appear in the group. ✅ Copyright-safe architecture.

</div>

---

## ✨ Features

| Feature | Description |
|---------|-------------|
| 🔍 **Smart Search** | Searches connected Telegram channels for movies & series by name |
| 📺 **Results Channel** | Results are posted to a private channel — never in the group |
| 🔗 **URL Button** | Group gets a "Click here to Get movie/Series" button linking to results |
| ⏱️ **Auto-Delete** | Results auto-delete after a configurable timer (1, 2, or 5 minutes) |
| 🔒 **Force Subscribe** | Require users to join a channel before they can search |
| 📡 **Multi-Channel** | Connect multiple content channels per group |
| 🔌 **Easy Disconnect** | Remove channels with inline tap buttons — no ID needed |
| ✅ **Group Verification** | Owner must verify groups before search is enabled |
| 📢 **Broadcast** | Send messages to all users or all groups |
| 🼎 **Spell Correction** | Auto-corrects misspelled queries via Google spell check |
| 🎞️ **IMDb Fallback** | Shows IMDb suggestions when nothing is found |

---

## 📱 How It Works

```
User types "Inspector Avinash" in group
        │
        ▼
Bot searches connected content channels (via user session)
        │
        ▼
Results posted to private RESULTS_CHANNEL
        │
        ▼
Group receives:
  ✅ Found 2 results in Channel.
  Page 1/1
  (Results auto-delete in 10 mins)
  [🎬 Click here to Get movie/Series] ← URL button
        │
        ▼
User clicks → opens results channel message → sees all links
        │
        ▼
Message auto-deletes from results channel after timer ✅
```

---

## 🤖 Commands

### Group Commands
| Command | Description |
|---------|-------------|
| `/verify` | Request group verification (owner only) |
| `/connect -100xxxxxxxxxx` | Connect a content channel |
| `/disconnect -100xxxxxxxxxx` | Disconnect a channel |
| `/connections` | View all connected channels with remove buttons |
| `/fsub -100xxxxxxxxxx` | Set force-subscribe channel |
| `/nofsub` | Remove force-subscribe |
| `/autodelete 1\|2\|5` | Set auto-delete timer (minutes) |

### General Commands
| Command | Description |
|---------|-------------|
| `/start` | Check if bot is alive |
| `/help` | Show all commands |
| `/id` | Get chat/user ID |
| `/ping` | Check bot speed |

### Owner Commands
| Command | Description |
|---------|-------------|
| `/stats` | Total users, groups, connected channels |
| `/broadcast` | Broadcast to all users (reply to a message) |
| `/broadcast_groups` | Broadcast to all groups |

---

## 🚀 Deploy on Railway

### Step 1 — Fork / use this repo
Railway watches the `replit-agent` branch for auto-deploys.

### Step 2 — Set environment variables

| Variable | Required | Description |
|----------|----------|-------------|
| `API_ID` | ✅ | From [my.telegram.org](https://my.telegram.org) |
| `API_HASH` | ✅ | From [my.telegram.org](https://my.telegram.org) |
| `BOT_TOKEN` | ✅ | From [@BotFather](https://t.me/BotFather) |
| `OWNER_ID` | ✅ | Your Telegram user ID (numeric) |
| `RESULTS_CHANNEL` | ✅ | Private results channel ID (e.g. `-1001234567890`) |
| `MONGO_URI` | ✅ | MongoDB connection string |
| `SESSION` | ✅ | Pyrogram user session string (for channel search) |
| `LOG_CHANNEL` | ☑️ | Channel ID for bot logs (optional) |
| `SEARCH_REPLY_TTL` | ☑️ | Auto-delete seconds (default: `600` = 10 min) |

### Step 3 — Railway settings
- **Repository:** `Azizthekiller3/CineRequestBot`
- **Branch:** `replit-agent`
- **Root directory:** `telegram-bot`
- **Start command:** `python bot.py`

### Step 4 — Set up results channel
1. Create a **private Telegram channel** (e.g. "My Results")
2. Add your bot as **Admin**
3. Get the channel ID using `/id` command → set as `RESULTS_CHANNEL`
4. Use `/fsub` in your group to force-subscribe members to this channel

### Step 5 — Get a Session String
Visit the `/gen` endpoint of your deployed bot (e.g. `https://your-app.railway.app/gen`) to generate a Pyrogram session string from your phone number.

---

## 🛠️ Group Setup (for admins)

1. Add the bot to your group as **Admin**
2. Type `/verify` in the group → wait for owner approval
3. Use `/connect -100xxxxxxxxxx` to link content channels
4. Use `/fsub -100xxxxxxxxxx` to force-subscribe members to the results channel
5. Members can now type any movie/series name and get a button ✅

---

## 📁 File Structure

```
telegram-bot/
├── bot.py              Entry point
├── client.py           User session + auto-delete bot clients
├── config.py           Environment variable loading
├── health.py           Flask health server + session generator (/gen)
├── requirements.txt
├── Dockerfile
├── database/
│   ├── __init__.py
│   └── db.py           MongoDB: groups, users, auto-delete
├── plugins/
│   ├── search.py       ★ Core: search → results channel → group button
│   ├── connect.py      /connect /disconnect /connections
│   ├── misc.py         /start /help /about /id /stats
│   ├── verify.py       Group verification
│   ├── fsub.py         Force subscribe
│   ├── autodelete.py   Auto-delete timer settings
│   ├── broadcast.py    Broadcast to users/groups
│   ├── ping.py         Ping command
│   └── newgroup.py     Welcome message on bot add
└── utils/
    ├── script.py       Message templates
    ├── helpers.py      Shared helpers
    ├── imdb.py         IMDb search fallback
    ├── spell.py        Google spell correction
    └── delete.py       Auto-delete background worker
```

---

## ⚙️ Tech Stack

- **Python 3.11**
- **[Pyrogram](https://docs.pyrogram.org)** — Telegram MTProto client
- **MongoDB** (via Motor async driver)
- **Flask** — health check server
- **Railway** — deployment platform

---

<div align="center">
Made with ❤️ — inspired by Locaflix architecture
</div>
