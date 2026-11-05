# Gymnasium et premier apprentissage par renforcement

L'intégration est disponible dans `src/rl`. Elle réutilise la physique headless.
L'interface Gymnasium et les exemples d'entraînement sont optionnels :
`python main.py --headless ...` n'importe ni Gymnasium, ni NumPy, ni PyTorch.
Installer les bibliothèques ne lance aucun entraînement.

## Installer et vérifier

Depuis la racine du dépôt :

```powershell
# Adaptateur Gymnasium seulement :
uv sync --extra rl

# Pour entraîner toi-même avec PPO et consulter TensorBoard :
uv sync --extra train

# Vérifie le contrat Gymnasium et Stable-Baselines3, sans apprentissage :
.\.venv\Scripts\python.exe -m examples.train_ppo --check-only
```

Si `uv` n'est pas dans le PATH de PowerShell, l'installation locale utilisée ici
est accessible par `& "$env:USERPROFILE\.local\bin\uv.exe" sync --extra train`.
Le fichier `uv.lock` fixe les versions résolues. L'intégration a été vérifiée
avec Gymnasium 1.4.0, NumPy 2.5.4, Stable-Baselines3 2.9.0 et PyTorch 2.14.1,
sous Python 3.13 / Windows. Un simple `uv sync` retire les extras non demandés ;
utiliser `--extra train` lorsque tu veux garder l'environnement d'entraînement.

## Utiliser l'environnement

```python
import gymnasium as gym
import src.rl  # enregistre JackassParrow-v0

env = gym.make("JackassParrow-v0", frame_skip=4, episode_limit=9000)
try:
    observation, info = env.reset(seed=42)
    observation, reward, terminated, truncated, info = env.step([2, 1, 0, 1])
finally:
    env.close()
```

L'action `[2, 1, 0, 1]` signifie droite + saut + tir. L'espace
`MultiDiscrete([3, 2, 2, 2])` contient quatre commandes :

| Index | Commande | Valeurs |
| --- | --- | --- |
| 0 | Déplacement | 0 immobile, 1 gauche, 2 droite |
| 1 | Saut | 0 non, 1 oui |
| 2 | Parade / chute rapide | 0 non, 1 oui |
| 3 | Tir | 0 non, 1 oui |

Une commande est maintenue pendant `frame_skip` ticks de physique à 60 Hz.
Avec 4, l'agent choisit donc jusqu'à **15 actions par seconde simulée**. Une mort
peut arrêter ces quatre ticks plus tôt. Le tir part à l'opposé du regard, comme
dans le jeu ; le recul est conservé. Il faut apprendre cette mécanique.

L'adaptateur utilise `episode_limit` pour configurer la limite interne de
décisions du moteur. `9000 × 4 / 60 = 600` secondes simulées au maximum. Le
paramètre réservé `max_episode_steps` de `gym.make` ajoute éventuellement un
`TimeLimit` extérieur ; il ne remplace pas cette limite interne. Pour une autre
durée, utiliser `episode_limit`, ou `episode_limit=None` avec un `TimeLimit`.

`terminated` signale la mort, ou la victoire en mode boss seul. `truncated`
signale une limite de durée. L'adaptateur simple exige un reset explicite après
la fin. Les enveloppes vectorielles des bibliothèques peuvent automatiser ce
reset et exposer autrement l'observation finale : suivre leur contrat d'API.
Les modes `render_mode="human"` (fenêtre) et `render_mode="rgb_array"` (tableau
RGB de forme 800 × 1280 × 3) affichent le moteur headless avec les graphismes du
jeu. Le rendu est chargé à la demande : un environnement sans rendu n'importe
toujours pas Pygame. Les animations ne modifient ni la physique, ni les délais,
ni le RNG. L'exemple d'évaluation reste numérique ; le spectateur ci-dessous
permet de regarder le modèle jouer.

## Ce que voit l'IA

