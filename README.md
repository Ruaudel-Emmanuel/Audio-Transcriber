# 🎧 Audio Transcriber

Ce projet illustre mon approche : une IA 100 % locale qui transforme une tâche chronophage — comptes rendus, réunions — en un document exploitable en quelques minutes.

---

## 🤝 Ce projet, c'est aussi mon métier

**Emmanuel Ruaudel — Directeur de la Transformation Numérique pour TPE/PME.**
J'aide les dirigeants à libérer 5 à 10 h par semaine en automatisant leurs tâches
répetitives : audit des processus, cas d'usage IA à fort ROI, déploiement et
fiabilisation (n8n · Python · IA locale).

👉 [LIGNE D'ACCROCHE DU REPO ICI]

📧 [ruaudel.emmanuel@orange.fr](mailto:ruaudel.emmanuel@orange.fr) · 🌐 [rennesdev.fr](https://rennesdev.fr)

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

## 🧠 Prompt idéal de départ

> Le prompt suivant est celui que j'aurais dû écrire pour arriver au plus proche
> de ce projet en un seul échange avec une IA générative.

Tu es un développeur Python expert en applications desktop et traitement audio.

Crée une application Windows tkinter qui capture le son système (loopback), le transcrit localement avec faster-whisper, et résume le texte avec un LLM local (Ollama) :

- **Capture audio** : sounddevice, entrée au choix (Stereo Mix / VB-Cable / micro), 16 kHz mono, buffer en mémoire puis sauvegarde WAV
- **Transcription** : faster-whisper (modèles tiny/base/small/medium sélectionnables), VAD filter, timestamps, langue française par défaut
- **Résumé** : requête POST à Ollama (/api/generate), modèle configurable, prompt structuré (sujet / points clés / décisions)
- **Interface** : tkinter, bouton Record/Stop unique, sélecteur de périphérique, barre de progression indéterminée, champ résultat éditable, bouton Sauvegarder en .md, bouton Effacer
- **Configuration** : persistée dans ~/.audio-transcriber-config.json (périphérique, modèles whisper/Ollama, dossier de sortie)
- **Contraintes** : thread worker pour ne pas bloquer l'UI, compatible CPU uniquement (int8), zéro dépendance externe autre que les packages pip
- **Cible** : Windows 11, Python 3.11+, Ollama installé localement
