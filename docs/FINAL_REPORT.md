# Rapport final de vérification

Date : 2026-10-27

## Atteint

- Paquet Python et CLI émetteur/récepteur/diagnostic.
- Encodage UTF-8 strict, bits MSB-first et QPSK Gray.
- Filtres RRC émission/réception, recherche de phase symbole/préambule et
  correction d'une phase complexe constante.
- Protocole DATA/ACK versionné, identifiants 32 bits, CRC-32 et limites de taille.
- Transport UDP de vrais I/Q `complex64`, fragmentation et défauts déterministes.
- ACK automatique, timeout explicite, rejet d'ACK erroné/corrompu, corruption
  DATA, doublons et messages successifs.
- Transport PyADI-IIO protégé par autorisation, configuration commune,
  buffers TX/RX, capture chevauchante, erreurs et libération des ressources.
- Scripts Linux/Windows, documentation de déploiement et CI Linux/Windows.
- Installation Linux propre par `scripts/setup.sh`, diagnostic et suite complète.

## Preuves logicielles

- 47 tests : réussis localement sur Python 3.12.3/Linux.
- Ruff : aucun problème après correction des 19 écarts initiaux.
- mypy : aucun problème dans 14 fichiers avec la cible locale Python 3.12.
- Deux processus CLI UDP : message UTF-8 reçu, CRC annoncé valide et ACK reçu.
- Copie Linux propre avec dépendances épinglées : 47 tests réussis.
- Rapports JUnit : `docs/evidence/`.

Les conditions et commandes précises restent la source de vérité dans
`docs/JOURNAL.md`; ce rapport ne transforme pas ces preuves en validation RF.

## Partiellement atteint

- Windows : scripts et CI préparés, mais aucune exécution Windows locale n'a été
  possible dans cet environnement Linux.
- PyADI-IIO : comportement testé avec double; le diagnostic local a détecté une
  incompatibilité entre PyADI-IIO et le runtime libiio disponible.

## Non vérifié

- Détection d'un vrai Pluto avec une pile libiio fonctionnelle.
- Niveaux RF, atténuation, saturation ADC/DAC et sécurité du montage.
- Réception QPSK à 868 MHz entre les deux Pluto physiques.
- Temporisation réelle de commutation TX/RX et ACK.
- Robustesse face au CFO, dérive d'horloge, multipath et bruit matériel.

## Critère final matériel

Le projet ne pourra déclarer la communication physique réussie qu'après un essai
autorisé où A transmet un DATA, B affiche exactement le texte avec CRC valide,
B transmet l'ACK, et A valide l'ACK de même identifiant. Les captures, réglages
et versions devront être ajoutés au journal sans extrapoler depuis la simulation.
