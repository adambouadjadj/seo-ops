# DataForSEO API - SERP Google Organic Live Advanced

## Objectif
Utiliser DataForSEO SERP API pour analyser la SERP Google d'un keyword 
cible : top 20 résultats organiques, PAA, featured snippet, related 
searches, AI Overview, types de résultats. Données consommées par 
`pattern_selector.py`, `faq_decision.py`, et l'analyse concurrents directs.

Toutes les infos de ce fichier sont issues de la doc officielle 
DataForSEO (https://docs.dataforseo.com/v3/serp/google/organic/live/advanced/).

---

## Configuration API

### Endpoint utilisé
`POST https://api.dataforseo.com/v3/serp/google/organic/live/advanced`

Méthode **Live** (synchrone) + fonction **Advanced** (complete overview).
Une seule requête pour tout obtenir : organic + PAA + featured snippet + 
related searches + AI Overview + autres éléments SERP.

### Authentification
Basic Auth avec login + password du compte DataForSEO. Le password 
est généré automatiquement par DataForSEO et n'est pas le même que 
le password du compte dashboard.

Credentials dans `.env` :
- `DATAFORSEO_LOGIN=...`
- `DATAFORSEO_PASSWORD=...`

En Python avec requests :
```python
import os
from requests.auth import HTTPBasicAuth

auth = HTTPBasicAuth(
    os.environ["DATAFORSEO_LOGIN"],
    os.environ["DATAFORSEO_PASSWORD"]
)
```

L'auth passe systématiquement dans le header `Authorization` au 
format `Basic {base64(login:password)}`. Pas de token, pas de call 
d'authentification séparé. `requests` gère l'encodage base64 
automatiquement avec `HTTPBasicAuth`.

### Rate limits
- 2000 POST/GET calls par minute maximum
- Chaque call Live ne peut contenir qu'une seule tâche
- Pour nos usages (~20 SL par run), on est très loin de la limite

### Coût
- Pricing officiel : 
  https://dataforseo.com/pricing/serp/google-organic-serp-api
- Facturé par SERP de 10 résultats. `depth: 20` = 2x le coût de base
- Budget actuel : 5€ de test
- La réponse contient le coût exact dans `tasks[0].cost`, à logger 
  pour tracker la consommation

---

## Requête type

### Payload

```python
payload = [
    {
        "keyword": "croisière méditerranée",
        "location_code": 2250,     # France (à vérifier)
        "language_code": "fr",
        "device": "desktop",
        "depth": 20
    }
]
```

Le body est un **tableau** contenant une seule tâche. Important : 
même avec une seule tâche, c'est un array, pas un objet.

### Paramètres utilisés

| Paramètre | Valeur | Raison |
|---|---|---|
| `keyword` | Keyword principal de la SL | Requête à analyser. Max 700 caractères. |
| `location_code` | 2250 | France. **À vérifier** au premier run via `GET /v3/serp/google/locations` |
| `language_code` | "fr" | Français |
| `device` | "desktop" | Cohérent avec le tracker GSC actuel |
| `depth` | 20 | Top 20 pour avoir de la marge si peu de concurrents directs dans le top 10 |

### Paramètres NON utilisés

- `load_async_ai_overview` : false (default). On ne prend pas le 
  surcoût de 0.002$ par requête pour récupérer l'AI Overview 
  asynchrone. Si l'AI Overview est dans le cache DataForSEO, on 
  l'aura quand même.
- `calculate_rectangles` : false (default). Pas besoin des 
  coordonnées pixel des éléments.

### Vérification `location_code: 2250`

Au premier run du skill, lancer :
```python
response = requests.get(
    "https://api.dataforseo.com/v3/serp/google/locations",
    auth=auth
)
```

Chercher dans la réponse l'entrée `"location_name": "France"` et 
confirmer la valeur de `location_code`. Si ce n'est pas 2250, mettre 
à jour ce fichier.

### Appel complet en Python

```python
import os
import requests
from requests.auth import HTTPBasicAuth

auth = HTTPBasicAuth(
    os.environ["DATAFORSEO_LOGIN"],
    os.environ["DATAFORSEO_PASSWORD"]
)

payload = [{
    "keyword": "croisière méditerranée",
    "location_code": 2250,
    "language_code": "fr",
    "device": "desktop",
    "depth": 20
}]

response = requests.post(
    "https://api.dataforseo.com/v3/serp/google/organic/live/advanced",
    auth=auth,
    headers={"Content-Type": "application/json"},
    json=payload,
    timeout=30
)

data = response.json()
```

---

## Structure de la réponse

### Enveloppe générale

```json
{
    "version": "0.1.20200129",
    "status_code": 20000,
    "status_message": "Ok.",
    "time": "3.5 sec.",
    "cost": 0.006,
    "tasks_count": 1,
    "tasks_error": 0,
    "tasks": [
        {
            "id": "...",
            "status_code": 20000,
            "status_message": "Ok.",
            "cost": 0.006,
            "result_count": 1,
            "path": ["v3", "serp", "google", "organic", "advanced", "live"],
            "data": { ... },     // Params passés dans le POST
            "result": [
                {
                    "keyword": "...",
                    "type": "organic",
                    "se_domain": "google.fr",
                    "location_code": 2250,
                    "language_code": "fr",
                    "check_url": "https://www.google.fr/search?...",
                    "datetime": "2026-04-24 14:30:00 +00:00",
                    "spell": null,
                    "refinement_chips": null,
                    "item_types": [...],
                    "se_results_count": 125000000,
                    "items_count": 20,
                    "items": [...]
                }
            ]
        }
    ]
}
```

### Accès au contenu utile

```python
response_data = response.json()

# Vérification global
if response_data.get("status_code") != 20000:
    raise Exception(f"API error: {response_data.get('status_message')}")

tasks = response_data.get("tasks", [])
if not tasks:
    raise Exception("No tasks in response")

task = tasks[0]
if task.get("status_code") != 20000:
    raise Exception(f"Task error: {task.get('status_message')}")

result = task["result"][0]
items = result.get("items", [])
item_types = result.get("item_types", [])
cost = task.get("cost", 0)
check_url = result.get("check_url", "")
```

### Types d'items disponibles

Liste officielle complète : `answer_box`, `app`, `carousel`, 
`multi_carousel`, `featured_snippet`, `google_flights`, 
`google_reviews`, `third_party_reviews`, `google_posts`, `images`, 
`jobs`, `knowledge_graph`, `local_pack`, `hotels_pack`, `map`, 
`organic`, `paid`, `people_also_ask`, `related_searches`, 
`people_also_search`, `shopping`, `top_stories`, `twitter`, `video`, 
`events`, `mention_carousel`, `recipes`, `top_sights`, 
`scholarly_articles`, `popular_products`, `podcasts`, 
`questions_and_answers`, `find_results_on`, `stocks_box`, 
`visual_stories`, `commercial_units`, `local_services`, 
`google_hotels`, `math_solver`, `currency_box`, 
`product_considerations`, `found_on_web`, `short_videos`, 
`refine_products`, `explore_brands`, `perspectives`, 
`discussions_and_forums`, `compare_sites`, `courses`, `ai_overview`.

**Types utilisés par le skill** :
- `organic` : résultats organiques classiques (analyse concurrents)
- `people_also_ask` : bloc PAA (alimente FAQ decision)
- `featured_snippet` : featured snippet (signal Pattern + FAQ)
- `related_searches` : recherches associées (vocabulaire sémantique)
- `ai_overview` : AI Overview Google (signal contexte SERP)

Tous les autres types sont ignorés pour V1.

---

## Parsing par le skill

### 1. Résultats organiques

Chaque item `organic` contient les champs suivants (utilisés par le 
skill) :

```python
organic_results = [item for item in items if item.get("type") == "organic"]

# Chaque organic a :
# - rank_group : position parmi les résultats organic (1-20)
# - rank_absolute : position absolue dans la SERP (inclut PAA, etc.)
# - url : URL du résultat
# - domain : domaine extrait
# - title : title affiché dans la SERP
# - description : meta description affichée
# - website_name : nom du site (parfois différent du domain)
# - is_featured_snippet : true si ce résultat est le featured snippet
# - breadcrumb : fil d'ariane affiché dans la SERP
# - faq : objet faq_box (non null si le résultat affiche des FAQ riches)
```

Champs additionnels disponibles mais non utilisés pour V1 : 
`cache_url`, `pre_snippet`, `extended_snippet`, `images`, `rating`, 
`price`, `highlighted`, `links` (sitelinks), `extended_people_also_search`, 
`about_this_result`, `related_result`, `timestamp`, `rectangle`.

### 2. Filtrage concurrents directs

Utiliser les listes de `reference/concurrents_directs.md` :

```python
OTA_DIRECTS = [...]  # croisieres.fr, croisieurope.com, etc.
ARMATEURS = [...]    # msccroisieres.fr, costacroisieres.fr, etc.

concurrents = []
for r in organic_results:
    domain = r.get("domain", "")
    if any(d in domain for d in OTA_DIRECTS):
        r["_category"] = "ota_direct"
        concurrents.append(r)
    elif any(d in domain for d in ARMATEURS):
        r["_category"] = "armateur"
        concurrents.append(r)
    # Sinon on ignore (guides, blogs, annuaires)
```

### 3. Extraction des PAA

```python
paa_items = [item for item in items if item.get("type") == "people_also_ask"]

if paa_items:
    paa_block = paa_items[0]
    paa_elements = paa_block.get("items", [])
    
    paa_questions = []
    for elem in paa_elements:
        # Chaque elem est un people_also_ask_element
        question = elem.get("title", "")
        seed = elem.get("seed_question", "")
        
        # La réponse est dans expanded_element (array)
        expanded = elem.get("expanded_element", [])
        answer_data = expanded[0] if expanded else {}
        
        paa_questions.append({
            "question": question,
            "seed_question": seed,
            "answer_title": answer_data.get("title", ""),
            "answer_description": answer_data.get("description", ""),
            "answer_url": answer_data.get("url", ""),
            "answer_domain": answer_data.get("domain", ""),
            "has_table": answer_data.get("table") is not None
        })
    
    paa_count = len(paa_questions)
```

**Structure PAA confirmée** :
- `items[].title` = question affichée
- `items[].seed_question` = question qui a déclenché l'expansion
- `items[].expanded_element[0]` = réponse avec title, description, 
  url, domain, timestamp, images, table (si réponse tabulaire)

### 4. Extraction du featured snippet

```python
fs_items = [item for item in items if item.get("type") == "featured_snippet"]

if fs_items:
    fs = fs_items[0]
    
    fs_data = {
        "present": True,
        "domain": fs.get("domain", ""),
        "url": fs.get("url", ""),
        "title": fs.get("title", ""),
        "featured_title": fs.get("featured_title", ""),
        "description": fs.get("description", ""),
        "has_table": fs.get("table") is not None,
        "has_images": bool(fs.get("images"))
    }
else:
    fs_data = {"present": False}
```

**Important** : la doc ne fournit pas de champ `type` explicite 
(paragraph / list / table) pour le featured snippet. On détecte :
- **Tableau** : `table` non null
- **Paragraphe / liste** : pas de discriminant natif, il faut parser 
  `description` pour détecter des puces (patterns `•`, `-`, numérotation)

Pour V1, on se contente de `has_table` comme signal structurant. 
Le distinguo list/paragraph peut être ajouté en V2 si nécessaire.

### 5. Extraction des related searches

```python
rs_items = [item for item in items if item.get("type") == "related_searches"]

if rs_items:
    related_queries = rs_items[0].get("items", [])
    # items est une array de strings (pas d'objets)
```

### 6. Extraction AI Overview (si présent)

```python
ai_items = [item for item in items if item.get("type") == "ai_overview"]

if ai_items:
    ai = ai_items[0]
    
    ai_data = {
        "present": True,
        "asynchronous": ai.get("asynchronous_ai_overview", False),
        "markdown": ai.get("markdown", ""),
        "references": []
    }
    
    # Parcourir items pour extraire les références
    for component in ai.get("items", []):
        if component.get("type") == "ai_overview_element":
            for ref in component.get("references", []):
                ai_data["references"].append({
                    "source": ref.get("source", ""),
                    "domain": ref.get("domain", ""),
                    "url": ref.get("url", ""),
                    "title": ref.get("title", "")
                })
else:
    ai_data = {"present": False}
```

**Note** : si l'AI Overview est marqué `asynchronous_ai_overview: 
true` et qu'on n'a pas activé `load_async_ai_overview`, on ne verra 
que sa présence, pas son contenu. Acceptable pour V1.

### 7. Extraction FAQ riches sur résultats organiques

Signal intéressant pour `faq_decision.py` : un concurrent avec des 
FAQ affichées en rich snippet.

```python
competitors_with_faq = []
for r in organic_results:
    if r.get("faq") is not None:
        faq_box = r["faq"]
        faq_items = faq_box.get("items", [])
        competitors_with_faq.append({
            "domain": r.get("domain"),
            "rank": r.get("rank_group"),
            "faq_count": len(faq_items),
            "faq_questions": [item.get("title", "") for item in faq_items]
        })
```

Si des concurrents directs affichent des FAQ riches sur ce keyword, 
c'est un signal fort que la FAQ schema fonctionne pour cette SERP.

---

## Signaux extraits pour le skill

Le module `serp_analyzer.py` retourne un dict structuré :

```python
{
    "keyword": "croisière méditerranée",
    "fetched_at": "2026-04-24T14:30:00Z",
    "cost_usd": 0.006,
    "check_url": "https://www.google.fr/search?...",
    
    "organic_results": [
        {
            "rank_group": 1,
            "rank_absolute": 3,
            "domain": "croisieres.fr",
            "url": "...",
            "title": "...",
            "description": "...",
            "website_name": "...",
            "is_featured_snippet": False,
            "category": "ota_direct",  # ota_direct | armateur | autre
            "has_faq": False
        },
        ...
    ],
    
    "concurrents_directs": [
        # Sous-ensemble filtré sur OTA_DIRECTS + ARMATEURS
    ],
    
    "concurrents_count": {
        "ota_direct": 6,
        "armateur": 2,
        "autres": 12
    },
    
    "competitors_with_faq": [
        # Liste des résultats organiques qui affichent des FAQ riches
    ],
    
    "paa": {
        "present": True,
        "count": 4,
        "questions": [
            {
                "question": "Quand partir en croisière Méditerranée ?",
                "seed_question": "...",
                "answer_title": "...",
                "answer_description": "...",
                "answer_url": "...",
                "answer_domain": "...",
                "has_table": False
            },
            ...
        ]
    },
    
    "featured_snippet": {
        "present": True,
        "domain": "...",
        "url": "...",
        "title": "...",
        "featured_title": "...",
        "description": "...",
        "has_table": False,
        "has_images": False
    },
    
    "ai_overview": {
        "present": True,
        "asynchronous": False,
        "markdown": "...",
        "references": [
            {"source": "...", "domain": "...", "url": "...", "title": "..."}
        ]
    },
    
    "related_searches": ["...", "...", ...],
    
    "item_types": [
        "organic", "people_also_ask", "related_searches", 
        "featured_snippet", "ai_overview"
    ]
}
```

---

## Usage par les autres modules

### pattern_selector.py
Utilise :
- `concurrents_count.ota_direct` → scoring Pattern A (volume concurrents)
- `paa.count` → scoring Pattern B (SERP questions-driven)
- `featured_snippet.has_table` → Pattern B
- `ai_overview.present` → signal contexte SERP moderne

### faq_decision.py
Utilise :
- `paa.count` → signal principal
- `paa.questions` → alimente la FAQ générée
- `featured_snippet.has_table` → signal
- `competitors_with_faq` → signal fort (FAQ schema efficace sur ce SERP)

### data_assembler.py
Utilise :
- `concurrents_directs` → analyse des patterns concurrents
- `paa.questions` → questions à intégrer dans la FAQ
- `related_searches` → vocabulaire sémantique
- `ai_overview.references` → sources citées par Google AI (signal GEO)

---

## Gestion des erreurs

### Status codes DataForSEO
- 20000 : OK
- 40000-49999 : erreur client (auth, payload, rate limit, etc.)
- 50000-59999 : erreur serveur DataForSEO

Le skill vérifie **3 niveaux** :

```python
# Niveau 1 : HTTP
if response.status_code != 200:
    raise Exception(f"HTTP {response.status_code}")

# Niveau 2 : API global
data = response.json()
if data.get("status_code") != 20000:
    raise Exception(f"API {data.get('status_code')}: {data.get('status_message')}")

# Niveau 3 : tâche
task = data["tasks"][0]
if task.get("status_code") != 20000:
    raise Exception(f"Task {task.get('status_code')}: {task.get('status_message')}")
```

### Timeout
Timeout request de 30 secondes. Si dépassé, fallback :
- Volume keyword via Textguru pour pattern_selector
- Pas d'analyse concurrents directs (continuer sans)
- Log warning dans le rapport final

### Rate limit
2000 calls/min théorique, jamais atteint pour nos usages. Si 429 
reçu, attendre 60s et retry une fois.

---

## Cache

Les résultats SERP sont cachés pendant 7 jours pour éviter les 
requêtes redondantes :
- `.claude/skills/sl-optimize/cache/dataforseo/{keyword_hash}.json`
- Key : hash MD5 de `keyword + location_code + language_code + device`
- Invalidation : flag CLI `--refresh-serp`

---

## Test manuel avant intégration

Avant d'intégrer dans le skill, tester la requête avec cURL :

```bash
LOGIN="ton_login"
PASSWORD="ton_password"
CRED=$(printf "${LOGIN}:${PASSWORD}" | base64)

curl --location --request POST \
  'https://api.dataforseo.com/v3/serp/google/organic/live/advanced' \
  --header "Authorization: Basic ${CRED}" \
  --header 'Content-Type: application/json' \
  --data-raw '[{
    "keyword": "croisière méditerranée",
    "location_code": 2250,
    "language_code": "fr",
    "device": "desktop",
    "depth": 20
  }]'
```

Vérifier que :
- Status 200
- `status_code: 20000` dans la réponse
- `tasks[0].status_code: 20000`
- `tasks[0].result[0].items` contient au moins 15-20 éléments
- `item_types` contient au minimum `"organic"`
- Coût dans `tasks[0].cost` entre 0.003 et 0.012 USD
- `check_url` pointe vers une vraie SERP Google France

---

## Sandbox DataForSEO

Pour tester sans consommer le budget :
https://sandbox.dataforseo.com/v3/serp/google/organic/live/advanced

Retourne des données mock. Utile pour dev du parser sans cramer 
le budget. À utiliser pour les premiers tests de 
`serp_analyzer.py`.

---

## Évolution future

V1 : SERP Google Organic Live Advanced, France desktop, depth 20, 
     focus sur organic + PAA + featured_snippet + related_searches 
     + ai_overview.

V2 possible :
- Parsing plus fin du featured snippet (détection list vs paragraph 
  via regex sur description)
- Ajout du device mobile en parallèle pour comparer
- Activation `load_async_ai_overview` si AI Overview devient 
  critique pour GEO (+0.002$/requête)
- Ajout des types `knowledge_graph` et `top_stories` pour contexte 
  SERP étendu
- SERP Bing en complément (pricing similaire)