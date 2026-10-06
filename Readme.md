# TikTok Daily Streak Bot

TikTok Daily Streak Bot is a GitHub Actions automation project that opens TikTok Messages, loads a logged-in TikTok session from exported cookies, finds pinned conversations, and sends a daily streak message.

The bot does not use your TikTok username or password. It uses exported browser cookies from an already logged-in TikTok session.

## Important Warning

Use this project at your own risk.

TikTok may change its website, message page, cookie system, or anti-automation behavior at any time. If that happens, the bot may stop working.

Do not use this project for spam, harassment, bulk messaging, or anything that violates TikTok rules or other people's privacy.

Never commit real cookies, Discord webhook URLs, Telegram bot tokens, screenshots, or log files.

---

> Original project by **TimeNitch**\
> Original repository: `https://github.com/TimeNitch/Tiktok-Streak-Bot-using-cookies`

---

## Table of Contents

<details>
<summary>Introduction</summary>

- [Important Warning](#important-warning)
- [Features](#features)
- [How It Works](#how-it-works)

</details>

<details>
<summary>Installation</summary>

- [Installation](#installation)
  - [1. Create the repository](#1-create-the-repository)
  - [2. Configure files](#2-configure-files)
  - [3. Choose target conversations](#3-choose-target-conversations)
  - [4. Export TikTok cookies](#4-export-tiktok-cookies)
  - [5. Add GitHub Secrets](#5-add-github-secrets)
  - [6. Optional: set up notifications](#6-optional-set-up-notifications)
  - [7. Optional: Configure the workflow schedule](#7-optional-configure-the-workflow-schedule)
  - [8. Run in Debug Mode first](#8-run-in-debug-mode-first)
  - [9. Enable real sending](#9-enable-real-sending)

</details>

<details>
<summary>Program Configuration</summary>

- [Configuration](#configuration)
  - [config.ini](#configini)
  - [text.txt](#texttxt)

</details>

## Features

* Runs automatically with GitHub Actions.
* Sends messages to pinned TikTok conversations.
* Supports scheduled sending by target time and timezone.
* Supports precheck before sending.
* Supports random message selection from `text.txt`.
* Supports Discord and Telegram notifications.
* Uploads logs and screenshots as GitHub Actions artifacts.

---

## How It Works

1. GitHub Actions starts the workflow automatically.
2. The workflow creates local token and cookies files from GitHub Secrets.
3. `Program.py` opens TikTok Messages.
4. The program injects your exported TikTok cookies.
5. The program checks pinned conversations.
6. If Debug Mode is enabled, it only reports detected targets and does not send messages.
7. If Debug Mode is disabled, it waits until the configured target time and sends messages.

---

## Installation

1. Create the repository
2. Configure files
3. Choose target conversations
4. Export TikTok cookies
5. Optional: set up notifications
6. Add GitHub Secrets
7. Configure the workflow schedule
8. Run in Debug Mode
9. Enable real sending

---

### 1. Create the repository

Create your own repository from this template, or copy the files into your own repository.

Repository visibility:

* **Public**: standard GitHub-hosted Actions runners are generally free for public repositories.
* **Private**: GitHub Actions may use your monthly free minutes quota.

Even if the repo is public, your private data is safe as long as you use GitHub Secrets and do not commit secret files.

---

### 2. Configure files

Create or edit these files in your repository:

```text
config.ini
text.txt
```

`config.ini` controls behavior such as Debug Mode, schedule, precheck, and timezone.

`text.txt` contains the messages that the bot can send.

Keep Debug Mode enabled for the first run:

```ini
DEBUG_MODE=True
```

---

### 3. Choose target conversations

The bot sends messages to conversations that are pinned on the TikTok messages page.

Open this link on your browser

```text
https://www.tiktok.com/messages?lang=en
```

Then pin the conversations that you want to send messages to.

For smartphone users, do not use the TikTok mobile app for this step. The app may limit pinned conversations to 5 conversations.

Instead:

1. Open a mobile browser.
2. Enable desktop site / desktop mode.
3. Open `https://www.tiktok.com/messages?lang=en`.
4. Pin the conversations from the desktop web view.

---

### 4. Export TikTok cookies

### Windows

1. Install Cookie-Editor extension to your browser.
2. Open `https://www.tiktok.com/messages?lang=en`.
3. Log in to TikTok.
4. Make sure the messages page loads and you can see the chats.
5. Open the Cookie-Editor extension.
6. Export cookies as JSON.
7. Add it to the GitHub secret named `COOKIE` in the next step.

### Android

1. Install Firefox from Google Play.
2. Install the Cookie-Editor extension in Firefox.
3. Open `https://www.tiktok.com/messages?lang=en`.
4. Log in to TikTok.
5. Make sure the messages page loads and you can see the chats.
6. Open Cookie-Editor.
7. Export cookies as JSON.
8. Add it to the GitHub secret named `COOKIE` in the next step.

### iOS

Not recommended.

A Cookie-Editor app from the App Store may not be able to access Safari or TikTok browser cookies.\
In testing, after logging in to TikTok, the app reported that no cookies were found.

### <u>NOTES</u>

* `COOKIE` is required.
* If the cookie expires, export a new cookie and update the `COOKIE` secret.
* Do not commit cookies and tokens into the repository.


---
### 5. Add GitHub Secrets

Add the exported cookie data to the GitHub secret named `COOKIE`.

Go to:

```text
Repository → Settings → Secrets and variables → Actions → New repository secret
```

Required secret:

```text
COOKIE
```

Optional secrets:

```text
DISCORD_WEBHOOK_URL
TELEGRAM_BOT_TOKEN
TELEGRAM_CHAT_ID
```
---

### 6. Optional: set up notifications

You can use Discord webhook, Telegram bot, Both or Neither

If you want notifications, create the notification token or webhook first, then put the values in the GitHub Secrets.

The bot can notify when:

* First precheck passes.
* Cookie has a problem or no target conversations are found.
* Debug Mode collects target conversations.
* Messages are sent successfully.


### Discord

Create a Discord webhook:

```text
Server Settings → Integrations → Webhooks → New Webhook
```

Copy the webhook URL and add it as a GitHub secret:

```text
DISCORD_WEBHOOK_URL
```

For local testing, create:

```text
discord_webhook.txt
```

Paste only the webhook URL inside the file.

Do not commit this file.


### Telegram

Telegram needs two values:

```text
TELEGRAM_BOT_TOKEN
TELEGRAM_CHAT_ID
```

Basic setup:

1. Open Telegram.
2. Search for `@BotFather`.
3. Send `/newbot`.
4. Follow the instructions and copy the bot token.
5. Open your new bot and press Start.
6. Send 'test' to the bot.
7. Open this URL in a browser and replace YOUR_BOT_TOKEN with your token:

```text
https://api.telegram.org/botYOUR_BOT_TOKEN/getUpdates
```

Find:

```json
"chat": {
  "id": 123456789
}
```

That number is your `TELEGRAM_CHAT_ID`.

Add these as GitHub Secrets:

```text
TELEGRAM_BOT_TOKEN
TELEGRAM_CHAT_ID
```

For local testing, create:

```text
telegram_bot_token.txt
telegram_chat_id.txt
```

Do not commit these files.


---

### 7. Optional: Configure the workflow schedule

GitHub cron uses UTC time.  
Thailand time is UTC+7.

By default, this project is designed to start the workflow at **02:00 UTC+7** and send the message at **06:00 UTC+7**.

However, GitHub Actions scheduled workflows may not always start exactly on time.  
Sometimes, there can be a delay, and in some cases the delay may be up to around **2 hours**.

For this reason, the workflow is intentionally scheduled to start earlier than the actual target send time.

While waiting, the program can also run pre-checks based on your configured interval.  
By default, the pre-check interval is every **10 minutes**.

If you want to change the target send time, edit these values in `config.ini`:

```ini
TARGET_RUN_TIME=12:00
TARGET_TIMEZONE=Asia/Bangkok
```

Change `TARGET_RUN_TIME` to your desired send time, and change `TARGET_TIMEZONE` to your own timezone.

You also need to update the workflow schedule in:

```text
.github\workflows\TikTok Streak Ubuntu.yml
```

on these line:

```yaml
on:
  schedule:
    - cron: "0 19 * * *"
  workflow_dispatch:
```

A good time to start the workflow is about **4 hours before** your target send time.  
After choosing the workflow start time in your timezone, convert that time to **UTC**, because GitHub cron always uses UTC.

Example:

```text
Target send time: 06:00 UTC+7
Workflow start time: 02:00 UTC+7
Cron time: 19:00 UTC
```

So the cron value should be:

```yaml
cron: "0 19 * * *"
```

If you do not want the program to wait until a fixed target time, you can disable it in `config.ini`:

```ini
WAIT_UNTIL_TARGET_TIME=false
```

When this option is disabled, the program will send the message as soon as GitHub Actions starts running.

---

### 8. Run in Debug Mode first

Before real sending, keep this in `config.ini`:

```ini
DEBUG_MODE=True
```

Debug Mode will:

* Open TikTok.
* Load cookies.
* Collect target conversations.
* Send notification if configured.
* Skip precheck and waiting.
* Not send any TikTok messages.

Run the workflow manually:

```text
Repository → Actions → TikTok Daily Streak Bot → Run workflow
```

Check that the detected target conversations are correct.

---

### 9. Enable real sending

After Debug Mode works, change:

```ini
DEBUG_MODE=False
```

Commit and push the change.

The bot will now use your schedule and send real messages.

## Configuration

### config.ini

There is a `config.ini` in the same folder as `Program.py`.

```ini
# Enable Debug Mode.
# True  = test only. Collect targets, notify, but do not send messages.
# False = normal mode. Use schedule/precheck and send messages.
DEBUG_MODE=True

# Enable Discord / Telegram notifications.
# True  = send notifications if notification files are configured.
# False = disable all notifications.
ENABLE_NOTIFY=True

# Wait until the target time before sending messages.
# True  = wait until TARGET_RUN_TIME.
# False = run immediately.
WAIT_UNTIL_TARGET_TIME=True

# Run precheck before the target time.
# True  = run precheck before sending.
# False = skip precheck.
PRECHECK_BEFORE_WAIT=True

# How often to run precheck before the target time, in minutes.
PRECHECK_INTERVAL_MINUTES=10

# Stop running precheck when the target time is this close, in minutes.
PRECHECK_STOP_WITHIN_MINUTES=5

# The time when the bot should send messages.
# Format: HH:MM or HH:MM:SS
TARGET_RUN_TIME=06:00

# IANA timezone name used for TARGET_RUN_TIME.
# Examples: Asia/Bangkok, Asia/Tokyo, America/New_York, Europe/London
# Full list: https://en.wikipedia.org/wiki/List_of_tz_database_time_zones
TARGET_TIMEZONE=Asia/Bangkok

# Selenium wait timeout in seconds.
TIKTOK_WAIT_SECONDS=10
```

Debug Mode behavior:
  
```text
DEBUG_MODE=True skips precheck and target-time waiting.
This makes Debug Mode run immediately and safely without sending messages.
```

---

### text.txt

Create `text.txt` in the same folder as `Program.py`.

Each line is one possible message.

```text
I'm here for the streak🔥
Daily streak check🔥
Keep the streak alive🔥
```

If there are multiple lines, the bot randomly chooses one message **per person**.
---
