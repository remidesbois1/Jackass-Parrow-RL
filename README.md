## La Team Bambou présente

# Jackass-Parrow

**Par Tristan Sauvage et Rémi Semenzin pour la GameJam 3**

**Thème :** Pirates et Chevaliers (et une poule qui court)

## Histoire

Quand il était jeune, Jackass-Parrow n'était pas le pirate le plus agile du navire.
C'est pour cela que ses parents lui ont greffé un canon scié sur l'arrière-train en guise de cadeau d'anniversaire.
Malheureusement, celui-ci fut exclu de sa fratrie lorsqu'il tira accidentellement dans la tête de son père en voulant s'étirer.
Jackass-Parrow passa donc le reste de son enfance dans une jungle, élevé par une tribu indigène.

Aujourd'hui, menacé par Tom de l'Abbaye et ses chevaliers, Jackass-Parrow est prêt à tout pour défendre ceux qui l'ont recueilli.
## Commandes

*   **Z ou ↑ :** Sauter
*   **Q ou ← :** Aller à gauche
*   **S ou ↓ (au sol) :** Parer (Bouclier)
*   **S ou ↓ (dans les air) :** Descente rapide
*   **D ou → :** Aller à droite
*   **Espace :** Tirer avec le fusil à canon scié arrière !

## Gameplay

Jackass-Parrow est un jeu de plateforme 2D où vous devez défendre votre territoire contre le maléfique Tom de l'Abbaye. Vous pouvez éliminer vos ennemis en leur tirant dessus avec votre fusil à canon scié arrière. Mais attention, Tom, malin comme il est, a envoyé ses meilleurs chevaliers et des poules kamikazes pour vous arrêter ! Heureusement, vous pouvez parer leurs attaques avec votre bouclier.

Arrivera un moment où vous devrez combattre Tom lui-même. Il est très fort et saura vous mettre à l'épreuve. Utilisez toutes vos compétences pour le vaincre et sauver votre foyer de cet être infâme.

La difficulté est croissante à chaque niveau, et une fois Tom vaincu, elle deviendra encore plus extrême.

Une fois la partie terminée, pensez à enregistrer votre score ! 

## Conseils des développeurs pour les profs ayant des doigts peu agiles
* Lorsqu'un projectile vous arrive dessus, privilégiez le bouclier pour vous défendre.
* Les tirs du joueur avancent à l'infini. Profitez de la distance et tirez à la hauteur maximale de votre saut pour annihiler les ennemis éloignés.
* Essayez d'utiliser un maximum la descente rapide, car vous êtes vulnérable dans les airs.
* À la fin du combat, Tom de l'Abbaye tire très vite. Restez caché derrière votre bouclier et attendez le bon moment pour lui asséner le coup fatal.

## Mode headless (simulation sans affichage)

Le mode headless permet d'exécuter de nombreuses parties en parallèle sans
Pygame, sons ni chargement d'images. Il prépare une future intégration IA ;
aucun entraînement n'est lancé.

```powershell
.\.venv\Scripts\python.exe main.py --headless --envs 256 --workers 8 --steps 5000
```

API Python : `HeadlessEnv`, `BatchEnv`, actions combinables, graines
reproductibles, `reset` / `step` et chemin rapide `advance`.
Voir [la documentation headless](doc/headless.md) pour les mesures,
les observations, les options et les différences avec le jeu graphique.

## Regarder l'IA entraînée (prête à l'emploi)

La branche `withhardlevels` contient un modèle déjà entraîné, `models/hard-v1/`,
sur le jeu complet : boucle jungle, Tom, puis boucles suivantes sur les tableaux
HARD (fond rouge). Sur un autre PC, avec [uv](https://docs.astral.sh/uv/) installé :

```powershell
git clone https://github.com/remidesbois1/Jackass-Parrow-RL.git
cd Jackass-Parrow-RL
git checkout withhardlevels
uv sync --extra train
.\.venv\Scripts\python.exe main.py --watch --model models/hard-v1/model.pt --config models/hard-v1/config.json
```

`uv sync --extra train` installe Python, Pygame, Gymnasium et PyTorch (version
CPU, aucun GPU n'est nécessaire pour regarder). Sous Linux/macOS, remplacer
`.\.venv\Scripts\python.exe` par `.venv/bin/python`. La partie se termine
uniquement à la mort de l'IA.

Espace met en pause, les flèches règlent la vitesse (jusqu'à ×8), R rejoue,
N change de partie, Tab alterne actions déterministes et échantillonnées,
Échap ferme la fenêtre. Résultats, réentraînement et reprise sur GPU :
[models/hard-v1/README.md](models/hard-v1/README.md).

## Gymnasium et apprentissage par renforcement

Un adaptateur optionnel expose les environnements Gymnasium du jeu, avec actions
simultanées et observations numériques. Le [guide RL](doc/rl.md) détaille
l'installation, les récompenses, l'entraînement PPO avec Stable-Baselines3 et
l'entraînement rapide vectorisé sur CPU ou GPU (`examples.train_vector`).

```powershell
uv sync --extra train
.\.venv\Scripts\python.exe -m examples.train_ppo --check-only
```

Cette vérification ne lance aucun apprentissage. Les commandes pour entraîner
et évaluer toi-même un agent sont dans le guide.

## Crédits

*   **Tristan Sauvage :** Développeur
*   **Rémi Semenzin :** Développeur
