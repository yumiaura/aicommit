# 🤖 aicommit

> **AI commit messages from your local LLM.**
> Reads `git diff --staged`, asks Ollama for a clean Conventional Commit, commits.

Everything runs offline. No API keys, no data leaves the box.

---

## ✨ Features

- 📝 Generates **Conventional Commit** messages from staged changes
- 🤖 Powered by a **local LLM** via Ollama (or `llama-cpp-python`)
- ✍️ Opens the proposal in `$EDITOR` for a quick approval / edit / regenerate loop
- 📋 `--copy` mode: generate a message, copy it to the clipboard, and exit
- 📓 `changelog` subcommand: summarizes a tag range into a `CHANGELOG.md` entry
- 🔌 Installs as a `git` subcommand — call it as `git aicommit`

---

## 🚀 Quick start

```bash
# 1. install a model in Ollama (any chat-instruct model works)
ollama pull qwen2.5-coder:7b

# 2. install aicommit straight from GitHub
pip install git+https://github.com/yumiaura/AICommit

# 3. stage and let it write the message
git add -A
git aicommit
```

Sample interaction:

```text
────────────────────────────────────────────────────────
proposed commit message:
────────────────────────────────────────────────────────
fix(parser): handle empty input gracefully

- return [] instead of raising on whitespace-only files
- add regression test for the empty-file case
────────────────────────────────────────────────────────

[ Enter = commit · e = edit · r = regenerate · q = quit ]
```

Changelog mode:

```bash
git aicommit changelog v0.4.0..HEAD --out CHANGELOG.md
```

---

## ⚙️ Configuration

Quickest way to get a config file:

```bash
aicommit config
```

That creates `~/.config/aicommit/config.toml` from the default template
(if it doesn't exist yet) and opens it in `$EDITOR` — falling back to
`$VISUAL`, then `nano`. Re-running just re-opens the file; your existing
values are never clobbered.

The file looks like this:

```toml
[llm]
backend     = "ollama"            # ollama | llama-cpp
model       = "qwen2.5-coder:7b"
url         = "http://localhost:11434"
temperature = 0.1
max_tokens  = 512

[commit]
style        = "conventional"     # conventional | plain
include_body = true
```

Environment variables override the file (`AICOMMIT_MODEL=...`), and CLI
flags override env. Per-repo overrides go in `<repo>/.aicommit.toml`.

Useful flags:

```text
aicommit [--backend {ollama,llama-cpp}] [--model M] [--url URL]
         [--temperature T] [--max-tokens N]
         [--style {conventional,plain}] [--no-body]
         [--review] [--review-only] [--copy]
         [--print] [--no-stream] [-y/--yes] [--debug] [--version]
aicommit changelog <rev-range> [--out CHANGELOG.md]
aicommit config
```

Copy mode is useful when you want the generated message but still plan to commit
from another tool:

```bash
git add -A
git aicommit --copy
git commit
```

---

## 📦 Stack

- `ollama` HTTP API via stdlib `urllib` (or `llama-cpp-python` for in-process inference)
- `subprocess` to call `git`
- `argparse` for the CLI
- `tomllib` (Python 3.11+) for config

Zero runtime dependencies for the default Ollama backend.

---

## 📄 License

[MIT](LICENSE).

Author: [@yumiaura](https://github.com/yumiaura)
