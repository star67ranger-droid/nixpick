# Complétion bash pour nixpick.
# Installation : `source assets/completions/nixpick.bash`
# (ou copie dans ~/.local/share/bash-completion/completions/nixpick).
# Synchro avec le CLI testée par tests/test_completions.py.
_nixpick() {
    local cur prev sub w
    COMPREPLY=()
    cur="${COMP_WORDS[COMP_CWORD]}"
    prev="${COMP_WORDS[COMP_CWORD-1]}"

    local cmds="doctor rebuild fix-git sync"
    local global_opts="--version --print-config --refresh --dry-run --transparent --opaque --tui --rofi --build-index-only --remove --list-installed --json --undo --why -h --help"

    # Les options à valeur n'appellent aucune complétion.
    if [[ "$prev" == "--why" ]]; then
        return 0
    fi

    # Repère une sous-commande déjà saisie.
    sub=""
    for w in "${COMP_WORDS[@]:1}"; do
        case "$w" in
            doctor|rebuild|fix-git|sync) sub="$w"; break ;;
        esac
    done

    local opts=""
    case "$sub" in
        doctor) opts="--json -h --help" ;;
        rebuild) opts="-y --yes --terminal --dry-run -h --help" ;;
        fix-git) opts="-y --yes --dry-run -h --help" ;;
        sync) opts="-y --yes --dry-run -h --help" ;;
        *) opts="$cmds $global_opts" ;;
    esac
    # shellcheck disable=SC2207
    COMPREPLY=($(compgen -W "$opts" -- "$cur"))
    return 0
}
complete -F _nixpick nixpick
