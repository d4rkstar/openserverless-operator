#!/bin/bash
# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.
#
cd $HOME
sudo apt-get -y install curl wget jq
# ensure local bin exists and is on PATH for this script
mkdir -p "$HOME/.local/bin"
export PATH="$HOME/.local/bin:$PATH"

# persist PATH for future interactive shells (append only if missing)
if ! grep -q "\$HOME/.local/bin" "$HOME/.profile" 2>/dev/null; then
    echo "export PATH=\"\$HOME/.local/bin:\$PATH\"" >> "$HOME/.profile"
fi

if [ -n "$ZSH_VERSION" ] && ! grep -q "\$HOME/.local/bin" "$HOME/.zshrc" 2>/dev/null; then
    echo "export PATH=\"\$HOME/.local/bin:\$PATH\"" >> "$HOME/.zshrc"
fi

# add ops bin (~/.ops/<os>-<arch>/bin). os is uname -s lowercase, map common arch names
os="$(uname -s | tr '[:upper:]' '[:lower:]')"
arch="$(uname -m)"
case "$arch" in
    x86_64) arch=amd64 ;;
    aarch64|arm64) arch=arm64 ;;
    armv7l) arch=armv7 ;;
    i386|i686) arch=386 ;;
esac
resolved_ops_bin="$HOME/.ops/${os}-${arch}/bin"
if [ -d "$resolved_ops_bin" ]; then
        export PATH="$resolved_ops_bin:$PATH"
        if ! grep -qF "$resolved_ops_bin" "$HOME/.profile" 2>/dev/null; then
                echo "export PATH=\"$resolved_ops_bin:\$PATH\"" >> "$HOME/.profile"
        fi
        if [ -n "$ZSH_VERSION" ] && ! grep -qF "$resolved_ops_bin" "$HOME/.zshrc" 2>/dev/null; then
                echo "export PATH=\"$resolved_ops_bin:\$PATH\"" >> "$HOME/.zshrc"
        fi
fi

echo "OPS BIN PATH IS $resolved_ops_bin"
echo "PATH IS $PATH"

# install ops, wsk wrapper and task
VER="0.1.0-2501041342.dev";\
URL="https://raw.githubusercontent.com/apache/openserverless-cli/refs/tags/v$VER/install.sh" ;\
curl -sL $URL | VERSION="$VER" bash ;\
echo -e '#!/bin/bash\nops -wsk "$@"' >$HOME/.local/bin/wsk ; chmod +x $HOME/.local/bin/wsk ;\
curl -sL https://taskfile.dev/install.sh | sh -s -- -d -b $HOME/.local/bin; \
echo "TASK IS: $(which task)"; \
task --version && 
ops -t && ls -lah $resolved_ops_bin
