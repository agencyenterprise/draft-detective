"""Run LibreOffice so it never fetches what a document links to.

A Word file can link an image instead of embedding it: the relationship names a
URL (``http://...``, ``file:///...``). LibreOffice follows such links while it
converts. Importing a Word 97 ``.doc`` sends ``OPTIONS``, ``HEAD`` and ``GET`` to
the URL, and exporting to PDF draws a ``file://`` image into the output. The
documents are uploaded by users, so a link would make the server request any
address it can reach, internal services included, or read an image off its own
disk into a rendering the uploader sees.

Every ``soffice`` run already gets a private profile (concurrent instances sharing
one exit 0 without writing their output). ``locked_down_profile`` seeds it with:

- ``BlockUntrustedRefererLinks``: links from a document outside a trusted location
  are not loaded, and no location is trusted. This stops the ``GET`` and the
  ``file://`` read, but not the ``OPTIONS`` and ``HEAD`` LibreOffice sends first.
- A manual HTTP and HTTPS proxy at a host that cannot resolve (``.invalid`` is
  reserved for that, RFC 6761), with no exceptions, so every request LibreOffice
  makes itself fails before it leaves the machine.

LibreOffice still honours ``NO_PROXY`` from the environment, which a deploy may set
to exactly its internal ranges, so ``soffice_env`` drops every proxy variable.

LibreOffice needs no network to convert: embedded images, charts and metafiles are
part of the file and still render.
"""

import os
from pathlib import Path

_UNREACHABLE_PROXY = "proxy.invalid"

_REGISTRY = f"""\
<?xml version="1.0" encoding="UTF-8"?>
<oor:items xmlns:oor="http://openoffice.org/2001/registry" \
xmlns:xs="http://www.w3.org/2001/XMLSchema" \
xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
<item oor:path="/org.openoffice.Office.Common/Security/Scripting">\
<prop oor:name="BlockUntrustedRefererLinks" oor:op="fuse"><value>true</value></prop>\
</item>
<item oor:path="/org.openoffice.Inet/Settings">\
<prop oor:name="ooInetProxyType" oor:op="fuse"><value>2</value></prop>\
</item>
<item oor:path="/org.openoffice.Inet/Settings">\
<prop oor:name="ooInetHTTPProxyName" oor:op="fuse"><value>{_UNREACHABLE_PROXY}</value></prop>\
</item>
<item oor:path="/org.openoffice.Inet/Settings">\
<prop oor:name="ooInetHTTPProxyPort" oor:op="fuse"><value>9</value></prop>\
</item>
<item oor:path="/org.openoffice.Inet/Settings">\
<prop oor:name="ooInetHTTPSProxyName" oor:op="fuse"><value>{_UNREACHABLE_PROXY}</value></prop>\
</item>
<item oor:path="/org.openoffice.Inet/Settings">\
<prop oor:name="ooInetHTTPSProxyPort" oor:op="fuse"><value>9</value></prop>\
</item>
<item oor:path="/org.openoffice.Inet/Settings">\
<prop oor:name="ooInetNoProxy" oor:op="fuse"><value></value></prop>\
</item>
</oor:items>
"""


def locked_down_profile(profile_dir: Path) -> str:
    """Seed ``profile_dir`` and return the ``soffice`` argument that selects it.

    The directory may exist already; LibreOffice fills in the rest on first use.
    """

    user_dir = profile_dir / "user"
    user_dir.mkdir(parents=True, exist_ok=True)
    (user_dir / "registrymodifications.xcu").write_text(_REGISTRY, encoding="utf-8")
    return f"-env:UserInstallation={profile_dir.as_uri()}"


def soffice_env() -> dict[str, str]:
    """This process's environment without its proxy settings, for ``soffice``."""

    return {
        name: value
        for name, value in os.environ.items()
        if not name.lower().endswith("_proxy")
    }
