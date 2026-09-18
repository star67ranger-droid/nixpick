# nixpick

Chercher un paquet nixpkgs et l'ajouter à ma configuration NixOS, sans ouvrir de
fichier ni deviner le bon nom d'attribut.

## Installation (une fois)

```bash
cd ~/Projets/nixpick
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

## Commande `nixpick`

Deux façons d'avoir la commande **`nixpick`** partout (sans `./nixpick.py`) :

1. **Immédiat** — lien dans ton PATH (déjà fait si tu as suivi l'install) :
   ```bash
   chmod +x ~/Projets/nixpick/bin/nixpick
   ln -sf ~/Projets/nixpick/bin/nixpick ~/.local/bin/nixpick
   ```
   Puis ouvre un nouveau terminal et tape `nixpick`.

2. **NixOS** — entrée dans `environment.systemPackages` (dans `modules/packages.nix`), puis :
   ```bash
   sudo nixos-rebuild switch --flake /etc/nixos#nixos
   ```
   Même commande, même après reboot, pour tous les shells.

## Lancer

| Commande | Effet |
| :--- | :--- |
| `nixpick` | **TUI** (recherche live, panneau détail, modale de confirmation) |
| `nixpick firefox` | mode CLI rapide (comme avant) |
| `./nixpick.py --dry-run` | TUI en simulation |
| `./nixpick.py --refresh` | TUI, index reconstruit au démarrage |
| `./nixpick.py --transparent` | TUI avec fond transparent |
| `./nixpick.py --opaque` | TUI avec fond opaque |

Au **premier lancement**, si tu n'as pas encore de config nixpick, l'outil reprend
`transparent_background` de superfile (`~/.config/superfile/config.toml`) — chez toi
c'est déjà `true`.

### Raccourcis TUI (lazygit / fzf)

- `/` ou `Ctrl+U` — focus recherche
- `j` / `k` — naviguer
- `Entrée` — ajouter (modale avec aperçu du diff, `y` pour confirmer)
- `d` — basculer mode simulation
- `t` — fond transparent (comme superfile, mémorisé dans `~/.config/nixpick/config.toml`)
- `r` — reconstruire l'index
- `?` — aide
- `q` — quitter

Les paquets déjà dans `environment.systemPackages` sont marqués `✓` en jaune.

## Mode CLI

```
$ ./nixpick.py obsidian

   1. obsidian 1.13.4
      Powerful knowledge base that works on top of a local folder of plain t
   2. obsidian-export 25.3.0
      Rust library and CLI to export an Obsidian vault to regular Markdown
   3. rofi-obsidian 0.1.5
      Launch your Obsidian vaults from the comfort of rofi

Lequel ? [1-12, Entrée pour annuler] 1

Modification prévue dans /etc/nixos/modules/packages.nix :
    networkmanagerapplet
    upower
  + obsidian  # Powerful knowledge base that works on top of a…

J'écris ? [o/N]
```

## Pourquoi cet outil existe

Installer une application sous NixOS demande de connaître le nom exact de
l'attribut, d'ouvrir le bon module, de l'ajouter au bon endroit, puis de
rebuild. `nixpick` fait les trois premières étapes et rappelle la quatrième.

## Le problème technique à résoudre : la lenteur

Trois façons d'interroger nixpkgs, mesurées sur cette machine :

| Méthode | Temps | Verdict |
| :--- | :--- | :--- |
| `nix search nixpkgs <terme>` | plus de 25 s, **à chaque appel** | inutilisable |
| `nix-env -qaP --json --meta` | plus de 10 min | inutilisable |
| `nix-env -qaP --json` | ~21 s, **une seule fois** | retenu pour l'index |
| `nix eval` sur 12 paquets | ~0,3 s | retenu pour les descriptions |

D'où l'architecture : un index complet **sans** description, construit une fois
et gardé en cache dans `~/.cache/nixpick/`, qui rend la recherche instantanée et
utilisable hors ligne. Les descriptions ne sont demandées que pour les douze
résultats affichés, en un seul appel.

C'est le cœur du projet : sans ce découpage, une barre de recherche interactive
est impossible.

## Utilisation

```bash
nixpick.py <terme>          # cherche, propose, ajoute après confirmation
nixpick.py --dry-run <t>    # montre la modification sans l'écrire
nixpick.py --refresh        # reconstruit l'index (à faire après un gros update)
```

L'index se reconstruit tout seul au bout de 7 jours.

## Garde-fous

- **Rien n'est appliqué automatiquement.** L'outil modifie le fichier et
  s'arrête là. Le `nixos-rebuild switch` reste une décision manuelle, parce
  qu'un switch commit *et pousse* tout `/etc/nixos` sur `origin/main`
  (cf. `/etc/nixos/AGENTS.md`). Le déclencher sans prévenir serait une
  mauvaise surprise.
- **Une sauvegarde est écrite** dans `packages.nix.bak` avant toute
  modification. Pour annuler :
  `cp /etc/nixos/modules/packages.nix.bak /etc/nixos/modules/packages.nix`
- **Les doublons sont détectés** : un paquet déjà présent n'est pas rajouté.
- **L'indentation du fichier est respectée**, elle est relevée sur les entrées
  existantes plutôt que codée en dur.

## Limites connues

- **Les paquets activés par une option ne sont pas détectés.** Firefox est chez
  moi dans `programs.firefox.enable = true`, pas dans `systemPackages` :
  `nixpick firefox` le proposera quand même. Sans conséquence grave, mais à
  traiter en même temps que la gestion des options.
- **Seul `modules/packages.nix` est visé.** Les paquets issus de flakes
  (`modules/steam-spicetify.nix`) ne sont ni lus ni écrits.
- **Pas de `home-manager`** : je n'en utilise pas.

## Ce qui existe déjà, et pourquoi ce projet garde du sens

[`nix-software-center`](https://github.com/snowfallorg/nix-software-center) de
Vlinkz fait la même chose en GTK4/libadwaita. Deux raisons de ne pas s'arrêter
là :

1. Il écrit dans `configuration.nix`, pas dans une configuration **modulaire**
   comme la mienne, où les paquets vivent dans `modules/packages.nix`.
2. C'est une application GNOME, alors que je suis sous **Hyprland avec le shell
   Noctalia**. L'interface naturelle ici n'est pas une fenêtre GTK, c'est le
   lanceur d'applications.

## Prochaine étape

Brancher ce moteur sur un lanceur (wofi, rofi, fuzzel, ou directement le lanceur
de Noctalia) : on tape le nom d'une app dans la barre de recherche habituelle et
elle s'ajoute à la config. C'est l'idée de départ, et le moteur est prêt.

Ensuite, éventuellement : gérer aussi les options NixOS, pas seulement les
paquets.
