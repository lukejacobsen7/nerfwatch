# Security

nerfwatch runs locally, stores everything in `~/.nerfwatch/`, and sends prompts only to the backends you configure. API keys are read from environment variables and never written to disk by nerfwatch.

The `code` probe family executes *model-generated* Python in a subprocess (`python -I`, 10 s timeout) to grade it. It is not a sandbox. If you point nerfwatch at an untrusted endpoint, be aware that its output is executed on your machine.

Report vulnerabilities by opening a private security advisory on GitHub.
