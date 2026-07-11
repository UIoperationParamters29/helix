# HELIX Security Model

HELIX gives an LLM real system access. This document explains how that access is bounded.

## Threat model

HELIX runs on your device (PC or Termux on Android). It has the same permissions as your user account (PC) or as Termux + ADB (phone). An LLM that goes off the rails could:

- Delete files (shell access)
- Send SMS / make calls (Termux:API)
- Tap / swipe / type (ADB UI control)
- Install / uninstall apps (ADB)
- Make network requests (web tools)
- Spend money (LLM API calls, SMS / calls)

The goal is to let the agent be useful while preventing catastrophic mistakes.

## Defense layers

### Layer 1: Tool design — read-only vs. dangerous flags

Every tool declares:

```python
class FileRead(Tool):
    read_only = True       # safe to auto-approve
    # ...

class Bash(Tool):
    dangerous = False      # but checked per-call via patterns
    read_only = False
    # ...

class PhoneSmsSend(Tool):
    dangerous = True       # always requires approval
    # ...
```

The `RiskAnalyzer` combines these flags with per-call pattern matching.

### Layer 2: Risk analyzer

Every tool call is scored 0-100 based on:

- Tool name (e.g. `phone_sms_send` is inherently risky)
- Argument patterns (regex-matched against `dangerous_patterns` from config)

Patterns checked (see `helix/security/policy.py`):

**Critical (100):**
- `rm -rf /` (root delete)
- `rm -rf ~` (home delete)
- `mkfs` (filesystem format)
- `dd ... of=/dev/hd` or `/dev/sd` (raw disk write)
- `shutdown | reboot`
- Fork bomb `:(){ :|:& };`

**High (75):**
- `curl ... | sh` (pipe to shell)
- `wget ... | sh`
- `git push --force`
- `npm publish`
- `pip install --user`

**Medium (50):**
- `rm -rf` (any recursive delete)
- `git reset --hard`
- `chmod +x`
- `sudo`

**Phone-specific:**
- `phone_sms_send`, `phone_call` → 80 (costs money / disturbs contacts)
- `phone_notification` → 30
- `phone_app_stop` → 40

### Layer 3: Approval policy

```python
class ApprovalPolicy:
    def needs_approval(self, tool_name, args) -> tuple[bool, RiskAssessment]:
        assessment = self.analyzer.assess(tool_name, args)
        # Auto-approve low risk if config allows
        if assessment.level == "low" and self.config.auto_approve_reads:
            return False, assessment
        # Auto-approve medium if auto_approve_writes is True
        if assessment.level == "medium" and self.config.auto_approve_writes:
            return False, assessment
        # High and critical always require approval
        return assessment.level in ("high", "critical"), assessment
```

Default config:
- `auto_approve_reads: true` — read-only tools run without prompts
- `auto_approve_writes: false` — destructive tools require approval

To make the agent fully autonomous (DANGEROUS):
```yaml
auto_approve_writes: true
```

### Layer 4: Pattern blocklist

Even before the risk analyzer runs, the `Bash` tool's `check_dangerous()` method regex-matches against `config.dangerous_patterns` and refuses to run matching commands. This is the last-resort blocklist.

You can extend it in `~/.helix/config.yaml`:
```yaml
dangerous_patterns:
  - "rm\\s+-rf\\s+/(?!tmp)"
  - "dd\\s+.*of=/dev/"
  - "mkfs"
  # Add your own:
  - "pm\\s+uninstall"        # block app uninstall
  - "am\\s+force-stop"       # block force-stop
  - "settings\\s+put"        # block system settings changes
```

### Layer 5: Profile isolation

Multiple agents don't share state. Each gets its own `HELIX_HOME`:

```bash
HELIX_HOME=~/.helix-work helix web --port 8765
HELIX_HOME=~/.helix-personal helix web --port 8766
```

A bug in one agent can't corrupt another's memory or skills.

### Layer 6: No telemetry

HELIX does not phone home. LLM calls go directly to your configured provider (OpenAI, Anthropic, Z.ai, Ollama, etc.). No usage data is sent to HELIX maintainers.

You can verify this: grep the codebase for `requests.post` / `httpx.post` — all HTTP calls are either to your configured LLM API or to URLs the agent itself fetched at your request.

## Known limitations

### The LLM can talk you into things

If the agent asks you to approve something you don't understand, **deny it**. The agent will adapt and try a different approach. Don't rubber-stamp approvals.

### ADB pairing is powerful

Once you pair self-ADB, anyone with access to Termux can:
- Install / uninstall apps
- Read notifications
- Grant / revoke permissions
- Reset app data

**Only pair your own device. Revoke pairing when not needed** (Settings → Wireless debugging → Reset pairing).

### Bash is bash

The blocklist catches obvious patterns, but a determined LLM can compose commands that bypass regex. If you're worried, run HELIX in a Docker container (once `DockerWorkspace` is implemented) or in a VM.

### Skills and memory are agent-writable

The agent can edit `MEMORY.md`, `USER.md`, `IDENTITY.md`, and create new skills. If it goes off the rails, it could persist bad behavior.

Mitigation: review the Memory tab in the web UI periodically. Delete any skills that look wrong. The web UI's Memory view lets you edit all three files directly.

### Phone tools have real-world consequences

`phone_sms_send` actually sends SMS. `phone_call` actually calls. `phone_torch` actually turns on the flashlight. These aren't simulations.

Default config marks these as `dangerous: true` requiring approval. Don't disable that unless you understand the risks.

## Responsible use

- **Start with `auto_approve_writes: false`.** Approve each destructive action manually.
- **Review the EventLog.** The Sessions tab shows every action the agent took. Audit it.
- **Use a separate LLM key for HELIX.** Set spending limits on your OpenAI / Anthropic account.
- **Don't pair self-ADB on a work-managed phone.** Use a personal device.
- **Don't give HELIX access to sensitive contacts.** The agent can read your SMS and call log.

## Reporting security issues

If you find a vulnerability in HELIX itself (not in your LLM's behavior), please open an issue on GitHub with the `security` label.

For vulnerabilities in dependencies, report to the upstream project.
