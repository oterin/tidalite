# tidalite/config.py

import json
import os
from pathlib import Path
from typing import Optional, Dict, Any

# define paths for configuration file
config_dir = Path(os.environ.get("xdg_config_home", Path.home() / ".config")) / "tidalite"
config_file = config_dir / "config.json"

# ensure the config directory exists
config_dir.mkdir(parents=True, exist_ok=True)

def load_config() -> Dict[str, Any]:
    """loads the configuration from the config file."""
    if not config_file.is_file():
        return {}
    with open(config_file, "r") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return {}

def save_config(config_data: Dict[str, Any]):
    """saves the configuration to the config file."""
    with open(config_file, "w") as f:
        json.dump(config_data, f, indent=2)

# --- auth credentials ---
def get_auth_credentials() -> Optional[Dict[str, Any]]:
    """retrieves auth credentials from the config."""
    config = load_config()
    return config.get("auth")

def save_auth_credentials(credentials: Dict[str, Any]):
    """saves auth credentials to the config."""
    config = load_config()
    config["auth"] = credentials
    save_config(config)

# --- api configuration ---
# use a client id/secret known to work with the device flow for mqa/hi-res access
client_id = "zU4XHVVkc2tDPo4t"
client_secret = "VJKhDFqJPqvsPVNBV6ukXTJ_vxF_4GStlpvy9Iqd-00"
auth_url = "https://auth.tidal.com/v1/oauth2"
api_url_v1 = "https://api.tidal.com/v1"
api_url_v2 = "https://api.tidal.com/v2"
