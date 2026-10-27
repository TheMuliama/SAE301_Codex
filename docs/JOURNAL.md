# Journal de développement fondé sur les preuves

Ce journal distingue systématiquement les essais logiciels/simulés des essais
sur matériel ADALM-Pluto. Les dates utilisent le fuseau local de l'environnement
de développement (Indian/Reunion).

## Entrée : 2026-10-27 — Jalon 1, fondation

**Objectif**

Créer un paquet Python installable, une configuration validée, un CLI avec
diagnostic non émetteur et les procédures de préparation Linux/Windows.

**Modifications apportées**

- Ajout de `AGENTS.md`, `pyproject.toml`, des fichiers de dépendances épinglés,
  de `.gitignore`, du paquet `sae301`, des scripts `setup.sh`/`setup.ps1` et des
  tests de fondation.
- La configuration regroupe les paramètres DSP, radio, simulation et protocole,
  accepte un document JSON et refuse les champs inconnus.
- Le CLI fournit `transmitter`, `receiver` et `check`; `check` est explicitement
  non émetteur et le mode matériel opérationnel requiert `--rf-authorized`.

**Décisions techniques**

Python 3.10+ conserve une base commune Linux/Windows. NumPy est la seule
dépendance d'exécution obligatoire; PyADI-IIO reste un extra afin que la
simulation fonctionne sans pile libiio. Le cahier des charges Python/PyADI-IIO
prime sur les anciennes notes GNU Radio de `references/notes_initiales.pdf`.

**Impact sur l'architecture**

La configuration devient la source commune des futurs composants DSP,
transports et applications. Le CLI charge les composants d'exécution à la
demande afin que le diagnostic de simulation reste indépendant de PyADI-IIO.

**Risques de régression potentiels**

Les versions épinglées peuvent nécessiter une mise à jour future. PowerShell et
les installations fraîches dépendent de plateformes non présentes ici. Les
limites de gains du Pluto sont validées mais pas encore mesurées sur le matériel.

**Impact attendu**

Installation reproductible, erreurs de configuration précoces et impossibilité
d'activer accidentellement le chemin matériel via le CLI sans confirmation.

**Tests effectués**

- `.venv/bin/python -m pytest tests/test_foundation.py -q` : 8 réussis en 0,04 s.
- `.venv/bin/python -m compileall -q sae301` : succès, aucune sortie.
- `bash -n scripts/setup.sh` : succès, aucune sortie.
- `.venv/bin/python -m sae301 check --mode simulation` : configuration et
  dépendances simulation OK; RF non demandée.
- `.venv/bin/python -m pytest tests/test_foundation.py --junitxml=docs/evidence/milestone1-foundation.xml -q` :
  8 réussis en 0,04 s.
- `git init` : échec (`.git/info/: Read-only file system`); aucun dépôt n'a pu
  être initialisé dans cet environnement.

**Preuves**

`docs/evidence/milestone1-foundation.xml` contient le rapport JUnit. Aucun essai
radio ni accès à un périphérique n'a eu lieu.

**Critères d'acceptation**

- Import, configuration et CLI de base : **PASS**.
- Diagnostic simulation sans émission : **PASS**.
- Syntaxe du script Linux : **PASS**.
- Installation Linux depuis un clone vierge : **NOT TESTED**.
- Exécution du script Windows : **NOT TESTED**.
- Initialisation Git : **FAIL** (montage `.git` en lecture seule).

**Résultat**

**PARTIELLEMENT ATTEINT** — la fondation logicielle vérifiée fonctionne; la
validation multiplateforme réelle et Git restent contraintes par l'environnement.

**Limites connues**

Les commandes opérationnelles attendent encore les modules DSP, protocole et
transport. Aucun test matériel n'a été exécuté.

**Action suivante**

Implémenter et tester le codage UTF-8, la trame DATA/ACK, QPSK, le filtre RRC,
la synchronisation de symbole/préambule et la correction de phase constante.

## Entrée : 2026-10-27 — Jalon 2, traitement QPSK

