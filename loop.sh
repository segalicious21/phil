#!/usr/bin/env bash
# Run trading cycles headlessly.
# Usage: ./loop.sh [cycles] [sleep_minutes] [--real]
#   --real: append REAL.md to the prompt so qualifying paper bets get a $1
#           real twin via Pearl Connect (requires PEARL_CONNECT_STORE and a
#           healthy local connect signer; downgrades to paper otherwise).
set -euo pipefail
cd "$(dirname "$0")"

# One loop per checkout. Two loop.sh processes in the same working tree
# commit over each other and collide with the cloud routine (2026-09-15 to
# 2026-09-21: a second loop started without PEARL_CONNECT_STORE ran next to
# the real one for six days). The pid file guards the start; a stale file
# left by a crashed loop is harmless because the pid is checked for liveness.
LOCK=".loop.pid"
if [ -f "$LOCK" ] && kill -0 "$(cat "$LOCK" 2>/dev/null)" 2>/dev/null; then
  echo "ERROR: loop.sh is already running in this checkout (pid $(cat "$LOCK")); refusing to start a second one" >&2
  exit 1
fi
echo $$ > "$LOCK"
trap 'rm -f "$LOCK"' EXIT

if [ -z "${PEARL_CONNECT_STORE:-}" ]; then
  echo "NOTE: PEARL_CONNECT_STORE is unset — this loop runs without the Pearl Connect tools (no mech second opinions, no real twins)" >&2
fi

# No git hooks (operator, 2026-10-16): code the session runs can write
# .git/hooks/*, and this shell's push, rebase and checkout would then run it
# outside claude's allowlist. The repo ships no hooks; CI is the guard.
# core.fsmonitor names a command too, so it is pinned off the same way.
export GIT_CONFIG_COUNT=2 GIT_CONFIG_KEY_0=core.hooksPath GIT_CONFIG_VALUE_0=/dev/null \
  GIT_CONFIG_KEY_1=core.fsmonitor GIT_CONFIG_VALUE_1=false
# Python run by this shell uses -I, so a json.py the session leaves in the
# repo root or a user-site .pth is never imported; -I also drops PYTHONUTF8,
# hence -X utf8 (without it the cp949 locale breaks core scripts on Windows).

REAL_MODE=0
ARGS=()
for a in "$@"; do
  [ "$a" = "--real" ] && REAL_MODE=1 || ARGS+=("$a")
done
CYCLES="${ARGS[0]:-1}"
SLEEP_MIN="${ARGS[1]:-45}"

# Nothing in this repo belongs in .claude/ or .mcp.json: a project or local
# settings file there is loaded by `claude -p` and widens the allowlist below
# (operator, 2026-10-16). It is untracked, so the post-cycle revert misses it.
# Checked before every tick and again before the push; a hit stops the loop
# for a human to look, it never deletes what may be the operator's own file.
stray_settings() {
  if [ -e .mcp.json ] || [ -n "$(ls -A .claude 2>/dev/null)" ]; then
    echo "ERROR: unexpected .claude/ or .mcp.json in this checkout - review and remove it before cycling:" >&2
    ls -lA .claude .mcp.json 2>/dev/null >&2 || true
    return 0
  fi
  return 1
}

