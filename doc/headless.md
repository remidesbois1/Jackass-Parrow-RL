# Mode headless

Le moteur `src.headless` permet de simuler des parties sans fenêtre, Pygame,
SDL, son, texture, police, menu, score sur disque ou dépendance d'IA. Il fonctionne
avec la bibliothèque standard de Python 3.12+. Aucun entraînement n'est lancé.
Le lancement graphique habituel reste `python main.py`.

## Lancer et mesurer

Depuis la racine du dépôt, avec le Python du projet :

```powershell
.\.venv\Scripts\python.exe main.py --headless --envs 256 --workers 8 --steps 5000
```

Autre point d'entrée, utilisable même sans installer les dépendances graphiques :

```powershell
python -m src.headless --envs 256 --workers 8 --steps 5000
```

Cette commande exécute un **benchmark fini** avec une séquence d'actions prédéfinie,
puis affiche un rapport JSON et ferme les processus. Elle ne joue pas avec un
modèle et n'en apprend aucun. Les épisodes terminés sont réinitialisés pour
maintenir le nombre demandé de parties jusqu'à la fin de la mesure.

Options :

| Option | Défaut | Effet |
| --- | --- | --- |
| `--envs` | 64 | Nombre total d'environnements |
| `--workers` | 1 | Processus ; chaque processus héberge un lot d'environnements |
| `--steps` | 1000 | Décisions par environnement, réinitialisations comprises |
| `--frame-skip` | 1 | Nombre de ticks à 60 Hz par décision |
| `--seed` | 0 | Graine de base ; environnement i = graine + i |
| `--boss-mode` | désactivé | Commencer directement contre Tom |
| `--observe` | désactivé | Inclure la construction des observations dans la mesure |
| `--memory` | désactivé | Mesurer les allocations Python avec `tracemalloc` |

Le temps inclut création des lots, démarrage des workers, actions, simulation,
réinitialisations et collecte finale. Les ticks réellement exécutés sont comptés :
une mort peut interrompre un `frame_skip`. Les résultats dépendent des parties,
du processeur, des observations et du nombre de processus. `--memory` ralentit
fortement la simulation ; ses débits ne sont pas comparables aux mesures normales.
`python_bytes` et `python_peak_bytes` sont la somme des allocations et des pics
Python des workers, pas la RAM totale/RSS et pas un pic simultané du système.

Mesure locale du 16 octobre 2026, Windows, Python 3.13.16, Ryzen AI 9 365
(10 cœurs / 20 threads), 256 environnements × 5000 décisions, seed 0,
frame_skip 1, sans observations ni traçage mémoire :

| Processus | Durée | Ticks physiques / seconde |
| --- | --- | --- |
| 1 | 7,63 s | 167 690 |
| 4 | 2,73 s | 469 287 |
| 8 | 1,96 s | 652 988 |

Ces trois exécutions ont produit les mêmes totaux : 1 280 000 ticks,
269 épisodes terminés, score cumulé 30 900. Ce sont des mesures ponctuelles,
pas une garantie de débit. Un petit travail peut être plus rapide sur un seul
processus, car le démarrage de Python sous Windows a un coût.

Un second essai, 1024 environnements × 2000 décisions sur 8 processus, a exécuté
2 048 000 ticks en 2,86 s, soit environ 716 000 ticks/s. Avec 1024 environnements
sur un processus et 100 décisions chacun, le traçage relève environ 4,2 Mo
d'allocations Python au pic ; cela exclut la mémoire de l'interpréteur et ne
représente donc pas la consommation RAM totale.

## API pour un futur agent

```python
from src.headless import Action, Config, HeadlessEnv

env = HeadlessEnv(seed=42, config=Config(frame_skip=4, max_episode_steps=9000))
observation, info = env.reset(seed=42)
observation, reward, terminated, truncated, info = env.step(Action.RIGHT | Action.FIRE)

# Chemin rapide : aucune observation/dictionnaire de résultat n'est construit.
reward = env.advance(Action.JUMP | Action.FIRE)
observation = env.observe()  # uniquement quand nécessaire

if env.done:
    observation, info = env.reset()  # continue le générateur propre à cette instance
```

