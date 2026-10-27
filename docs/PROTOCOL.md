# Protocole radio SAÉ 3.01

Version actuelle : **1**. Tous les champs multioctets sont en ordre réseau
(big-endian). Dans chaque octet, le bit de poids fort est transmis en premier.

## Trame binaire

| Offset | Taille | Champ | Valeur / sens |
|---:|---:|---|---|
| 0 | 8 | Préambule | `f3 5a c7 19 6d 84 b2 e1` |
| 8 | 1 | Version | `0x01` |
| 9 | 1 | Type | `0x01` DATA, `0x02` ACK |
| 10 | 4 | Identifiant | entier non signé 32 bits |
| 14 | 2 | Longueur | nombre d'octets de charge utile |
| 16 | N | Charge utile | UTF-8 pour DATA, vide pour ACK |
| 16+N | 4 | CRC-32 | CRC du champ Version à la fin de la charge utile |

Le CRC est le CRC-32 standard exposé par `zlib.crc32`, sérialisé sur 4 octets
big-endian. Le préambule et le CRC lui-même ne sont pas protégés. La longueur
maximale applicative par défaut est 1 024 octets, même si le champ permet 65 535.

Une trame est rejetée si le préambule, la version, le type, la longueur, la
contrainte ACK vide, la taille effective ou le CRC est invalide. Une charge DATA
qui n'est pas un UTF-8 strict est également rejetée par l'application.

## Identifiants et ACK

Chaque processus émetteur choisit un point de départ 32 bits aléatoire, puis
incrémente l'identifiant modulo 2³². Un ACK n'est valide que s'il est de type ACK,
sans charge utile, avec un CRC valide et un identifiant égal au DATA courant.
Les ACK anciens ou destinés à un autre message sont donc ignorés. Il n'y a pas de
réémission automatique dans ce MVP.

Le récepteur mémorise une fenêtre bornée d'identifiants DATA déjà vus. Une copie
est reconnue comme doublon mais reçoit tout de même un ACK, ce qui permet au
protocole de rester compatible avec une future politique de réémission.

## QPSK et forme d'onde

Deux bits consécutifs forment un symbole. La constellation, normalisée à énergie
unitaire, est :

| Bits | Symbole complexe |
|---|---|
| `00` | `( +1 + j) / √2` |
| `01` | `( -1 + j) / √2` |
| `11` | `( -1 - j) / √2` |
| `10` | `( +1 - j) / √2` |

Cet ordre est un codage de Gray autour de la constellation. Comme toute trame a
un nombre entier d'octets, aucun bit de bourrage QPSK n'est nécessaire.

Le signal utilise un filtre root-raised-cosine (RRC) de roll-off 0,35, étendue
8 symboles et 8 échantillons/symbole. Avec le taux d'échantillonnage par défaut
de 1 MHz, le débit symbole est 125 ksymbole/s et la largeur occupée théorique
approximative `(1 + 0,35) × 125 kHz = 168,75 kHz`; la bande RF configurée à
500 kHz laisse une marge aux imperfections du matériel.

Le récepteur applique le même RRC comme filtre adapté, essaie les huit phases
d'échantillonnage, recherche la corrélation normalisée maximale du préambule,
estime un gain complexe constant sur ce préambule, puis corrige tous les symboles
de la trame avec ce gain. Le seuil par défaut est 0,72.

## Limites de synchronisation

La méthode corrige un décalage temporel constant inférieur ou supérieur à un
symbole grâce à la recherche préambule/phase et corrige une phase porteuse
constante. Elle ne suit ni dérive d'horloge, ni décalage de fréquence porteuse,
ni phase variant pendant la trame. Ces limites sont intentionnelles pour le MVP
et devront être caractérisées sur les deux Pluto physiques.

