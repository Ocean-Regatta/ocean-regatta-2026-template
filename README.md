# Ocean Regatta 2026 — Starter Kit Participant 🚤

Bienvenue dans le dépôt de départ de la compétition d'autonomie marine **Ocean Regatta 2026** !
Ce kit contient tout le nécessaire pour développer, tester et visualiser vos algorithmes de navigation autonome pour le catamaran **BlueBoat** sous le simulateur **Gazebo Jetty**.

---

## 🎯 Objectif du Challenge 2026

Votre objectif est de programmer un contrôleur autonome en Python capable de :
1. **Franchir 3 portes de chenal** (paires de bouées rouge bâbord et verte tribord) malgré un courant marin transversal et une dissymétrie des moteurs.
2. **Contourner une balise cardinale** selon la réglementation maritime internationale IALA (dans le monde d'entraînement, une cardinale NORD).
3. **Franchir la porte d'entrée de la jetée** pour aligner le drone le long du quai.
4. **Effectuer un suivi de quai** à $5.0 \text{ m}$ du mur à l'aide de l'échosondeur acoustique Ping2 latéral sans jamais heurter la paroi.
5. **Franchir la porte de sortie de la jetée** pour terminer le parcours dans le temps imparti (180 s).

---

## 📁 Structure du Starter Kit

```
participant_template/
├── models/
│   └── blueboat/                # Modèle SDF complet (hydrodynamique, propulseurs, capteurs)
├── worlds/
│   └── practice_world.sdf       # Monde d'entraînement Gazebo officiel
├── starter_kit/
│   ├── student_controller.py    # ✏️ VOTRE CODE ICI (seul fichier évalué sur le serveur)
│   ├── blueboat_driver.py       # Pilote matériel d'abstraction capteurs/actionneurs
│   ├── run_docker.sh            # Lancement clé en main sous Docker (recommandé)
│   ├── run_local.sh             # Lancement en natif (si Gazebo Jetty est installé)
│   └── Dockerfile.local         # Image Docker de développement local
└── .github/
    └── workflows/
        └── evaluate.yml         # Workflow d'évaluation automatique sur Pull Request
```

> [!IMPORTANT]
> **Règle d'or de l'évaluation :**
> Lors de l'évaluation automatisée sur les serveurs de la compétition, **seul votre fichier `student_controller.py` est extrait et exécuté**. Le serveur injecte sa propre version officielle et immuable de `blueboat_driver.py` et génère un monde d'évaluation inédit avec une graine aléatoire.

---

## 👁️ Guide des Capteurs & API

Votre contrôleur reçoit à chaque pas de temps ($10 \text{ Hz}$) un objet `obs: Observation` fourni par le `BlueBoatDriver`.

### 1. Caméra Optique Avant (`obs.buoys`)
Le capteur sémantique simule une caméra optique embarquée :
* **Champ de vision (FOV) :** $\pm 55^\circ$ devant le drone, portée maximale de $35.0 \text{ mètres}$.
* **Mesures transmises :** Strictement la distance euclidienne `range` (mètres) et le gisement relatif au cap `bearing` (radians, $>0$ bâbord / $<0$ tribord).
* **Classification visuelle :**
  * `color` : `"RED"`, `"GREEN"`, `"YELLOW_BLACK"`
  * `shape` : `"CYLINDER"`, `"CONE"`, `"CARDINAL"`
* **Absence d'identifiants de triche :** Aucune étiquette du type `"gate_1_port"` n'est fournie. Les bouées sont simplement triées par distance croissante (`obs.buoys[0]` étant la plus proche).
* **Sortie naturelle du champ :** Dès que vous franchissez une porte, les bouées passent derrière le drone ($x_{\text{body}} < 0$) et sortent automatiquement du champ de vision. La porte suivante devient instantanément la plus proche !

#### Conversion Polaire $\rightarrow$ Cartésienne Body Frame
Pour calculer les coordonnées d'une bouée dans le repère du bateau ($x$ vers l'avant, $y$ vers la gauche) :
```python
x_body = buoy.range * math.cos(buoy.bearing)
y_body = buoy.range * math.sin(buoy.bearing)
```

