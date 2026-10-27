# Architecture

## Vue d'ensemble

L'application sépare quatre responsabilités afin que le même protocole et le
même traitement du signal soient exercés en simulation et sur ADALM-Pluto :

1. `framing.py` et `protocol.py` transforment texte, octets et trames DATA/ACK.
2. `qpsk.py` produit les symboles Gray-QPSK et le signal filtré RRC.
3. `synchronization.py` filtre, synchronise, corrige la phase, décide les bits et
   valide la trame.
4. Les applications émetteur/récepteur échangent les échantillons complexes via
   une interface de transport; UDP simulé et PyADI-IIO sont les deux implémentations.

Le chemin complet prévu est :

```text
texte -> UTF-8 -> DATA+CRC -> bits -> QPSK -> RRC -> transport I/Q
      -> RRC adapté -> synchro préambule/phase -> bits -> CRC -> UTF-8
      -> ACK+CRC -> même chaîne en sens inverse
```

## Composants actuels

- `config.py` : dataclasses validées, chargement JSON et paramètres communs.
- `cli.py` : commandes terminal et garde explicite `--rf-authorized`.
- `framing.py` : UTF-8 strict et conversion octets/bits MSB-first.
- `protocol.py` : format binaire, CRC-32, types, identifiants et validation ACK.
- `qpsk.py` : constellation unitaire et filtre RRC.
- `synchronization.py` : filtre adapté, recherche exhaustive des phases symbole,
  corrélation du préambule et correction d'un gain complexe constant.
- `transport/base.py` : contrat des rafales I/Q, erreurs et timeouts.
- `transport/simulation.py` : datagrammes UDP fragmentés et défauts déterministes.
- `transport/pluto.py` : PyADI-IIO, garde TX, mise à l'échelle et buffers.
- `transmitter.py` : transaction DATA, purge des ACK obsolètes et attente stricte.
- `receiver.py` : validation DATA/UTF-8, fenêtre de doublons et ACK automatique.

## Paramètres DSP et radio

Les valeurs par défaut sont 868 MHz, 1 MS/s, 8 échantillons/symbole,
RRC 0,35 sur 8 symboles, bande RF 500 kHz, gain TX -30 dB et gain RX manuel
30 dB. Cela donne 125 ksymboles/s. Les gains sont des réglages initiaux prudents,
pas des niveaux validés pour le montage physique.

## Interfaces publiques

- `AppConfig.from_json()` charge une configuration portable et rejette les
  champs inconnus.
- `serialize_frame()` / `parse_frame()` définissent la frontière protocolaire.
- `modulate_bytes()` construit une rafale complexe à partir d'une trame.
- `decode_burst()` retourne une trame validée et les métriques de synchronisation.

## Différences simulation / matériel

Le transport simulation ajoute de manière déterministe bruit, phase et retard
avant d'envoyer de vrais échantillons `complex64` par UDP. Le transport Pluto
configure et échange ces mêmes échantillons via PyADI-IIO. Seules la mise à
l'échelle, la taille des buffers et la commutation TX/RX sont spécifiques au
matériel. Deux buffers RX successifs sont concaténés : une rafale, bornée à moins
d'un buffer par validation de configuration, reste entière même si elle franchit
une frontière de capture.

## Limites techniques connues

- Pas de correction de décalage de fréquence ni de suivi de dérive d'horloge.
- Phase supposée constante sur une rafale.
- Pas de détection/correction d'erreurs au-delà du rejet CRC.
- Pas de réémission automatique ni de gestion de collisions.
- Les paramètres radio et temporisations ne sont pas encore validés physiquement.
