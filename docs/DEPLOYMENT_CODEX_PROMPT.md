# Prompt de déploiement pour un second Codex

Copier le bloc suivant dans Codex sur l'ordinateur B :

```text
Tu prépares le poste récepteur B du projet SAÉ 3.01 présent dans ce dépôt.

1. Lis intégralement AGENTS.md, README.md, docs/DEPLOYMENT.md et
   docs/PROTOCOL.md avant toute modification.
2. Détecte l'OS et la version Python. Exécute scripts/setup.sh sous Linux ou
   scripts/setup.ps1 sous Windows. N'installe aucun paquet système, pilote ou
   composant global sans mon autorisation.
3. Résous uniquement les problèmes sûrs de dépendances/configuration locale.
   Garde les adresses et réglages machine dans config.local.json, jamais dans Git.
4. Exécute le diagnostic simulation, la suite pytest, Ruff et mypy. Donne les
   commandes exactes et les résultats réels, y compris les échecs.
5. Lance un échange de simulation DATA/ACK à deux processus. Confirme que les
   échantillons I/Q UDP sont utilisés, que le texte/CRC est valide et que
   l'émetteur reçoit un ACK au bon identifiant.
6. Si un ADALM-Pluto est connecté, exécute seulement `python -m sae301 check
   --mode hardware --pluto-uri ...`. Ce diagnostic ne doit pas transmettre.
7. Compare avec le poste A : protocole v1, 868 MHz, 1 MS/s, bande 500 kHz,
   8 échantillons/symbole, RRC 0,35 sur 8 symboles, charge maximale 1024 octets.
8. Prépare le récepteur. Ne lance aucune émission/ACK RF tant que je n'ai pas
   confirmé les câbles coaxiaux, atténuateurs, puissances, limites matérielles et
   conditions de laboratoire/réglementaires. Même après confirmation, utilise
   obligatoirement --rf-authorized.
9. Termine par la commande exacte pour démarrer le récepteur, les versions,
   tests PASS/FAIL/NOT TESTED et tout blocage matériel.
10. Ne modifie pas la logique applicative/protocolaire et ne pousse aucune
    modification locale vers GitHub sans autorisation explicite.
```

