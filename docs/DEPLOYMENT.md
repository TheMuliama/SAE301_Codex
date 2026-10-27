# Déploiement sur le second ordinateur

L'ordinateur B exécute normalement le récepteur principal et émet les ACK. Ne
modifiez pas la logique protocolaire pour l'adapter à une machine; utilisez un
fichier `config.local.json` ignoré par Git ou les options CLI.

## 1. Préparer une copie propre

1. Cloner le dépôt GitHub dans un chemin sans synchronisation automatique.
2. Lire `AGENTS.md`, `README.md`, ce document et `docs/PROTOCOL.md`.
3. Ne pas copier `.venv`, `.pytest_cache`, logs ou configuration locale depuis A.

## 2. Installer

Linux :

```bash
./scripts/setup.sh
```

Windows PowerShell :

```powershell
.\scripts\setup.ps1
```

Pour un Pluto, installer d'abord le runtime/pilote libiio adapté à l'OS depuis
une source Analog Devices ou le gestionnaire de paquets de la distribution,
puis relancer avec `--with-pluto` (Linux) ou `-WithPluto` (Windows). Aucun script
du projet n'installe de composant système.

## 3. Valider sans matériel

```bash
.venv/bin/python -m sae301 check --mode simulation
.venv/bin/python -m pytest -q
.venv/bin/python -m ruff check .
.venv/bin/python -m mypy sae301
```

Sous Windows, remplacer `.venv/bin/python` par
`.\.venv\Scripts\python.exe`.

Faire ensuite un essai UDP à deux terminaux avec les commandes de simulation du
README. Pour deux ordinateurs, ouvrir uniquement les deux ports UDP convenus.

## 4. Vérifier la compatibilité A/B

Les valeurs suivantes doivent être identiques :

| Paramètre | Valeur par défaut |
|---|---:|
| Protocole | 1 |
| Fréquence | 868 000 000 Hz |
| Échantillonnage | 1 000 000 échantillons/s |
| Bande RF | 500 000 Hz |
| Échantillons/symbole | 8 |
| RRC | roll-off 0,35; étendue 8 symboles |
| Charge maximale | 1 024 octets |

Comparer les deux copies de `docs/PROTOCOL.md` ou, de préférence, déployer le
même commit Git. Les adresses UDP et URI Pluto restent propres à chaque poste.

## 5. Diagnostic Pluto sans émission

Brancher le Pluto B par USB, vérifier son apparition dans les outils libiio du
système, puis :

```bash
.venv/bin/python -m sae301 check --mode hardware --pluto-uri ip:192.168.2.1
```

Cette commande ouvre le contexte et lit les contrôles attendus sans configurer
le signal et sans appeler TX. Corriger d'abord tout problème de runtime libiio,
pilote, pare-feu USB/IP ou URI.

## 6. Préparer l'essai RF câble

Avant toute commande `--rf-authorized`, faire valider par la personne
responsable du laboratoire :

- Pluto A TX → atténuateur approprié → Pluto B RX;
- Pluto B TX → atténuateur approprié → Pluto A RX;
- atténuation totale, puissance TX, niveaux RX et limites des appareils;
- environnement sans antenne involontaire et conformité réglementaire.

Une fois validé, commande exacte du récepteur B :

```bash
.venv/bin/python -m sae301 receiver --mode hardware \
  --pluto-uri ip:192.168.2.1 --rf-authorized
```

Puis démarrer l'émetteur A avec la commande du README. Capturer les sorties des
deux terminaux et noter gains, atténuation, câbles, versions et erreurs dans une
nouvelle entrée de `docs/JOURNAL.md`. Ne déclarer le jalon matériel réussi
qu'après réception du texte, CRC valide et ACK correspondant observés réellement.

## 7. Règles de changement

- Résoudre localement les dépendances et paramètres sûrs.
- Ne pas modifier préambule, constellation, structure de trame ou paramètres
  communs sur un seul ordinateur.
- Ne pas pousser `config.local.json`, journaux machine, secrets ou captures lourdes.
- Ne pas pousser vers GitHub sans autorisation explicite.
- Rapporter la commande exacte de démarrage, versions, tests, erreurs et statut
  matériel `PASS`, `FAIL` ou `NOT TESTED`.

