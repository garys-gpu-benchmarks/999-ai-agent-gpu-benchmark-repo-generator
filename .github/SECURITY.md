# Security policy

## Supported versions

This repository is the `TEMPLATE_00_64` generator seed (public preview version `0.9.0`). Security fixes land here first. Generated workload repositories inherit the template copy from the seed that created them; regenerate or patch those copies after a template fix.

## How to report a vulnerability

Do **not** open a public issue for leaked credentials, SSH keys, hostnames, IP addresses, or other secrets.

Use GitHub's private advisory form:

https://github.com/garys-gpu-benchmarks/ai-agent-gpu-benchmark-repo-generator/security/advisories/new

Or contact the repository owner, Gary Bass (`garymichaelbass`), privately.

Include what was exposed, where it appears in the tree, and whether it is still valid.

## What not to commit

- Private keys, tokens, `.env` files, or `HF_TOKEN`
- Real SSH key paths, hostnames, or IP addresses (use `<ssh_key>` and `<REMOTE_HOST_IP>`)
- Live hardware serials, system UUIDs, or MAC addresses in example inventory files

`docs/examples/hw-sw-inventory/` must stay synthetic (RFC 5737 documentation addresses).
