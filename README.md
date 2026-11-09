# Naukri Career MCP

A local MCP server for Naukri profile review, job search, application tracking, and resume assistance. It uses Playwright with a persistent browser profile and SQLite stored on the user's machine.

This is an independent community project. It is not affiliated with or endorsed by Naukri or DeepSeek. Naukri may change its website, restrict automation, or require CAPTCHA/manual interaction; selectors and login checks can stop working without notice.

## Features

- Read and audit profile details
- Search jobs and inspect job descriptions
- Match jobs against a locally supplied resume
- Track applications locally
- Draft profile improvements, resumes, and cover letters
- Apply profile changes only through explicit confirmation tools

## Requirements

- Python 3.10 or newer
- Playwright Chromium
- An MCP-compatible client (for example, DeepSeek Harness)

## Install

```powershell
git clone https://github.com/Auchit-Sawai/naukri-career-mcp.git naukri-career-mcp
cd naukri-career-mcp/python
py -m venv .venv
.\.venv\Scripts\Activate.ps1
py -m pip install -e .
playwright install chromium
```

On macOS/Linux, activate `.venv` with `source .venv/bin/activate` and use `python` in place of `py`.

## Configure the MCP client

Add a stdio MCP server entry to your client's configuration. Use absolute paths appropriate for your computer:

```json
{
  "mcpServers": {
    "naukri-career": {
      "command": "<absolute-path-to-venv-python>",
      "args": ["-m", "naukri_mcp.server"],
      "cwd": "<absolute-path-to-this-repository>/python"
    }
  }
}
```

For DeepSeek Harness, install the repository as a local package or add its MCP client entry to your own profile. Keep that profile and its paths local; do not copy machine-specific settings from someone else's setup.

The server optionally reads `python/naukri_mcp_config.json`. Start from `naukri_mcp_config.json.example` and set a private browser profile directory. The default browser profile is under the current user's home directory. Never share the browser profile, cookies, database, or config containing private paths.

Example `python/naukri_mcp_config.json`:

```json
{
  "database_path": "naukri_career.db",
  "headless": false,
  "browser_profile_dir": "<private-path-on-your-computer>/naukri-browser-profile"
}
```

## Login and first checks

Start with `naukri_check_session`. If you need to sign in, use the visible browser login flow and complete any CAPTCHA or verification yourself. Do not send your password to an AI model or store it in this repository. Then try read-only `naukri_get_profile` and `naukri_search_jobs`.

Phone login: `naukri_login_with_otp` takes only your 10-digit phone number, asks Naukri to send the OTP, and waits up to 2 minutes for you to type the OTP in the visible browser (set `headless` to `false`). The OTP never passes through the AI model.

If searches return "Cloudflare challenge", run with `headless` set to `false`; a visible browser is blocked far less often.

Some Naukri pages may return access-denied responses or load incompletely in automation. Treat errors as inconclusive; do not bypass CAPTCHA or access controls.

## Privacy and safety

- Browser cookies, profile data, resume files, application history, and database remain local by default.
- Do not commit credentials, browser profiles, SQLite databases, resumes, exports, or logs.
- Review generated text before using it.
- Profile edits and job applications affect your account; inspect each proposed action and explicitly authorize it.
- Use the automation only in ways permitted by Naukri's current terms and applicable law.

## Tools

The server provides tools for profile audit/read/proposals, job search/details/matching, application tracking, resume parsing/tailoring, cover letters, login/session checks, and local data export. Tool names and inputs are defined in `python/naukri_mcp/server.py`.

## Development

Run the server directly from the `python` folder:

```powershell
py -m naukri_mcp.server
```

MCP stdio protocol messages use standard output; diagnostics are written to standard error and `naukri_mcp.log`.

## License

MIT. See `LICENSE`.

