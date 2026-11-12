# Security

PixelForge executes model-directed operations. Treat model output, project files, and tool arguments as untrusted input.

## Current controls

- Provider credentials are read from environment variables only.
- Credentials are not written into generated projects or trace output.
- Filesystem tools are rooted in one workspace and reject absolute paths, parent traversal, and symlink components.
- Text reads and writes have size limits.
- Only explicitly registered tools can be called.
- The agent loop has a hard maximum step count.
- No unrestricted shell, subprocess, network-fetch, or package-install tool is exposed to the model.

## Deployment guidance

Do not expose a future remote runtime publicly without authentication, per-user isolation, rate limits, audit logs, and sandbox policy. Run generated projects with least privilege, preferably in disposable containers or isolated browser runtimes.

Never put API keys in frontend JavaScript, generated games, screenshots, or committed configuration. Use a secret manager for hosted deployments.

## Reporting a vulnerability

Please do not publish exploitable security details in a public issue. Contact the repository owner through GitHub with a private vulnerability report.