### 2. Échosondeur Acoustique Ping2 (`obs.ping2`)
* Orienté à $+90^\circ$ (strictement orienté sur le flanc bâbord / gauche).
* Mesure la distance à la jetée : `obs.ping2.distance` (mètres, $0.5 \text{ m}$ à $30.0 \text{ m}$).
* Champ `obs.ping2.is_valid` : vaut `True` si l'écho est récent ($< 0.5 \text{ s}$) et dans la plage valide.

### 3. Centrale Inertielle (`obs.imu`)
* `obs.imu.yaw` : Cap du drone en radians ($-\pi$ à $+\pi$, $0 = \text{Est}$).
* `obs.imu.yaw_rate` : Vitesse de lacet en rad/s (dérivée du cap pour l'amortissement).

### 4. Récepteur GPS (`obs.gps`)
* `obs.gps.x`, `obs.gps.y` : Position cartésienne locale métrique estimée.

---

## 🎯 Système de Waypoints Capsulaires Dynamiques

Chaque porte et étape de suivi est matérialisée par une capsule semi-transparente de 2 mètres de large :
* **Couleur initiale :** Rouge ($0\%$ des points).
* **Précision maximale :** Si le centre du bateau passe à **moins de 50 cm ($0.50 \text{ m}$)** du centre de la capsule, vous obtenez **$100\%$ des points** et la capsule passe au **Vert pur** !
* **Dégradé progressif :** Entre 50 cm et 1.0 m, le score est calculé proportionnellement et la couleur effectue un fondu dynamique (Fade Rouge $\rightarrow$ Vert) visible dans Gazebo.

> [!NOTE]
> **Bouée cardinale :** Aucune capsule n'est placée sur la cardinale afin de ne pas encourager le rase-cailloux dangereux. L'arbitre valide automatiquement le bon quadrant de passage (+250 pts).

---

## 💻 Exécution en Local

### Option A : Avec Docker (Recommandé)
Nécessite uniquement Docker installé sur votre machine (Linux, macOS ou Windows avec WSL2) :
```bash
# 1. Autoriser l'affichage graphique X11 (sur Linux)
xhost +local:root

# 2. Lancer la simulation et le contrôleur
./starter_kit/run_docker.sh
```

### Option B : Installation Native (Ubuntu 22.04 / 24.04 avec Gazebo Jetty)
```bash
# Terminal 1 : Lancer le monde d'entraînement
gz sim -v 3 -r ./worlds/practice_world.sdf

# Terminal 2 : Lancer votre contrôleur Python
python3 ./starter_kit/student_controller.py
```

---

## 📤 Soumission & Évaluation Automatique

1. Travaillez sur une branche dédiée :
   ```bash
   git checkout -b feature/mon-super-controleur
   git add starter_kit/student_controller.py
   git commit -m "feat: Amélioration du suivi de quai au Ping2"
   git push origin feature/mon-super-controleur
   ```
2. Ouvrez une **Pull Request** vers la branche `master` sur GitHub.
3. Le workflow CI GitHub Actions démarre automatiquement :
   * Il construit l'environnement dans un conteneur headless sécurisé.
   * Il teste votre contrôleur face à une graine secrète avec courant marin et perturbations.
   * Il publie un rapport détaillé en commentaire de votre PR avec votre score et vos badges.
   * Il transmet votre résultat au **Scoreboard officiel**.

### 🎥 Rejouer votre course en 3D
Chaque évaluation génère un artéfact GitHub contenant l'enregistrement physique complet de votre run :
1. Téléchargez le fichier `gz-replay-pr-*.zip` depuis l'onglet Actions de votre PR.
2. Décompressez l'archive et lancez :
   ```bash
   gz sim --playback ./output/replay
   ```
Vous pourrez observer votre bateau évoluer dans les vagues, voir les capsules changer de couleur et analyser votre trajectoire au millimètre près !\n