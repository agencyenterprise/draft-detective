# Microsoft integrations

Draft Detective reaches into Microsoft 365 from more than one direction, and the
directions are not interchangeable. Each subdirectory here is one of them, and this
file exists to say which one you want before you open it.

| Directory                        | Surface           | Can it change a document? |
| -------------------------------- | ----------------- | ------------------------- |
| [`word-addin/`](word-addin/)     | Word task pane    | Yes                       |
| [`teams-app/`](teams-app/)       | Teams bot         | No — answers in chat      |

## What decides the split

**Only a Word client can write to a document someone is editing.** SharePoint refuses
a whole-file write with `423 Locked` while the document is open, whatever identity
asks — which was verified rather than assumed.
So anything that adds a comment or a tracked change has to run inside Word, through
the add-in. Everything that only needs to *read* can run on the server.

That single fact is why there are two integrations rather than one, and it is worth
knowing before proposing a feature: "reply in the margin" and "answer in chat" are
not two renderings of the same capability.

## Word add-in

The task pane, loaded from the frontend at `/addin`. Draft Detective replies to a
comment thread that mentions it, and can additionally leave comments elsewhere in the
document or offer tracked changes the author accepts or rejects.

The add-in hands the backend the document's markup, because it is the only party that
can see a document mid-edit. Backend routes live under `/api/microsoft/word`.

See [`word-addin/README.md`](word-addin/README.md) for local development: tunnelling,
manifest sideloading, and the standalone comment-watcher harness.

## Teams app

A bot with its own identity, mentioned in a channel or a chat. It answers questions
about a document and writes nothing to it, which is the whole point of this path: no
write means no lock to fight and no Word client to automate.

The document is not configured — someone links to it in the message. **A link is the
only way in.** Looking a document up by name was built and removed: matching names
means searching somewhere, and anything the service can search is wider than what the
person asking may be allowed to read, whereas a link is something they already had.

The backend loads the document itself here, always as the person who asked: it holds a
delegated token for them, obtained through the OAuth connection named by
`TEAMS_USER_AUTH_CONNECTION`, so it can reach nothing they could not. Each person signs
in once, from wherever they first ask — the bot replies with a sign-in card that works in
channels too. One click, once, and never again.

`GRAPH_ALLOWED_HOSTS` and `GRAPH_ALLOWED_SITE_PATHS` narrow it further and fail closed:
unset means nothing is readable. They decide which sites the bot may be pointed at at
all, on top of what each user can open.

Worth knowing that gating the read does not gate the audience: the answer goes into the
channel the question came from, visible to everyone there regardless of who can open
the document.

See [`teams-app/build_package.py`](teams-app/build_package.py) for the manifest and
how the installable package is built. Backend routes live under
`/api/microsoft/teams`.
