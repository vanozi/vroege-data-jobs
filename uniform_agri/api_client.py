# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "requests",
#     "python-dotenv"
# ]
# ///

import os
from pathlib import Path
from typing import Any, Dict
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


def get_access_token() -> str:
    """Get OAuth2 access token from Uniform API"""
    username = os.getenv('UNIFORM_USERNAME')
    password = os.getenv('UNIFORM_PASSWORD')
    base_url = os.getenv('UNIFORM_BASE_URL')
    auth_url = f"{base_url}/oauth2/token"

    data = {
        'grant_type': 'password',
        'username': username,
        'password': password,
        'client_id': os.getenv('UNIFORM_CLIENT_ID')
    }

    response = requests.post(
        auth_url,
        json=data,
        headers={
            'accept': 'application/json'
        }
    )
    response.raise_for_status()

    return response.json()['access_token']


class ApiClient:
    """Low-level API client for making HTTP requests with automatic token refresh"""

    def __init__(self, token: str = None):
        self.base_url = os.getenv('UNIFORM_BASE_URL')

        # Check if token exists in env, if not get and store it
        if token:
            self.token = token
        else:
            self.token = os.getenv('UNIFORM_ACCESS_TOKEN')
            if not self.token:
                self.token = self._get_and_store_token()

    def _get_and_store_token(self) -> str:
        """Get new access token and store it in .env file"""
        token = get_access_token()
        self._update_env_file('UNIFORM_ACCESS_TOKEN', token)
        return token

    def _update_env_file(self, key: str, value: str) -> None:
        """Update .env file with new key-value pair"""
        env_path = Path('.env')

        if not env_path.exists():
            env_path.write_text(f'{key}="{value}"\n')
            os.environ[key] = value
            return

        # Read existing .env file
        lines = env_path.read_text().splitlines()
        updated = False

        # Update existing key or add new one
        for i, line in enumerate(lines):
            if line.startswith(f'{key}='):
                lines[i] = f'{key}="{value}"'
                updated = True
                break

        if not updated:
            lines.append(f'{key}="{value}"')

        # Write back to file
        env_path.write_text('\n'.join(lines) + '\n')

        # Update runtime environment
        os.environ[key] = value

    def _request_with_retry(self, method: str, endpoint: str, **kwargs: Any) -> Dict[str, Any]:
        """Make HTTP request with automatic token refresh on 401"""
        url = f"{self.base_url}{endpoint}"
        headers = kwargs.pop('headers', {})
        headers['Authorization'] = f"Bearer {self.token}"

        try:
            response = requests.request(
                method=method.upper(),
                url=url,
                headers=headers,
                **kwargs
            )

            # If 401, refresh token and retry once
            if response.status_code == 401:
                self.token = self._get_and_store_token()
                headers['Authorization'] = f"Bearer {self.token}"

                response = requests.request(
                    method=method.upper(),
                    url=url,
                    headers=headers,
                    **kwargs
                )

            response.raise_for_status()
            return response.json()

        except requests.exceptions.HTTPError as e:
            raise

    def request(self, method: str, endpoint: str, **kwargs: Any) -> Dict[str, Any]:
        """Make HTTP request and return JSON response"""
        return self._request_with_retry(method, endpoint, **kwargs)

    def get(self, endpoint: str, **kwargs) -> Dict[str, Any]:
        """GET request"""
        return self.request('GET', endpoint, **kwargs)

    def post(self, endpoint: str, **kwargs) -> Dict[str, Any]:
        """POST request"""
        return self.request('POST', endpoint, **kwargs)
