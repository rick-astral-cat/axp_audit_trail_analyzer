import json
import asyncio
import httpx
import os
import time

class AxpClient:
    def __init__(self, config_file="config.json"):
        self.config_file = config_file
        self.client_id = None
        self.client_secret = None
        self.account_id = None
        self.auth_token_url = None
        self.bearer_token = None
        self.refresh_token = None
        self.token_expires_at = 0
        self.refresh_token_expires_at = 0
        self.token_refresh_task = None
        self.queues = []
        self._load_config()

    def _load_config(self):
        if not os.path.exists(self.config_file):
            raise FileNotFoundError(f"Config file not found: {self.config_file}")
        with open(self.config_file, 'r') as f:
            config = json.load(f)
            self.client_id = config.get("AVAYA_AXP_CLIENT_ID")
            self.client_secret = config.get("AVAYA_AXP_CLIENT_SECRET")
            self.account_id = config.get("AVAYA_ACCOUNT_ID")
            self.auth_token_url = f"https://na.api.avayacloud.com/api/auth/v1/{self.account_id}/protocol/openid-connect/token"

        if not all([self.client_id, self.client_secret, self.account_id, self.auth_token_url]):
            raise ValueError("Missing client ID, client secret, account ID, or auth token URL in config file.")

    async def _authenticate(self):
        print("Attempting to authenticate and obtain new tokens...")
        token_url = self.auth_token_url
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
        }
        data = {
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": self.client_secret
        }
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(token_url, headers=headers, data=data)
                response.raise_for_status()
                token_data = response.json()
                self.bearer_token = token_data["access_token"]
                self.refresh_token = token_data["refresh_token"]
                self.token_expires_at = time.time() + token_data["expires_in"]
                self.refresh_token_expires_at = time.time() + token_data["refresh_expires_in"]
                print("Authentication successful. New tokens obtained.")
                return True
            except httpx.HTTPStatusError as e:
                print(f"HTTP error during authentication: {e}")
                print(f"Response: {e.response.text}")
            except Exception as e:
                print(f"An error occurred during authentication: {e}")
        return False

    async def _refresh_access_token(self):
        print("Attempting to refresh access token...")
        token_url = self.auth_token_url
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
        }
        data = {
            "grant_type": "refresh_token",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "refresh_token": self.refresh_token
        }
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(token_url, headers=headers, data=data)
                response.raise_for_status()
                token_data = response.json()
                self.bearer_token = token_data["access_token"]
                self.refresh_token = token_data.get("refresh_token", self.refresh_token) # Use new refresh token if provided
                self.token_expires_at = time.time() + token_data["expires_in"]
                if "refresh_expires_in" in token_data:
                    self.refresh_token_expires_at = time.time() + token_data["refresh_expires_in"]
                print("Access token refreshed successfully.")
                return True
            except httpx.HTTPStatusError as e:
                print(f"HTTP error refreshing token: {e}")
                print(f"Response: {e.response.text}")
            except Exception as e:
                print(f"An error occurred refreshing token: {e}")
        return False

    async def get_bearer_token(self):
        # Check if the access token is expired or close to expiring
        if not self.bearer_token or time.time() >= self.token_expires_at - 50:
            # Check if the refresh token is still valid
            if self.refresh_token and time.time() < self.refresh_token_expires_at:
                if not await self._refresh_access_token():
                    # If refresh fails, try a full re-authentication
                    await self._authenticate()
            else:
                # If refresh token is invalid or doesn't exist, do a full authentication
                await self._authenticate()
        return self.bearer_token

    async def _refresh_token_periodically(self):
        while True:
            # Refresh every 500 seconds
            await asyncio.sleep(60)
            await self.get_bearer_token()

    async def start_token_refresh(self):
        if self.token_refresh_task is None:
            self.token_refresh_task = asyncio.create_task(self._refresh_token_periodically())
            print("Token refresh task started.")

    async def stop_token_refresh(self):
        if self.token_refresh_task:
            self.token_refresh_task.cancel()
            self.token_refresh_task = None
            print("Token refresh task stopped.")

    def get_token_expiration_status(self):
        now = time.time()
        access_token_remaining = self.token_expires_at - now if self.token_expires_at > 0 else 0
        refresh_token_remaining = self.refresh_token_expires_at - now if self.refresh_token_expires_at > 0 else 0
        return {
            "access_token_remaining": access_token_remaining,
            "refresh_token_remaining": refresh_token_remaining
        }

    # Example of a protected API call
    async def get_user_updates(self):
        await self.get_bearer_token() # Ensure token is fresh
        if not self.bearer_token:
            print("Cannot get user updates: no bearer token available.")
            return None

        updates_url = f"https://na.api.avayacloud.com/api/v1/{self.account_id}/user/updates" # Example endpoint
        headers = {
            "Authorization": f"Bearer {self.bearer_token}",
            "Content-Type": "application/json"
        }
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(updates_url, headers=headers)
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                print(f"HTTP error getting user updates: {e}")
                print(f"Response: {e.response.text}")
            except Exception as e:
                print(f"An error occurred getting user updates: {e}")
        return None

    async def get_queues(self):
        await self.get_bearer_token()  # Ensure token is fresh
        if not self.bearer_token:
            print("Cannot get queues: no bearer token available.")
            return None

        self.queues = []
        queues_url = f"https://na.cc.avayacloud.com/api/admin/match/v1beta/accounts/{self.account_id}/queues"
        headers = {
            "Authorization": f"Bearer {self.bearer_token}",
            "Content-Type": "application/json"
        }
        async with httpx.AsyncClient() as client:
            while queues_url:
                try:
                    response = await client.get(queues_url, headers=headers)
                    response.raise_for_status()
                    data = response.json()
                    for queue in data.get('queues', []):
                        self.queues.append({
                            'queueId': queue.get('queueId'),
                            'name': queue.get('name')
                        })
                    
                    # Handle pagination
                    if 'links' in data and 'next' in data['links']:
                        next_path = data['links']['next']
                        # The next link is a relative path, so we need to construct the full URL
                        base_url = "https://na.cc.avayacloud.com"
                        queues_url = f"{base_url}{next_path}"
                    else:
                        queues_url = None

                except httpx.HTTPStatusError as e:
                    print(f"HTTP error getting queues: {e}")
                    print(f"Response: {e.response.text}")
                    return None
                except Exception as e:
                    print(f"An error occurred getting queues: {e}")
                    return None
        print(f"Successfully retrieved {len(self.queues)} queues.")
        return self.queues

