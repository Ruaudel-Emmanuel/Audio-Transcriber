# 🎧 Audio Transcriber

Capture système → transcription locale → résumé IA → fichier .md

## Prérequis

- **Python 3.11+** sur Windows
- **Ollama** installé et lancé (`ollama serve`)
- Modèles Ollama pour le résumé : `qwen2.5:3b` ou `qwen2.5:7b`
- **FFmpeg** (optionnel, pour meilleure conversion audio)

## ⚠️ Capture du son système (loopback)

Pour enregistrer **tout son qui passe par la carte son** (pas seulement le micro), il faut activer une entrée audio de type **Stereo Mix** ou **Loopback** sur Windows :

### Option A — Activer Stereo Mix (si ta carte son le supporte)
1. Clic droit sur l'icône 🔊 dans la barre des tâches → **Paramètres du son**
2. Dans l'onglet **Entrée**, cherche une entrée nommée « Stereo Mix », « Mix », « Ce qu'on entend »
3. Active-la (certains drivers Realtek l'incluent)

### Option B — VB-Cable (recommandé si Stereo Mix absent)
1. Télécharge [VB-Cable](https://vb-audio.com/Cable/) (gratuit, don de 2 € conseillé)
2. Installe et lance `VBCable.exe` → un câble virtuel apparaît dans les périphériques audio
3. Dans les paramètres son de Windows, `VB-Cable Output` devient la sortie audio par défaut
4. Dans le script, sélectionne `VB-Cable Input` comme périphérique d'enregistrement

### Option C — Windows 11 + Son sans perte (le plus simple)
Certains PC sous Windows 11 récent exposent directement une entrée **« Son de l'ordinateur »** — regarde dans les périphériques d'entrée.

## Installation

```bash
# 1. Créer l'environnement virtuel
python -m venv .venv
.venv\Scripts\activate

# 2. Installer les dépendances
pip install -r requirements.txt
```

## Modèles whisper

Le script utilise `faster-whisper` avec le modèle `small` par défaut (~1.5 Go, bon équilibre vitesse/précision sur CPU).  
Tu peux choisir un autre modèle dans l'interface :

| Modèle | RAM | Vitesse (CPU) | Précision |
|---|---|---|---|
| `tiny` | ~1 Go | ★★★★★ | ★★ |
| `base` | ~1 Go | ★★★★ | ★★★ |
| `small` | ~1.5 Go | ★★★ | ★★★★ |
| `medium` | ~3 Go | ★★ | ★★★★★ |

## Utilisation

```bash
.venv\Scripts\activate
python audio-transcriber.py
```

1. **Lancer le script** → les périphériques d'entrée sont scannés
2. **Sélectionner le bon périphérique** dans le menu déroulant (Stereo Mix / VB-Cable Input / Son de l'ordinateur)
3. Cliquer **🔴 Record** → la capture démarre (tout son qui passe par la carte son)
4. Cliquer **⏹ Stop** → l'enregistrement s'arrête
5. La transcription **faster-whisper** démarre automatiquement (barre de progression)
6. Le résumé **Ollama** s'enchaîne
7. Le résultat s'affiche dans la zone de texte
8. Cliquer **💾 Sauvegarder .md** → choisir l'emplacement du fichier