**Objectif**

Transformer les octets en QPSK filtrée RRC et retrouver les symboles malgré un
retard d'échantillonnage, une phase constante et un bruit contrôlé.

**Modifications apportées**

Ajout des conversions MSB-first, de la constellation QPSK Gray, du calcul RRC,
de la mise en forme, du filtre adapté, de la recherche des huit phases symbole,
de la corrélation de préambule et de l'estimation du gain complexe.

**Décisions techniques**

Le récepteur maximise une corrélation normalisée du préambule sur chaque phase
d'échantillonnage. Cette méthode simple est observable et suffisante pour le MVP;
une boucle de Gardner/Costas aurait ajouté de la complexité avant toute preuve
matérielle de nécessité. Le RRC 0,35, 8 symboles et 8 échantillons/symbole donne
125 ksymboles/s à 1 Méchantillon/s.

**Impact sur l'architecture**

La chaîne DSP est indépendante du transport. `decode_burst()` constitue la
frontière commune aux futurs transports UDP et Pluto.

**Risques de régression potentiels**

Un offset fréquent, une phase variable ou une dérive d'horloge peut dégrader la
corrélation et les décisions. Le seuil 0,72 devra être caractérisé sur matériel.

**Impact attendu**

Récupération reproductible des rafales idéales et bruitées sans contourner la
modulation/démodulation QPSK.

**Tests effectués**

- `.venv/bin/python -m pytest tests/test_protocol.py tests/test_dsp.py -q` :
  19 réussis en 0,37 s.
- Même sélection avec
  `--junitxml=docs/evidence/milestone2-3-dsp-protocol.xml` : 19 réussis en 0,15 s.

**Preuves**

`docs/evidence/milestone2-3-dsp-protocol.xml`. Le test DSP couvre 117° de phase,
5 échantillons de retard et un canal déterministe à 10 dB SNR sur 128 octets.

**Critères d'acceptation**

- Mapping/démapping QPSK : **PASS**.
- Forme et énergie du RRC : **PASS**.
- Synchronisation préambule et phase symbole : **PASS**.
- Correction de phase constante : **PASS**.
- Tolérance déterministe à 10 dB SNR : **PASS**.
- Comportement avec offsets matériels réels : **NOT TESTED**.

**Résultat**

**ATTEINT** pour le modèle logiciel simulé; la robustesse radio physique reste
explicitement hors de cette preuve.

**Limites connues**

Absence intentionnelle de correction CFO, de récupération adaptative d'horloge
et d'égalisation de canal.

**Action suivante**

Employer la chaîne DSP dans le protocole DATA/ACK complet et le transport UDP.

## Entrée : 2026-10-27 — Jalon 3, protocole DATA/ACK

**Objectif**

Définir et valider une trame binaire sûre avec CRC, identifiant et ACK strict.

**Modifications apportées**

Ajout de `protocol.py`, des trames DATA/ACK, CRC-32, identifiants 32 bits,
limites de charge, validation des tailles/types et documentation exacte dans
`docs/PROTOCOL.md`.

**Décisions techniques**

Le protocole utilise des champs big-endian fixes et une charge bornée à 1 024
octets. Un ACK est nécessairement vide et ne valide que le même identifiant. Le
point de départ aléatoire puis l'incrément réduisent le risque qu'un ACK ancien
d'une exécution précédente corresponde au message courant.

**Impact sur l'architecture**

Le protocole est la représentation commune située entre l'application et la
chaîne DSP; aucun transport ne manipule directement le texte décodé.

**Risques de régression potentiels**

Tout changement du préambule, de l'ordre des octets ou du CRC rompt la
compatibilité sur l'air et doit faire évoluer documentation et tests ensemble.

**Impact attendu**

Rejet explicite des trames corrompues, surdimensionnées, inconnues ou tronquées,
et impossibilité pour un ACK d'identifiant différent de confirmer un DATA.

**Tests effectués**

