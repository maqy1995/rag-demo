# Pushing to GitHub — three paths

Pick **one** of the three options below. Each ends with the repo live
on `github.com/<you>/<repo>` and `git push` working without re-entering creds.

---

## Path A — `gh` CLI (recommended, easiest)

Best if you don't mind installing one Homebrew formula and authenticating
in the browser. The CLI handles HTTPS, SSH, and credential caching.

```bash
brew install gh
gh auth login                          # choose GitHub.com → HTTPS → login via browser
gh repo create <repo-name> --public --source=. --remote=origin --push
```

After this, `git push` will just work — `gh` stores the token in the macOS
keychain via `git credential-osxkeychain` (already configured in `~/.gitconfig`).

---

## Path B — HTTPS + Personal Access Token

Use this if you can't or don't want to install `gh`. You keep full control
over which token is used.

1. Create a fine-grained PAT at <https://github.com/settings/tokens?type=beta>
   with `Contents: Read & write` on the target repo.
2. Create the empty repo on GitHub first (web UI, **do not** initialize with
   README/license/.gitignore).
3. Locally:

   ```bash
   git remote add origin https://github.com/<you>/<repo>.git
   git push -u origin main
   # when prompted, paste the PAT as the password
   ```

   macOS will offer to save the PAT in the keychain — accept it.

---

## Path C — SSH key

Use this if you already have SSH set up with GitHub, or if you want to
avoid HTTPS entirely. The downside: this machine has **no `~/.ssh` yet**,
so you need to generate + upload a key first.

```bash
ssh-keygen -t ed25519 -C "maqy1995@163.com" -f ~/.ssh/id_ed25519
eval "$(ssh-agent -s)"
ssh-add --apple-use-keychain ~/.ssh/id_ed25519
# print the public key, then paste it into https://github.com/settings/keys
cat ~/.ssh/id_ed25519.pub

git remote add origin git@github.com:<you>/<repo>.git
git push -u origin main
```

---

## Common gotchas on this machine

- `http(s).proxy` is set to `127.0.0.1:7897` in `~/.gitconfig`. If you
  switch off the proxy (e.g. you're at a coffee shop), unset it
  temporarily with `git -c http.proxy= -c https.proxy= push ...`.
- `credential.helper=osxkeychain` is configured globally — when `gh` or
  PAT is stored there, you will not be re-prompted.
- Codex and Claude Code are both running through a third-party proxy
  (`api.minimaxi.com`). The RAG demo itself does **not** depend on that
  proxy — pick whichever LLM provider (OpenAI, Anthropic, or local) you
  have keys for.
