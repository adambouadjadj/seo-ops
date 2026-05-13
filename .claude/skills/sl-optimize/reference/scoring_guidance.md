# Scoring guidance - Textguru API V2 et usage dans le skill

## Objectif
Utiliser Textguru API pour récupérer automatiquement le brief 
sémantique (keywords, entités, scores cibles) et mesurer le 
contenu généré contre ces cibles. Remplace la saisie manuelle 
du brief Textguru qui se faisait jusqu'ici.

## Configuration API

- Base URL : `https://yourtext.guru/api/v2`
- Auth : clé API dans la variable d'environnement `YTG_API`
- Méthode auth : à confirmer lors de la 1re requête 
  (probablement header `KEY: {YTG_API}` ou `Authorization: 
  Bearer {YTG_API}`, vérifier la doc Swagger après 
  authorize)
- Rate limiting strict : vérifier les headers 
  `x-ratelimit-limit` et `x-ratelimit-remaining` à chaque 
  requête et implémenter un backoff si proche de la limite

## Workflow dans le skill

### Étape 1 : créer ou récupérer un guide

Pour une SL donnée, le skill :

1. Cherche si un guide existe déjà pour ce keyword + lang 
   via `GET /guides` (recherche par query)
2. Si oui → récupérer son `id`
3. Si non → créer via `POST /guides` avec le keyword et 
   la langue (fr)