Les deux commandes du jalon 2 incluent les tests protocole : UTF-8, empaquetage
des bits, sérialisation DATA/ACK, CRC altéré, limite, identifiants et validation
d'ACK. Résultat partagé : 19 réussis, aucun échec.

**Preuves**

`docs/evidence/milestone2-3-dsp-protocol.xml` et spécification
`docs/PROTOCOL.md`.

**Critères d'acceptation**

- Format DATA et ACK documenté/testé : **PASS**.
- CRC et corruption détectée : **PASS**.
- Mauvais identifiant ACK refusé : **PASS**.
- Charges invalides/surdimensionnées refusées : **PASS**.
- Suite et bouclage des identifiants : **PASS**.

**Résultat**

**ATTEINT** dans les tests logiciels.

**Limites connues**

Le protocole n'offre ni authentification, ni chiffrement, ni FEC, ni gestion de
collision et, conformément au périmètre, aucune réémission automatique.

**Action suivante**

Implémenter le transport I/Q UDP et les boucles applicatives émetteur/récepteur
avec ACK automatique, doublons, corruption et timeouts.

## Entrée : 2026-10-27 — Jalon 4, simulation complète DATA/ACK

**Objectif**

Faire communiquer deux processus par de vrais échantillons I/Q UDP en réutilisant
intégralement le DSP, le protocole et la validation ACK.

**Modifications apportées**

- Ajout de l'interface `IQTransport` et du transport UDP fragmenté `complex64`.
- Ajout des défauts déterministes AWGN, phase et retard d'échantillonnage.
- Ajout des machines d'état émetteur/récepteur, ACK automatique, purge des ACK
  obsolètes, timeout, filtre d'identifiant et fenêtre de doublons.
- Ajout des boucles terminal, du mode message unique et du mode réception unique.

**Décisions techniques**

Une rafale peut dépasser la taille maximale d'un datagramme; elle est donc
fragmentée avec identifiant, index, nombre de fragments et nombre d'échantillons.
Une perte de fragment produit un timeout, jamais une trame texte partielle. Le
CRC protocolaire reste l'arbitre final de l'intégrité. Un doublon valide est
signalé et acquitté à nouveau.

**Impact sur l'architecture**

Les applications ne connaissent pas UDP : elles consomment et produisent des
rafales via `IQTransport`. Elles emploieront exactement le même chemin avec le
Pluto.

**Risques de régression potentiels**

UDP ne garantit ni livraison ni ordre; une rafale incomplète expire. Les pare-feu
peuvent bloquer les deux ports. Le protocole UDP de simulation n'est pas chiffré.

**Impact attendu**

Validation du protocole bidirectionnel avant tout branchement RF, y compris des
conditions d'échec qui ne doivent jamais afficher un faux succès.

**Tests effectués**

- Première exécution sandbox de
  `.venv/bin/python -m pytest tests/test_simulation.py -q` : 7 réussis, 1 échec,
  socket local interdit par le sandbox (`PermissionError`).
- Première exécution autorisée : 7 réussis, 1 échec; le test supposait à tort
  qu'une charge de 200 octets dépassait 60 000 octets I/Q (valeur réelle 57 856).
- Après charge portée à 320 octets : 8 réussis en 0,98 s.
- Deux processus réels : commandes et sorties dans
  `docs/evidence/milestone4-cli-processes.txt`; texte, CRC et ACK observés.
- Régression avec JUnit à ce stade : 35 réussis en 1,03 s.
- Tests renforcés finaux (ACK obsolète, UTF-8 invalide, deux transactions et UDP
  bidirectionnel bruité) : 12 tests simulation réussis en 1,34 s.

**Preuves**

`docs/evidence/milestone4-simulation.xml` et
`docs/evidence/milestone4-cli-processes.txt`.

**Critères d'acceptation**

- DATA complet et reconstruction du texte : **PASS**.
- ACK automatique/reçu/validé : **PASS**.
- Timeout et mauvais/corrompu ACK sans faux succès : **PASS**.
- DATA corrompu ou UTF-8 invalide sans ACK : **PASS**.
- Messages successifs et doublons : **PASS**.
- UDP fragmenté et défauts reproductibles : **PASS**.
- Deux processus CLI séparés : **PASS**.

