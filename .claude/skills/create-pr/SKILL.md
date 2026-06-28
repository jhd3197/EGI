---
name: create-pr
description: Generate a pull request title and description from the current branch's commits (EGI dev -> main flow). Produces a concise summary, optional feature highlights, and collapsible technical details. Normal human titles, no conventional-commit prefixes. Supports a lite mode for small PRs.
---

# Create PR Description

Generate a pull request title and description that's scannable, informative, and has just enough personality to feel human. This is the EGI flow: many commits land on `dev`, then one PR collects them for `main`.

## Instructions

### 1. Gather context (do ALL of these)

Run these commands to build a complete picture before writing anything. EGI ships from `dev` into `main`, so diff against `main`:

```bash
# Commit overview
git log main..HEAD --oneline --stat

# Full diff stat for file-level scope
git diff main..HEAD --stat

# Actual code changes — read the diff, don't just skim filenames
git diff main..HEAD
```

If the full diff is too large, diff individual areas (server routes/modules, frontend, mobile/android, egi CLI, etc.) in batches. You must understand **what the code actually does**, not just which files were touched.

### 2. Decide: full structure or lite?

Not every PR is a 30-commit milestone. Pick based on the actual change:

- **Lite** — a small, self-contained change (a bug fix, a copy tweak, a config bump, a handful of lines in one area). Write just a title and a 1-3 sentence summary. No Highlights, no Technical-changes accordion. Don't pad it.
- **Full** — a substantial PR (a feature, a multi-area change, a big batch of dev commits). Use the full structure below.

When in doubt and the PR is genuinely small, prefer lite. Forcing the full scaffold onto a two-line fix reads worse, not better.

### 3. Write the PR file

Write the file to `.pr/YYYY-MM-DD.md` (using today's date — the `.pr/` directory is gitignored). Create `.pr/` if it doesn't exist. If a file for today's date already exists, append a counter: `YYYY-MM-DD-2.md`, `YYYY-MM-DD-3.md`, etc.

#### Lite PR:

~~~markdown
# <Title>

<1-3 sentence summary of what changed and why.>
~~~

#### Full PR with user-facing features:

~~~markdown
# <Title>

<4-6 sentence summary>

### Highlights

- Highlight 1
- Highlight 2
- ...

<details>
<summary>Technical changes</summary>

- Detail 1
- Detail 2
- ...

</details>
~~~

#### Full PR that's purely internal (no user-facing features):

~~~markdown
# <Title>

<4-6 sentence summary>

<details>
<summary>Technical changes</summary>

- Detail 1
- Detail 2
- ...

</details>
~~~

Omit the Highlights section entirely for internal-only PRs — don't force it.

### Style Rules

#### Title
- **A normal, human-readable headline.** Describe the dominant change in plain language. Sentence case, concise (~70 chars), no trailing period.
- **No conventional-commit prefixes.** Do **not** start the title with `feat:`, `fix:`, `ci:`, `refactor:`, `chore:`, `type(scope):`, or anything like that. Just write the title a person would write.
  - Good: `Offline routing from X to Y`, `Fix the Android blank-screen on launch`, `Shelter and refugee information hub`
  - Bad: `feat(routing): offline directions`, `fix: blank screen`, `ci: add release`
- Pick the headline that covers the **dominant** change across the whole PR, not just one commit. Mixed PRs lean on the most user-significant change (a feature wins over the chores that came with it).
- **The title does not affect versioning.** EGI's app version is automatic: on merge to `main` the patch digit is the CI build number (`0.1.<run_number>`), with the major.minor base in the repo-root `VERSION` file. Nothing keys off the title or commit prefixes, so the title is purely for humans — write it for clarity, not for tooling.
- The `# <Title>` line at the top of the generated file **is** the PR title — when the PR is eventually opened, that same string is the `gh pr create --title` value. Don't write a second, different headline.

#### Summary
- **Full PRs: 4-6 sentences. Lite PRs: 1-3 sentences.** This is the part people actually read — give a full PR room to breathe.
- **Open with a touch of personality.** One line that makes the reader smile — a wry observation, a lighthearted remark, a playful metaphor. Not forced, just human. Examples of the energy (don't copy these literally, invent your own each time):
  - "This one's mostly about cleaning house."
  - "Turns out the WebView was right to complain."
  - A playful metaphor about what the code was doing wrong
  - A wry observation about the state of things before this PR
- **Match the tone to the change.** The voice should fit what the PR actually is — a bug fix can read dry and a little relieved ("This should've been caught months ago."), a new feature can read genuinely excited, a refactor can read like satisfying cleanup, a security or privacy fix should stay sober and matter-of-fact. Don't paste the same energy onto every PR.
- **Then explain what was going on and what this PR does about it.** Set the scene — what was broken, missing, or annoying? What's the approach? Name the main change areas (new feature, refactor target, bug fixed) but describe them in context, not as a dry list. The reader should walk away understanding the *story* of this PR, not just a changelog.
- **Include the "why" and the reasoning.** If there was a design choice, a trade-off, or a particular reason you went one way instead of another, mention it briefly. "We went with X instead of Y because Z" is the kind of thing that saves people from asking in review.
- **Do not repeat what Highlights or Technical changes already cover** verbatim, but it's fine to reference the same areas — the summary gives narrative context, the sections below give specifics.

#### Highlights (full PRs, only when applicable)
- One bullet per user-facing feature, behavior change, or notable improvement.
- Write from the user's perspective — what they'll notice, not internal implementation.
- Plain language, no code references. "Shelters now show live capacity and what supplies they need" not "`ShelterDetailScreen` gains a capacity prop".
- 3-7 bullets is the sweet spot. If you can only think of 1-2, fold them into the summary and skip this section.

#### Technical changes (full PRs, inside the accordion)
- One bullet per discrete change. Be specific — name files, modules, functions, patterns.
- Format: `backtick code references` for identifiers, plain text for descriptions.
- Every meaningful change in the diff must have a bullet. If a change touches security/privacy (auth, RBAC, SQL, the trust gate, person data), error handling, accessibility, or offline/sync behavior, it gets its own bullet — do not bury these.
- Bullets should describe the mechanism, not just the intent. "Stale mesh relays can't clobber newer rows: `sync_upload` now skips an incoming record whose `updatedAt` is older than the stored `updated_at`" is good. "Fix sync issues" is not.
- Group related changes together (all server routes, all frontend, all Android, all CLI, etc.).

#### Contributors
- If the PR includes commits from multiple authors (not just the repo owner), add a **Contributors** section after the summary and before Highlights.
- Use `git log main..HEAD --format='%aN <%aE>' | sort -u` to find unique commit authors.
- Exclude bot accounts (e.g., `github-actions[bot]`).
- Format: `@username` if their GitHub handle is available (check the ARGUMENTS or commit metadata), otherwise use their name. Add a brief note about what they contributed if it's clear from the commits.
- Keep it short — one line per contributor, no need for a full changelog.

#### General
- **No test plan section.** Do not include "Test plan" or "Testing".
- **No mention of tests.** Do not reference test files, test results, or testing.
- **No emoji.**
- **No "Generated by" footer.**

### 4. Stop after writing the file

This skill's job ends when the `.pr/` file is written. **Do not** run `gh pr create`, `git push`, or any other remote-affecting command to actually open the PR — that's a separate, explicit step the user requests on its own. Print the path of the file you wrote and a one-line note that it's ready to review/copy.
