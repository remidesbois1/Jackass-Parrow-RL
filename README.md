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

## Crédits

*   **Tristan Sauvage :** Développeur
*   **Rémi Semenzin :** Développeur
