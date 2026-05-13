# Pattern selector - Algorithme de choix A/B/C

## Objectif
Choisir automatiquement le pattern de destination content 
(A, B ou C) le plus adapté à la SL cible, basé sur l'analyse 
SERP et le volume du keyword principal.

## Les 3 patterns (rappel)

Voir `sl_anatomy.md` section "Destination content" pour les 
spécifications détaillées.

- **Pattern A** : Dense prose, style Costa. Gros volumes, 
  concurrence forte.
- **Pattern B** : Structured + lists, style Îles Grecques. 
  Volume moyen, destinations touristiques.
- **Pattern C** : Minimal, style Cunard. Petits volumes, 
  faible concurrence.

## Algorithme de scoring

Le skill calcule un score pour chaque pattern. Le pattern 
avec le score le plus élevé est choisi.

### Pattern A : +1 point pour chaque critère rempli
- Volume keyword principal ≥ 5000
- 5+ OTA concurrents directs dans le top 10 SERP
- Longueur moyenne du contenu du top 3 SERP > 1500 mots
- Featured snippet absent ou de type paragraphe (pas liste)
- PAA ≤ 2 (peu nombreux ou absents)

### Pattern B : +1 point pour chaque critère rempli
- 3+ PAA présents dans la SERP
- Featured snippet de type liste, tableau ou steps visible
- 2+ guides/informationnels dans le top 10 (TripAdvisor, 
  routard, magazines voyage)
- Keyword principal contient un pattern interrogatif 
  (comment, quand, quelle, quels, où, pourquoi, combien)
- Volume keyword entre 1000 et 10 000

### Pattern C : +1 point pour chaque critère rempli
- Volume keyword principal < 1000
- Longueur moyenne du contenu du top 10 < 500 mots
- Moins de 3 OTA concurrents directs dans le top 10
- Pas de PAA, pas de featured snippet
- Top 10 clairsemé (URLs peu établies, peu d'autorité 
  apparente)

## Résolution des égalités

- **A = B** : prendre **B** (pattern le plus polyvalent)
- **A = C** : prendre **A** (pattern safe par défaut)
- **B = C** : prendre **B**

## Fallback si DataForSEO indisponible

Si le budget DataForSEO est épuisé ou l'API down, se baser 
uniquement sur le volume du keyword principal (obtenu via 
Textguru ou saisie manuelle) :

- Volume ≥ 5000 → **Pattern A**
- Volume 1000-5000 → **Pattern B**
- Volume < 1000 → **Pattern C**

## Override manuel

L'utilisateur peut forcer un pattern via le flag 
`--pattern A|B|C`. Dans ce cas, l'algorithme automatique 
est bypassé et le pattern spécifié est appliqué.

Cas d'usage de l'override :
- Tester un autre pattern que celui recommandé par l'algo
- Garder la cohérence avec des SL sœurs déjà optimisées
- Expérimentation manuelle

## Logging

À chaque exécution du skill, logger dans metadata.json le 
pattern choisi, les scores de chaque pattern, les signaux 
détectés dans la SERP, et si un override ou fallback a été 
utilisé. Ça permet de :
- Tracer pourquoi tel pattern a été choisi
- Analyser a posteriori si les choix étaient pertinents
- Ajuster les seuils de l'algo si certains choix se révèlent 
  systématiquement contre-productifs

Structure du log :

- pattern_chosen : "A", "B" ou "C"
- scores : dict avec les 3 scores
- signals : dict avec toutes les valeurs de SERP ayant 
  influencé le choix (volume, nb OTA top 10, nb PAA, 
  featured snippet type, nb guides top 10, keyword 
  interrogatif, longueur moyenne contenu)
- override_used : bool
- fallback_used : bool

## Exemples de décisions attendues

| Keyword | Volume | Pattern retenu | Raison principale |
|---|---|---|---|
| croisière Méditerranée | 40 500 | A | Volume élevé, OTA dominent, contenu long |
| croisière Costa | 90 500 | A | Volume énorme, concurrence forte |
| croisière îles grecques | 2 400 | B | Volume moyen, PAA + guides présents |
| quand partir en Méditerranée | 1 900 | B | Pattern interrogatif, PAA nombreux |
| croisière Cunard | 390 | C | Volume faible, top 10 léger |
| croisière all inclusive | 880 | C ou B | Seuil limite, à voir selon PAA |
| croisière MSC dernière minute | 880 | A ou C | Intent transac, pas de PAA |

## Évolution future

Si après 10-20 SL traitées on constate que certains patterns 
sous-performent, on peut :
- Ajuster les seuils de scoring
- Ajouter de nouveaux critères (ex: présence vidéos YouTube, 
  shopping results, knowledge panel)
- Créer des sous-patterns (ex: A1 = pattern A très dense, 
  A2 = pattern A moyennement dense)

Tout ajustement doit être documenté ici et testé sur 2-3 SL 
avant généralisation.