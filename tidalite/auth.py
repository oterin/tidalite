# tidalite/auth.py

import asyncio
import time
from typing import Optional, Dict, Any

import httpx
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.align import Align
from rich import box # import box style directly

from . import config # <-- removed 'tui' import

console = Console()

async def get_device_code() -> Dict[str, Any]:
    """initiates the device flow and returns the device code response."""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{config.auth_url}/device_authorization",
            data={"client_id": config.client_id, "scope": "r_usr w_usr w_sub"},
        )
        response.raise_for_status()
        return response.json()

async def poll_for_token(device_code_info: Dict[str, Any]) -> Dict[str, Any]:
    """polls the token endpoint until the user authorizes the device."""
    device_code, interval, expires_in = (
        device_code_info["deviceCode"],
        device_code_info["interval"],
        device_code_info["expiresIn"],
    )
    start_time = time.time()

    while time.time() - start_time < expires_in:
        await asyncio.sleep(interval)
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{config.auth_url}/token",
                    auth=(config.client_id, config.client_secret),
                    data={
                        "client_id": config.client_id,
                        "device_code": device_code,
                        "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                        "scope": "r_usr w_usr w_sub",
                    },
                )
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 400 and e.response.json().get("error") == "authorization_pending":
                continue
            raise
    raise TimeoutError("device authorization timed out.")

def is_token_expired(creds: Dict[str, Any]) -> bool:
    """checks if the access token is expired."""
    return time.time() > creds.get("expires_at", 0)

async def refresh_token() -> Optional[Dict[str, Any]]:
    """refreshes an expired access token."""
    creds = config.get_auth_credentials()
    if not creds or "refresh_token" not in creds:
        return None

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{config.auth_url}/token",
                auth=(config.client_id, config.client_secret),
                data={
                    "client_id": config.client_id,
                    "refresh_token": creds["refresh_token"],
                    "grant_type": "refresh_token",
                    "scope": "r_usr w_usr w_sub",
                },
            )
            response.raise_for_status()
            new_creds = response.json()
            if "refresh_token" not in new_creds:
                new_creds["refresh_token"] = creds["refresh_token"]
            new_creds["expires_at"] = time.time() + new_creds["expires_in"]
            config.save_auth_credentials(new_creds)
            return new_creds
        except httpx.HTTPStatusError:
            config.save_auth_credentials({})
            return None

async def get_valid_credentials() -> Optional[Dict[str, Any]]:
    """gets credentials, refreshing the token if it's expired."""
    creds = config.get_auth_credentials()
    if not creds:
        return None
    
    if is_token_expired(creds):
        new_creds = await refresh_token()
        return new_creds
    return creds

async def run_auth_flow():
    """runs the full interactive device authentication flow."""
    console.clear()
    header_text = Text()
    # use generic styles instead of tui.theme
    header_text.append("tidalite", style="bold")
    header_text.append(" / ", style="dim")
    header_text.append("authentication", style="dim")
    console.print(Align.center(header_text))
    console.print(Align.center("" * 40, style="dim"))
    console.print()

    try:
        with console.status("  requesting device code...", spinner_style="dim"):
            device_code_info = await get_device_code()
        
        panel_content = Text(justify="center")
        panel_content.append("1. open a browser and go to:\n")
        panel_content.append(f"{device_code_info['verificationUriComplete']}\n\n", style="bold")
        panel_content.append("2. enter the following code:\n")
        panel_content.append(device_code_info['userCode'], style="bold")
        
        console.print(Align.center(Panel(panel_content, box=box.SIMPLE, border_style="dim")))

        with console.status("  waiting for authorization in browser...", spinner_style="dim"):
            creds = await poll_for_token(device_code_info)
        
        creds["expires_at"] = time.time() + creds["expires_in"]
        config.save_auth_credentials(creds)
        user_name = creds.get("user", {}).get("username", "unknown")
        console.print(f"\n  [bold][/bold] authentication successful. welcome, {user_name}.")
        await asyncio.sleep(2)

    except (TimeoutError, Exception) as e:
        console.print(f"\n  [bold][/bold] an error occurred: {e}")
