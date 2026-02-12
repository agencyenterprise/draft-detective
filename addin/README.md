## Office Add-in (local dev)

### Prereqs

- Run the backend API locally with `uv run dev.py`
- Run the frontend locally with `pnpm dev` from `frontend/`

### Expose local apps (tunnel)

You need public HTTPS URLs for:

- frontend (`localhost:3000`)
- API (`localhost:8000`)

Use any tunnel provider. Two common options:

#### Ngrok

1. Copy `addin/ngrok.yaml` to a new file (for example, `addin/ngrok-dev.yaml`).
2. Update the new file with your ngrok token.
3. From `addin/`, run `ngrok start --config ngrok-dev.yaml --all`.

#### Port Forward

Forward the ports 3000 and 8000 in VSCode/Cursor. Make sure they are public.

Use the generated public HTTPS URLs in the steps below.

### Prepare the manifest

1. Copy `addin/manifest-template.xml` to a new file (for example, `addin/manifest-dev.local.xml`).
2. Replace `{FRONTEND_URL}` with your public frontend URL (the 3000 tunnel).
   - Example: `sed -i "" "s|{FRONTEND_URL}|https://<your-frontend-url>|g" addin/manifest-dev.local.xml`

### Frontend API URL

- Set `NEXT_PUBLIC_API_URL` in `frontend/.env` to your public API URL (the 8000 tunnel).

### Add to Office

1. Open Word Web (https://word.cloud.microsoft/) and create a blank file.
2. Go to `Home` → `Add-ins` → `More Add-ins`.
3. Go to `My Add-ins`.
4. Choose `Manage My Add-in` → `Upload My Add-in`.
5. Select your updated manifest file.

### Notes

- Keep both the API and frontend running while testing.
- If your tunnel URLs change, update the manifest and `.env`, then reload/re-upload the add-in.

## Sideload Office Add-ins on Mac for testing

To test the add-in locally on MacOS, inside installed word (Microsoft 365):

https://learn.microsoft.com/en-us/office/dev/add-ins/testing/sideload-an-office-add-in-on-mac

```bash
cp addin/manifest-dev.local.xml ~/Library/Containers/com.microsoft.Word/Data/Documents/wef
```

Requires re-opening Word every time manifest changes.

## Preview in browser (without Word)

To speed up development, you can preview the add-in sidebar directly in the browser.

1. Remove the Office script import from `frontend/app/addin/layout.tsx`.
2. Open `http://localhost:3000/addin?token=SHARE_TOKEN`, replacing SHARE_TOKEN by the project shared token.

Limitations: paragraph-related features do not work (for example, paragraph filtering and jump to paragraph).

## Publish the Word add-in in your organization

Official deployment guide:
https://learn.microsoft.com/en-us/microsoft-365/admin/manage/office-addins?view=o365-worldwide#upload-custom-office-add-ins-in-your-organization

In step 3, choose **Add-in only manifest** and provide the manifest URL.

Manifest URL from this repo: `https://raw.githubusercontent.com/agencyenterprise/ai-reviewer/refs/heads/dev/addin/manifest.xml`

Reference video (older, but still useful): https://www.youtube.com/watch?v=p3aeO9muEI8&t=181s
