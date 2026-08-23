#!/bin/sh
# Install VS Code extensions (idempotent), then launch code-server.
code-server --install-extension ms-python.python
code-server --install-extension redhat.ansible
# containerlab extension — present on Open VSX at time of writing;
# if not, install the VSIX manually (docs/host-and-toolchain.md)
code-server --install-extension srl-labs.vscode-containerlab || \
  echo "NOTE: containerlab extension not found in registry — install VSIX manually"

exec code-server --bind-addr 0.0.0.0:8080 --auth password /opt/branch-as-code