**Note** : la création d'un guide prend du temps côté 
Textguru ("quelques minutes" selon la doc). Le skill doit 
donc :
- Créer le guide si absent
- Poller `GET /guides/{guideId}` jusqu'à ce que `ready: 
  true`
- Timeout de sécurité : 5 minutes max, sinon ERREUR

### Étape 2 : récupérer les données brief

Une fois le guide ready, récupérer en parallèle :

- `GET /guides/{guideId}` : pour `1grams`, `2grams`, 
  `3grams`, `entities`, `target_soseo_min/max`, 
  `target_dseo_min/max`
- `GET /guides/{guideId}/paa` : pour les PAA (utiles pour 
  la décision FAQ)
- `GET /guides/{guideId}/serp` : pour la SERP analysée par 
  Textguru (complémentaire de DataForSEO)
- `GET /guides/{guideId}/brief` : pour le brief complet

### Étape 3 : passer les données aux autres modules

Le `textguru_client.py` retourne un dict structuré :

```python
{
    "guide_id": "...",
    "query": "croisière méditerranée",
    "lang": "fr",
    "keywords": {
        "1grams": [...],  # unigrammes prioritaires
        "2grams": [...],  # bigrammes prioritaires
        "3grams": [...],  # trigrammes prioritaires
    },
    "entities": [...],    # entités nommées à couvrir
    "targets": {
        "soseo_min": 70,
        "soseo_max": 85,
        "dseo_min": 65,
        "dseo_max": 80,
    },
    "paa": [...],         # questions People Also Ask
    "serp": [...],        # analyse SERP par Textguru
}
```

Ces données alimentent :
- `content_generator.py` : pour intégrer keywords et entités 
  naturellement dans le contenu
- `faq_decision.py` : les PAA Textguru complètent ceux de 
  DataForSEO
- `pattern_selector.py` : la SERP Textguru complète celle 
  de DataForSEO

### Étape 4 : analyser le contenu généré

Après génération du contenu, envoyer le texte complet à 
Textguru pour obtenir le score SOSEO/DSEO :

- `POST /guides/{guideId}/brief/analyze` avec le texte 
  généré dans le body
- Récupérer le résultat (score SOSEO, score DSEO, 
  statut)

**Comparer avec les targets** :
- Si score SOSEO dans [soseo_min, soseo_max] → OK
- Si score SOSEO < soseo_min → contenu sous-optimisé, 
  le skill peut itérer (1 seule fois) pour enrichir
- Si score SOSEO > soseo_max → contenu sur-optimisé 
  (keyword stuffing), le skill doit alléger

## Attention : scoring Textguru sur SL ≠ articles

**Textguru est calibré pour des articles de blog**, pas 
pour des SL transactionnelles. Les scores cibles 
(`target_soseo_min/max`) ne s'appliquent pas tels quels 
sur une SL.

**Règles appliquées par le skill sur les SL :**

1. **Le score Textguru est directionnel, pas un objectif 
   absolu**. Un contenu SL avec score 60-70 peut être 
   parfait si le reste (structure, liens internes, patterns 
   éditoriaux) est bon.

2. **Ce qui compte** : couverture des entités nommées du 
   brief (oui/non pour chaque entité), pas le score global.

3. **Ne pas forcer le score vers la cible**. Si le skill 
   tente d'enrichir pour atteindre un score 80+, il 
   risque de produire du keyword stuffing et dégrader 
   la qualité éditoriale.

4. **Seuil d'alerte plutôt que cible** : le skill flag si 
   le score est < 50 (probablement manque de couverture 
   sémantique), mais ne cherche pas à dépasser 70.

## Usage des 1grams, 2grams, 3grams

Les n-grammes indiquent les termes les plus importants à 
couvrir. Le skill les utilise comme **guide de vocabulaire**, 
pas comme liste à cocher.

- **1grams** (unigrammes) : souvent trop génériques 
  (croisière, mer, port), usage diffus
- **2grams** (bigrammes) : plus spécifiques (port départ, 
  îles grecques, compagnie maritime), à intégrer 
  naturellement
- **3grams** (trigrammes) : les plus précis (croisière 
  îles grecques, départ port marseille), à intégrer dans 
  le top content et les H3 si pertinent

**Le skill ne doit pas bourrer les n-grammes** : s'ils 
apparaissent naturellement dans une rédaction factuelle, 
tant mieux. Sinon, ne pas forcer.

## Usage des entités

Les entités nommées (villes, compagnies, navires, 
destinations) doivent être **toutes couvertes** si 
possible dans le contenu, car elles structurent la 
compréhension sémantique de Google sur le sujet.

Le skill :
1. Liste les entités du brief Textguru
2. Croise avec les entités déjà présentes dans le contenu 
   (actuel ou généré)
3. Flag les entités manquantes dans le diagnostic
4. Propose de les intégrer dans le destination content si 
   possible, avec liens internes depuis le catalogue URL 
   quand l'entité matche une URL

## Usage des PAA Textguru

Les PAA de Textguru complètent ceux de DataForSEO :

- Si DataForSEO renvoie 5 PAA et Textguru 3, fusionner 
  et dédupliquer → garder le set unique
- Les PAA Textguru sont souvent plus stables (moins de 
  variation jour à jour) que DataForSEO
- Utilisés pour alimenter la décision FAQ 
  (voir `faq_decision_tree.md`)

## Cache

Les données Textguru pour un keyword donné changent peu 
au jour le jour. Le skill devrait :
- Cacher les résultats pendant 7 jours (un keyword n'a 
  pas besoin d'être re-analysé tous les jours)
- Cache sur disque dans `.claude/skills/sl-optimize/cache/
  textguru/{guide_id}.json`
- Invalidation manuelle possible via flag `--refresh-textguru`

## Gestion des erreurs

### Rate limit atteint
Si `x-ratelimit-remaining` = 0 :
- Attendre la fenêtre de reset (header 
  `x-ratelimit-reset`)
- Si pas d'attente possible, stop le skill et logger

### Guide en cours de création (pas ready)
Poller avec backoff : 10s, 30s, 60s, 120s, 300s max
Si toujours pas ready après 5 min → ERREUR, passer en 
fallback (brief manuel ou brief partiel)

### API down
Si l'API Textguru est inaccessible :
- Logger l'erreur
- Fallback sur un brief manuel fourni par l'utilisateur 
  (flag `--brief-file path/to/brief.md`)
- Si pas de brief manuel → ERREUR bloquante

## Évolution future

V1 : création de guide à chaque run si absent
V2 (si nécessaire) : maintenir un mapping local 
`SL_URL → guide_id` pour éviter de recréer des guides 
existants et économiser des crédits Textguru

## Coût estimé

À vérifier avec les rate limits réels, mais approximation :
- 1 run de skill = 4-5 appels API (get + brief + paa + 
  serp + analyze)
- Pour 20 SL = ~100 appels
- À monitorer via le header `x-ratelimit-remaining` et 
  l'endpoint `GET /consumption/openai`