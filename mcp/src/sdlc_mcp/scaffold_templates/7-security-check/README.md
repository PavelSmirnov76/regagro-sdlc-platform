# 7 — Security check

Security review of evaluated results before they ship. The **security gate** —
vulnerabilities, secrets, dependency risks, and access/permission concerns are
caught here, not in production.

An item passes this stage when it clears security review and moves on to
`../8-deploy/`.

## What goes here
- Security review findings and their resolution
- Dependency / vulnerability scan results
- Secrets and access/permission audits
