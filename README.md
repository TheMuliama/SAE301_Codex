# SAÉ 3.01 — liaison QPSK entre deux ADALM-Pluto

Application terminal Python pour transmettre du texte en QPSK à 868 MHz,
valider les trames par CRC-32 et retourner automatiquement un ACK. Le mode
simulation échange les **échantillons I/Q modulés** par UDP; il ne contourne ni
la modulation, ni la synchronisation, ni le protocole.

## État vérifié

- Chaîne UTF-8 → DATA/CRC → QPSK/RRC → synchronisation → texte : testée en simulation.
- ACK automatique, timeout, mauvais ACK, corruption, doublons et messages successifs : testés.
- Deux processus CLI sur UDP local : testés.
- Transport PyADI-IIO : testé avec un double logiciel; **pas avec un Pluto physique**.
- Communication RF et ACK physique : **NOT TESTED**.

Les résultats exacts sont dans [le journal](docs/JOURNAL.md) et
[le rapport final](docs/FINAL_REPORT.md).

## Sécurité RF

Ne reliez jamais directement une sortie TX à une entrée RX sans atténuation
appropriée. Avant `--rf-authorized`, vérifiez les deux câbles coaxiaux, les deux
atténuateurs, les niveaux TX/RX, les limites des Pluto et les règles du
laboratoire/réglementaires. Le drapeau confirme ces vérifications; le logiciel
ne peut pas les mesurer.

Le diagnostic `check` n'émet aucun signal RF.

## Installation

Python 3.10+ est requis. Les versions de dépendances reproductibles sont dans
`requirements*.txt`.

### Linux

```bash
./scripts/setup.sh
source .venv/bin/activate
```

Pour préparer aussi le matériel, installez d'abord une version compatible de
libiio fournie par votre distribution/Analog Devices, puis :

```bash
./scripts/setup.sh --with-pluto
```

Le script ne tente pas d'installer de paquet système et ne demande pas les
privilèges administrateur.

### Windows (PowerShell)

Installez Python depuis python.org avec le lanceur `py`, puis :

```powershell
.\scripts\setup.ps1
```

Pour le Pluto, installez au préalable le runtime libiio et les pilotes Windows
Analog Devices adaptés, puis :

```powershell
.\scripts\setup.ps1 -WithPluto
```

## Simulation locale — commandes exactes

Dans le terminal B, démarrez d'abord le récepteur :

```bash
.venv/bin/python -m sae301 receiver --mode simulation
```

Dans le terminal A :

```bash
.venv/bin/python -m sae301 transmitter --mode simulation
```

Le récepteur utilise par défaut `127.0.0.1:9000` et l'émetteur
`127.0.0.1:9001`. Un essai non interactif reproductible est possible avec :

```bash
.venv/bin/python -m sae301 receiver --mode simulation --once
.venv/bin/python -m sae301 transmitter --mode simulation --message "Bonjour QPSK"
```

Les deux dernières commandes doivent être lancées dans deux terminaux, le
récepteur en premier.

### Simulation avec défauts contrôlés

```bash
.venv/bin/python -m sae301 transmitter --mode simulation \
  --snr-db 14 --phase-offset-deg 83 --timing-offset-samples 5 --seed 301
```

Le bruit complexe, la phase et le retard sont appliqués aux I/Q sortants. Une
même graine et une même séquence de messages produisent les mêmes défauts.

### Simulation sur deux ordinateurs

Supposons `IP_A=192.0.2.10` et `IP_B=192.0.2.20`. Sur B :

```bash
.venv/bin/python -m sae301 receiver --mode simulation \
  --bind-host 0.0.0.0 --bind-port 9000 --peer-host 192.0.2.10 --peer-port 9001
```

Sur A :

```bash
.venv/bin/python -m sae301 transmitter --mode simulation \
  --bind-host 0.0.0.0 --bind-port 9001 --peer-host 192.0.2.20 --peer-port 9000
```

Autorisez ces ports UDP dans les pare-feu. Le transport de simulation n'est ni
chiffré ni authentifié; utilisez-le seulement sur un réseau de confiance.

## Diagnostic et matériel

Vérification purement logicielle :

```bash
.venv/bin/python -m sae301 check --mode simulation
```

Vérification de connectivité Pluto, toujours sans émission :

```bash
.venv/bin/python -m sae301 check --mode hardware --pluto-uri ip:192.168.2.1
```

Après validation physique et autorisation, sur l'ordinateur B :

```bash
.venv/bin/python -m sae301 receiver --mode hardware \
  --pluto-uri ip:192.168.2.1 --rf-authorized
```

Sur l'ordinateur A :

```bash
.venv/bin/python -m sae301 transmitter --mode hardware \
  --pluto-uri ip:192.168.2.1 --rf-authorized
```

Les deux rôles utilisent TX et RX : B retourne l'ACK et A le reçoit. Chaque URI
est locale à son ordinateur; il est normal qu'elles soient identiques.

## Configuration JSON

Copiez `config.example.json` vers `config.local.json` (ignoré par Git), adaptez
les adresses/ports locaux, puis ajoutez `--config config.local.json`. Les options
CLI explicites remplacent les champs correspondants. Ne versionnez pas les
adresses propres aux machines.

Paramètres communs à garder identiques : fréquence 868 MHz, 1 MS/s, bande
500 kHz, 8 échantillons/symbole, RRC 0,35 sur 8 symboles, protocole version 1.

## Tests et qualité

```bash
.venv/bin/python -m pytest -q
.venv/bin/python -m ruff check .
.venv/bin/python -m mypy sae301
```

La CI exécute ces contrôles sur Ubuntu et Windows avec Python 3.10 et 3.12. Les
tests marqués `hardware` resteraient exclus d'une CI sans équipement; les tests
du transport Pluto actuels utilisent un double et n'émettent rien.

## Documentation

- [Architecture](docs/ARCHITECTURE.md)
- [Protocole exact](docs/PROTOCOL.md)
- [Déploiement du second ordinateur](docs/DEPLOYMENT.md)
- [Prompt pour le second Codex](docs/DEPLOYMENT_CODEX_PROMPT.md)
- [Journal et preuves](docs/JOURNAL.md)

## Limites

Ce MVP ne corrige pas l'offset de fréquence, ne suit pas une dérive d'horloge,
n'égalise pas un canal sélectif, ne gère pas les collisions et ne réémet pas
automatiquement. La synchronisation suppose une phase constante durant la
rafale. Ces choix sont documentés et devront être réévalués à partir de mesures
sur les deux Pluto.

