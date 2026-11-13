# Security

PixelForge executes model-directed operations. Treat model output, project files, and tool arguments as untrusted input.

## Current controls

- Provider credentials are read from environment variables only and are never added to model messages or trace events by the runtime.
- Trace writes reject symlinked path components, non-regular targets, and hard-linked files; on platforms with descriptor-relative filesystem APIs, directory traversal and final file opening use no-follow semantics. New trace files use restrictive permissions where supported.
- Provider endpoint configuration must use an absolute HTTP(S) URL without embedded user information, query strings, or fragments.
- Bearer API keys are sent only over HTTPS; plain HTTP endpoints are accepted with an API key only when the host is loopback (\`localhost\`, \`127.0.0.0/8\`, or \`::1\`).
- Provider bearer credentials use unredirected request headers, so they are not forwarded to HTTP redirect targets.
- Provider requests have a bounded timeout (1–600 seconds), and response bodies are capped at 5 MiB.
- HTTP error responses are not echoed into CLI errors, preventing arbitrary response bodies from being displayed as diagnostic text.
- Filesystem tools are rooted in one workspace and reject absolute paths, parent traversal, backslash paths, and symlink components.
- Workspace reads open and validate a regular file descriptor, then enforce the byte limit while reading so concurrent file growth cannot bypass it; FIFO and device targets are rejected. On platforms with descriptor-relative filesystem APIs, reads and atomic writes traverse parent directories using no-follow directory descriptors, preventing symlink swaps from redirecting I/O. Writes use exclusive temporary files and atomic replacement within the opened parent directory. Platforms without descriptor-relative APIs use a path-based fallback with no-follow final-file flags where available.
- The model cannot read or write common credential/private metadata paths, including \`.env\` variants, \`.git\`, \`.pixelforge\`, SSH/AWS/Azure/Docker configuration directories, credential files, and private-key/certificate extensions.
- Workspace listings omit private metadata, dependency caches, generated build output, and symlinked files/directories.
- Text reads and writes have size limits; writes use a temporary file and atomic replacement.
- Phaser scaffold generation refuses to replace an existing project directory and removes an incomplete new project if generation fails.
- Only explicitly registered tools can be called. Tool call count, argument size, per-result size, and aggregate tool-result size are bounded.
- The agent loop has a hard maximum step count.
- No unrestricted shell, subprocess, network-fetch, or package-install tool is exposed to the model.

These controls reduce accidental exposure and resource exhaustion. They are not a substitute for operating-system isolation: the CLI runs with the privileges of the local user, and the model can modify ordinary files inside the selected workspace.

## Deployment guidance

Do not expose a future remote runtime publicly without authentication, per-user isolation, rate limits, audit logs, and sandbox policy. Run generated projects with least privilege, preferably in disposable containers or isolated browser runtimes.

Never put API keys in frontend JavaScript, generated games, screenshots, or committed configuration. Use a secret manager for hosted deployments.

## Reporting a vulnerability

Please do not publish exploitable security details in a public issue. Contact the repository owner through GitHub with a private vulnerability report.
