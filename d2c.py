from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional

import requests


@dataclass
class SandboxResponse:
    id: str
    status: Optional[str]
    created_at: datetime
    credentials: Optional[dict[str, Any]] = None


class Dev2CloudError(Exception):
    """Raised when the API returns an error response."""

    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"[{status_code}] {detail}")


class Dev2Cloud:
    """Client for the Dev2Cloud sandbox management API."""

    def __init__(self, api_key: str, api_url: str = "https://api.dev2.cloud") -> None:
        """Initialise the Dev2Cloud client.

        Args:
            api_key: API key used to authenticate requests (sent as ``X-Api-Key`` header).
            api_url: Base URL of the Dev2Cloud API. Defaults to ``https://api.dev2.cloud``.
        """
        self._api_url = api_url.rstrip("/")
        self._session = requests.Session()
        self._session.headers.update({"X-Api-Key": api_key})

    # -- helpers ----------------------------------------------------------

    def _url(self, path: str) -> str:
        return f"{self._api_url}{path}"

    @staticmethod
    def _raise_on_error(response: requests.Response) -> None:
        if response.ok:
            return
        try:
            detail = response.json().get("detail", response.text)
        except ValueError:
            detail = response.text
        raise Dev2CloudError(response.status_code, detail)

    @staticmethod
    def _parse_sandbox(data: dict[str, Any]) -> SandboxResponse:
        return SandboxResponse(
            id=data["id"],
            status=data.get("status"),
            created_at=datetime.fromisoformat(data["created_at"]),
            credentials=data.get("credentials"),
        )

    # -- public API -------------------------------------------------------

    def list_sandboxes(self) -> list[SandboxResponse]:
        """Lists all active sandboxes for the authenticated user.

        Returns:
            A list of sandbox objects sorted by creation time.

        Raises:
            Dev2CloudError: If the API returns an error response.
        """
        response = self._session.get(self._url("/api/v1/sandboxes"))
        self._raise_on_error(response)
        return [self._parse_sandbox(item) for item in response.json()]

    def create_sandbox(self, timeout: float = 180) -> SandboxResponse:
        """Creates a new sandbox and waits for it to be ready.

        Provisions a sandbox and polls its status once per second until it
        transitions to ``running`` (credentials will be available) or
        ``failed``.

        Args:
            timeout: Maximum seconds to wait for the sandbox to become
                ready. Defaults to 180 (3 minutes).

        Returns:
            The sandbox object with ``running`` status and connection credentials.

        Raises:
            Dev2CloudError: If the sandbox transitions to ``failed`` or
                does not become ready within ``timeout`` seconds.
        """
        response = self._session.post(self._url("/api/v1/sandboxes"))
        self._raise_on_error(response)
        sandbox = self._parse_sandbox(response.json())

        deadline = time.monotonic() + timeout
        while sandbox.status == "pending":
            if time.monotonic() >= deadline:
                raise Dev2CloudError(
                    0, f"Sandbox {sandbox.id} did not become ready within {timeout}s"
                )
            time.sleep(1)
            sandbox = self.get_sandbox(sandbox.id)

        if sandbox.status == "failed":
            raise Dev2CloudError(0, f"Sandbox {sandbox.id} failed to provision")

        return sandbox

    def get_sandbox(self, sandbox_id: str) -> SandboxResponse:
        """Gets a sandbox by its ID.

        Args:
            sandbox_id: The unique identifier of the sandbox.

        Returns:
            The sandbox object including its current status and credentials.

        Raises:
            Dev2CloudError: If the API returns an error response.
        """
        response = self._session.get(self._url(f"/api/v1/sandboxes/{sandbox_id}"))
        self._raise_on_error(response)
        return self._parse_sandbox(response.json())

    def delete_sandbox(self, sandbox_id: str) -> None:
        """Permanently deletes a sandbox.

        This action is irreversible. Connection credentials are revoked
        immediately.

        Args:
            sandbox_id: The unique identifier of the sandbox to delete.

        Raises:
            Dev2CloudError: If the API returns an error response.
        """
        response = self._session.delete(self._url(f"/api/v1/sandboxes/{sandbox_id}"))
        self._raise_on_error(response)
