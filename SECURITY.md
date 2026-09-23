# Security Policy

## Supported versions

Only the latest release of `obi-energy-tracker` on PyPI receives security fixes.

## Reporting a vulnerability

Please do **not** open a public issue for a security problem.

Report it through GitHub's private vulnerability reporting: open the
[Security tab](https://github.com/OBI-Smart-Technologies/energy-tracker-api-client-python/security/advisories/new)
of this repository and file a draft advisory. Only the maintainers can see it.

Include what you need to reproduce the problem: the affected version, the request or
payload involved, and the impact you see. Please leave out real access tokens — a
redacted example is enough.

We aim to acknowledge a report within five working days and to ship a fix or a mitigation
before the advisory is published.

## Scope

This repository is an API client. It never stores credentials: the access token is supplied
by the caller through a `TokenProvider` and is only put into the `Authorization` header of
outgoing requests. Issues in the OBI ENERGY TRACKER cloud service or in the OBI account
system are out of scope here — report those to OBI directly.