**Résultat**

**ATTEINT** en simulation. Aucun résultat de cette entrée ne provient d'un SDR.

**Limites connues**

La fragmentation UDP ne réémet pas un fragment perdu et ne convient qu'à un
réseau local contrôlé. Aucun mécanisme de sécurité réseau n'est fourni.

**Action suivante**

Implémenter PyADI-IIO, le diagnostic non émetteur et la garde d'autorisation RF.

## Entrée : 2026-10-27 — Jalon 5, intégration ADALM-Pluto préparée

**Objectif**

Intégrer les API PyADI-IIO sans émettre, tester le comportement par double et
évaluer la connectivité disponible.

**Modifications apportées**

Ajout de `transport/pluto.py` : connexion, configuration LO/taux/bande/gains,
mode manuel RX, TX non cyclique, mise à l'échelle DAC, attente de fin de rafale,
deux buffers RX chevauchants, suppression DC, purge, timeouts et fermeture. Le
diagnostic ouvre et lit seulement les contrôles. `send_samples` refuse tout TX
si `allow_transmit` est faux, indépendamment du CLI.

**Décisions techniques**

Les propriétés et méthodes ont été vérifiées dans le code PyADI-IIO 0.0.21
installé (`adi.Pluto`, `rx`, `tx`, `rx_destroy_buffer`, `tx_destroy_buffer`). Une
rafale maximale tient dans un buffer 65 536; concaténer deux captures protège le
cas où elle traverse une frontière. L'échelle DAC utilise 70 % de 2¹⁴ et le gain
complexe est ensuite estimé par le préambule.

**Impact sur l'architecture**

Le matériel implémente la même interface I/Q que la simulation; aucune branche
matérielle n'existe dans le protocole ou le DSP.

**Risques de régression potentiels**

La durée réelle de vidage TX, la latence USB/IP, le niveau DC, le gain et les
transitions demi-duplex dépendent du firmware/runtime et restent à mesurer. Deux
buffers ajoutent une latence de capture.

**Impact attendu**

Chemin matériel prêt pour un essai contrôlé, avec échec explicite sur dépendance,
connexion, timeout ou absence d'autorisation.

**Tests effectués**

- `.venv/bin/python -m pytest tests/test_pluto_transport.py -q` : 5 réussis en
  0,12 s, puis 0,09 s après amélioration du diagnostic.
- `timeout 10s .venv/bin/python -m sae301 check --mode hardware` : code 2,
  `libiio version 1.x required, found version 0`; aucune émission demandée.
- Aucun objet Pluto physique accessible et aucun appel TX réel.

**Preuves**

Tests avec double dans `tests/test_pluto_transport.py`. Le diagnostic d'échec est
reproductible dans l'environnement courant; aucune mesure RF n'existe.

**Critères d'acceptation**

- Configuration/API PyADI-IIO par double : **PASS**.
- Refus TX sans autorisation : **PASS**.
- Buffers, timeout et fermeture par double : **PASS**.
- Chargement d'une pile PyADI/libiio locale compatible : **FAIL**.
- Détection d'un ADALM-Pluto physique : **NOT TESTED**.
- Transmission/réception/ACK RF : **NOT TESTED**.

**Résultat**

**PARTIELLEMENT ATTEINT** — implémentation et tests isolés terminés; validation
physique impossible avec la pile et le matériel disponibles.

**Limites connues**

Les réglages -30 dB TX et +30 dB RX sont des valeurs initiales, pas des niveaux
validés. La pile libiio doit être réparée avant le premier diagnostic matériel.

**Action suivante**

Finaliser documentation/CI, valider une installation Linux vierge et préparer
la procédure contrôlée du second poste.

## Entrée : 2026-10-27 — Jalon 7, validation finale et déploiement

**Objectif**

Vérifier une installation propre, la qualité statique, la régression complète et
livrer les procédures du second ordinateur sans surévaluer le statut matériel.

