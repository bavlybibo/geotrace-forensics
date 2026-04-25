# Security Policy

## Supported versions

Security fixes are accepted for the latest public release candidate and newer development branches.

## Reporting a vulnerability

If you find a security issue in GeoTrace Forensics X, please report it privately to the project maintainer before public disclosure. Include:

- Affected version or commit
- Clear reproduction steps
- Impact explanation
- Any safe proof-of-concept material
- Whether the issue affects evidence confidentiality, integrity, or availability

Do not include real victim evidence or private case material in reports.

## Scope

Important issue classes include:

- Evidence or report privacy leaks
- Unsafe archive extraction or path traversal
- Tampering with manifest/hash verification
- Crashes that can corrupt case state
- Unintended network transmission of evidence data
- Dependency or packaging issues that affect analyst safety

## Disclosure

Please allow reasonable time for review and remediation before public disclosure.
