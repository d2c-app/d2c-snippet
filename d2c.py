from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal, Optional, Self

import requests
from pydantic import BaseModel, model_validator

SandboxType = Literal["postgres", "redis"]


class SandboxResponse(BaseModel):
    id: str
    sandbox_type: SandboxType
    status: Optional[str]
    created_at: datetime
    credentials: Optional[dict[str, Any]] = None
    url: Optional[str] = None

    @model_validator(mode="after")
    def validate_credentials(self) -> Self:
        try:
            if self.sandbox_type == "postgres":
                self.url = f"postgresql://{self.credentials['user']}:{self.credentials['password']}@{self.credentials['host']}:{self.credentials['port']}/{self.credentials['database']}"
            elif self.sandbox_type == "redis":
                self.url = f"redis://{self.credentials['user']}:{self.credentials['password']}@{self.credentials['host']}:{self.credentials['port']}"
        except Exception:
            pass
        return self


class Dev2CloudError(Exception):
    """Raised when the API returns an error response."""

    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"[{status_code}] {detail}")


class Dev2Cloud:
    """Client for the Dev2Cloud sandbox management API.

    Example::

        from d2c import Dev2Cloud

        client = Dev2Cloud(api_key="your-api-key")

        # Create a sandbox and wait until it's running
        sandbox = client.create_sandbox("postgres")
        print(sandbox.credentials)

        # List all active sandboxes
        for sb in client.list_sandboxes():
            print(sb.id, sb.status)

        # Clean up
        client.delete_sandbox(sandbox.id)
    """

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
            sandbox_type=data["sandbox_type"],
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

    def create_sandbox(
        self, sandbox_type: SandboxType, *, timeout: float = 180
    ) -> SandboxResponse:
        """Creates a new sandbox and waits for it to be ready.

        Provisions a sandbox and polls its status once per second until it
        transitions to ``running`` (credentials will be available) or
        ``failed``.

        Args:
            sandbox_type: The type of sandbox to create (``"postgres"`` or ``"redis"``).
            timeout: Maximum seconds to wait for the sandbox to become
                ready. Defaults to 180 (3 minutes).

        Returns:
            The sandbox object with ``running`` status and connection credentials.

        Raises:
            Dev2CloudError: If the sandbox transitions to ``failed`` or
                does not become ready within ``timeout`` seconds.
        """
        response = self._session.post(
            self._url("/api/v1/sandboxes"),
            json={"sandbox_type": sandbox_type},
        )
        self._raise_on_error(response)
        sandbox_id = response.json()["id"]

        deadline = time.monotonic() + timeout
        while True:
            if time.monotonic() >= deadline:
                raise Dev2CloudError(
                    0, f"Sandbox {sandbox_id} did not become ready within {timeout}s"
                )
            time.sleep(1)
            sandbox = self.get_sandbox(sandbox_id)
            if sandbox.status != "pending":
                break

        if sandbox.status == "failed":
            raise Dev2CloudError(0, f"Sandbox {sandbox_id} failed to provision")

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

    def delete_all(self) -> list[str]:
        """Deletes all active sandboxes.

        Fetches the current sandbox list and deletes each one. Deletion
        errors for individual sandboxes are silently ignored so that one
        failure does not prevent the remaining sandboxes from being removed.

        Returns:
            A list of sandbox IDs that were successfully deleted.
        """
        sandboxes = self.list_sandboxes()
        deleted: list[str] = []
        for sb in sandboxes:
            try:
                self.delete_sandbox(sb.id)
                deleted.append(sb.id)
            except Dev2CloudError:
                pass
        return deleted
