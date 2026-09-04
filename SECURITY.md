# Security policy

TIDAL MCP handles account-scoped OAuth sessions and can perform remote mutations when a user
explicitly enables them. Security reports are taken seriously.

## Supported versions

| Version | Supported |
| --- | --- |
| 1.x | Yes |
| Earlier upstream versions | No |

## Report a vulnerability privately

Use **Report a vulnerability** in this repository's GitHub Security tab. Do not open a public issue
for suspected credential exposure, authorization bypasses, approval-token failures, arbitrary
endpoint access, command injection, or other exploitable behavior.

Include:

- affected version and commit;
- operating system and Python version;
- minimal reproduction steps;
- expected and observed behavior;
- impact and any suggested mitigation;
- whether real TIDAL account data was exposed or modified.

Never include OAuth tokens, refresh tokens, a real `session.json`, private playlist contents, or
other personal account data. Redact IDs unless they are essential to the reproduction.

## Security boundaries

- Authentication runs outside MCP tools through `tidal-auth`.
- Session and approval files live outside the repository and use private filesystem permissions
  where supported.
- Tool output passes through explicit public-field serializers.
- Writes are disabled by default.
- Enabled writes require an exact short-lived preview plus a single-use commit token.
- Raw private endpoints, arbitrary URLs, media downloads, DRM handling, and shell execution are not
  exposed.

Security annotations are descriptive hints, not the enforcement boundary. The server validates
inputs and checks write state and approval records at execution time.

## Response expectations

Reports will be acknowledged as maintainers are available. Valid issues will be reproduced,
triaged by impact, fixed on a private branch when appropriate, and disclosed after users have a
reasonable opportunity to update.