Le tir part dans la direction opposée au regard du joueur et applique son recul.
Les actions sont des masques entiers de 0 à 31 :

| Action | Bit |
| --- | --- |
| `IDLE` | 0 |
| `LEFT` | 1 |
| `RIGHT` | 2 |
| `JUMP` | 4 |
| `DOWN` | 8 |
| `FIRE` | 16 |

Les bits se combinent avec `|`. Gauche a priorité si les deux directions sont
actives. `DOWN` pare au sol et accélère la chute en l'air. Les actions sont
maintenues pendant tous les ticks d'une décision. Le moteur conserve l'ordre
du jeu graphique : collisions et mouvement, puis commandes du joueur.

`reward` est seulement le delta du score du jeu (100 ou 150 par ennemi tué).
Aucune récompense d'entraînement supplémentaire n'est imposée. `terminated`
signifie mort du joueur, ou victoire en mode boss seul. `truncated` signifie
limite de décisions atteinte. La limite par défaut est de 36 000 décisions,
soit 10 minutes simulées avec frame_skip 1 ; `None` la désactive. La mort
interrompt immédiatement les ticks restants. Avancer après la fin lève une
erreur jusqu'à un `reset` explicite. Aucun état final n'est perdu par un
autoreset caché.

`step()` suit la forme de retour à cinq valeurs courante, mais l'objet n'est
pas une implémentation de `gymnasium.Env` : pas de dépendance Gymnasium,
`action_space`, `observation_space`, padding ou normalisation imposés. Un futur
adaptateur pourra les ajouter selon le modèle choisi.

### Observations

`observe()` fournit un dictionnaire de tuples numériques détachés de l'état
mutable. Positions et tailles en pixels, vitesses en pixels/seconde, délais en
secondes, indicateurs booléens en 0/1. Les collections d'entités ont une longueur
variable. Elles sont sérialisables en JSON.

| Clé | Contenu de chaque ligne |
| --- | --- |
| `player` | x, y, largeur, hauteur, vitesse horizontale, vitesse verticale, recul, direction (-1/+1), PV, au sol, bouclier, délai de tir restant, invulnérabilité restante |
| `enemies` | x, y, largeur, hauteur, type (0 chevalier / 1 furieux / 2 poule), direction, âge du dernier tir |
| `bullets`, `enemy_bullets` | x, y, largeur, hauteur, vitesse horizontale |
| `blocks` | x, y, largeur, hauteur, transparent aux projectiles |
| `boss` | x, y, largeur, hauteur, PV, index du trou, invulnérabilité restante, délai de tir restant ; tuple vide si absent |
| `boss_shields` | x, y, largeur, hauteur |
| `context` | monde (à partir de 0), numéro du tableau, identifiant du niveau (0 = boss), danger, ticks physiques, décisions |

La géométrie physique vient des dimensions des sprites existants, sans lire
les images à l'exécution. Un test signale si ces dimensions deviennent obsolètes.
Le calcul utilise des flottants Python ; Pygame utilise des `FRect` de précision
simple. Les trajectoires ne sont donc pas promises identiques bit à bit.

### Lots et parallélisme

```python
from src.headless import Action, BatchEnv, Config

batch = BatchEnv(256, seed=100, config=Config(frame_skip=4))
actions = [int(Action.FIRE)] * 256
rewards = batch.advance(actions)
# rewards, terminated et truncated sont des buffers réutilisés.
saved_rewards = rewards.copy()  # si l'appelant veut conserver ce résultat
final_observation = batch.envs[0].observe()
batch.reset_done()  # après avoir récupéré les éventuels états finaux
```

