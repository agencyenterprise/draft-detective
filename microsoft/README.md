# Microsoft integrations

Draft Detective reaches into Microsoft 365 from more than one direction, and the
directions are not interchangeable. Each subdirectory here is one of them, and this
file exists to say which one you want before you open it.

| Directory                        | Surface           | Can it change a document? |
| -------------------------------- | ----------------- | ------------------------- |
| [`word-addin/`](word-addin/)     | Word task pane    | Yes                       |
| [`teams-app/`](teams-app/)       | Teams bot         | Only through the add-in   |

## What decides the split

**Only a Word client can write to a document someone is editing.** SharePoint refuses
a whole-file write with `423 Locked` while the document is open, whatever identity
asks — which was verified rather than assumed.
So anything that adds a comment or a tracked change has to run inside Word, through
the add-in. Everything that only needs to *read* can run on the server.

That single fact is why there are two integrations rather than one, and it is worth
knowing before proposing a feature: "write in the margin" and "answer in chat" are
not two renderings of the same capability.

It was probed again on 2026-10-08, writing as the same account that had the document
open: an idle Word for the web tab and a View Only Word desktop session both got 423.
Closing the web tab released the lock within seconds; quitting Word desktop did not
release it for more than nine minutes. So "write when nobody has it open" is not a
plan either.

## From Teams to Word

When someone asks the bot for comments or tracked changes, it cannot write them, so it
hands them to the add-in. The bot stores what it would add, keyed by the document and
by who asked (`lib/services/microsoft/word/handoffs.py`), and says so in the thread.
When that person opens the document in Word, the task pane signs them in as their
Microsoft account (Office single sign-on, or a dialog when that is unavailable), finds
the handoffs released to that same account -- matched by Entra object id, never by
email -- and applies one on **Apply**; the result is posted
back into the Teams thread. Items are placed by quote, so anything whose words have
since changed is reported rather than misplaced. Routes live under
`/api/microsoft/word/handoffs`.

## Word add-in

The task pane, loaded from the frontend at `/addin`. It writes Draft Detective's
comments, and tracked changes the author accepts or rejects, into the open document;
today those are the changes asked for in Teams (above).

The add-in hands the backend the document's markup, because it is the only party that
can see a document mid-edit. Backend routes live under `/api/microsoft/word`.

See [`word-addin/README.md`](word-addin/README.md) for local development: tunnelling,
and manifest sideloading.

## Teams app

A bot with its own identity, mentioned in a channel or a chat. It answers questions
about a document and writes nothing to it: no write means no lock to fight and no Word
client to automate. Asked for changes, it hands them to the add-in (above).

The document is not configured — someone links to it in the message. **A link is the
only way in.** Looking a document up by name was built and removed: matching names
means searching somewhere, and anything the service can search is wider than what the
person asking may be allowed to read, whereas a link is something they already had.

The backend loads the document itself here, always as the person who asked: it holds a
delegated token for them, obtained through the OAuth connection named by
`TEAMS_USER_AUTH_CONNECTION`, so it can reach nothing they could not. Each person signs
in once, from wherever they first ask — the bot replies with a sign-in card that works in
channels too. One click, once, and never again.

Worth knowing that gating the read does not gate the audience: the answer goes into the
channel the question came from, visible to everyone there regardless of who can open
the document.

See [`teams-app/build_package.py`](teams-app/build_package.py) for the manifest and
how the installable package is built. Backend routes live under
`/api/microsoft/teams`.

## Setting it up in your own Microsoft 365 tenant

Everything an organisation needs to run both integrations against its own deployment,
in order. The linked READMEs have the detail for each step; this is the checklist.

**You will need:** a tenant administrator (to register apps and grant admin consent), a
Teams administrator (to allow and install a custom app), an Azure subscription (for the
Azure Bot resource), and the public HTTPS addresses of your deployment's frontend
(`<frontend>`) and API (`<api>`).

### 1. The Teams bot

Follow [`teams-app/README.md`](teams-app/README.md), sections 1 to 4:

1. **Azure Bot resource** with a Microsoft App ID and client secret. Messaging endpoint:
   `https://<api>/api/microsoft/teams/messages`. Add the **Microsoft Teams** channel.
2. **Graph app registration** for signing users in: Web redirect URI
   `https://token.botframework.com/.auth/web/redirect`, delegated `Files.Read.All` with
   admin consent, a client secret.
