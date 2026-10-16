# CPROJ Bash integration. Source from ~/.bashrc (do not execute it).
# Directory changes and venv activation must happen in the current shell.

_cproj_sync_venv() {
    local project=$1
    local config_file="${XDG_CONFIG_HOME:-$HOME/.config}/cproj/cproj.conf"
    local CPROJ_AUTO_VENV=1
    # The configuration uses Bash syntax; localize its known variables so
    # reading it does not alter project-search settings in the user's shell.
    local -a CPROJ_ROOTS=()
    local CPROJ_MAX_DEPTH CPROJ_CACHE_TTL CPROJ_PREVIEW_LINES

    if [[ -f $config_file ]]; then
        # This is a trusted, user-owned Bash config file.
        if ! source "$config_file"; then
            printf 'CPROJ: Unable to read venv configuration: %s\n' "$config_file" >&2
            return 1
        fi
    fi

    case $CPROJ_AUTO_VENV in
        0) return 0 ;; # Do not alter the current virtual environment.
        1) ;;
        *) printf 'CPROJ: CPROJ_AUTO_VENV must be 0 or 1.\n' >&2; return 1 ;;
    esac

    local target="$project/.venv"
    if [[ -f $target/bin/activate ]]; then
        # Do not reactivate a venv that is already active. Normalize paths
        # because VIRTUAL_ENV and the discovered project may contain symlinks.
        if [[ -n ${VIRTUAL_ENV:-} ]]; then
            local active_real target_real
            active_real=$(realpath -m -- "$VIRTUAL_ENV")
            target_real=$(realpath -m -- "$target")
            [[ $active_real == "$target_real" ]] && return 0
        fi

        # Preserve the user's custom PS1 (Bash's venv normally prepends a name).
        # Local variable affects sourcing but does not persist in their shell.
        local VIRTUAL_ENV_DISABLE_PROMPT=${VIRTUAL_ENV_DISABLE_PROMPT:-1}
        # Python/uv venv's activate script handles deactivating any old venv.
        if ! source "$target/bin/activate"; then
            printf 'CPROJ: Could not activate %s\n' "$target" >&2
            return 1
        fi
    elif [[ -n ${VIRTUAL_ENV:-} ]]; then
        # Leaving Python projects for a project without .venv.
        if declare -F deactivate >/dev/null; then
            deactivate
        else
            printf 'CPROJ: VIRTUAL_ENV is set but no deactivate function exists.\n' >&2
            return 1
        fi
    fi
}

cproj() {
    case ${1:-} in
        --help|-h|--version|-V|--list|--refresh|--add|--config)
            command cproj "$@"
            return $?
            ;;
    esac

    local destination
    destination=$(command cproj "$@") || return $?
    [[ -n $destination && -d $destination ]] || {
        printf 'CPROJ: Selected directory is unavailable.\n' >&2
        return 1
    }

    builtin cd -- "$destination" || return $?

    # Ensure history records navigation even if activating .venv fails.
    command cproj --record "$PWD" >/dev/null 2>&1 || true
    _cproj_sync_venv "$PWD"
}
