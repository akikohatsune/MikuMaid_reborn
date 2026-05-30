<p align="center">
  <img src="miku.jpg" alt="MikuMaintaining" width="500">
</p>
<p align="center"><span style="color:#8a8f98;">"39!"</span></p>

<h1 align="center">MikuMaid_reborn</h1> 

**MikuMaid_reborn** is a minimalist version, fully focused on performance with the support of NVIDIA NIM. The project has been streamlined to remove redundant components.

## Features

- **NVIDIA NIM Integration:** Utilizes the `google/gemma-3n-e4b-it` model (or other models supported by NVIDIA NIM) for ultra-fast response times.
- **User-Based Memory Isolation:** Each user has their own distinct "brain." Chat history is isolated by `user_id`, eliminating context confusion between different users.
- **KomiFilter 2.0:** An advanced security filter against Prompt Injection, Jailbreak, and system rule leaking (Prompt Leak).
- **Visual Env Sync:** A visual configuration synchronization system that automatically updates and lists missing variables upon startup.
- **Maximal Minimalism:** All complex Hooks and other Providers have been removed to optimize resources.

## Quick Setup

```bash
# Create a virtual environment
python -m venv .venv
# Activate the environment (Windows)
.venv\Scripts\activate
# Install dependencies
pip install -r requirements.txt
```

## Configuration (.env)

The system will automatically generate a `.env` file from `.env.example` when you run the bot for the first time. You just need to fill in the essential information:

- `NVIDIA_API_KEY`: API Key obtained from the NVIDIA API Catalog.
- `NVIDIA_MODEL`: The model to use (default: `google/gemma-3n-e4b-it`).
- `DISCORD_TOKEN`: Your Discord bot token.
- `OWNER_USER_ID`: Your ID to use Admin commands.

## Commands

### Chat & AI
- **@Bot + Message:** Chat directly with Miku.
- **!chat <message>:** Chat using a command (supports image attachments).
- **!ask <message>:** Alias for the chat command.

### Management (Admin Only)
- **!clearmemo:** Clear the entire short-term memory of **all users**.
- **!ban @user [reason]:** Ban a user from using the bot.
- **!removeban @user:** Unban a user.
- **!replaymiku ls:** View a list of recent chat logs.
- **!replaymiku <id>:** View detailed chat content by ID.

### Misc
- **!provider:** View information about the current model and system configuration.
- **!terminated on|off:** Enable/disable the bot's paused state.

## Security (KomiFilter)

`KomiFilter` protects the bot through 3 layers:
1. **Block User Injection:** Prevents commands like "ignore previous instructions".
2. **Block Prompt Leak:** Prevents users from requesting source code or system rules.
3. **Block Response Leak:** Automatically hides AI responses if they contain sensitive system information.

## Storage

The system uses SQLite to store data independently:
- `chat_memory.db`: Stores chat history isolated by User ID.
- `ban_control.db`: Stores the list of banned users.
- `callnames.db`: Stores personalized nicknames.

---
**License:** MIT  
**Art by:** [gomya0_0](https://x.com/gomya0_0)