L'observation est un vecteur de **454 valeurs `float32`** (1816 octets de données),
de taille fixe, compatible avec `MlpPolicy`. Elle décrit directement les objets
du jeu ; elle ne contient pas de captures d'écran. Les coordonnées x/largeurs
sont divisées par 1280 et les coordonnées y/hauteurs par 800. Les vitesses sont
ramenées à une échelle comparable. Le vecteur est borné entre -10 et 10 ; les
valeurs inhabituelles hors de cette plage sont saturées. Cela représente une
observation numérique privilégiée du simulateur, pas la vision d'un joueur.

Les entités absentes ont une ligne à zéro, avec un masque de présence en première
colonne. L'ordre des entités suit celui du moteur. Si une capacité est dépassée,
les entités les plus proches du joueur sont gardées ; les nombres omis figurent
dans `info["observation_overflow"]`. Ce choix rend alors l'observation partielle.

| Segment | Taille | Champs |
| --- | --- | --- |
| `player` | 13 | x, y, largeur, hauteur, vitesse / 400, vitesse verticale / 1250, recul / 1500, direction, PV / 3, au sol, bouclier, délai de tir, invulnérabilité |
| `context` | 6 | monde / (monde+1), tableau / 7, id géométrie / 10, danger / (danger+1), fraction de décisions restantes, mode boss |
| `enemies` | 8 × 10 | présence, x, y, largeur, hauteur, type / 2, direction, âge du dernier tir / 2,2 s (maximum 1), bord gauche et droit de la plateforme |
| `blocks` | 16 × 6 | présence, x, y, largeur, hauteur, transparence aux tirs |
| `bullets` | 8 × 6 | présence, x, y, largeur, hauteur, vitesse / 600 |
| `enemy_bullets` | 32 × 6 | même format |
| `boss` | 9 | présence, x, y, largeur, hauteur, PV / 10, trou / 2, invulnérabilité, délai de tir |
| `boss_shields` | 2 × 5 | présence, x, y, largeur, hauteur |

Les délais du joueur et du boss sont en secondes, calculés avec la comparaison
stricte du moteur : un tir avec un délai d'une seconde devient disponible au
tick 61. Les snapshots sont indépendants : une étape suivante ne modifie pas
une observation déjà récupérée.

Pour examiner une partie du vecteur :

```python
from src.rl.observations import OBSERVATION_SLICES, OBSERVATION_SHAPES

enemies = observation[OBSERVATION_SLICES["enemies"]].reshape(OBSERVATION_SHAPES["enemies"])
present_enemies = enemies[enemies[:, 0] == 1]
```

Le schéma est versionné par l'identifiant `JackassParrow-v0`. Conserver le code
et la configuration associés à un modèle : modifier la signification ou l'ordre
des champs rend un ancien modèle incompatible, même si la taille reste identique.

## Score et récompense d'apprentissage

L'environnement de base renvoie le **delta du score brut** : 100 par chevalier
normal ou poule tuée par un tir, 150 par chevalier furieux. Ce score n'accorde
aucun point pour Tom. Pour apprendre aussi les boss, l'exemple utilise par
défaut l'enveloppe explicite `LearningReward` :

| Événement | Récompense proposée |
| --- | --- |
| Score brut gagné | score / 100 : +1 ou +1,5 par ennemi |
| Point de vie retiré à Tom | +0,25 |
| Tableau normal terminé | +1 |
| Boss vaincu | +5, en plus de la récompense du coup |
| Vie perdue | -0,25 |
| Mort du joueur | -1 supplémentaire |
| Tick de physique exécuté | -0,0001, soit -0,006 par seconde simulée |

Ce sont des **hypothèses de départ à tester**, pas des coefficients déjà optimisés.
Il n'y a pas de récompense positive pour rester en vie sans progresser. Les
événements sont comptés par le moteur, y compris quand une transition arrive au
milieu d'un `frame_skip`. Le score du jeu est conservé dans `info["score"]`.
`info["reward_components"]` permet de comprendre chaque composante.

Pour changer les coefficients toi-même :

```python
from src.rl import JackassParrowEnv, LearningReward, RewardWeights

env = LearningReward(JackassParrowEnv(), RewardWeights(boss_defeated=8.0, tick=0.0))
```

Pour comparer au score seul dans le lanceur, utiliser `--reward score`. Toute
comparaison doit garder le même mode de récompense, ou se baser sur les métriques
du jeu plutôt que sur la somme des récompenses.

