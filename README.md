# Dev2Cloud Client

A single-file client for the [Dev2Cloud](https://dev2.cloud) sandbox API, available in **Python** and **JavaScript**.

## Setup

### Python

**Prerequisites:** Python 3.7+, `requests`

1. Copy `d2c.py` into your project
2. Install the dependency:

```bash
pip install requests
```

### JavaScript

**Prerequisites:** Node.js 18+ (uses the built-in `fetch` API)

1. Copy `d2c.js` into your project — no additional dependencies required.

## Usage

### Python

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

### JavaScript

```javascript
const { Dev2Cloud } = require("./d2c");

const client = new Dev2Cloud("your-api-key");

// Create a sandbox (awaits until ready, up to 3 min)
const sandbox = await client.createSandbox();
console.log(sandbox.credentials);
// => { user: '...', password: '...', host: 'connect.dev2.cloud', port: 5432, database: 'postgres' }

// List all active sandboxes
for (const sb of await client.listSandboxes()) {
  console.log(sb.id, sb.status);
  // => uuid, running
}

// Clean up
await client.deleteSandbox(sandbox.id);

// Or delete everything at once
await client.deleteAll();
```

## API Reference

### Python — `Dev2Cloud(api_key, api_url="https://api.dev2.cloud")`

| Method | Description |
|---|---|
| `create_sandbox(timeout=180)` | Create a sandbox and wait until it's running. Returns `SandboxResponse`. |
| `get_sandbox(sandbox_id)` | Get a sandbox by ID. |
| `list_sandboxes()` | List all active sandboxes. |
| `delete_sandbox(sandbox_id)` | Permanently delete a sandbox. |
| `delete_all()` | Delete all active sandboxes. Returns list of deleted IDs. |

### JavaScript — `new Dev2Cloud(apiKey, apiUrl = "https://api.dev2.cloud")`

| Method | Description |
|---|---|
| `createSandbox(timeout = 180)` | Create a sandbox and wait until it's running. Returns a sandbox object. |
| `getSandbox(sandboxId)` | Get a sandbox by ID. |
| `listSandboxes()` | List all active sandboxes. |
| `deleteSandbox(sandboxId)` | Permanently delete a sandbox. |
| `deleteAll()` | Delete all active sandboxes. Returns array of deleted IDs. |

### Sandbox object

| Field | Python type | JavaScript type |
|---|---|---|
| `id` | `str` | `string` |
| `status` | `str \| None` | `string \| null` |
| `created_at` / `createdAt` | `datetime` | `Date` |
| `credentials` | `dict \| None` | `object \| null` |

### `credentials` object

When a sandbox is running, `credentials` contains Postgres connection details:

```json
{
  "user": "...",
  "password": "...",
  "host": "connect.dev2.cloud",
  "port": 5432,
  "database": "postgres"
}
```

### Error Handling

All methods raise/throw `Dev2CloudError` on API failures. The error exposes `status_code` (Python) / `statusCode` (JS) and `detail`.

**Python:**

```python
from d2c import Dev2Cloud, Dev2CloudError

try:
    sandbox = client.get_sandbox("nonexistent-id")
except Dev2CloudError as e:
    print(e.status_code, e.detail)
```

**JavaScript:**

```javascript
const { Dev2Cloud, Dev2CloudError } = require("./d2c");

try {
  const sandbox = await client.getSandbox("nonexistent-id");
} catch (err) {
  if (err instanceof Dev2CloudError) {
    console.log(err.statusCode, err.detail);
  }
}
```