3. **OAuth connection** on the bot (Azure Active Directory v2) using that registration,
   scope `Files.Read.All`. Note its name.
4. **Build and install the Teams package**: `uv run python microsoft/teams-app/build_package.py`,
   then upload it in Teams (custom app uploads must be allowed by policy).

### 2. The Word add-in's Entra app

Follow "Signing in" in [`word-addin/README.md`](word-addin/README.md). The add-in signs
in with **the same app registration as Draft Detective's own "Sign in with Microsoft"**
(the one `AUTH_MICROSOFT_ENTRA_ID_ID` names). If you already have that app, add the
settings below to it; otherwise register one with all of them:

- **Expose an API**: Application ID URI `api://<frontend>/<client id>`, scope
  `access_as_user`, and client application `ea5a67f6-b6f3-4338-b240-c655ddc3cc8e`
  (Microsoft Office) pre-authorized for it.
- **Manifest**: `requestedAccessTokenVersion` = `2`.
- **Authentication**: Web redirect URI `https://<frontend>/api/auth/callback/microsoft-entra-id`.
- **Token configuration**: optional claim `email`, on ID and access tokens.
- **API permissions**: Microsoft Graph delegated `openid`, `profile`, `email`,
  `offline_access`, `User.Read`, with admin consent.
- **Certificates & secrets**: a client secret (the frontend's sign-in needs it).

Register it as single-tenant (**Accounts in this organizational directory only**)
unless people from other tenants will use the add-in.

### 3. The Word add-in manifest

1. Copy `word-addin/manifest-template.xml` and replace `{FRONTEND_URL}`
   (`https://<frontend>`), `{FRONTEND_HOST}` (`<frontend>`) and `{ENTRA_CLIENT_ID}` (the
   app from step 2). Give it a new `<Id>` (any GUID) so it does not collide with ours.
2. Publish it to your users from the Microsoft 365 admin centre: **Settings →
   Integrated apps → Upload custom apps → Office Add-in**, and assign it to users or
   groups. (See "Publish the Word add-in in your organization" in
   [`word-addin/README.md`](word-addin/README.md).)

### 4. Configuration

Backend:

| Variable | Value |
|---|---|
| `TEAMS_BOT_APP_ID` | The Azure Bot's Microsoft App ID (step 1.1) |
| `TEAMS_BOT_APP_PASSWORD` | Its client secret |
| `TEAMS_BOT_TENANT_ID` | Your tenant id, for a single-tenant bot; leave unset for a multi-tenant one |
| `TEAMS_USER_AUTH_CONNECTION` | The OAuth connection's name (step 1.3) |

Backend **and** frontend: Draft Detective's "Sign in with Microsoft", which the add-in
signs in with too (already set if the UI signs in with Microsoft). All three are required
for the add-in to sign anyone in.

| Variable | Value |
|---|---|
| `AUTH_MICROSOFT_ENTRA_ID_ID` | The sign-in app's client id (step 2) |
| `AUTH_MICROSOFT_ENTRA_ID_SECRET` | Its client secret |
| `AUTH_MICROSOFT_ENTRA_ID_ISSUER` | `https://login.microsoftonline.com/<tenant id>/v2.0`: only your tenant's accounts are accepted |

On the backend, these also make the MCP server sign people in with Microsoft when Google
(`AUTH_GOOGLE_ID`, `AUTH_GOOGLE_SECRET`) is not configured.

### 5. Database and network

- Run `uv run alembic upgrade head`. It creates the tables both integrations use
  (`microsoft_teams_signin_state`, `microsoft_word_handoffs`).
- The backend must accept inbound HTTPS from the Bot Framework on
  `/api/microsoft/teams/messages`, and reach `login.microsoftonline.com` (token signing
  keys), `graph.microsoft.com`, `api.botframework.com` / `token.botframework.com`, and
  the Teams service URLs (`*.trafficmanager.net`) outbound.

### 6. Check it works

1. In Teams, message the bot with a question and a SharePoint link. It asks you to sign
   in once, then answers.
2. Ask it for comments or fixes on a document. It replies that they will be applied in
   Word.
3. Open that document in Word with the add-in. The pane signs you in (usually without a
   click), shows the suggestions, and **Apply** writes them in as Draft Detective.
4. The Teams thread gets an "Applied to … in Word" message.
