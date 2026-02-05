## Office Add-in (local dev)

### Prereqs
- Run the backend API locally with `uv run dev.py`
- Run the frontend locally with `pnpm dev` from `frontend/`

### Start ngrok
1. Copy the `addin/ngrok.yaml` to a new file (for example, `addin/ngrok-dev.yaml`)
2. Change this new file adding your ngrok token
3. From `addin/`, run `ngrok start --config ngrok-dev.yaml --all`

### Prepare the manifest
1. Copy `addin/manifest-dev.xml` to a new file (for example, `addin/manifest-dev.local.xml`).
2. Replace `{NGROK_FRONTEND}` with the ngrok frontend URL on this new file.

### Add to Office
1. Open Word Web (https://word.cloud.microsoft/) and cerate a blank file.
2. Go to `Home` → `Add-ins` → `More Add-ins`.
2. Go to `My Add-ins`.
3. Choose `Manage My Add-in` → `Upload My Add-in`.
4. Select your updated manifest file.

### Notes
- Keep both the API and frontend running while testing.
- If the ngrok URL changes, update the manifest and re-upload it.
