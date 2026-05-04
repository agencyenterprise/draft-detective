from fastmcp import FastMCP
from mcp.server.fastmcp import Icon

from lib.api.mcp_auth import create_mcp_auth
from lib.config.env import config as env_config

mcp_auth = create_mcp_auth()
mcp = FastMCP(
    "AI Reviewer / Draft Detective",
    auth=mcp_auth,
    website_url=env_config.FRONTEND_URL,
    icons=[Icon(src=env_config.FRONTEND_URL + "/icon.svg")],
)