for i in $(seq 1 "$CYCLES"); do
  echo "=== cycle $i/$CYCLES $(date -u +%FT%TZ) ==="
  stray_settings && exit 1

  # With HEAD detached, `git push origin main` pushes the stale local branch
  # ref and reports success - the cycle's commits never reach the remote
  # (2026-08-17: 34 commits nearly lost). Reattach main to HEAD before any
  # sync or push logic can judge state.
  if ! git symbolic-ref -q HEAD >/dev/null; then
    echo "WARNING: HEAD detached — reattaching main to HEAD" >&2
    git checkout -B main HEAD
  fi

  # Sync with origin before cycling so a stale local main can never silently
  # fork for days (the 2026-07-31 orphaned-history incident). Fast-forward
  # only; a genuine divergence needs a human, not an automatic reset.
  if git remote get-url origin >/dev/null 2>&1; then
    # A shallow clone manufactures fake divergence (no merge-base, spurious
    # "forced update") — unshallow before any behind/diverged judgment.
    if [ "$(git rev-parse --is-shallow-repository 2>/dev/null)" = "true" ]; then
      git fetch --unshallow origin 2>/dev/null \
        || git fetch --deepen=1000 origin 2>/dev/null \
        || echo "WARNING: could not unshallow clone" >&2
    fi
    if git fetch origin main 2>/dev/null; then
      if git merge-base --is-ancestor HEAD origin/main; then
        git checkout -B main origin/main
      elif ! git merge-base --is-ancestor origin/main HEAD; then
        echo "WARNING: local main and origin/main have diverged — resolve manually" >&2
      fi
    else
      echo "WARNING: could not fetch origin/main; cycling on local state" >&2
    fi
  fi

  # Pearl Connect attach: when the local signer is up, expose its read-only
  # wallet_info MCP tool plus the mech marketplace tools, and deny the
  # session the token file (journal is public — the bearer token must never
  # be readable, let alone committed).
  # The probe must positively identify the connect signer: every Pearl agent
  # serves /healthcheck on 8716, and a full trader FSM also reports
  # is_healthy=true — but only connect's body is bare (no "rounds" field).
  PEARL_UP=0
  STORE="${PEARL_CONNECT_STORE:-}"
  if [ -n "$STORE" ] && [ -f "$STORE/.mcp.json" ]; then
    HC="$(curl -sf -m 2 http://127.0.0.1:8716/healthcheck 2>/dev/null || true)"
    if echo "$HC" | grep -q '"is_healthy": *true' \
       && ! echo "$HC" | grep -q '"rounds"'; then
      PEARL_UP=1
    fi
  fi

  # Runner lease (core/lease.py): one cycle at a time across the cloud
  # routine and this loop. Taken here, in the interactive shell where the
  # keyring is unlocked, and released after the push below; PHIL_LEASE tells
  # CYCLE.md step 0 it is already taken. Without the lease (the other runner
  # holds it, or it could not be written) the whole tick is skipped, not run
  # LIGHT: a LIGHT tick still commits settled rows next to the holder's
  # cycle, and that is how main forks. lease.py's docstring has the why.
  if ! LEASE="$(PHIL_PUSH_BY_LOOP=1 python3 -I -X utf8 core/lease.py acquire)"; then
    echo "WARNING: runner lease not taken - skipping this tick: $LEASE" >&2
    [ "$i" -lt "$CYCLES" ] && sleep $((SLEEP_MIN * 60))
    continue
  fi

  # Screener journal rotation (operator, 2026-10-11): once a month, move the
  # pre-month head of journal/screener.jsonl into a gzip archive so the file
  # stays under GitHub's 100 MB push limit. A no-op until the month turns;
  # the cycle's own `git add -A` commits the result. A failure here never
  # blocks the cycle. core/screener_archive.py has the details.
  python3 -I -X utf8 core/screener_archive.py >&2 \
    || echo "WARNING: screener_archive failed - journal left as it was" >&2

  # Model per tick (operator, 2026-09-23): Opus 5.5 for any tick that may run
  # FULL or TRIGGERED, Sonnet 5 for a tick CYCLE.md step 0/0b will run LIGHT.
  # Pinned because an unpinned `claude -p` takes the account-level default,
  # which follows the model last picked in any interactive session: from
  # 2026-09-08 to 2026-09-21 that ran these cycles on Fable. The prediction
  # uses only checks CYCLE.md applies itself, read after the same sync, and a
  # failed check falls through to Opus, so a mistake costs money rather than
  # running a FULL cycle on Sonnet. The collision guard is left to CYCLE.md:
  # an operator commit landing between here and the session's own fetch
  # would flip it, and the error would go the wrong way.
  MODEL=claude-opus-5-5
  MODEL_WHY="tick may run FULL"
  if python3 -I -X utf8 - <<'PY'
