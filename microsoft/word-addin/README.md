# Word add-in

One of the Microsoft integrations — see [`../README.md`](../README.md) for how this
one differs from the Teams bot, and why only this path can change a document.

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

1. Copy `microsoft/word-addin/ngrok.yaml` to a new file (for example, `microsoft/word-addin/ngrok-dev.yaml`).
2. Update the new file with your ngrok token.
3. From `microsoft/word-addin/`, run `ngrok start --config ngrok-dev.yaml --all`.

#### Port Forward

Forward the ports 3000 and 8000 in VSCode/Cursor. Make sure they are public.

Use the generated public HTTPS URLs in the steps below.

### Prepare the manifest

1. Copy `microsoft/word-addin/manifest-template.xml` to a new file (for example, `microsoft/word-addin/manifest-dev.local.xml`).
2. Replace the placeholders:
   - `{FRONTEND_URL}`: your public frontend URL (the 3000 tunnel), with `https://`.
   - `{FRONTEND_HOST}`: the same host, without `https://`.
   - `{ENTRA_CLIENT_ID}`: the client id of the add-in's Entra app (see "Signing in" below).
   - Example: `sed -i "" -e "s|{FRONTEND_URL}|https://<host>|g" -e "s|{FRONTEND_HOST}|<host>|g" -e "s|{ENTRA_CLIENT_ID}|<client id>|g" microsoft/word-addin/manifest-dev.local.xml`

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
cp microsoft/word-addin/manifest-dev.local.xml ~/Library/Containers/com.microsoft.Word/Data/Documents/wef
```

Requires re-opening Word every time manifest changes.

## Preview in browser (without Word)

To work on the pane's layout, open `http://localhost:3000/addin` in a browser. Anything
that reads or writes the document needs Word.

## Publish the Word add-in in your organization

Official deployment guide:
https://learn.microsoft.com/en-us/microsoft-365/admin/manage/office-addins?view=o365-worldwide#upload-custom-office-add-ins-in-your-organization

In step 3, choose **Add-in only manifest** and provide the manifest URL.

Manifest URL from this repo: `https://raw.githubusercontent.com/agencyenterprise/draft-detective/refs/heads/dev/microsoft/word-addin/manifest.xml`

Reference video (older, but still useful): https://www.youtube.com/watch?v=p3aeO9muEI8&t=181s

## How the pane writes to the document

The pane reads a paragraph's markup with `getOoxml`, sends it to
`/api/microsoft/word/comments/annotate` or `/api/microsoft/word/suggestions/apply`, and
puts the result back with `insertOoxml` (`frontend/lib/addin/word-writes.ts`). The
backend writes the comment, or the `w:ins`/`w:del` of a tracked change, authored as
Draft Detective. See `frontend/lib/addin/apply-handoff.ts` and "From Teams to Word" in
[`../README.md`](../README.md) for how changes asked for in Teams get there.

Two things worth knowing:

- It has to be markup. Word's API attributes a comment to whoever is signed in, with
  no way to override it, and cannot create a tracked change at all.
- The pane switches the document's change tracking off around every write and
  restores it afterwards. Left on, Word records our write as a revision by the
  signed-in user, which wraps Draft Detective's suggestion inside the author's own.

## Signing in

The pane signs in as a Microsoft account, because changes asked for in Teams are
released only to the account that asked (matched by Entra object id, not email).

1. **Office single sign-on**, tried silently when the pane opens: Office hands over a
   token for the account signed in to Word, issued for the add-in's Entra app. The
   backend verifies it (`lib/api/addin_auth.py`).
2. **A dialog**, when single sign-on is not available: `/addin/sign-in` signs in with
   Draft Detective's own Microsoft sign-in and hands the session token back. Only a
   Microsoft sign-in works here; it is the one that carries the object id.

Both use one Entra app registration per environment: the same one as Draft Detective's
own "Sign in with Microsoft" (`AUTH_MICROSOFT_ENTRA_ID_ID`), with:

- **Expose an API**: Application ID URI `api://<frontend host>/<client id>`, a scope
  `access_as_user` (admins and users can consent), and the client application
  `ea5a67f6-b6f3-4338-b240-c655ddc3cc8e` (Microsoft Office) pre-authorized for it.
- **Manifest**: `requestedAccessTokenVersion` set to `2`.
- **Authentication**: Web redirect URI `https://<frontend host>/api/auth/callback/microsoft-entra-id`.
- **Token configuration**: optional claim `email` on the ID and access tokens.
- **API permissions**: Microsoft Graph delegated `openid`, `profile`, `email`,
  `offline_access`, `User.Read`, with admin consent.
- **Certificates & secrets**: a client secret, for the frontend.

Then set `AUTH_MICROSOFT_ENTRA_ID_ID`, `AUTH_MICROSOFT_ENTRA_ID_SECRET` and
`AUTH_MICROSOFT_ENTRA_ID_ISSUER` (`https://login.microsoftonline.com/<tenant id>/v2.0`) in
**both** the frontend and the backend. All three are required: a deployment that does not
sign its users in with Microsoft has no add-in sign-in. A tenant-specific issuer means only
that tenant's accounts are accepted. The manifest's `WebApplicationInfo` names the
same client id and Application ID URI. The URI contains the frontend host, so a tunnel
whose URL changes needs the app, the manifest and the redirect URI updated with it.
