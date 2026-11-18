# Upstream sources verified on 2026-11-18

The `--latest` command clones the listed branch of these repositories and logs
the actual checked-out commit before installation. This table records the
branch tip observed when Linux Essentials v0.5.0 was assembled; it is **not**
a version lock. `--latest` may fetch newer commits on later dates.

| Tool | Repository | Branch | Verified SHA |
| --- | --- | --- | --- |
| CPROJ | shS83/cproj | root | e17ce7149e23453f8719fffd9b037127ea239676 |
| CmdVault | shS83/cmdvault | root | 6e24abbc13891a7e827fab2eb902645103a7701d |
| NADAR | shS83/nadar | root | e353767fae0a119148208bfcd08556d5bcd5898f |
| SRVPULSE | shS83/srvpulse | root | 53b869174e9c71ab35c086a22fbad3f6b370bcee |
| GitPublish | shS83/git-publish | main | cf45abb389754a22cc77e210361ebdfcc5966b2b |
| Cmedia | shS83/cmedia | root | 61f0d4c6ed5c41e76f5e3679c6eef88eb834ec1c |
| dotfiles-sync | shS83/dotfiles-sync | root | d538b8bbec45dd8fa347e9b90f26790028cc2982 |
| Clipvault | shS83/Clipvault | root | d2cc40f393eb8db7a89a13b28962d03f72f9287e |

The bundled Clipvault GUI is the 2026-11-16 statusbar fix from the user's
previous package. The bundled dotfiles-sync launcher corrects the upstream
bare-repository usage and uses a user-local systemd unit. Source snapshots
outside `vendor/clipvault/` may be older than the branch heads above;
`--latest` is the supported full refresh mode.

Do not run this bootstrap as root, and review source changes and commit history
before rolling out latest versions across important computers.
