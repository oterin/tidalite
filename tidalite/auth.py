# tidalite/auth.py

import asyncio
import time
from typing import Optional, Dict, Any

import httpx
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.align import Align
from rich import box

from . import config
from .models import Credentials

console = Console()

async def get_device_code() -> Dict[str, Any]:
    """Initiates the device flow and returns the device code response."""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{config.auth_url}/device_authorization",
            data={"client_id": config.client_id, "scope": "r_usr w_usr w_sub"},
        )
        response.raise_for_status()
        return response.json()

async def poll_for_token(device_code_info: Dict[str, Any]) -> Optional[Credentials]:
    """Polls the token endpoint until the user authorizes the device."""
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
                creds_data = response.json()
                creds_data["expires_at"] = time.time() + creds_data["expires_in"]
                return Credentials(**creds_data)
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 400 and e.response.json().get("error") == "authorization_pending":
                continue
            raise
    raise TimeoutError("Device authorization timed out.")

async def refresh_token(refresh_token: str) -> Optional[Credentials]:
    """Refreshes an expired access token."""
    if not refresh_token:
        return None

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{config.auth_url}/token",
                auth=(config.client_id, config.client_secret),
                data={
                    "client_id": config.client_id,
                    "refresh_token": refresh_token,
                    "grant_type": "refresh_token",
                    "scope": "r_usr w_usr w_sub",
                },
            )
            response.raise_for_status()
            new_creds_data = response.json()
            if "refresh_token" not in new_creds_data:
                new_creds_data["refresh_token"] = refresh_token
            new_creds_data["expires_at"] = time.time() + new_creds_data["expires_in"]
            return Credentials(**new_creds_data)
        except httpx.HTTPStatusError:
            return None

async def authenticate() -> Optional[Credentials]:
    """Runs the full interactive device authentication flow."""
    console.clear()
    header_text = Text()
    header_text.append("tidalite", style="bold")
    header_text.append(" / ", style="dim")
    header_text.append("authentication", style="dim")
    console.print(Align.center(header_text))
    console.print(Align.center("-" * 40, style="dim"))
    console.print()

    try:
        with console.status("Requesting device code...", spinner_style="dim"):
            device_code_info = await get_device_code()
        
        panel_content = Text(justify="center")
        panel_content.append("1. Open a browser and go to:\n")
        panel_content.append(f"{device_code_info['verificationUriComplete']}\n\n", style="bold")
        panel_content.append("2. Enter the following code:\n")
        panel_content.append(device_code_info['userCode'], style="bold")
        
        console.print(Align.center(Panel(panel_content, box=box.SIMPLE, border_style="dim")))

        with console.status("Waiting for authorization in browser...", spinner_style="dim"):
            creds = await poll_for_token(device_code_info)
        
        if creds:
            user_name = creds.user.get("username", "unknown")
            console.print(f"\nAuthentication successful. Welcome, {user_name}.")
            await asyncio.sleep(2)
        return creds

    except (TimeoutError, Exception) as e:
        console.print(f"\nAn error occurred: {e}")
        return None