import datetime as dt, json, re, sys
now = dt.datetime.now(dt.timezone.utc)
iso = lambda t: dt.datetime.fromisoformat(t.replace("Z", "+00:00"))
s = json.load(open("strategy/schedule.json"))
hold = s.get("next_full_cycle_after")
if not hold or iso(hold) <= now:
    sys.exit(1)
# Count the tick type stated right after the cash figure, "cash $952.98
# (FULL cycle, ...". A LIGHT line can quote "(FULL" further along, and
# overcounting is the error that runs FULL on Sonnet.
# A line whose timestamp does not parse is skipped: undercounting FULL
# cycles errs towards Opus. cycles.log has hand-written lines such as
# 2026-09-15T04:2xZ.
full = 0
for line in open("journal/cycles.log"):
    m = re.match(r"(\S+Z) cycle done: .*?cash \$[\d,.]+ (?:-- )?\(FULL", line)
    try:
        if m and now - iso(m.group(1)) <= dt.timedelta(hours=24):
            full += 1
    except ValueError:
        continue
sys.exit(0 if full >= s["min_full_cycles_per_day"] else 1)
PY
  then
    MODEL=claude-sonnet-5
    MODEL_WHY="LIGHT tick: pacing hold with the daily FULL minimum met"
  fi
  echo "model: $MODEL ($MODEL_WHY)" >&2

  PROMPT="$(cat CYCLE.md)"
  REAL_ON=0
  if [ "$REAL_MODE" -eq 1 ]; then
    if [ "$PEARL_UP" -eq 1 ] \
       && python3 -I -X utf8 core/real.py doctor 2>/dev/null | grep -q '"ready": true'; then
      PROMPT="$(cat CYCLE.md REAL.md)"
      REAL_ON=1
    else
      echo "WARNING: --real requested but Pearl Connect signer not ready — running paper-only cycle" >&2
    fi
  fi

  # No "Bash(git push:*)": on this machine loop.sh owns the push (see the
  # push block below). The ref plumbing is allowlisted because CYCLE.md
  # step 9 and its rebase path mandate exactly these commands, and a
  # permission-blocked "checkout -B" strands the cycle's commits on a
  # detached HEAD (2026-08-28).
  #
  # strategy/tools (operator, 2026-10-11, proposals K2): that folder is
  # agent-editable, so "Bash(python3 strategy/tools/*)" on this machine would
  # run any code the session writes there, and this PC holds other projects'
  # API keys. Only the two tools the playbook needs that touch no network are
  # allowed (reconcile.py reads the journal, devig.py is arithmetic); the
  # session may not edit them (an Edit(path) deny covers every file-editing
  # tool), and they are reverted after the cycle like the protected paths.
  # The other tools stay unrunnable here.
  LOCKED_TOOLS=(strategy/tools/reconcile.py strategy/tools/devig.py)
  # PowerShell (operator, 2026-10-16): on Windows the session also gets a
  # PowerShell tool billed as the primary shell, and every rule below is
  # Bash(...), so git fetch and $env: reads went there and needed approval
  # no headless session can give (cycles.log 2026-10-11). Bash only. The
  # .claude/ deny stops the session writing a project settings file that
  # would widen this allowlist for the next cycle; the user-level settings
  # and .mcp.json denies close the same door one level up.
  DISALLOWED=("PowerShell" "Edit(./.claude/**)" "Edit(~/.claude/**)" "Edit(./.mcp.json)")
  # Allowlist audit (operator, 2026-10-16). Every protected path is also
  # Edit-denied, not just reverted afterwards: a session that can rewrite
  # core/score.py and then run it has the K2 hole back. .git/ is denied too,
  # since a hook or config line there runs on the next allowed git command.
  # `git log`/`git diff --output=<file>` writes any file without a file tool
  # (git takes no abbreviation of it; checked on 2.55).
  PROTECTED_PATHS=(core/ config/ .github/ CYCLE.md REAL.md loop.sh CLAUDE.md LICENSE README.md .gitignore
                   "${LOCKED_TOOLS[@]}")
  for p in "${PROTECTED_PATHS[@]}" .git/; do
    case "$p" in */) DISALLOWED+=("Edit(./$p**)") ;; *) DISALLOWED+=("Edit(./$p)") ;; esac
  done
  DISALLOWED+=("Bash(git log*--output*)" "Bash(git diff*--output*)")
  # The session has no allowed way to read its environment; state the two
  # flags CYCLE.md steps 0 and 9 ask about, both set on the claude call below
  # (this point is only reached after the lease was acquired above).
  PROMPT="$PROMPT