**Modifications apportées**

Ajout du README, de la CI Ubuntu/Windows Python 3.10/3.12, de la documentation de
déploiement, du prompt Codex, du rapport final, de l'exemple JSON et des preuves.
La validation croisée empêche aussi une charge configurée de dépasser un buffer
RX physique.

**Décisions techniques**

La CI n'installe pas PyADI-IIO car les tests matériels utilisent un double et la
simulation ne doit pas dépendre de libiio. Les dépendances de développement sont
épinglées. Une copie sous `/tmp`, sans environnement ni caches, a exercé le vrai
script Linux.

**Impact sur l'architecture**

Aucun changement de protocole. Les contraintes de taille DSP/radio sont désormais
validées ensemble et les procédures rendent explicites les paramètres communs.

**Risques de régression potentiels**

La CI distante n'a pas encore été exécutée par GitHub. PowerShell et Windows
restent non vérifiés localement. Les versions épinglées devront être maintenues.

**Impact attendu**

Un clone Linux/Windows peut être préparé de façon reproductible; le second Codex
dispose de limites d'autorité et de critères matériels précis.

**Tests effectués**

- Installation initiale de Ruff/mypy dans le sandbox : échec DNS; relance réseau
  autorisée réussie (`ruff 0.11.13`, `mypy 1.16.1`).
- Premier Ruff : 19 erreurs; corrections; résultat `All checks passed!`.
- mypy local avec NumPy 2.5.4 et cible 3.10 : échec dans les stubs NumPy utilisant
  la syntaxe 3.12; contrôle local explicite 3.12 : succès sur 14 fichiers.
- Copie propre `/tmp/sae301-clean.f4CpYV`, `./scripts/setup.sh` : succès; NumPy
  2.2.6, diagnostic simulation OK et paquet éditable installé.
- Copie propre, premier mypy cible 3.10 : 4 erreurs de forme NDArray; annotations
  corrigées; relance : succès sur 14 fichiers.
- Copie propre, Ruff : `All checks passed!`.
- Copie propre, pytest après correction : 42 réussis en 1,09 s (avant ajout des
  quatre tests d'intégration renforcés finaux).
- Dépôt courant, `.venv/bin/python -m pytest
  --junitxml=docs/evidence/final-regression.xml -q` : 47 réussis en 1,39 s.
- Copie propre avec dépendances épinglées, `.venv/bin/python -m pytest -q` :
  47 réussis en 1,45 s.
- Dépôt courant, `.venv/bin/python -m ruff check .` : `All checks passed!`.
- Dépôt courant, `.venv/bin/python -m mypy --python-version 3.12 sae301` :
  succès sur 14 fichiers; la cible 3.10 a été vérifiée dans la copie propre.

**Preuves**

Les rapports finaux et versions sont dans `docs/evidence/`. Aucun commit n'est référencé :
`git init` reste impossible car `.git/info` est monté en lecture seule.

**Critères d'acceptation**

- Installation Linux propre et diagnostic : **PASS**.
- Tests/lint/types avec dépendances épinglées : **PASS**.
- Documentation et prompt second ordinateur : **PASS**.
- Workflow CI Linux/Windows créé : **PASS**.
- Exécution CI distante : **NOT TESTED**.
- Exécution Windows locale : **NOT TESTED**.
- Validation matérielle : **NOT TESTED**.

**Résultat**

**PARTIELLEMENT ATTEINT** — logiciel et déploiement Linux vérifiés; Windows, CI
distante et matériel restent honnêtement non vérifiés.

**Limites connues**

Voir `docs/FINAL_REPORT.md`; le jalon 6 RF reste entièrement à réaliser sous
autorisation avec deux appareils et une pile libiio fonctionnelle.

**Action suivante**

Sur le second poste, suivre `docs/DEPLOYMENT.md`, valider la simulation, réparer
la pile libiio si nécessaire, puis réaliser le jalon 6 uniquement après contrôle
physique documenté du montage.
