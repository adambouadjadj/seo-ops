# sl_anatomy.md - Règles éditoriales et structurelles des SL ABCroisière

Ce document est LA référence de rédaction pour le skill /sl-optimize.

## Principes fondamentaux (non négociables)

### Principe 1 : SEO d'abord, GEO en bonus
ABCroisière a un capital SEO fort. Un contenu propre et informatif 
suffit à ranker si l'architecture et les invariants sont respectés. 
Les optimisations GEO viennent en bonus quand elles sont 
SEO-compatibles. Elles ne doivent jamais casser la fluidité de 
lecture ou la pertinence.

### Principe 2 : Données réelles uniquement
Chaque donnée chiffrée (prix, volume, nb de compagnies, nb de 
navires) vient du schema JSON-LD de la page ou du brief catalogue. 
Aucune estimation, aucune invention, aucune fourchette floue. 
Si une donnée manque, flag [À VÉRIFIER] plutôt qu'inventer.

### Principe 3 : Ne pas casser ce qui marche
Les liens internes existants sur la SL actuelle sont conservés 
dans le nouveau contenu (adaptés si besoin). Les patterns qui 
performent (Cunard, Costa, Îles Grecques) sont préservés.

### Principe 4 : Cohérence title / meta / schema
Les valeurs chiffrées (prix plancher, volume) doivent être 
identiques dans le title, la meta description et le schema 
Product. Toute divergence est flaguée en erreur par le skill.

### Principe 5 : Contraintes marque strictes
Les contraintes marque documentées (voir brand_constraints/) 
sont appliquées sans exception dans tout le contenu, y compris 
breadcrumbs et microdata.

## Architecture DOM cible

Ordre invariant :
1. H1 (simple et direct : "Croisières X")
2. Top content (1 à 3 paragraphes, dense en liens internes 
   et entités)
3. Catalogue JS dynamique (hors scope rédactionnel)
4. Destination content (H2 + H3 + paragraphes, prose ou 
   listes selon pattern)
5. Signature auteur (signal EEAT, voir authors.md)
6. Schema JSON-LD (Product, BreadcrumbList, FAQPage si applicable)

## Top content

### Format
1 à 3 paragraphes <p>, en prose, dense en liens internes et 
entités nommées. Pas de H3 dans le top content.

### Longueur
Pas de règle stricte. Guide :
- SL petit volume / faible concurrence : 1 paragraphe de 50-80 
  mots peut suffire (cf Cunard)
- SL volume moyen : 2 paragraphes de 60-100 mots chacun 
  (cf Îles Grecques)
- SL gros volume / concurrence forte : 2-3 paragraphes de 
  80-150 mots chacun (cf Costa)

### Contenu à couvrir - SL Destination
Le top content couvre ces intents sur 1 à 3 paragraphes :
1. Compagnies présentes (3 max, les plus volumétriques du 
   catalogue)
2. Volume de croisières disponibles (valeur schema)
3. Ports de départ FR en priorité, puis internationaux clés
4. Prix plancher (valeur schema)
5. Saison principale (mention naturelle, pas forcée)

