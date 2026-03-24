# Security Policy

## Scope

This repository is a curated list of public APIs maintained as a Markdown file.
It does not contain executable code deployed to production servers.

## Reporting a Vulnerability

If you discover a security issue (e.g., a malicious link, phishing URL, or
compromised API endpoint in the list), please:

1. **Open an issue** with the `security` label, or
2. **Email the maintainers** directly if the issue is sensitive

We will review and remove malicious entries within 48 hours.

## What Counts as a Security Issue

- A listed API URL that redirects to malware or phishing
- A listed API that has been compromised and serves malicious content
- A PR that attempts to inject malicious links
- XSS or injection attempts in API descriptions

## What Does NOT Count

- APIs that require authentication (this is expected and documented)
- APIs that are simply offline or returning errors (use the "broken link" issue template)
- Disagreements about whether an API is "free enough" to be listed
