# Teams app (bot)

Draft Detective as a bot: mention it in a channel or a chat with a question about a
Word document, and it answers there. It reads the document from SharePoint as the
person who asked and never writes to it — see [`../README.md`](../README.md) for why
that division exists.

Setting this up means creating **three** things in Azure, which is the part that
surprises people:

| What                                     | Why                                                          |
| ---------------------------------------- | ------------------------------------------------------------ |
| An **Azure Bot** resource                | Gives Teams somewhere to deliver messages, and an identity   |
| An **app registration** for Graph        | Signs each user in, so documents are read with their access  |
| A **Teams app package** (this directory) | Installs the bot in the tenant                               |

The bot's identity and the Graph registration are deliberately separate. They have
different purposes, different secrets to rotate, and different blast radii if one
leaks: the bot credential lets someone impersonate the bot, while the Graph
registration is what users sign in to.

---

## 1. The Azure Bot resource

→ [**Azure Bot resources**](https://portal.azure.com/#browse/Microsoft.BotService%2FbotServices)
in the Azure portal.

1. Select **+ Create** and choose the **Azure Bot** resource type.
2. Choose **Multi-tenant** or **Single-tenant**. Whichever you pick has to match
   `TEAMS_BOT_TENANT_ID` below — set it for single-tenant, leave it unset for
   multi-tenant. Mismatched, tokens are issued for the wrong authority and every
   request fails validation.
3. Let it create a new Microsoft App ID, or point it at an existing registration.
   That App ID is `TEAMS_BOT_APP_ID`.
4. Under **Configuration**, set the **Messaging endpoint** to your public HTTPS URL
   plus the bot's path:

   ```
   https://<your-host>/api/microsoft/teams/messages
   ```

5. Under **Channels**, add **Microsoft Teams**. This is easy to miss and the failure
   is unhelpful: uploading the app package reports **"Invalid Bot"** with no mention
   of channels.
6. Under the registration's **Certificates & secrets**, create a client secret. That
   value is `TEAMS_BOT_APP_PASSWORD`, and it is shown once.

## 2. Signing users in

The bot reads every document as the person who asked, with a delegated token for them,
so Graph refuses anything they could not open themselves. Each person signs in once,
from wherever they first ask — a channel, a group chat or a 1:1 chat — and never again.

### The Graph app registration

→ [**App registrations**](https://portal.azure.com/#view/Microsoft_AAD_RegisteredApps/ApplicationsListBlade)
in Microsoft Entra ID.

1. Select **New registration** and give it a name.
2. Add the **Web** redirect URI `https://token.botframework.com/.auth/web/redirect`.
3. Under **API permissions**, add the Microsoft Graph **delegated** permission
   **`Files.Read.All`**, then **grant admin consent**. Without consent each person also
   sees Entra's consent screen the first time they sign in.
4. Create a client secret.

### The OAuth connection

→ your bot under [**Azure Bot resources**](https://portal.azure.com/#browse/Microsoft.BotService%2FbotServices).

1. Go to **Configuration → Add OAuth Connection Settings**.
2. Name it (for example `graph-user`) and choose the **Azure Active Directory v2**
   service provider.
3. Give it the client id, secret and tenant id of the Graph registration above, and put
   `Files.Read.All` in **Scopes**. **Leave Token Exchange URL blank** — it is only for
   silent SSO, which this setup does not use. The registration's secret lives here, in
   Azure, not in this service's environment.
4. Select **Test Connection**. It signs you in with the connection on its own, before
   any code runs, so a tenant policy that blocks it shows up here first.
5. Set `TEAMS_USER_AUTH_CONNECTION` to the connection's name. The bot refuses to start
   without it.

What the user experiences: nothing, once signed in. If there is no token, the bot
parks the question and replies with a card asking them to sign in. Pressing **Sign in**
opens the Entra sign-in window; once it closes the card says they are signed in and the
answer follows in the thread — no need to ask again. The refresh token is held by the
Bot Framework token service; this service never stores it.

### Signing in where the question was asked

The Bot Framework's usual sign-in card, the `OAuthCard`, only works in a 1:1 chat.
Pressed in a channel it fails with a misleading "this action can't be performed since
the app does not exist or has been uninstalled":

> OAuth isn't supported in the group chat or channel scopes directly.
>
> — [Teams bot authentication](https://learn.microsoft.com/en-us/microsoftteams/platform/bots/how-to/authentication/add-authentication)

So the bot does not use it. It posts an Adaptive Card whose button is an
`Action.Execute`, the one route Teams documents for signing in inside a group chat or
channel ([Universal Actions authentication](https://learn.microsoft.com/en-us/microsoftteams/platform/task-modules-and-cards/cards/universal-actions-for-adaptive-cards/authentication-flow-in-universal-action-for-adaptive-cards)).
When the button's action reaches the bot without a token, the bot answers with a
`loginRequest`, and Teams opens the sign-in window right there. After sign-in Teams
sends the action again with a code, the token service turns it into the user's token,
and the parked question is answered. The code is in
`lib/services/microsoft/teams/sign_in.py`.

Only the person who asked can release their question. Anyone in the channel can press
the button, and they are told the sign-in is someone else's — the answer is never read
with the presser's access.

**`validDomains` must contain `token.botframework.com`** or sign-in cannot work in any
scope, with the same misleading error. `build_package.py` sets it; the comment there
explains why it is not empty despite this app having no tabs.

### Where the sign-in state lives

Sign-in spans several requests — the message that posts the card, and the card actions
that follow — so the parked question cannot live in process memory. Production runs
Uvicorn with `--workers 4`, so those requests usually land on different processes and
an in-memory store would usually lose the parked question. A single-process dev server
never shows this.

It is kept in the `microsoft_teams_signin_state` table instead, which any server running
current migrations already has. A row is written when the card is posted and removed
when the question is answered; one nobody finishes is swept an hour later, because the
parked message is in there.

No tokens are stored — the refresh token stays in the Bot Framework token service. Only
the question waiting to be answered, and where to answer it.

### Why there is a click at all

Teams SSO replaces the click with a silent token exchange, but it needs an Application
ID URI, an exposed scope and the Teams client ids pre-authorised on the registration,
and bot SSO does not work in channels at all. It would save one click, once per person,
for a permanent increase in setup complexity.

### Things to know before relying on it

- **Conditional Access may refuse.** Sign-in happens in the user's own browser, so
  device-based policies are evaluated there, but a tenant can still block the
  registration (`AADSTS530035` is the usual one). **Test Connection** settles it before
  any code runs; if it is refused, an admin can scope an exclusion for this app.
- **This gates the read, not the audience.** The answer is posted into the channel the
  question came from, so everyone there sees the document's contents whether or not
  they can open the file. If that matters, restrict which channels the bot is in.

## 3. Environment

```bash
# The bot's identity
TEAMS_BOT_APP_ID=00000000-0000-0000-0000-000000000000
TEAMS_BOT_APP_PASSWORD=<client secret>
TEAMS_BOT_TENANT_ID=<tenant id, single-tenant bots only>

# Required. The OAuth connection users sign in with (section 2).
TEAMS_USER_AUTH_CONNECTION=graph-user
```

## 4. Build and install the app package

```bash
uv run python microsoft/teams-app/build_package.py
```

This writes `draft-detective-teams.zip` next to the script — generated rather than
committed, because the manifest carries your tenant's ids.

→ [**Teams**](https://teams.microsoft.com/), then:

**Apps → Manage your apps → Upload a custom app** (`Fazer upload de um aplicativo
personalizado`). The tenant has to permit custom app uploads; if the option is absent,
that policy is why.

### Updating an installed app

Teams identifies an app by the `id` in its manifest, so re-uploading the same id is
refused with **"This app has already been submitted in your org"**. To change an
installed app:

→ [**Teams admin centre → Manage apps**](https://admin.teams.microsoft.com/policies/manage-apps).

1. Raise the version: `uv run python microsoft/teams-app/build_package.py 1.0.2`
2. Find the app there and use its update action — not _Manage your apps_ in the Teams
   client, where the only actions offered are _View details_ and _Copy link_.

Two ids are easy to confuse, and the admin centre shows the wrong one first:

- **External app ID** (`ID do aplicativo externo`) — this is `manifest.id`, and the
  one that must match on an update.
- **App ID** (`ID do Aplicativo`) — Teams' own catalog id, read-only. Putting it in
  the manifest fails with a bare _"cannot upload the app, try again"_.

If a catalog entry is in the way and removing it is more trouble than it is worth,
`--new-app-id` mints a fresh id and installs a second app alongside the old one.

## 5. Local development

Teams delivers messages over the public internet, so the backend needs a public HTTPS
URL even for local work. Any tunnel does — VS Code dev tunnels and ngrok both work:

```bash
uv run dev.py                                    # the backend on :8000
# then expose :8000 and use the resulting host
```

Put the tunnel host in the **Messaging endpoint** of your bot under
[Azure Bot resources](https://portal.azure.com/#browse/Microsoft.BotService%2FbotServices)
(step 1.4). The host
changes each time the tunnel restarts unless it is a reserved one, and a stale
endpoint fails silently from the Teams side — the message simply never arrives.

Watch the log for what the bot resolved:

```
Teams bot question from Carlos Bonetti: 'check the abbreviations' (document: https://...)
resolved https://...:w:/s/... to https://.../sites/YourSite/DD Test/v3-CERN.docx
```
