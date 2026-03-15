#!/bin/bash
# Override the default sudoers entry to allow passwordless sudo
# This runs after the container's built-in init which sets "admin ALL=(ALL) ALL"
sed -i 's/^admin ALL=(ALL) ALL$/admin ALL=(ALL) NOPASSWD: ALL/' /etc/sudoers