### Contenu à couvrir - SL Compagnie
1. Destinations principales couvertes (3-4 bassins)
2. Volume + nb de navires
3. Navires phares (3 max)
4. Prix plancher + formule clé (ex: "pension complète 
   incluse", "enfants gratuits")
5. Ports de départ FR en priorité

### Règles de rédaction
- Préférer une entrée sur entité forte ou chiffre concret
  ("Costa Croisières propose...", "648 croisières...").
  Toléré : "Partez" ou "Découvrez" suivi immédiatement d'une
  entité forte et d'un verbe d'action concret ("Partez en
  croisière Costa avec la compagnie...", "Partez pour une
  croisière dans les îles grecques et explorez...").
  Interdit : phrases creuses sans entité forte en tête
  ("La Méditerranée vous attend", "Partez à la découverte
  de merveilles inoubliables", "Embarquez pour une aventure
  magique").
- Entités denses mais naturelles : ~1 entité nommée tous 
  les 6-8 mots. Pas de bourrage forcé.
- Liens internes denses : chaque entité mentionnée qui a 
  une URL dans le catalogue URL doit être linkée
- URLs toujours en relatif (/fr/croisieres/...)
- Ton informatif-factuel dominant. Léger descriptif toléré 
  ("expérience unique", "haut de gamme"). Pas de superlatifs 
  marketing ("inoubliable", "paradis", "rêve", "meilleure 
  expérience").
- Mot-clé principal en <b> : 1 à 2 fois par paragraphe max

### Ce qu'on ne fait pas
- Pas de listes à puces dans le top content
- Pas de H3 dans le top content
- Pas d'accroche molle
- Pas d'estimation de prix
- Pas d'entity echoing forcé (contrairement à l'ancienne 
  méthodo GEO-first)
- **Pas de tirets cadratins (—)** dans le contenu généré. 
  Remplacer par des parenthèses pour les appositions 
  ("X (A, B, C)"), des virgules pour les incises, des 
  deux-points pour les énumérations, ou un point-virgule 
  pour séparer deux idées distinctes.

## Destination content

### 3 patterns possibles

Le skill choisit le pattern selon l'analyse SERP. Par défaut 
si indécis : **Pattern A**.

**Pattern A - Dense prose (DEFAULT, style Costa)**
- Usage : SL gros volume + concurrence forte (ex: croisière 
  Méditerranée, croisière MSC, croisière Costa)
- Structure : 1 H2 parent, 3-5 H2 ou H3 majoritairement 
  thématiques ("Itinéraires en Méditerranée"), certains en 
  questions ("Quand partir ?")
- Paragraphes de longueur variable (30 à 300 mots selon l'intent)
- Prose principalement, peu ou pas de listes
- Signal SERP : top 10 dominé par des OTA avec contenu prose 
  dense, peu de listes visibles

**Pattern B - Structured + lists (style Îles Grecques)**
- Usage : SL volume moyen, destinations touristiques, SERP 
  avec signaux "listes" forts
- Structure : 1 H2 parent (en question), 3-5 H3 (mix questions 
  + thématiques), listes à puces pour énumérations (escales, 
  compagnies, avantages saison)
- FAQ microdata en fin SI conditions remplies 
  (voir faq_decision_tree.md)
- Signal SERP : PAA présents, Google affiche des listes dans 
  les résultats, featured snippet liste

**Pattern C - Minimal (style Cunard)**
- Usage : SL petit volume (<1000), faible concurrence
- Structure : 1 H2 parent (thématique), 2-3 H3 thématiques, 
  prose courte (100-200 mots par section)
- Signal SERP : top 10 clairsemé, concurrents directs avec 
  contenu bref

### Règles de rédaction (tous patterns)
- H3 questions OU thématiques au choix selon ce qui lit le 
  mieux. Pas d'obligation "questions systématique"
- Entity echoing non obligatoire. Si le premier mot du 
  paragraphe reprend naturellement l'entité du H3 parce que 
  c'est fluide, tant mieux, sinon OK
- Auto-suffisance souple : un bloc doit être compréhensible 
  sans contexte, mais n'a pas besoin d'être "citable LLM" 
  avec phrases courtes hachées
- Liens internes partout où pertinent : ports, destinations, 
  compagnies, navires, escales, mois, durées, classes
- Chiffres concrets valorisés : nb croisières, années, durées, 
  prix (données réelles uniquement)
- Mot-clé principal en <b> : 1 fois par section max

### Sections prioritaires - SL Destination
Couvrir au minimum (ordre libre selon SERP) :
1. Itinéraires / types de circuits / bassins géographiques
2. Escales incontournables (idéal en liste en pattern B)
3. Meilleure période / saisonnalité
4. Compagnies principales (idéal en liste en pattern B)
5. Prix et formules disponibles (si pertinent selon SERP)

### Sections prioritaires - SL Compagnie
Couvrir au minimum :
1. Présentation / positionnement / histoire
2. Destinations couvertes (1 H3 par bassin principal)
3. Flotte et navires phares
4. Formules et cabines
5. Saisonnalité par destination

### H2 parent
- SL Destination : H2 en question ou thématique selon pattern
  (Costa Destination content : "Où partir avec Costa ?", 
  Îles Grecques : "Quel itinéraire pour une croisière dans 
  les Îles Grecques ?")
- SL Compagnie : H2 thématique type "Tout savoir sur [Compagnie]" 
  ou "Partir en croisière avec [Compagnie]"

## FAQ (conditionnelle)

Règles d'ajout détaillées dans faq_decision_tree.md.

En résumé : FAQ ajoutée SI au moins un signal SERP le justifie 
(PAA ≥ 3, guides dans top 10, featured snippet question/réponse, 
pattern interrogatif du keyword principal).

**Format obligatoire** : microdata schema.org/FAQPage 
(itemscope + itemtype + itemprop). Jamais en simple liste à 
puces. Toujours exploitable en rich result Google.

**Contenu** :
- 4-6 questions max
- Mix 2-3 questions PAA (reprises quasi-textuellement) + 
  2-3 questions du brief Textguru / intents transactionnels
- Réponses 40-80 mots, factuelles, avec données réelles

## Signature auteur (systématique)

Voir authors.md pour le mapping personas/domaines et le format 
HTML exact.

Placement : fin de destination content, juste avant le schema 
JSON-LD.

4 personas stables (Élodie, Marc, Claire, Thomas) répartis par 
domaine d'expertise. Une fois assigné à une SL, le persona ne 
change pas.

## Title

### Structure
`Croisières [Nom] [Année] : [intent] & [promo|itinéraires]`

### Exemples validés
- Costa : "Croisières Costa 2026 : itinéraires & offres dès 169€"
- Îles Grecques : "Croisières Îles Grecques 2026-2027 : promos 
  & itinéraires"
- MSC : "Croisières MSC 2026 : destinations & offres dès 79€" 
  (respecte contrainte marque : pas de "pas cher")

### Règles
- Année en cours (2026) ou année+1 (2026-2027), jamais d'année 
  passée
- Prix plancher systématique si pertinent, valeur identique au 
  schema Product
- Longueur 50-60 caractères max (Google tronque au-delà)
- Contraintes marque respectées (voir brand_constraints/)

## Meta description

### Structure
`[Volume] croisières [keyword] avec [compagnies]. Départs 
[ports FR]. [Destinations clés]. Dès [prix]€.`

### Exemples validés
- Méditerranée : "1 000 croisières Méditerranée avec MSC, 
  Costa et Royal Caribbean. Départs de Marseille, Nice, Rome, 
  Barcelone. Baléares, Sicile, îles grecques dès 79€."
- MSC : "1 000 croisières MSC sur 22 navires : Méditerranée, 
  Caraïbes, fjords, Europe du Nord. Départs Marseille, Gênes, 
  Barcelone, Miami. Cabine dès 79€, enfants <12 ans gratuits."

### Règles
- 150-160 caractères max
- Commencer par un chiffre ou une entité forte
- Prix plancher identique au title et au schema
- Volume identique au schema
- Contrainte marque respectée
- Ne jamais commencer par "Partez...", "Découvrez..."
- **Pas d'emojis, pictos ou caractères HTML décoratifs** 
  (☀, ☛, ✓, →, etc.). Héritage d'anciens rédacteurs, ne 
  plus utiliser. Meta en texte plain uniquement.
- **Pas de promesses promotionnelles agressives** (type 
  "-60% de réduction", "offre flash") sauf sur des SL 
  dédiées aux promos

## Checklist de validation (SEO classique)

Le skill vérifie automatiquement en sortie :
- [ ] Title 50-60 caractères
- [ ] Meta description 150-160 caractères
- [ ] Title / meta / schema cohérents sur prix et volume
- [ ] Année title = année courante ou année+1
- [ ] H1 cohérent avec title, accents corrects
- [ ] Top content : 1-3 <p>, pas de H3, pas de liste
- [ ] Top content : ≥ 5 liens internes
- [ ] Top content : mot-clé principal en <b> 1-2 fois
- [ ] Destination content : H2 parent + 2-5 H3
- [ ] Destination content : ≥ 10 liens internes
- [ ] Tous les liens en relatif (/fr/...)
- [ ] Pas de <strong>, <em>, <h4>, <h1> dans les blocs 
  générés
- [ ] Pas de CSS inline, classes, attributs data
- [ ] Contraintes marque respectées partout
- [ ] Signature auteur présente en fin
- [ ] Liens internes existants (pré-optimisation) conservés

## Checklist de validation (GEO bonus)

Observations de qualité, pas bloquantes :
- [ ] Top content commence par entité forte (pas accroche 
  molle)
- [ ] Entités nommées denses (~1 / 6-8 mots top content)
- [ ] Chiffres concrets présents dans destination content 
  (prix, durée, saison)
- [ ] H3 en questions quand naturel
- [ ] FAQ microdata présente si conditions remplies
- [ ] Signature auteur en bas (EEAT)

## Ce qui change vs l'ancienne méthodo GEO-first

Pour info, pour bien identifier ce qui évolue :

| Ancienne règle (GEO-first) | Nouvelle règle (SEO-first + GEO bonus) |
|---|---|
| 1 seul <p> top content | 1 à 3 <p> selon SL |
| H3 systématiquement en questions | H3 questions OU thématiques |
| 120-180 mots par bloc strict | Longueur libre selon intent |
| Entity echoing début de <p> obligatoire | Entity echoing optionnel |
| Entity density ~20% cible | Entités denses mais naturelles |
| Auto-suffisance stricte de chaque bloc | Auto-suffisance souple |
| Pas d'accroche molle (règle stricte absolue) | Pas d'accroche molle sans entité forte (ex: "La Méditerranée vous attend" interdit, "Partez en croisière Costa avec..." toléré) |
| Pas de liste à puces | Listes à puces OK en pattern B |
| Pas de FAQ ou FAQ sans microdata | FAQ microdata conditionnelle |
| Pas de signature auteur | Signature auteur systématique (EEAT) |