# Commit Message Guidelines

## Format
<gitmoji> <type>(<scope>): <subject>

<BLANK LINE>
<body>
<BLANK LINE>
<footer>

## Rules

### 1. SUBJECT LINE (REQUIRED)
- Keep under 72 characters
- Use imperative mood ("Add feature" not "Added feature" or "Adds feature")
- No period at the end
- Capitalize first letter

### 2. GITMOJI (OPTIONAL BUT RECOMMENDED)
- Use one relevant gitmoji at the beginning
- See common examples below

### 3. TYPE (REQUIRED)
- feat: New feature
- fix: Bug fix
- docs: Documentation changes
- style: Code formatting (no logic change)
- refactor: Code restructuring (no behavior change)
- enhance: Code enhancement (no or almost no behavior change)
- perf: Performance improvement
- test: Adding/fixing tests
- chore: Maintenance tasks (deps, config, etc.)
- ci: CI/CD pipeline changes
- build: Build system changes

### 4. SCOPE (OPTIONAL)
- Specify affected component/module in lowercase
- Examples: (auth), (api), (ui), (database)

### 5. BODY (OPTIONAL)
- Explain WHAT and WHY (not HOW)
- Use bullet points with "-" for multiple items
- Wrap at 72 characters

### 6. FOOTER (OPTIONAL)
- Reference issues: "Closes #123" or "Fixes #456"
- Breaking changes: "BREAKING CHANGE: <description>"

## Common Gitmoji Examples

✨ feat: Introduce new features
🐛 fix: Fix a bug
📚 docs: Add or update documentation
💄 style: Improve formatting, styling
♻️ refactor: Refactor code structure
⚡️ perf: Improve performance
✅ test: Add or update tests
🔧 chore: Maintenance tasks
🚀 deploy: Deploy stuff
👷 ci: CI/CD changes
📦 build: Packaging changes
⏪ revert: Revert changes
🧪 experimental: Experimental features
🧑‍💻 instructions: Improve instruction files like e.g., AGENTS.md for coding agent

## Good Examples

✨ feat(auth): implement password reset functionality

🐛 fix(api): handle null values in user profile endpoint

📚 docs(readme): add installation instructions

♻️ refactor(ui): extract modal component to separate file

⚡️ perf(database): optimize query for user search

✅ test(auth): add unit tests for login validation

## Bad Examples (DON'T DO THIS)

❌ "fixed bug" (no gitmoji, no type, vague)
❌ "✨ Fixed the login issue that was breaking everything!!!" (not imperative, too long, multiple !)
❌ "feat: add new stuff" (vague, no scope)
❌ "✨ feat(ui): Fixed button styling." (not imperative, has period)

## Pro Tips

- One commit = one logical change
- If you can't summarize it concisely, consider splitting into multiple commits
- When in doubt, ask: "What changed and why?"