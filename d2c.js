/**
 * @typedef {"postgres"|"redis"} SandboxType
 */

/**
 * @typedef {Object} SandboxResponse
 * @property {string} id
 * @property {SandboxType} sandboxType
 * @property {string|null} status
 * @property {Date} createdAt
 * @property {Object.<string, any>|null} [credentials]
 */

class Dev2CloudError extends Error {
  /**
   * Raised when the API returns an error response.
   * @param {number} statusCode
   * @param {string} detail
   */
  constructor(statusCode, detail) {
    super(`[${statusCode}] ${detail}`);
    this.name = "Dev2CloudError";
    this.statusCode = statusCode;
    this.detail = detail;
  }
}

class Dev2Cloud {
  /**
   * Client for the Dev2Cloud sandbox management API.
   *
   * @example
   * const client = new Dev2Cloud("your-api-key");
   *
   * // Create a sandbox and wait until it's running
   * const sandbox = await client.createSandbox("postgres");
   * console.log(sandbox.credentials);
   *
   * // List all active sandboxes
   * for (const sb of await client.listSandboxes()) {
   *   console.log(sb.id, sb.status);
   * }
   *
   * // Clean up
   * await client.deleteSandbox(sandbox.id);
   */

  /**
   * Initialise the Dev2Cloud client.
   *
   * @param {string} apiKey - API key used to authenticate requests (sent as `X-Api-Key` header).
   * @param {string} [apiUrl="https://api.dev2.cloud"] - Base URL of the Dev2Cloud API.
   */
  constructor(apiKey, apiUrl = "https://api.dev2.cloud") {
    this._apiUrl = apiUrl.replace(/\/+$/, "");
    this._apiKey = apiKey;
  }

  // -- helpers ----------------------------------------------------------

  /**
   * @param {string} path
   * @returns {string}
   */
  _url(path) {
    return `${this._apiUrl}${path}`;
  }

  /**
   * @param {Response} response
   * @throws {Dev2CloudError}
   */
  static async _raiseOnError(response) {
    if (response.ok) return;
    let detail;
    try {
      const body = await response.json();
      detail = body.detail ?? response.statusText;
    } catch {
      detail = response.statusText;
    }
    throw new Dev2CloudError(response.status, detail);
  }

  /**
   * @param {Object.<string, any>} data
   * @returns {SandboxResponse}
   */
  static _parseSandbox(data) {
    return {
      id: data.id,
      sandboxType: data.sandbox_type,
      status: data.status ?? null,
      createdAt: new Date(data.created_at),
      credentials: data.credentials ?? null,
    };
  }

  /**
   * @param {string} path
   * @param {RequestInit} [options]
   * @returns {Promise<Response>}
   */
  _fetch(path, options = {}) {
    const headers = {
      "X-Api-Key": this._apiKey,
      ...options.headers,
    };
    return fetch(this._url(path), { ...options, headers });
  }

  // -- public API -------------------------------------------------------

  /**
   * Lists all active sandboxes for the authenticated user.
   *
   * @returns {Promise<SandboxResponse[]>} A list of sandbox objects sorted by creation time.
   * @throws {Dev2CloudError} If the API returns an error response.
   */
  async listSandboxes() {
    const response = await this._fetch("/api/v1/sandboxes");
    await Dev2Cloud._raiseOnError(response);
    const data = await response.json();
    return data.map(Dev2Cloud._parseSandbox);
  }

  /**
   * Creates a new sandbox and waits for it to be ready.
   *
   * Provisions a sandbox and polls its status once per second until it
   * transitions to `running` (credentials will be available) or `failed`.
   *
   * @param {SandboxType} sandboxType - The type of sandbox to create (`"postgres"` or `"redis"`).
   * @param {number} [timeout=180] - Maximum seconds to wait for the sandbox to become ready.
   * @returns {Promise<SandboxResponse>} The sandbox object with `running` status and connection credentials.
   * @throws {Dev2CloudError} If the sandbox transitions to `failed` or does not become ready within `timeout` seconds.
   */
  async createSandbox(sandboxType, timeout = 180) {
    const response = await this._fetch("/api/v1/sandboxes", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ sandbox_type: sandboxType }),
    });
    await Dev2Cloud._raiseOnError(response);
    let sandbox = Dev2Cloud._parseSandbox(await response.json());

    const deadline = Date.now() + timeout * 1000;
    while (sandbox.status === "pending") {
      if (Date.now() >= deadline) {
        throw new Dev2CloudError(
          0,
          `Sandbox ${sandbox.id} did not become ready within ${timeout}s`
        );
      }
      await new Promise((resolve) => setTimeout(resolve, 1000));
      sandbox = await this.getSandbox(sandbox.id);
    }

    if (sandbox.status === "failed") {
      throw new Dev2CloudError(0, `Sandbox ${sandbox.id} failed to provision`);
    }

    return sandbox;
  }

  /**
   * Gets a sandbox by its ID.
   *
   * @param {string} sandboxId - The unique identifier of the sandbox.
   * @returns {Promise<SandboxResponse>} The sandbox object including its current status and credentials.
   * @throws {Dev2CloudError} If the API returns an error response.
   */
  async getSandbox(sandboxId) {
    const response = await this._fetch(`/api/v1/sandboxes/${sandboxId}`);
    await Dev2Cloud._raiseOnError(response);
    return Dev2Cloud._parseSandbox(await response.json());
  }

  /**
   * Permanently deletes a sandbox.
   *
   * This action is irreversible. Connection credentials are revoked immediately.
   *
   * @param {string} sandboxId - The unique identifier of the sandbox to delete.
   * @throws {Dev2CloudError} If the API returns an error response.
   */
  async deleteSandbox(sandboxId) {
    const response = await this._fetch(`/api/v1/sandboxes/${sandboxId}`, {
      method: "DELETE",
    });
    await Dev2Cloud._raiseOnError(response);
  }

  /**
   * Deletes all active sandboxes.
   *
   * Fetches the current sandbox list and deletes each one. Deletion
   * errors for individual sandboxes are silently ignored so that one
   * failure does not prevent the remaining sandboxes from being removed.
   *
   * @returns {Promise<string[]>} A list of sandbox IDs that were successfully deleted.
   */
  async deleteAll() {
    const sandboxes = await this.listSandboxes();
    const deleted = [];
    for (const sb of sandboxes) {
      try {
        await this.deleteSandbox(sb.id);
        deleted.push(sb.id);
      } catch (err) {
        if (!(err instanceof Dev2CloudError)) throw err;
      }
    }
    return deleted;
  }
}

module.exports = { Dev2Cloud, Dev2CloudError };
