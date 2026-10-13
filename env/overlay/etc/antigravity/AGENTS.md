# Antigravity Android Agent Rules & Environment Guidelines

> [!NOTE]
> This rule is automatically loaded into every conversation in Antigravity for Android (AGY v2).
> It defines the operating environment, execution rules, package management, and elevated permissions.

---

## 1. Platform & Environment Identity

- **Platform:** Native Android (Linux kernel 6.1+, ARM64 / `aarch64` architecture, ARMv8.1-A+ with LSE).
- **Application Context:** Runs under the installed AGY application id (`$AGY_APPLICATION_ID`) and the current Android user/profile.
- **Key Filesystem Paths:**
  - Application Root (`$HOME`): the app-private `files/` directory.
  - Linux Userspace Prefix (`$PREFIX`): `$HOME/usr`.
  - User Binary Path: `$PREFIX/bin` (prefer the existing `$PATH`; do not hard-code `/data/user/0` or an application id).
  - Runtime Internals: `$HOME/runtime/bin`.
  - External / Shared Storage: `/storage/emulated/0` (Projects typically reside in `/storage/emulated/0/Documents/`).
  - AI State & Config: `$HOME/.gemini/config/`.
  - Conversation Brain & Artifacts: `$HOME/.gemini/antigravity-app/brain/<conversation-id>/`.

---

## 2. Terminal Execution Rules

- **No Bubblewrap / Desktop Sandboxing:**
  Standard desktop Linux bubblewrap (`bwrap`) is **not supported** by the Android kernel and SELinux. Never attempt to invoke `bwrap` or run commands wrapped in desktop sandboxes. All shell commands execute directly within the user shell.
- **Path Quoting:**
  Android storage paths frequently contain spaces (e.g. `/storage/emulated/0/Documents/antigravity v2/`). Always quote file paths in commands.
- **Environment Variables for Shell Commands:**
  When executing commands, ensure the environment is configured:
  ```bash
  # HOME is resolved by the AGY profile; derive PREFIX without a fixed app id.
  : "${HOME:?open an AGY shell with the env profile loaded}"
  export PREFIX="${PREFIX:-$HOME/usr}"
  export HOME PREFIX
  export PATH="$PREFIX/bin:$PATH"
  ```
- **Git on Android Storage:**
  Git installed via Termux repos may check `/data/data/com.termux/files/usr/etc/` which doesn't exist. Always use:
  ```bash
  export GIT_CONFIG_NOSYSTEM=1
  git config --global --add safe.directory "<path>"
  ```

---

## 3. Package Management (`pkg` / `tlx`)

AGY includes a small Termux-repository package client (`pkg`) written in Bash & AWK. Python is part of the default seed package set and is installed on first networked startup; first launch can remain offline, in which case Python stays pending until a later retry.

- **Correct Syntax:**
  ```bash
  # Update package indexes:
  pkg update

  # Install packages (do NOT pass -y flag; list package names directly):
  pkg install git python nodejs bash

  # Search and query:
  pkg search <pattern>
  pkg list
  pkg installed
  pkg info <package>

  # Remove package:
  pkg remove <package>

  # System health self-test:
  pkg selftest
  ```
- **Post-Install Path Fixes:**
  After installing global Python/Node scripts (`pip`, `npm`), fix hardcoded shebangs using:
  ```bash
  agy-fix-paths
  ```

---

## 4. Elevated Operations via Shizuku (`rish`)

The agent has native access to Shizuku's elevated ADB shell (`uid=2000(shell)`):
- **Executable Location:** `$PREFIX/bin/rish`. It discovers the Shizuku dex under `$PREFIX/../runtime/bin` and receives the current package id from the app bridge.
- **How to Execute:**
  ```bash
  rish -c "<command>"
  ```
- **When to Use `rish`:**
  1. **Filesystem Access:** Read, write, or copy files in protected Android directories or shared storage blocked by app sandbox permissions:
     ```bash
     rish -c "ls -la /storage/emulated/0/Android/data"
     rish -c "cp <src> <dest>"
     ```
  2. **APK & Package Management (`pm`):**
     ```bash
     rish -c "pm install -r /storage/emulated/0/.../app.apk"
     rish -c "pm list packages -3"
     rish -c "pm uninstall com.example.app"
     ```
  3. **Activity Management & Diagnostics (`am`, `logcat`, `dumpsys`):**
     ```bash
     rish -c "am start -n com.example.app/.MainActivity"
     rish -c "logcat -d -t 150"
     rish -c "dumpsys package com.example.app"
     ```
  4. **System Properties & Settings:**
     ```bash
     rish -c "getprop ro.build.version.release"
     rish -c "settings get global airplane_mode_on"
     ```

---

## 5. Development & Server Guidelines

- **Port Binding:** Local development servers (Vite, Next.js, Express, FastAPI) MUST bind to `localhost` or `127.0.0.1` on ports such as `3000`, `5173`, `8000`, `8080`. Avoid ports `45157` and `45158` (reserved for Antigravity core).
- **Compilation:** When compiling native C/C++/Rust code, target `-march=armv8.1-a` (or higher) to leverage native LSE atomics.

---

## 6. Background Daemon & Android Notifications

Antigravity includes an ultra-lightweight background scheduler and native notification CLI:

- **Notifications (`agy-notify`):**
  Post, list, or clear Android status notifications from the terminal:
  ```bash
  # Send an alert to user notification tray:
  agy-notify post -t "Build Finished" -m "Tests passed without errors"

  # Inspect active notifications:
  agy-notify list
  ```

- **Autonomous Background Daemon (`agy-daemon`):**
  Enables delayed, interval, and event-based triggers that continue executing even when the screen is turned off:
  ```bash
  # Schedule task after duration (e.g. 4h, 30m, 10s):
  agy-daemon add --name "Nightly Backup" --delay 4h --command "tar -czf ~/backup.tar.gz ~/Documents"

  # Run periodically:
  agy-daemon add --name "Disk Health Check" --interval 30m --command "df -h > ~/.gemini/disk.log"

  # Watch GitHub repo for new PRs:
  agy-daemon add --name "Watch PRs" --github-pr "werdio325-png/antigravity-android" --interval 5m --command "agy-notify post -t 'GitHub Alert' -m 'New Pull Request detected'"

  # List active background tasks:
  agy-daemon list
  ```
