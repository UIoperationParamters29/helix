# Skill Development Guide

Skills are HELIX's long-term memory for **procedures**. After solving a non-trivial task, the agent is encouraged to create a skill so future sessions can repeat the success.

This doc explains:
- What a skill is
- How the agent discovers and uses them
- How to write good skills (manually or by instructing the agent)
- The progressive disclosure model

## What is a skill?

A skill is a markdown file at `HELIX_HOME/skills/<name>/SKILL.md`. It contains:

- A title (H1)
- A one-line description (first non-empty, non-heading line)
- Full procedural content (steps, gotchas, examples)
- Optional: references to other files (Level 2)

Example:

```markdown
# deploy-nextjs-vercel

How to deploy a Next.js app to Vercel from the command line.

## Prerequisites
- Vercel CLI installed (`npm i -g vercel`)
- Logged in (`vercel login`)
- Project at the current directory

## Steps
1. Run `vercel` to deploy a preview
2. Review the URL returned
3. Run `vercel --prod` to promote to production

## Gotchas
- Environment variables: `vercel env add VAR_NAME`
- Custom domains: `vercel domains add example.com`
- If build fails, check `vercel logs <url>`
```

## How the agent discovers skills

### Level 0: Summaries (always loaded)

At session start, HELIX scans `~/.helix/skills/*/SKILL.md` and loads Level-0 info:

- Skill name (directory name)
- Title (first H1)
- One-line description (first non-heading line)

These are injected into the system prompt as a bullet list. Cost: ~50 tokens per skill. The agent knows they exist.

### Level 1: Full content (on demand)

When the agent decides a skill is relevant, it calls `skill_read` with the skill name. The full markdown content is returned as an observation. The agent now has the complete procedure.

### Level 2: Referenced files (on demand)

If a skill says "see /path/to/template.txt", the agent can `file_read` that path. The skill author decides what to reference.

This three-level system means HELIX can ship dozens of skills without bloating the system prompt.

## Creating skills

### Option A: Let the agent create them (recommended)

In chat, after solving a task:

> "That worked well. Create a skill capturing this procedure so you can repeat it next time."

The agent calls `skill_manage` with:
- `action: "create"`
- `name: "deploy-nextjs-vercel"` (kebab-case)
- `description: "How to deploy a Next.js app to Vercel"`
- `content: "# Deploy Next.js to Vercel\n\n..."`

### Option B: Write skills manually

Create the file directly:

```bash
mkdir -p ~/.helix/skills/my-skill
cat > ~/.helix/skills/my-skill/SKILL.md << 'EOF'
# my-skill

One-line description here.

## Steps
1. ...
2. ...
EOF
```

The skill is automatically picked up on the next session.

### Option C: Instruct the agent during a task

> "While you're doing X, also create a skill for it."

The agent will both complete the task and persist a skill simultaneously.

## Updating skills

The agent can update existing skills via `skill_manage` with `action: "update"`. This is useful when:
- A procedure has changed
- A gotcha was discovered
- A faster approach was found

You can also edit the file directly via the Files tab in the web UI.

## Deleting skills

```bash
rm -rf ~/.helix/skills/skill-name
```

Or via the agent: "Delete the skill called 'X'."

## What makes a good skill

### DO

- **Be specific.** "Deploy Next.js to Vercel" > "Deploy a website"
- **Include prerequisites.** What must be true before starting?
- **List concrete commands.** Not "run the deploy command" — `vercel --prod`
- **Document gotchas.** What surprised you? What failed?
- **Include examples.** Show actual input/output
- **Use kebab-case names.** `deploy-nextjs-vercel` not `DeployNextjsVercel`

### DON'T

- **Don't duplicate tool docs.** The agent already knows how to use `bash` and `file_write`. Skills are for *procedures*, not tool reference.
- **Don't make skills too long.** If a skill is > 5KB, split it into multiple skills.
- **Don't hard-code secrets.** Skills are plain text on disk. Use env vars.
- **Don't make skills for one-off tasks.** Skills are for *reusable* procedures.

## Example skills

### Skill: setup-python-venv

```markdown
# setup-python-venv

Create and activate a Python virtual environment for a project.

## Steps
1. cd to the project directory
2. python3 -m venv .venv
3. source .venv/bin/activate  # Linux/macOS/Termux
   # or: .venv\Scripts\activate  # Windows
4. pip install -r requirements.txt
5. Verify: python -c "import sys; print(sys.prefix)"

## Gotchas
- Always activate before running any project commands
- If pip is slow, set PIP_INDEX_URL to a mirror
- Don't commit the .venv/ directory — add to .gitignore
```

### Skill: send-morning-summary

```markdown
# send-morning-summary

Send myself a morning summary of unread notifications + calendar events.

## Prerequisites
- Termux + termux-api installed
- Notification access granted to Termux:API
- Calendar app accessible via ADB

## Steps
1. Get unread notifications: termux-notification-list
2. Get current time: date
3. Open calendar app: phone_app_launch com.android.calendar
4. Screenshot the day view: phone_ui_screenshot
5. Read the screenshot to extract events
6. Compose summary
7. Post as a notification: phone_notification --title "Morning summary" --content "..."

## Gotchas
- Notification access must be re-granted after Termux reinstall
- Calendar app package varies by phone: com.android.calendar / com.google.android.calendar
```

## Skill management via chat

The agent has three tools for skill management:

| Tool | What it does |
|---|---|
| `skill_list` | List all skills (Level 0 summaries) |
| `skill_read` | Load full content of a skill (Level 1) |
| `skill_manage` | Create / update / delete a skill |

You can ask the agent:

- "What skills do you have?"
- "Show me the content of the X skill."
- "Create a skill for Y."
- "Update the X skill with this new step."
- "Delete the X skill — it's outdated."

## Skills vs. memory

| | Skills | Memory |
|---|---|---|
| **What** | Reusable procedures | Facts and lessons |
| **Format** | One markdown file per skill | Three files: IDENTITY/USER/MEMORY.md |
| **Discovery** | Level 0 summaries in system prompt | Always loaded fully |
| **When to use** | "How do I do X?" | "Remember that the user prefers..." |
| **Example** | "deploy-nextjs-vercel" | "User's name is Alex; they prefer tabs over spaces" |

Both are agent-editable. Both persist across sessions. Both shape future behavior.

## Self-improvement loop

The closed loop:

1. User asks the agent to do something non-trivial
2. Agent plans + executes (may fail, retry, succeed)
3. Agent is prompted (in system prompt): "After solving a non-trivial task, CONSIDER creating a skill"
4. Agent decides if the procedure is reusable
5. If yes: calls `skill_manage` to create the skill
6. Agent also appends lessons to `MEMORY.md` via `memory_update`
7. Next session: skill is auto-discovered; memory is loaded

Over time, the agent accumulates a library of procedures tailored to your specific use cases. This is what makes HELIX get smarter the longer it runs.
