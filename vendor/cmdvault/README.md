# CmdVault resource and upstream source

`cmdvault.png` is bundled **byte for byte** from shS83/cmdvault/root
(Git blob SHA1: `8cd4b766f396b2621de73e9d3f1aeb0d44b77d2b`).
This is the Kitty logo used by upstream CmdVault.

The rest of CmdVault is installed from a full checkout (`~/Code/cmdvault`),
from `--source cmdvault=...`, or from the GitHub root branch when no local
source is available. The installer uses upstream's install.sh to install
all visuals, security and sync modules, avoiding the broken standalone binary.
If a local checkout has no cmdvault.png, it is staged into a temporary
copy with this exact asset so the source checkout stays untouched.