Runner note (loop.sh): PHIL_LEASE=acquired and PHIL_PUSH_BY_LOOP=1 are set for this session. Do not read the environment to check them."
  CMD=(claude -p "$PROMPT" --model "$MODEL"
       --allowedTools "Read" "Glob" "Grep" "WebSearch" "WebFetch"
         "Edit" "Write" "Task"
         "Bash(python3 strategy/tools/reconcile.py:*)"
         "Bash(python3 strategy/tools/devig.py:*)"
         "Bash(git add:*)" "Bash(git commit:*)"
         "Bash(git rev-parse:*)" "Bash(git log:*)" "Bash(git diff:*)"
         "Bash(git status:*)" "Bash(git symbolic-ref:*)"
         "Bash(git merge-base:*)" "Bash(git rev-list:*)"
         "Bash(git fetch origin main)" "Bash(git fetch --unshallow origin)"
         "Bash(git fetch --deepen=1000 origin)"
         "Bash(git checkout -B main origin/main)"
         "Bash(git checkout -B main HEAD)"
         "Bash(git rebase --continue)" "Bash(git rebase --abort)"
         "Bash(git rebase --quit)"
         "Bash(git pull --rebase origin main)")
  # One rule per core script, never "core/*": that glob also matched
  # core/../strategy/x.py and core/real.py. These are the scripts CYCLE.md
  # and the playbook call; lease.py stays with this shell (PHIL_LEASE), and
  # real.py is reachable only on a tick that loaded REAL.md.
  for s in ci resolve score scan screen odds mechlog forecast ledger validate \
           counterfactual screen_replay replay; do
    CMD+=("Bash(python3 core/$s.py:*)")
  done
  if [ "$REAL_ON" -eq 1 ]; then
    CMD+=("Bash(python3 core/real.py settle)" "Bash(python3 core/real.py place:*)")
  fi
  if [ "$PEARL_UP" -eq 1 ]; then
    # wallet_info is read-only; the mech_* tools buy predictions from the
    # Olas mech marketplace (~$0.01 USDC each, paid by the service safe) per
    # CYCLE.md step 5a. No other signing tools are exposed.
    CMD+=("mcp__pearl-connect__wallet_info"
          "mcp__pearl-connect__mech_tools"
          "mcp__pearl-connect__mech_request"
          "mcp__pearl-connect__mech_result"
          --mcp-config "$STORE/.mcp.json")
    DISALLOWED+=("Read($STORE/.mcp.json)")
  fi
  CMD+=(--disallowedTools "${DISALLOWED[@]}" --permission-mode acceptEdits)

  # PHIL_PUSH_BY_LOOP tells CYCLE.md step 9 to commit but not push — the push
  # happens below, in this shell. GIT_TERMINAL_PROMPT/GIT_ASKPASS make any
  # stray credential lookup fail fast instead of hanging on a keyring prompt
  # no headless session can answer; GIT_EDITOR stops `git rebase --continue`
  # from opening an editor and blocking forever.
  #
  # Paper ticks run without PEARL_CONNECT_STORE (operator, 2026-10-16):
  # core/scan.py and core/replay.py import agent-editable strategy/ code, and
  # core/real.py finds the signer only through that variable, so without it
  # strategy code cannot reach real funds on a paper tick. --mcp-config above
  # still names the store for the mech tools.
  # .git/config and .gitattributes can name commands (filter drivers,
  # sshCommand, credential helpers) that this shell's git calls would run;
  # a change during the tick stops the loop below for a human to look.
  GITCFG_SUM="$(cat .git/config .gitattributes 2>/dev/null | cksum)"
  RUN_ENV=()
  [ "$REAL_ON" -eq 1 ] || RUN_ENV=(env -u PEARL_CONNECT_STORE -u CONNECT_POLYMARKET_VENV)
  PHIL_PUSH_BY_LOOP=1 PHIL_LEASE=acquired \
  GIT_TERMINAL_PROMPT=0 GIT_ASKPASS=/usr/bin/true GIT_EDITOR=true \
    ${RUN_ENV[@]+"${RUN_ENV[@]}"} "${CMD[@]}" || echo "cycle $i failed; continuing"

  # Enforce the protected boundary: revert any agent edits to core/config.
  if ! git diff --quiet HEAD -- "${PROTECTED_PATHS[@]}"; then
    echo "WARNING: agent touched protected files — reverting" >&2
    git checkout -- "${PROTECTED_PATHS[@]}"
  fi
  # An untracked core/<name>.py (e.g. json.py) shadows the stdlib for every
  # core script, lease.py below included; the checkout above never sees it.
  # __pycache__ is kept: a .pyc there is never imported without its source.
  if [ -n "$(git clean -ndx -e __pycache__ -- core/)" ]; then
    echo "WARNING: untracked files in core/ - removing:" >&2
    git clean -fdx -e __pycache__ -- core/ >&2
  fi
  PROTECTED_IN_LAST_COMMITS=$(git log --oneline -5 --name-only | grep -cE '^(core/|config/|\.github/|CYCLE\.md|REAL\.md|loop\.sh|CLAUDE\.md|LICENSE|README\.md|\.gitignore)' || true)
  if [ "$PROTECTED_IN_LAST_COMMITS" -gt 0 ]; then
    echo "WARNING: protected files appear in recent commits — review manually" >&2
  fi

  if [ "$(cat .git/config .gitattributes 2>/dev/null | cksum)" != "$GITCFG_SUM" ]; then
    echo "ERROR: .git/config or .gitattributes changed during the cycle - review before pushing" >&2
    PHIL_PUSH_BY_LOOP=1 python3 -I -X utf8 core/lease.py release >/dev/null || true
    exit 1
  fi
  if stray_settings; then
    PHIL_PUSH_BY_LOOP=1 python3 -I -X utf8 core/lease.py release >/dev/null || true
    exit 1
  fi

  # Push from this shell, not from the agent. The credential helper is
  # `gh auth git-credential`, which reads the token from the macOS keyring —
  # a keyring prompt is unanswerable inside `claude -p`, so pushes there hang
  # until timeout and the cycle's commits never leave the machine
  # (2026-08-28: three hangs, commits stranded on a detached HEAD). This shell
  # is the interactive one the operator started, where the keychain is already
  # unlocked. CI remains the guard on protected-path commits.
  if git remote get-url origin >/dev/null 2>&1; then
    if ! git symbolic-ref -q HEAD >/dev/null; then
      echo "WARNING: HEAD detached after cycle — reattaching main to HEAD" >&2
      git checkout -B main HEAD
    fi
    if ! git push origin main; then
      echo "push rejected — rebasing onto origin/main and retrying" >&2
      if git pull --rebase origin main; then
        git push origin main \
          || echo "WARNING: push still failing after rebase — resolve manually" >&2
      else
        # Never hand-resolve a ledger conflict here; leave it for the operator.
        git rebase --abort 2>/dev/null || true
        echo "WARNING: rebase onto origin/main failed — commits are local only, resolve manually" >&2
      fi
    fi
  fi

  # Release the runner lease after the push, even a failed one: the tick is
  # over either way, and release commits onto origin/main, not onto HEAD.
  PHIL_PUSH_BY_LOOP=1 python3 -I -X utf8 core/lease.py release >/dev/null \
    || echo "WARNING: could not release the runner lease - it expires on its own" >&2

  [ "$i" -lt "$CYCLES" ] && sleep $((SLEEP_MIN * 60))
done