## Bibliothèque conseillée pour commencer

Je recommande **Stable-Baselines3 + PPO**, un réseau dense `MlpPolicy` et le CPU
pour ce premier essai. Le choix vise un premier résultat facile à reproduire et
à comprendre ; il ne prouve pas que PPO sera le meilleur algorithme sur ce jeu.
PPO prend en charge les actions `MultiDiscrete`, et sa documentation recommande
le CPU en particulier pour les réseaux sans CNN.
[Documentation officielle PPO](https://stable-baselines3.readthedocs.io/en/master/modules/ppo.html).

Le lanceur fourni utilise 16 environnements en mémoire dans un seul processus
(`DummyVecEnv`), des rollouts de 512 décisions par environnement, un réseau
128 → 128, des mini-lots de 256 et un taux d'apprentissage de 0,0003.
Les 8192 transitions d'un rollout représentent les interactions de tous les
environnements avant les mises à jour. Ces réglages sont un point de départ.

Ce jeu a un moteur léger : je commencerais ainsi avant de payer le coût des
communications par processus. L'option `--backend subproc --envs 8` permet de
comparer avec huit processus. Avec SB3, ce backend crée un processus par
environnement : **ne pas y transposer les 1024 environnements du benchmark**.
Le regroupement de 128 simulations par worker du benchmark n'est pas un
collecteur SB3. Un futur collecteur par lots pourrait l'exploiter si les mesures
montrent que la collecte est le facteur limitant.

Les 935 000 ticks/s du benchmark ne prédisent pas le débit d'apprentissage :
celui-ci inclut encodage des observations, décisions du réseau, stockage des
trajectoires, calcul des gradients et évaluations. Le GPU n'est pas nécessaire
pour commencer ; le choix CPU ici évite aussi de supposer une configuration GPU.

## Faire toi-même un premier entraînement

Le lanceur accepte aussi `--reward-profile combat` : le score est multiplié
par 0,02, la perte d'un PV vaut -0,5 et la mort -5. Les autres coefficients
restent inchangés ; `--tick-penalty` règle séparément le coût par tick. Ce
profil est expérimental. Les évaluations utilisent les mêmes graines à chaque
fois et sauvegardent aussi `best/best_game.zip` selon le score moyen, puis
les tableaux terminés et les PV restants en cas d'égalité. Cette sélection ne
garantit pas une meilleure généralisation : utiliser les graines de test
indépendantes décrites plus bas. `--n-steps` contrôle les décisions collectées
par environnement avant chaque mise à jour PPO.

Pour répartir les simulations entre plusieurs processus, le backend `grouped`
place plusieurs environnements dans chaque worker et échange un lot par
décision. Exemple de configuration expérimentale :

```powershell
.\.venv\Scripts\python.exe -m examples.train_ppo --timesteps 2000000 --envs 128 --backend grouped --workers 8 --n-steps 64 --batch-size 1024 --epochs 3 --episode-limit 1800 --reward-profile combat --output runs/ppo-rapide
```

Les processus sont créés avec `spawn` et le nombre de workers doit être au
plus égal au nombre d'environnements. Cette configuration réduit aussi le
nombre de passes PPO et agrandit les mini-lots : elle change l'apprentissage,
et sa vitesse ne prouve pas une meilleure qualité à budget égal. Comparer les
modèles obtenus sur des graines indépendantes. Le backend `fast` retire les
copies récursives inutiles tout en restant dans un seul processus. Les anciens
backends `dummy` et `subproc` restent disponibles.

1. Vérifier l'installation avec `--check-only`.
2. Lancer une expérience de **1 million de décisions**, puis examiner les résultats.
3. Comparer au hasard sur les mêmes graines d'évaluation.
4. Relancer avec plusieurs graines d'entraînement avant de conclure.
5. Modifier un choix à la fois : récompense, architecture ou hyperparamètres.

Commande qui **lance effectivement l'apprentissage**, uniquement quand tu l'exécutes :

```powershell
.\.venv\Scripts\python.exe -m examples.train_ppo --timesteps 1000000 --envs 16 --seed 0 --output runs/ppo-seed0
```

Un million est un budget d'essai, pas une promesse de maîtrise du jeu. PPO
termine ses rollouts : le nombre réel de décisions peut dépasser légèrement le
budget demandé. `frame_skip=4` correspond à jusqu'à quatre millions de ticks.
Le dossier doit être nouveau, pour éviter d'écraser ou de mélanger les expériences.
Une interruption clavier pendant `learn()` sauvegarde `interrupted.zip` et ferme
les environnements. Le script ne fournit pas encore de commande de reprise.

Le dossier d'expérience contient :

- `config.json` : environnement, récompenses, graines, versions et réglages.
- `final.zip` : modèle de fin d'entraînement.
- `best/best_model.zip` : meilleur modèle selon la récompense d'évaluation, une
  fois qu'une évaluation a eu lieu.
- `checkpoints/` : sauvegardes périodiques.
- `train-monitor/`, `eval-monitor/` : CSV par épisode, avec score et progression.
- `tensorboard/` : courbes de récompense et métriques `game/score_mean`,
  `game/levels_cleared_mean`, `game/boss_damage_mean`, etc.

Pour suivre les courbes dans un autre terminal :

```powershell
.\.venv\Scripts\tensorboard.exe --logdir runs
```

Le modèle est évalué périodiquement sur un environnement distinct, avec une
séquence aléatoire séparée. Les tests ci-dessous utilisent encore d'autres
graines, fixes pour chaque épisode, afin de comparer les politiques. L'évaluation
du meilleur modèle pendant l'entraînement utilise la récompense choisie ; vérifier
également le score brut et les boss, plutôt que se fier à cette récompense seule.
La séparation évaluation/entraînement et les essais avec plusieurs graines
suivent les [conseils officiels SB3](https://stable-baselines3.readthedocs.io/en/master/guide/rl_tips.html).

Évaluer le meilleur modèle et une politique aléatoire sur les mêmes 20 épisodes :

```powershell
.\.venv\Scripts\python.exe -m examples.evaluate_ppo --model runs/ppo-seed0/best/best_model.zip --config runs/ppo-seed0/config.json --episodes 20 --seed 200000
.\.venv\Scripts\python.exe -m examples.evaluate_ppo --random --config runs/ppo-seed0/config.json --episodes 20 --seed 200000
```

Le script affiche moyenne, écart-type et résultats par graine : score, tableaux
terminés, dégâts à Tom, boss vaincus, durée et récompense. L'évaluation n'appelle
jamais `learn()`. Une durée plus longue seule ne suffit pas à prouver que l'agent
joue mieux : il pourrait simplement rester derrière son bouclier.

Pour reproduire l'essai avec d'autres initialisations, utiliser par exemple
`--seed 1 --output runs/ppo-seed1`, puis `--seed 2 --output runs/ppo-seed2`.
Garder les mêmes graines de test pour comparer les expériences. Si l'agent ne
progresse pas, examiner les composantes des récompenses, les commandes et les
observations avant d'augmenter massivement le nombre d'environnements.

## Regarder un modèle jouer

```powershell
.\.venv\Scripts\python.exe -m examples.watch_ppo --model runs/ppo-seed0/final.zip --config runs/ppo-seed0/config.json
```

Le point d'entrée `python main.py --watch ...` est équivalent. Le fichier de
configuration restaure le frame-skip, la limite de durée et les récompenses
du modèle ; aucune nouvelle mise à jour du réseau n'est effectuée. Le rendu
montre chaque tick physique à 60 Hz, y compris entre les décisions de l'IA,
et affiche score, vie, temps et commandes appliquées. Les parties recommencent
avec une graine suivante lorsqu'elles se terminent. Il n'y a pas de son.

| Commande | Effet |
| --- | --- |
| Espace | Pause / reprise |
| Flèches gauche / droite | Ralentir / accélérer de 0,25× à 8× |
| R | Rejouer la même graine |
| N | Passer à une nouvelle partie |
| Tab | Alterner politique déterministe / échantillonnage |
| Échap ou fermeture | Quitter et libérer la fenêtre |

Le mode déterministe prend l'action privilégiée par le modèle. Le mode
échantillonnage tire une action selon les probabilités apprises : ce sont
toujours les décisions du modèle, avec davantage de variété. `--stochastic`
active ce mode dès le lancement. `--speed 2` démarre en accéléré. Une politique
très peu entraînée peut rester immobile, parer en boucle ou tirer mal orientée.

Pour un essai fini : `--episodes 2` ou `--max-decisions 300`. L'option
`--screenshot image.png` sauvegarde une image après une seconde simulée.
Une partie regardée n'a pas de limite de durée : elle se termine à la mort
(ou à la victoire en mode boss). `--time-limit` rétablit la limite de décisions
de l'entraînement ; les exercices de curriculum et de parcours gardent toujours
la leur. Le rendu et l'inférence
CPU peuvent ralentir légèrement le temps réel, sans changer le pas physique.

Une démo locale courte a été entraînée sur 16 384 décisions avec huit
environnements et une limite de 900 décisions par épisode :

```powershell
.\.venv\Scripts\python.exe -m examples.train_ppo --timesteps 16384 --envs 8 --episode-limit 900 --eval-every 8192 --eval-episodes 2 --torch-threads 2 --output runs/ppo-demo
.\.venv\Scripts\python.exe main.py --watch --model runs/ppo-demo/final.zip --config runs/ppo-demo/config.json --stochastic
```

La première commande ne doit pas être relancée dans un dossier déjà existant.
Les modèles, logs et captures dans `runs/` sont locaux et ignorés par Git.
Ce premier modèle sert à vérifier la chaîne entraînement → sauvegarde → lecture ;
son niveau de jeu n'est pas représentatif d'un entraînement abouti.

## Vérifications du dépôt

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Les tests Gymnasium vérifient les espaces, masques, graines, snapshots, actions
simultanées, limites, récompenses et vecteurs sync/async sous `spawn`. Les tests
SB3 vérifient le contrat et une prédiction d'une politique non entraînée, sans
appeler `learn()`. Les tests optionnels sont ignorés si leurs extras ne sont pas
installés. Le moteur headless seul est toujours testé sans site-packages.

## Curriculum de compétences (schéma v1)

Le lanceur dédié conserve le même réseau pendant six étapes : déplacement au
sol, plateforme accessible, position et orientation pour tirer, ennemi passif,
ennemi qui riposte, puis jeu normal. La physique du jeu normal reste inchangée.
Les exercices ont des géométries simples et des ennemis sans attaque aux
premières étapes ; leurs scores ne sont pas des scores de maîtrise du jeu.

```powershell
.\.venv\Scripts\python.exe -m examples.train_curriculum --output runs/curriculum-v1
```

Par défaut : 128 simulations, 8 processus, budget maximal de 1,5 million de
décisions par étape. Une étape passe après au moins 75 % de réussite sur 24
situations de validation, confirmé sur une seconde série de 24 situations.
Le budget épuisé arrête le programme sans sauter la compétence non acquise.
15 % des épisodes reprennent des étapes précédentes. La dernière étape réduit
progressivement les aides et compare le meilleur modèle à des actions
aléatoires sur 20 graines de test distinctes.

L'observation contient les 454 valeurs précédentes et 14 valeurs supplémentaires :
position relative de l'objectif et de l'ennemi, étape, meilleur rapprochement,
stabilité, bonus de placement déjà obtenu et intensité des aides. Le schéma
`JackassParrowCurriculum-v1` ne doit pas être confondu avec les anciens modèles.

Récompenses : progrès au-delà du meilleur rapprochement (+4 fois la réduction
de distance normalisée), placement stable (+1 une seule fois), exercice réussi
(+10), score brut x 0,02, PV perdu -0,5, mort -3 et décision -0,001. Le bonus de
placement et le progrès sont réduits avec l'intensité des aides. Changer de
cible ne crée pas de bonus. Les allers-retours ne réinitialisent pas les bonus.

Les dossiers `move`, `platform`, `aim`, `shoot`, `combat`, `normal` contiennent
configurations, modèles `best.zip`, `latest.zip`, `final.zip` et évaluations.
`status.json` indique la progression ou la raison d'arrêt. Le spectateur sait
charger ces modèles :

```powershell
.\.venv\Scripts\python.exe main.py --watch --model runs/curriculum-v1/move/best.zip --config runs/curriculum-v1/move/config.json
```

Remplacer `move` par une autre étape disponible. Pour juger le jeu complet,
utiliser `normal` et consulter `final-comparison.json`. Les aides et les seuils
sont expérimentaux ; leur implémentation ne garantit pas la réussite du cursus.

## Parcours et transfert v2

`--courses` ajoute neuf étapes : escaliers bas, escaliers hauts (jusqu'à quatre
sauts), zigzags, descente par les paliers, tir après ascension, navigation sur
les cartes originales, ennemis passifs sur ces cartes, combat sur ces cartes,
puis jeu normal. Les parcours sont générés avec des variations de hauteur,
de position et de sens. Les points de passage ne donnent leur bonus qu'une
fois, après trois décisions stables sur leur plateforme.

```powershell
.\.venv\Scripts\python.exe -m examples.train_curriculum --courses --init-model runs/curriculum-progressif/combat/final.zip --reference-model runs/curriculum-progressif/normal/best.zip --stage-budget 2000000 --chunk 65536 --output runs/parcours-v2
```

Les poids des compétences v1 sont repris, les six nouvelles entrées sont
initialisées à poids nul et l'optimiseur est réinitialisé. Le schéma devient
`JackassParrowCourses-v2` (474 valeurs). Il ajoute la progression dans le
parcours, la taille du parcours, la position finale relative, un indicateur de
route trouvée et l'étape du cursus. Les anciens modèles restent compatibles
avec leurs propres configurations.

Un planificateur géométrique propose les points de passage sur les cartes du
jeu. Il ne choisit aucune commande. Ses estimations de portée sont conservatrices
mais ne constituent pas une preuve exacte de faisabilité pour toutes les cartes.
L'agent bénéficie de cette aide de navigation, y compris en évaluation : il ne
s'agit pas d'une planification entièrement apprise. La physique et les ennemis
restent ceux du jeu normal à la dernière étape ; les récompenses intermédiaires
sont alors retirées progressivement et l'évaluation utilise une intensité nulle.
Le spectateur affiche le prochain objectif par un cercle cyan.

La progression exige 75 % de réussite sur deux séries de 24 situations. Un
échec au seuil arrête le cursus sans sauter l'étape. Le bilan final utilise
40 graines inédites identiques pour le modèle, les actions aléatoires et,
si `--reference-model` est fourni, l'ancien modèle v1 du jeu normal. La vitesse
et les compétences simplifiées ne suffisent pas à conclure à une amélioration
du score en jeu complet.

### Reprendre une étape sans recommencer le cursus

`--resume-from` charge un checkpoint et le `config.json` situé dans son dossier.
Le schéma doit correspondre au cursus sélectionné. Le réseau, l'optimiseur et
le compteur de décisions sont restaurés ; les épisodes repartent avec la graine
indiquée. Les étapes précédentes ne sont pas rejouées comme étapes principales,
mais restent présentes dans le mélange d'exercices de rappel. Le dossier de
sortie doit être nouveau. Les seuils de réussite restent obligatoires.

```powershell
.\.venv\Scripts\python.exe -m examples.train_curriculum --courses --resume-from runs/parcours-v2/map_shoot/final.zip --stage-budget 4000000 --final-budget 8000000 --chunk 131072 --seed 8 --reference-model runs/curriculum-progressif/normal/best.zip --output runs/parcours-v2-suite
```

Les budgets sont des décisions supplémentaires pour chaque étape reprise ou
nouvelle ; `--final-budget` s'applique au jeu normal. `status.json` distingue
le compteur total historique, les décisions de l'étape et son budget.
L'évaluation initiale de la reprise est conservée pour ne pas écraser le
meilleur modèle avec une version moins performante.

## Agent sans itinéraire fourni

Les résultats des parcours v2 utilisent une aide géométrique explicite. Pour
entraîner un agent qui décide également où aller, le lanceur standard utilise
uniquement les 454 valeurs d'état du jeu : aucun objectif, point de passage,
planificateur ou bonus de parcours. `--init-from-guide` peut réutiliser les poids
communs d'un modèle guidé, en supprimant réellement toutes ses colonnes d'entrée
de guidage et en réinitialisant l'optimiseur. Cette conversion peut dégrader
fortement ses performances et doit être suivie d'un nouvel entraînement.

```powershell
.\.venv\Scripts\python.exe -m examples.train_ppo --init-from-guide runs/parcours-v2-suite/normal/best.zip --timesteps 4000000 --envs 128 --backend grouped --workers 8 --n-steps 64 --batch-size 1024 --epochs 5 --episode-limit 1800 --reward-profile combat --output runs/autonome-v1
```

`initial.zip` permet de mesurer la performance juste après suppression du
guidage. La configuration indique `navigation_guidance: false`. Le spectateur
avec cette configuration n'affiche aucun cercle : le moteur ne possède plus
cet objectif. Charger un ancien modèle v2 avec son ancienne configuration
continue, en revanche, à utiliser son aide de navigation originale.

## Entraînement rapide vectorisé (schéma v2, CPU ou GPU)

Le lanceur `examples.train_vector` remplace la collecte SB3 multi-processus
par un moteur **torch vectorisé** (`src/rl/vector/engine.py`) : des milliers de
parties avancent ensemble sur un seul appareil, sans échange entre processus.
Les règles, constantes et l'ordre des mises à jour sont ceux de `HeadlessEnv`,
en float64. Les tirages aléatoires suivent les mêmes lois, pas le même flux.
`tests/test_vector_engine.py` compare chaque tick au moteur de référence, depuis
des états synchronisés (joueur, ennemis, projectiles, boss, dégâts, chargements).

```powershell
# CPU local (~10 000 décisions/s, 1024 parties par défaut)
.\.venv\Scripts\python.exe -m examples.train_vector --timesteps 100000000 --output runs/vector-cpu
# GPU (A40) : 32 768 parties × 16 pas, simulation en graphe CUDA, réseau en TF32
python -m examples.train_vector --envs 32768 --n-steps 16 --timesteps 1500000000 --eval-every 50000000 --eval-envs 512 --eval-episode-limit 1800 --checkpoint-every 50000000 --output runs/hard-v1
```

Débits mesurés le 5 novembre 2026 (politique et PPO inclus sauf mention) :

| Configuration | Décisions/s |
| --- | --- |
| Ancien lanceur SB3, 128 parties, 8 processus (Ryzen AI 9 365) | 1 516 |
| Moteur vectorisé, CPU local, 1024 parties (simulation seule) | ~10 000 |
| A40, 16 384 parties, sans graphe CUDA (simulation seule) | 193 000 |
| A40, 16 384 parties, graphe CUDA (simulation seule) | 645 000 |
| A40, 16 384 parties, graphe CUDA, entraînement complet | 424 000 |
| A40, jeu avec tableaux HARD, 16 384 × 32 pas, entraînement complet | 380 000 |
| A40, jeu avec tableaux HARD, 32 768 × 16 pas + TF32, entraînement complet | 481 000 |

Sur CUDA, le moteur ne lit jamais de valeur du GPU pendant un pas : `GraphedStep`
capture tout `VectorGame.step` (≈10 000 noyaux) dans un graphe rejoué en un appel.
`--no-cuda-graph` revient au lancement direct des noyaux.

**Observation `JackassParrow-v2` (265 valeurs).** Égocentrique : positions
relatives au centre du joueur, ennemis et projectiles triés par distance. Pour
chaque ennemi : type, direction, âge du dernier tir, plateforme, et trois faits
calculés sur la géométrie exacte : alignement avec la ligne du tir du joueur,
ligne de tir dégagée, tir qui partirait vers lui. Tom : PV, trou du bouclier,
délais, ligne de tir par le trou. Les 12 blocs du tableau sont donnés relativement
au joueur, avec l'identifiant de tableau (11 valeurs : arène, 5 normaux, 5 HARD).
Jusqu'à 8 ennemis (les tableaux HARD ont 8 plateformes d'apparition). Pas de
temps restant : les épisodes coupés par la limite sont prolongés par la valeur
estimée (bootstrap). La v2 ajoute les tableaux HARD des boucles suivantes ; les
modèles v1 de la branche `main` ne se chargent pas avec ce schéma.

**14 actions** au lieu de 24 combinaisons : PARADE annule toute direction, et
SAUT + PARADE annule le saut dans les commandes du jeu ; ces doublons sont retirés.
L'environnement Gymnasium garde l'espace `MultiDiscrete([3, 2, 2, 2])`.

**Récompense.** Mêmes composantes que `LearningReward` : ennemi +1 (furieux
+1,5), tableau +1, coup sur Tom +1, Tom vaincu +5, PV perdu -1, mort -2, et
-0,001 par décision. Deux aides d'entraînement, inscrites dans `config.json` :

- `--shaping 1` : façonnage par potentiel `γΦ(s') − Φ(s)` vers une ligne de tir
  (proximité verticale d'un ennemi, ligne dégagée ; trou du bouclier pour Tom).
  Cette forme ne change pas la politique optimale (Ng et al., 1999).
- `--random-start 0.5` : la moitié des parties commencent à un tableau tiré au
  hasard, contre Tom ou dans la deuxième boucle. Les statistiques `game/*` et
  les évaluations ne comptent que les parties démarrées normalement.

PPO tourne entièrement sur l'appareil : normalisation des observations dans le
réseau (sauvegardée avec lui), récompenses divisées par l'écart-type du retour
actualisé, deux réseaux 256 → 256 (SiLU), taux d'apprentissage décroissant.
L'évaluation périodique joue la première partie de `--eval-envs` jeux en mode
déterministe et garde `best.pt` selon la progression moyenne (tableaux + dégâts
à Tom / 10). Le dossier contient `config.json`, `metrics.jsonl`, `tensorboard/`,
`best.pt`, `final.pt` et `checkpoints/`. `--resume fichier.pt` reprend réseau,
optimiseur et normalisations dans un nouveau dossier.

Les modèles `.pt` se regardent et s'évaluent avec les outils existants, qui
jouent sur le **moteur de référence** (`FeatureEnv` synchronise l'état vers
l'encodeur vectorisé à chaque décision) :

```powershell
.\.venv\Scripts\python.exe main.py --watch --model runs/hard-v1/best.pt --config runs/hard-v1/config.json
.\.venv\Scripts\python.exe -m examples.evaluate_ppo --model runs/hard-v1/best.pt --config runs/hard-v1/config.json --episodes 40 --seed 600000
```

### Sur RunPod

Le proxy `ssh <pod>-<hôte>@ssh.runpod.io` n'accepte ni `scp` ni commande non
interactive : le code est envoyé en base64 dans un terminal (`scripts/runpod_pod.sh`), puis
`pip install gymnasium tensorboard` suffit sur l'image `runpod-torch-v280`.
Lancer l'entraînement avec `setsid nohup ... &` pour qu'il survive à la
déconnexion, et supprimer le pod après avoir rapatrié le dossier du run.

### Résultat sans tableaux HARD (branche `main`)

Sur `main` (schéma v1, boucles toujours dans 1..5), `vector-v1` a atteint en
400 M décisions sur une A40 (16 minutes, ~0,45 $) 15,8 tableaux et 1,9 victoire
sur Tom par partie de 2 minutes sur le moteur de référence, contre 1,3 tableau
pour l'ancien meilleur modèle. Ce chiffre ne vaut pas pour cette branche : à
partir de la deuxième boucle, le jeu y utilise les tableaux HARD.

### Modèle fourni avec tableaux HARD (`models/hard-v1`)

Entraîné 1 300 M décisions sur une A40 (~45 min, ~0,55 $), versionné avec la
branche pour être regardé sans réentraîner. Sur le moteur de référence, 40 graines
inédites, parties de 2 minutes : score 8 034 ± 304, 14,65 tableaux, 1,98 victoire
sur Tom, 1 mort sur 40. Détails, courbes, commande de reprise :
[models/hard-v1/README.md](../models/hard-v1/README.md).

```powershell
.\.venv\Scripts\python.exe main.py --watch --model models/hard-v1/model.pt --config models/hard-v1/config.json
```
