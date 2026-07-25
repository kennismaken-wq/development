# develop-tool

Floris's new HandigerAI tool. Isolated dev environment, deploys independently
from the Outreach dashboard — see `CONTEXT.md` for the required "glassy"
lay-out before building any UI.

## Live

`http://develop.handigerai.nl` (HTTPS pending DNS — see below).

## Deploy

Push to `main` → GitHub Actions (`.github/workflows/deploy.yml`) SSHes into
the VPS as the `develop` user (scoped: own directory only, no access to the
Outreach app, no root — restart of `develop-tool.service` only via a narrow
sudoers rule) and restarts the service.

## Local dev

```
python3 -m venv .venv
./.venv/bin/pip install -r requirements.txt
./.venv/bin/python app.py
```
Runs on `:5001`.

## VPS layout

- Path: `/srv/handigerai/develop-tool`
- Linux user: `develop`
- systemd service: `develop-tool.service`
- nginx: proxies `develop.handigerai.nl` → `127.0.0.1:5001`

_Last verified deploy: trigger test._
