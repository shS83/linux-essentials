
#!/usr/bin/env bash
set -euo pipefail

SRC_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
MACHINE="${HOSTNAME%%.*}"
REPO_NAME="dotfiles-sync-${MACHINE}"
REPO="$HOME/.${REPO_NAME}.git"
SYSTEMD_DIR="$HOME/.config/systemd/user"

echo "==> Installing dotfiles-sync"

# Install the executable and user units.
sudo install -Dm755 "$SRC_DIR/dotfiles-sync" /Tools/dotfiles-sync
install -Dm644 "$SRC_DIR/dotfiles-sync.service" "$SYSTEMD_DIR/dotfiles-sync.service"
install -Dm644 "$SRC_DIR/dotfiles-sync.timer" "$SYSTEMD_DIR/dotfiles-sync.timer"

# Use HOME as the worktree without putting .git inside HOME.
if [[ ! -d "$REPO" ]]; then
	git init --bare --initial-branch=main "$REPO"

	echo "==> Created local repository: $REPO"
elif [[ "$(git --git-dir="$REPO" rev-parse --is-bare-repository 2>/dev/null || true)" != true ]]; then
	echo "ERROR: $REPO exists but is not a bare Git repository" >&2
	exit 1
fi

git --git-dir="$REPO" config status.showUntrackedFiles no

# Don't automatically stage the user's entire home directory.
# Existing tracked files remain trackable; new paths need 'git add -f'.
EXCLUDE_FILE="$REPO/info/exclude"
if ! grep -Fxq '/*' "$EXCLUDE_FILE" 2>/dev/null; then
	printf '\n# dotfiles-sync: ignore all new HOME paths by default\n/*\n' >> "$EXCLUDE_FILE"
fi

publish_to_github() {
	if ! command -v gh >/dev/null 2>&1; then
		echo "==> gh not found; skipping GitHub publication"
		return 0
	fi
	if ! gh auth status >/dev/null 2>&1; then
		echo "==> gh is not authenticated; skipping GitHub publication"
		return 0
	fi

	local owner response remote branch author_name author_email
	if ! owner="$(gh api user --jq '.login' 2>/dev/null)" || [[ -z "$owner" ]]; then
		echo "WARNING: Could not determine GitHub account; skipping publication" >&2
		return 0
	fi

	# Don't interpret network/authentication errors as 'repository missing'.
	if response="$(gh api -i "repos/$owner/$REPO_NAME" 2>&1)"; then
		echo "==> GitHub repository already exists: $owner/$REPO_NAME"
		local created=false
	elif [[ "$response" == *'HTTP 404'* || "$response" =~ HTTP/[0-9.]+[[:space:]]+404 ]]; then
		echo "==> Creating private GitHub repository: $owner/$REPO_NAME"
		if ! gh repo create "$owner/$REPO_NAME" --private \
			--description "Dotfiles backup for $MACHINE"; then
			echo "WARNING: GitHub repository creation failed" >&2
			return 0
		fi
		local created=true
	else
		echo "WARNING: GitHub query failed; not creating a repository" >&2
		return 0
	fi

	remote="git@github.com:$owner/$REPO_NAME.git"
	if git --git-dir="$REPO" remote get-url origin >/dev/null 2>&1; then
		if [[ "$(git --git-dir="$REPO" remote get-url origin)" != "$remote" ]]; then
			echo "WARNING: origin points elsewhere; leaving it unchanged" >&2
			return 0
		fi
	else
		git --git-dir="$REPO" remote add origin "$remote"
	fi

	if [[ "$created" == true ]]; then
		# A new bare repository has no commit yet. Publish an empty baseline
		# instead of staging HOME (which can contain private keys and tokens).
		if ! git --git-dir="$REPO" rev-parse --verify HEAD >/dev/null 2>&1; then
			author_name="$(git config user.name || true)"
			author_email="$(git config user.email || true)"
			[[ -n "$author_name" ]] || author_name="$owner"
			[[ -n "$author_email" ]] || author_email="$owner@users.noreply.github.com"
			git -c user.name="$author_name" -c user.email="$author_email" \
				-c commit.gpgsign=false --git-dir="$REPO" --work-tree="$HOME" \
				commit --allow-empty -m "Initialize $REPO_NAME"
		fi
		branch="$(git --git-dir="$REPO" symbolic-ref --quiet --short HEAD)"
		if git --git-dir="$REPO" push -u origin "$branch"; then
			echo "==> Published: https://github.com/$owner/$REPO_NAME"
		else
			echo "WARNING: Repository created, but git push failed" >&2
		fi
	fi
}

publish_to_github

systemctl --user daemon-reload
systemctl --user enable --now dotfiles-sync.timer

echo "==> Installation completed"
echo "Local repo: $REPO"
echo "Timer: systemctl --user status dotfiles-sync.timer"
