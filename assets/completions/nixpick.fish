# Complétion fish pour nixpick.
# Installation : copie dans ~/.config/fish/completions/nixpick.fish.
# Synchro avec le CLI testée par tests/test_completions.py.

# Sous-commandes.
complete -c nixpick -f -n __fish_use_subcommand -a doctor -d "vérifie config, cache, outils, Git flake et flake.lock"
complete -c nixpick -f -n __fish_use_subcommand -a rebuild -d "lance la commande rebuild configurée"
complete -c nixpick -f -n __fish_use_subcommand -a fix-git -d "git add les fichiers non suivis du dépôt flake"
complete -c nixpick -f -n __fish_use_subcommand -a sync -d "installe dans le profil les paquets listés mais absents"

# Options globales (avant toute sous-commande).
complete -c nixpick -f -n __fish_use_subcommand -l version -d "affiche la version"
complete -c nixpick -f -n __fish_use_subcommand -l print-config -d "affiche le fichier cible et la commande rebuild"
complete -c nixpick -f -n __fish_use_subcommand -l refresh -d "reconstruit l'index nixpkgs au démarrage"
complete -c nixpick -f -n __fish_use_subcommand -l dry-run -d "simulation : n'écrit pas dans packages.nix"
complete -c nixpick -f -n __fish_use_subcommand -l transparent -d "TUI : fond transparent"
complete -c nixpick -f -n __fish_use_subcommand -l opaque -d "TUI : fond opaque"
complete -c nixpick -f -n __fish_use_subcommand -l tui -d "force la TUI même avec un terme"
complete -c nixpick -f -n __fish_use_subcommand -l rofi -d "recherche via Rofi"
complete -c nixpick -f -n __fish_use_subcommand -l build-index-only -d "reconstruit l'index puis quitte"
complete -c nixpick -f -n __fish_use_subcommand -l remove -d "retire un paquet (avec le terme CLI)"
complete -c nixpick -f -n __fish_use_subcommand -l list-installed -d "liste les attributs déjà présents"
complete -c nixpick -f -n __fish_use_subcommand -l json -d "avec --list-installed : sortie JSON"
complete -c nixpick -f -n __fish_use_subcommand -l undo -d "restaure packages.nix depuis la dernière sauvegarde"
complete -c nixpick -f -n __fish_use_subcommand -l why -r -d "dit si un attribut est dans packages.nix"
complete -c nixpick -f -n __fish_use_subcommand -l print -r -d "affiche le meilleur attr sur stdout"
complete -c nixpick -f -n __fish_use_subcommand -s h -l help -d "affiche l'aide"

# Options par sous-commande.
complete -c nixpick -f -n "__fish_seen_subcommand_from doctor" -l json -d "sortie JSON"
complete -c nixpick -f -n "__fish_seen_subcommand_from doctor" -s h -l help -d "affiche l'aide"
complete -c nixpick -f -n "__fish_seen_subcommand_from rebuild" -s y -l yes -d "sans demander confirmation"
complete -c nixpick -f -n "__fish_seen_subcommand_from rebuild" -l terminal -d "ouvre un émulateur pour sudo / la sortie"
complete -c nixpick -f -n "__fish_seen_subcommand_from rebuild" -l dry-run -d "affiche la commande sans l'exécuter"
complete -c nixpick -f -n "__fish_seen_subcommand_from rebuild" -s h -l help -d "affiche l'aide"
complete -c nixpick -f -n "__fish_seen_subcommand_from fix-git" -s y -l yes -d "sans demander confirmation"
complete -c nixpick -f -n "__fish_seen_subcommand_from fix-git" -l dry-run -d "affiche la commande git sans l'exécuter"
complete -c nixpick -f -n "__fish_seen_subcommand_from fix-git" -s h -l help -d "affiche l'aide"
complete -c nixpick -f -n "__fish_seen_subcommand_from sync" -s y -l yes -d "sans demander confirmation"
complete -c nixpick -f -n "__fish_seen_subcommand_from sync" -l dry-run -d "affiche la commande nix sans l'exécuter"
complete -c nixpick -f -n "__fish_seen_subcommand_from sync" -l upgrade -d "met aussi à jour les listés déjà installés"
complete -c nixpick -f -n "__fish_seen_subcommand_from sync" -s h -l help -d "affiche l'aide"
