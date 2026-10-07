# Security Policy

## Reporting a vulnerability

Do not open a public issue for leaked credentials, private keys, access tokens, private hostnames/IP addresses, or other sensitive information. Use the repository owner's private security-reporting channel or GitHub Security Advisories when enabled.

When reporting, include the affected file/path, the nature of the exposure, and whether the credential or secret may still be valid.

## Do not commit

- API keys, access tokens, `HF_TOKEN`, cookies, or `.env` files
- SSH private keys or private key paths
- Private hostnames, lab IP addresses, or cloud credentials
- Downloaded model weights or licensed/proprietary datasets
- Hardware serial numbers, system UUIDs, or MAC addresses in examples
- Runtime logs or result archives containing sensitive system inventory
