# AMD Developer Cloud — Initial Registration

_Last updated: 2026-08-04_

This guide walks you through registering for the AMD Developer Cloud, generating an SSH key, and spinning up your first GPU droplet so you can run the ROCm install script in this repository.

> **Conventions used below**
> - `<username>` — your Windows account name
> - `<hostname>` — your local machine's hostname
> - `<DROPLET_IP>` — the public IPv4 address shown in your droplet panel after it boots
> Replace these placeholders with your own values.

### Prerequisites

- Windows with the OpenSSH client available (`ssh` and `ssh-keygen` on your PATH — included by default on Windows 10/11; if either command isn't found, add the "OpenSSH Client" optional feature in Settings).
- A payment method you're able to add to the account. DigitalOcean requires a valid card on file before you can launch a GPU droplet, even if your usage will be fully covered by credits.
- An email address you can access to complete verification.

---

## 1. Create an account

1. Go to <https://amd.digitalocean.com/>.
2. To the right of "Don't have an account?", click **Sign up**.
3. Check the box for "I agree to the Terms..." then click **Sign Up with Email**.
4. Enter your full name, email address, and password, then click **Sign Up**.
5. Open the verification email from DigitalOcean and click the link to finish creating your AMD Developer Cloud account.
6. Add a payment method when prompted — required to launch a droplet, even if you're only spending credits.
7. Check for a signup credit. New accounts are often granted an initial credit balance (frequently enough to cover dozens of GPU-hours) with no approval step. Look for it on your billing page before requesting anything further.
8. If you need more GPU capacity than your account defaults to, you can request a GPU limit increase. A reasonable "Reason for increase" is something like:
   > _"I am working on low-level programming and would like to evaluate AMD GPUs."_

---

## 2. Generate an SSH key

You'll need an SSH key pair to log into your droplet.

> **Important:** an SSH key pair has two files. The `.pub` file is your **public** key — that's the one you upload to AMD/DigitalOcean. The file *without* `.pub` is your **private** key — keep it on your local machine and never paste it into any web form, repo, or chat. **Use a passphrase** so that even if the private key file is stolen it isn't immediately usable.

Open a Windows terminal (PowerShell) and run `ssh-keygen`:

```text
PS> ssh-keygen -t ed25519
Generating public/private ed25519 key pair.
Enter file in which to save the key (C:\Users\<username>\.ssh\id_ed25519): C:\Users\<username>\.ssh\amd-devcloud-key
Enter passphrase (empty for no passphrase): ********
Enter same passphrase again:                ********
Your identification has been saved in C:\Users\<username>\.ssh\amd-devcloud-key
Your public key has been saved in C:\Users\<username>\.ssh\amd-devcloud-key.pub
The key fingerprint is:
SHA256:XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX <username>@<hostname>
The key's randomart image is:
[randomart omitted]
```

This produces two files in `C:\Users\<username>\.ssh\`:

| File | What it is | Where it goes |
|------|------------|---------------|
| `amd-devcloud-key`     | **Private** key | Stays on your local machine. Never share. |
| `amd-devcloud-key.pub` | **Public** key  | Uploaded to AMD Developer Cloud (next step). |

### Passphrases and automation

*If you're only doing a manual, one-off login with no scripted install involved, skip to "Manual, one-off logins" below.*

**Most installs in this repository need a passphrase-less key, not a passphrase-protected one.** A majority of the benchmark suite includes a ROCm setup step that reboots the droplet partway through. When that happens, the install script has to disconnect and reconnect over SSH on its own, with no human at the keyboard to re-enter a passphrase. A passphrase-protected key can't support that: the OpenSSH agent trick under "Manual, one-off logins" only keeps the key unlocked for as long as the local terminal session that ran `ssh-add` stays open, and it doesn't help a script that reconnects after the droplet itself has rebooted out from under it. So for anything in this repo that automates a reboot — which is most of it — treat the no-passphrase key below as the default you'll need, not a rare edge case reserved for scheduled tasks.

**Creating the no-passphrase key.** Create a *separate* key file with no passphrase and use it only for droplet automation — don't strip the passphrase from your main key or reuse this file for anything else. The simplest approach is to copy your existing private key and strip the passphrase from the copy:

```text
PS> Copy-Item C:\Users\<username>\.ssh\amd-devcloud-key C:\Users\<username>\.ssh\amd-devcloud-key-nopassphrase
PS> ssh-keygen -p -f C:\Users\<username>\.ssh\amd-devcloud-key-nopassphrase
```

Enter your existing passphrase when prompted for the old one, then press Enter twice to leave the new passphrase blank. Reference this no-passphrase copy with `ssh -i ...\amd-devcloud-key-nopassphrase ...` in your install scripts. The keypair is mathematically identical to the original, so the public key already uploaded to AMD authenticates both — no need to re-upload anything.

Because this file now authenticates unattended for most of your benchmark runs, it's a higher-value target than a normal private key: keep it under the same restricted permissions as your other keys, don't copy it anywhere outside `.ssh\`, and delete it once you're done with the droplet (see [Tearing down](#5-tearing-down)) rather than leaving it around for next time — regenerate a fresh one per droplet instead of reusing it long-term.

**Manual, one-off logins.** For the remaining installs that don't reboot, or whenever you're logging in by hand rather than running a script, load your regular passphrase-protected key into the OpenSSH agent once at the start of your terminal session. The agent caches the unlocked key in memory, and any subsequent `ssh` calls made from that same session — including scripts you launch from it — use it transparently with no further prompts.

```text
PS> ssh-add C:\Users\<username>\.ssh\amd-devcloud-key
```

---

## 3. Create your first GPU droplet

1. Go to <https://amd.digitalocean.com/> and log in.
2. Click the green **Create** dropdown in the top navigation bar, then select **GPU Droplets**.
3. Click **Add SSH Key**.
4. Open your **public** key file in Notepad:
   ```
   C:\Users\<username>\.ssh\amd-devcloud-key.pub
   ```
   (Note the `.pub` extension — make sure you are not opening the private key by mistake.)
5. Copy the entire contents and paste them into the **SSH Key content** box.
6. Give the key a descriptive name, for example `MyAmdPublicKey-YYYYMMDD`.
7. On the **Create GPU Droplet** page, choose:
   - **GPU Plan:** the single-GPU **`MI300X`** plan — not **`MI300X x8`**, which sits directly above it in the list. Both are priced the same per GPU, but `x8` bills for all eight GPUs at once (roughly 8x the hourly cost of the single-GPU plan) and is easy to select by mistake.
   - **Image:** under the **Bare OS** tab (not **Quick Start**), select **Ubuntu → 24.04 (LTS) x64**. This repository's ROCm install script is written for a bare Ubuntu image — the **`ROCm™ Software`** Quick Start image under **Quick Start** already ships ROCm plus a preconfigured Jupyter/Docker stack, which the install script isn't meant to run on top of.
   - **SSH Key:** the key you just added
8. Note the hourly price shown on the page before confirming — GPU droplets are billed per hour while running regardless of whether you're actively using them.
9. Click **Create GPU Droplet** to launch.

> **Billing note:** GPU droplets bill by the hour while running. Check the current price displayed on the page before you confirm, and **destroy the droplet when you're done** to avoid surprise charges.

Wait a few minutes for the system to boot, then copy the **Public IPv4** address from the droplet panel — you'll need it for the next step.

---

## 4. Log in to the droplet

Open a Windows command line and SSH in, referencing your private key. Enter your passphrase when prompted.

The **first** time you connect to a given `<DROPLET_IP>`, SSH will pause before the passphrase prompt to ask whether the server's host key should be trusted:

```text
The authenticity of host '<DROPLET_IP> (<DROPLET_IP>)' can't be established.
ED25519 key fingerprint is SHA256:xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx.
Are you sure you want to continue connecting (yes/no/[fingerprint])?
```

This is a real trust decision, not a formality — you're confirming the fingerprint belongs to your droplet and not to someone else who happens to be on that address. Before typing `yes`:

- Confirm `<DROPLET_IP>` in the prompt matches the Public IPv4 shown in your droplet panel.
- If you want to verify the fingerprint itself rather than just the IP, open the droplet's **Access** tab in the control panel and launch the **web console**. The host key fingerprint appears in the boot log there, or you can run `ssh-keygen -l -f /etc/ssh/ssh_host_ed25519_key.pub` from that console to print it directly for comparison.

Once you type `yes`, OpenSSH saves the fingerprint in `C:\Users\<username>\.ssh\known_hosts` and won't ask again for this IP — unless the fingerprint later changes (see Troubleshooting below).

```text
C:\Users\<username>> ssh -i C:\Users\<username>\.ssh\amd-devcloud-key root@<DROPLET_IP>
Enter passphrase for key 'C:\Users\<username>\.ssh\amd-devcloud-key':
Welcome to Ubuntu 24.04.3 LTS (GNU/Linux 6.8.0-87-generic x86_64)

 * Documentation:  https://help.ubuntu.com
 * Management:     https://landscape.canonical.com
 * Support:        https://ubuntu.com/pro

System information as of <date>

root@<droplet-hostname>:~#
```

> Because this is the **Bare OS** image rather than the **`ROCm™ Software`** Quick Start image, you'll get a plain Ubuntu login banner — no Jupyter server, no Docker container, no ROCm. That's expected: this repository's install script is what sets ROCm up, not the image itself.

You're logged in. Since ROCm isn't installed yet, `rocm-smi` won't exist at this point — don't treat that as an error. Confirm the GPU is visible at the PCI level instead, which works with no GPU software installed at all:

```text
root@<droplet-hostname>:~# lspci | grep -i amd
```

You should see a line identifying the MI300X as an AMD/ATI display or accelerator controller. That confirms the kernel sees the card before any driver or userspace stack is on top of it. If nothing shows up, that points to a droplet provisioning problem rather than something to fix in software — check with AMD Developer Cloud support before going further.

From here you can run the ROCm install script from this repository — see `<script-name>` in the repository README for the exact command. Once that script finishes, `rocm-smi` becomes available and gives you the fuller memory/utilization view.

### Troubleshooting

- **`Permission denied (publickey)`** — double-check the `-i` path points to your *private* key (no `.pub`), and confirm the matching public key was actually added to the droplet in step 3.
- **Connection times out or is refused** — the droplet may still be booting; wait a minute and retry. If it persists, confirm you copied the Public IPv4 (not the private IP) from the droplet panel.
- **Prompted for a password instead of a passphrase** — this usually means the SSH key wasn't uploaded, or you're pointing at the wrong key file.
- **`WARNING: REMOTE HOST IDENTIFICATION HAS CHANGED!`** — the fingerprint saved for `<DROPLET_IP>` no longer matches what the server presents. This is expected if you destroyed your old droplet and a *new* one you created was assigned the same IP; DigitalOcean does recycle addresses. It can also mean something else is now listening on that IP. Only proceed once you've confirmed in the control panel that the old droplet is gone and this new one is yours. Then clear the stale entry and reconnect:
  ```text
  PS> ssh-keygen -R <DROPLET_IP>
  ```
  You'll be prompted to accept the new fingerprint on the next connection attempt, as if connecting for the first time.

---

## 5. Tearing down

When you're finished, return to the AMD Developer Cloud control panel and **destroy** the droplet (not just power it off — powered-off droplets may still incur charges depending on the plan). Verify in the droplets list that it's gone.
