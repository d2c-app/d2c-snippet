# Dev2Cloud Python Client

A single-file Python client for the [Dev2Cloud](https://dev2.cloud) sandbox API.

## Setup

**Prerequisites:** Python 3.7+, `requests`

1. Copy `d2c.py` into your project
2. Install the dependency:

```bash
pip install requests
```

## Usage

```python
from d2c import Dev2Cloud

client = Dev2Cloud(api_key="your-api-key")

# Create a sandbox (blocks until ready, up to 3 min)
sandbox = client.create_sandbox()
print(sandbox.credentials)
# >>> {'user': '...', 'password': '...', 'host': 'connect.dev2.cloud', 'port': 5432, 'database': 'postgres'}

# List all active sandboxes
for sb in client.list_sandboxes():
    print(sb.id, sb.status)
    # >>> uuid, running

# Clean up
client.delete_sandbox(sandbox.id)

# Or delete everything at once
client.delete_all()
```

## API Reference

### `Dev2Cloud(api_key, api_url="https://api.dev2.cloud")`

| Method | Description |
|---|---|
| `create_sandbox(timeout=180)` | Create a sandbox and wait until it's running. Returns `SandboxResponse`. |
| `get_sandbox(sandbox_id)` | Get a sandbox by ID. |
| `list_sandboxes()` | List all active sandboxes. |
| `delete_sandbox(sandbox_id)` | Permanently delete a sandbox. |
| `delete_all()` | Delete all active sandboxes. Returns list of deleted IDs. |

### `SandboxResponse`

| Field | Type |
|---|---|
| `id` | `str` |
| `status` | `str \| None` |
| `created_at` | `datetime` |
| `credentials` | `dict \| None` |

### `credentials` dict

When a sandbox is running, `credentials` contains Postgres connection details:

```python
{
    "user": "...",
    "password": "...",
    "host": "connect.dev2.cloud",
    "port": 5432,
    "database": "postgres",
}
```

### Error Handling

All methods raise `Dev2CloudError` on API failures. The exception exposes `status_code` and `detail`:

```python
from d2c import Dev2Cloud, Dev2CloudError

try:
    sandbox = client.get_sandbox("nonexistent-id")
except Dev2CloudError as e:
    print(e.status_code, e.detail)
```