`batch.step(actions)` retourne les observations, récompenses, terminaisons,
troncatures et infos sous forme de snapshots. Une entrée invalide ou un épisode
déjà terminé est détecté avant de modifier le lot. Chaque environnement possède
son RNG et ses entités ; les tableaux géométriques immuables sont partagés dans
le processus. Un reset avec une graine reproduit une partie ; un reset sans
graine continue la séquence indépendante de cette instance.

`BatchEnv` tourne dans le processus appelant. Pour utiliser plusieurs cœurs,
le lanceur distribue un lot par worker avec `spawn`, sans créer un processus
par partie. Il ne transfère que les paramètres initiaux et un résultat agrégé
par worker. Il ne transmet pas d'actions ou d'observations par IPC à chaque
frame. Les graines globales restent les mêmes quand le nombre de workers change.
Les workers sont fermés à la sortie, y compris en cas d'exception. Pour un futur
entraînement, placer les rollouts par lots dans les workers et regrouper les
échanges avec le modèle ; le benchmark ne fournit pas encore ce protocole.

Commencer avec 4 à 8 processus et mesurer sur une charge représentative. Plus
de processus n'est pas systématiquement plus rapide. Une instance mutable
appartient à son appelant et n'est pas conçue pour être modifiée simultanément
par plusieurs threads. Un script qui crée ses propres processus doit placer
son point d'entrée sous `if __name__ == "__main__":` sous Windows.

## Périmètre et différences intentionnelles

Le mode headless reproduit la difficulté **OLD**, celle utilisée par
`GameManager.start_game()` : sept tableaux jungle sans répétition immédiate,
Tom, puis nouvelle boucle avec danger augmenté de trois. Le mode boss seul est
également disponible. Les autres difficultés, dont certains mondes ne sont pas
implémentés dans le jeu graphique, ne sont pas exposées.

Les dix géométries normales et l'arène boss sont partagées avec le jeu graphique
dans `src/system/level_data.py`. Les constantes communes sont dans
`src/system/mechanics.py`. Les systèmes physiques headless et graphique restent
distincts ; les tests de comparaison protègent les géométries, dimensions et
séquences de déplacement/recul à 60 Hz.

Différences nécessaires pour des épisodes reproductibles et exploitables :

- Les délais dépendent des ticks simulés, jamais du rendu ni de l'heure réelle.
  Une partie démarre à t=0 ; attendre dans un menu n'accélère aucun premier tir.
- Les cinématiques, clignotements, animations d'explosion et cadavres sont omis.
  Les ennemis morts sont retirés immédiatement ; ils ne peuvent plus accorder
  plusieurs fois leur score en recevant d'autres tirs.
- Les dégâts respectent l'invulnérabilité de 600 ms, y compris les poules.
  Plusieurs collisions dans le même tick ne suppriment pas plusieurs vies.
- Le bouclier du joueur est recalculé à chaque commande, sans dépendre du
  relâchement d'une touche particulière. Les boucliers de Tom laissent bien
  un trou correspondant à l'index choisi et différent du précédent.
- Les transitions et la fin ne dépendent pas d'un menu ou d'un appel à `render`.

Les projectiles hors écran et les entités mortes sont éliminés. Le filtrage des
plateformes à la naissance d'un projectile est réactualisé lors d'un changement
de niveau. Les listes sont compactées sur place, sans snapshots de groupes de
sprites. Le cache des géométries est limité à onze niveaux. Il n'y a pas
d'historique conservé ou d'accumulation d'observations dans le moteur.

## Vérification

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Les tests couvrent notamment l'exécution sans site-packages/Pygame, la
reproductibilité intercalée, l'équivalence mono/multiprocessus, l'isolation des
instances, les transitions jusqu'au boss, les dégâts/boucliers, les collisions,
les fins et resets explicites, la parité physique avec Pygame et un run prolongé
avec contrôle du nombre d'entités. Les tests de comparaison graphique nécessitent
les dépendances habituelles du projet ; le moteur headless seul n'en a pas besoin.
