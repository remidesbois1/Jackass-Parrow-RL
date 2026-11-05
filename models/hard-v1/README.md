# Modèle `hard-v1`

Agent PPO entraîné sur le jeu complet de la branche `withhardlevels` : sept
tableaux jungle, Tom, puis boucles suivantes sur les tableaux HARD (danger +3
par boucle). Schéma d'observation `JackassParrow-v2` (265 valeurs), 14 actions.

| Fichier | Contenu |
| --- | --- |
| `model.pt` | Meilleur modèle (évaluation à 1 250 M décisions), à regarder ou évaluer |
| `config.json` | Configuration d'entraînement (parties de 3 600 décisions = 4 min) |
| `config-2min.json` | Même configuration, parties de 1 800 décisions (2 min) pour l'évaluation |
| `resume.pt` | Dernier état (1 300 M décisions) avec optimiseur, pour reprendre l'entraînement |
| `metrics.jsonl` | Courbes d'entraînement et évaluations périodiques |
| `evaluation-2min.json` | Évaluation détaillée sur le moteur de référence (tableau ci-dessous) |

## Regarder

```powershell
uv sync --extra train
.\.venv\Scripts\python.exe main.py --watch --model models/hard-v1/model.pt --config models/hard-v1/config.json
```

Aucun GPU n'est nécessaire. La partie regardée n'a pas de limite de temps : elle
se termine à la mort. `--speed 8` accélère, `--stochastic` échantillonne les
actions au lieu de prendre la plus probable, `--seed N` change la partie.

## Résultats

Moteur de référence (`HeadlessEnv`, mêmes règles que le jeu graphique),
40 graines jamais vues à l'entraînement (600000 à 600039), parties de 2 minutes,
politique déterministe :

```powershell
.\.venv\Scripts\python.exe -m examples.evaluate_ppo --model models/hard-v1/model.pt --config models/hard-v1/config-2min.json --episodes 40 --seed 600000
```

| Modèle | Score | Tableaux | Coups sur Tom | Tom vaincu | Morts |
| --- | --- | --- | --- | --- | --- |
| Ancien meilleur SB3 (`parcours-v2-suite`, guidé, sans HARD) | 200 | 1,3 | — | 0 | 16 / 40 |
| `vector-v1` (branche `main`, sans HARD, 400 M) | 6 864 | 15,8 | — | 1,9 | 2 / 40 |
| **`hard-v1` (avec HARD, 1 250 M)** | **8 034 ± 304** | **14,65** | **19,95** | **1,98** | **1 / 40** |

Évaluations périodiques pendant l'entraînement (512 parties de 2 min, moteur
vectorisé) :

| Décisions | Score | Tableaux | Tom vaincu | Morts |
| --- | --- | --- | --- | --- |
| 100 M | 1 870 | 5,7 | 0,03 | 48 % |
| 150 M | 2 535 | 7,2 | 0,92 | 10 % |
| 400 M | 6 881 | 13,5 | 1,07 | 9 % |
| 850 M | 7 371 | 14,0 | 1,62 | 3,7 % |
| 1 250 M | 7 946 | 14,5 | 1,91 | 2,9 % |

La progression plafonne à partir de ~1 000 M décisions : en 2 minutes, la
limite est surtout le temps passé sur Tom (10 coups, 2 s d'invulnérabilité
entre deux coups). Un seul entraînement (graine 1) : refaire un run avec une
autre `--seed` pour juger la stabilité de la méthode.

## Entraînement

1 300 M décisions sur une NVIDIA A40 (RunPod), ~45 min, ~0,55 $ :
32 768 parties en parallèle × 16 pas, simulation en graphe CUDA, réseau 256 → 256
en TF32, 481 000 décisions/s. Récompense, aides d'entraînement (façonnage par
potentiel vers une ligne de tir, 50 % de départs variés) et observations :
voir [doc/rl.md](../../doc/rl.md#entraînement-rapide-vectorisé-schéma-v2-cpu-ou-gpu).

```powershell
python -m examples.train_vector --envs 32768 --n-steps 16 --timesteps 1500000000 --eval-every 50000000 --eval-envs 512 --eval-episode-limit 1800 --checkpoint-every 50000000 --seed 1 --output runs/hard-v1
```

Reprendre à partir de ce modèle (réseau, optimiseur et normalisations
restaurés ; le taux d'apprentissage repart de `--lr` et décroît sur le nouveau
budget) :

```powershell
python -m examples.train_vector --resume models/hard-v1/resume.pt --lr 0.0001 --envs 32768 --n-steps 16 --timesteps 500000000 --eval-every 50000000 --eval-envs 512 --eval-episode-limit 1800 --checkpoint-every 50000000 --output runs/hard-v2
```
