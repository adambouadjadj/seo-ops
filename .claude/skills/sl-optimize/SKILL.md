# /sl-optimize — Optimisation des Selective Landings ABCroisière

## Ce que fait ce skill

Optimise les SL (Selective Landings destinations et compagnies) d'ABCroisière :
1. Fetch et audite la page actuelle (diagnostics automatiques)
2. Collecte les données SERP (DataForSEO) et sémantiques (Textguru)
3. Choisit le pattern éditorial adapté (A/B/C)
4. Assemble toutes les données dans un dict structuré
5. Claude Code génère le contenu inline (title, meta, top content, destination content)
6. Valide le contenu généré (SEO bloquant + GEO non-bloquant)
7. Écrit les outputs (HTML CMS-ready + rapports)

**Architecture : Option B.** Les modules Python collectent les données.
La génération du contenu est faite inline par Claude Code à partir du
résultat de `data_assembler.py` et des fichiers `reference/`.

---

## Usage

```
/sl-optimize --url <URL> --type <destination|compagnie> [options]
```

### Flags

| Flag | Requis | Défaut | Description |
|---|---|---|---|
| `--url` | Oui | — | URL complète de la SL cible |
| `--type` | Oui | — | `destination` ou `compagnie` |
| `--brief` | Non | — | Path vers brief catalogue manuel (voir `reference/brief_catalogue_format.md`) |
| `--textguru-keyword` | Non | déduit de l'URL | Override keyword Textguru |
| `--pattern` | Non | scoring auto | Force le pattern `A`, `B` ou `C` |
| `--dry-run` | Non | false | Diagnostics + data collection uniquement, sans génération |
| `--refresh-textguru` | Non | false | Invalide le cache Textguru pour cette SL |
| `--refresh-serp` | Non | false | Invalide le cache DataForSEO pour cette SL |
| `--mode-variables` | Non | `hardcoded` | `hardcoded` (défaut, bug CMS actuel) ou `dynamic` (post-fix) |

**Déduction du keyword depuis l'URL :**
Extraire le segment entre `/fr/croisieres/` et le suivant `/`, retirer le
préfixe `croisiere-`, remplacer les `-` par des espaces, réaccentuer
(remplacement simple : `iles` → `îles`, `caraibes` → `Caraïbes`, etc.),
ajouter "croisière" en tête. Exemples :
- `croisiere-costa-croisieres` → "croisière Costa Croisières"
- `croisiere-iles-grecques` → "croisière îles grecques"
- `croisiere-cunard` → "croisière Cunard"

---

## Structure des outputs

Tout dans `.claude/skills/sl-optimize/output/<YYYY-MM-DD>/<slug>/` :

```
output/2026-04-24/croisiere-costa-croisieres/
├── title_meta.txt              # Title + meta proposés (texte brut)
├── top_content.html            # HTML CMS-ready, copier-coller direct
├── destination_content.html    # HTML CMS-ready, copier-coller direct
├── full_cms_ready.html         # Top + destination concaténés
├── diagnostic_report.md        # Anomalies détectées (sévérité + fix)
├── bilan_seo.md                # Résultats validator_seo (checklist)
├── bilan_geo.md                # Résultats validator_geo (non-bloquant)
├── maillage_manquant.md        # Entités citées sans URL dans le catalogue
├── data_assembled.json         # Dict complet produit par data_assembler
└── metadata.json               # Pattern, scores, sources, coûts API
```

---

## Architecture des fichiers

```
.claude/skills/sl-optimize/
├── SKILL.md                    ← ce fichier (orchestration)
├── runner.py                   ← entry point CLI (argparse + orchestration)
├── modules/
│   ├── __init__.py
│   ├── content_fetcher.py      ← fetch HTML + parse JSON-LD
│   ├── diagnostics_runner.py   ← 10 checks + check 5 bis
│   ├── textguru_client.py      ← API Textguru V2
│   ├── serp_analyzer.py        ← API DataForSEO SERP
│   ├── pattern_selector.py     ← scoring A/B/C
│   ├── faq_decision.py         ← FAQ par défaut sur compagnie + destination A/B
│   ├── data_assembler.py       ← compile tout pour Claude Code
│   ├── validator_seo.py        ← validation SEO (règles dures, bloquant)  ✅
│   ├── validator_geo.py        ← validation GEO (bonus, non-bloquant)    ✅
│   └── output_formatter.py     ← écriture des fichiers output            ✅
├── reference/                  ← 15 fichiers de règles (lecture seule)
├── templates/                  ← templates title/meta/signature
├── cache/
│   ├── textguru/               ← {guide_id}.json, TTL 7j
│   ├── dataforseo/             ← {md5(keyword+loc+lang+device)}.json, TTL 7j
│   └── content/                ← {md5(url)}.json, TTL 24h
├── output/
└── briefs/                     ← briefs catalogue manuels réutilisables
```

**Path vers le catalogue URLs :** `../../../../output/url_catalogue/catalogue_urls_latest.json`
(relatif au répertoire du skill). Résoudre via `Path(__file__).parents[3]` dans runner.py.

---

## Workflow d'exécution pas à pas

### Étape 1 — Fetch + parse HTML

`runner.py` appelle `content_fetcher.py` qui retourne :

```python
{
    "url": "...",
    "fetched_at": "ISO timestamp",
    "title": "...",
    "meta_description": "...",
    "h1": "...",
    "top_content_html": "...",        # inner HTML du .line-clamp-text
    "top_content_paragraphs_count": N,
    "destination_content_html": "...", # inner HTML du .kv-blocSEO
    "destination_content_h3_count": N,
    "author_signature": "...|null",
    "internal_links_existing": [...],  # LISTE À PRÉSERVER
    "schema": {
        "product": {
            "offer_count": N,
            "low_price": N,
            "currency": "EUR"
        },
        "breadcrumb": [...],
        "events_count": N,
        "ports_depart": [...],
        "destinations_mentionnees": [...]
    },
    "anomalies_detected": [...]
}
```

Sélecteurs CSS (voir `reference/extraction_selectors.md` pour détail complet) :
- H1 : `h1.kv-products-search-list-headTitle`
- Top content : `div.kv-products-search-list-headSubtitle div.line-clamp-text`
- Destination content : `div.kv-blocSEO-wrapper div.kv-blocSEO`
- JSON-LD : `script[type="application/ld+json"]`

Cache HTML 24h dans `cache/content/{md5(url)}.json`.

---

### Étape 2 — Diagnostics

`diagnostics_runner.py` exécute les checks définis dans `reference/sl_diagnostics.md`.

**Check 5 bis (schema suspect) — comportement bloquant :**

Si déclenché ET aucun `--brief` fourni → arrêt immédiat avec ce message :

```
[WARNING] Schema AggregateOffer suspect sur cette SL :
  offerCount : {valeur détectée}
  lowPrice   : {valeur détectée}
  Raison     : {valeur ronde / identique à d'autres SL / ...}

Le skill ne peut pas continuer sans valeurs fiables.
Fournis un brief catalogue :
  /sl-optimize --url {url} --type {type} --brief briefs/{slug}.md
Template disponible dans reference/brief_catalogue_format.md
```

Si `--brief` fourni, le check 5 bis ne bloque pas : le brief override le schema.

Tous les autres checks (1 à 10) : logger, continuer, inclure dans le rapport final.

---

### Étape 3 — Textguru

`textguru_client.py` utilise `reference/scoring_guidance.md`.

Auth : `Authorization: Bearer {YTG_API}` (clé dans `tools/.env`).
Base URL : `https://yourtext.guru/api/v2`

Retourne :
```python
{
    "guide_id": "...",
    "query": "croisière méditerranée",
    "keywords": {"1grams": [...], "2grams": [...], "3grams": [...]},
    "entities": [...],
    "targets": {"soseo_min": N, "soseo_max": N, "dseo_min": N, "dseo_max": N},
    "paa": [...],
    "serp": [...]
}
```

Polling guide creation : backoff 10s → 30s → 60s → 120s → 300s. Timeout = erreur non-bloquante
(fallback sur brief manuel ou analyse partielle).

---

### Étape 4 — DataForSEO SERP

`serp_analyzer.py` utilise `reference/dataforseo_api.md`.

Auth : HTTPBasicAuth(`DATAFORSEO_LOGIN`, `DATAFORSEO_PASSWORD`) depuis `tools/.env`.
Endpoint : `POST https://api.dataforseo.com/v3/serp/google/organic/live/advanced`
Sandbox pour dev : `https://sandbox.dataforseo.com/v3/serp/google/organic/live/advanced`

Paramètres : `location_code: 2250` (France — vérifier au premier run), `language_code: "fr"`,
`device: "desktop"`, `depth: 20`.

Retourne le dict défini dans `reference/dataforseo_api.md` section "Signaux extraits".
Logger `cost_usd` dans `metadata.json`.

---

### Étape 5 — Pattern selector

`pattern_selector.py` utilise `reference/pattern_selector.md`.

Signaux consommés :
- Volume keyword : depuis `textguru.targets` (proxy : score cible Textguru correlé au volume)
  ou override manuel `--textguru-keyword` si le keyword a un volume connu
- `serp.concurrents_count.ota_direct` → scoring Pattern A
- `serp.paa.count` → scoring Pattern B
- `serp.featured_snippet.has_table` → scoring Pattern B
- Override CLI `--pattern A|B|C` → bypass tout le scoring

Loggue dans `metadata.json` : `pattern_chosen`, `pattern_scores`, `signals`, `override_used`.

---

### Étape 6 — FAQ decision

`faq_decision.py` utilise `reference/faq_decision_tree.md`.

Fusionne PAA DataForSEO (`serp.paa.questions`) + PAA Textguru (`textguru.paa`),
dédupliqués par similarité de texte (lower + strip).

Retourne :
```python
{
    "add_faq": True|False,
    "questions": [...],     # Questions PAA retenues (4-6 max)
    "signals": {
        "paa_count": N,
        "has_featured_snippet_table": bool,
        "guides_in_top10": N,
        "interrogative_keyword": bool,
        "competitors_with_faq_count": N
    }
}
```

---

### Étape 7 — Data assembler

`data_assembler.py` compile tout en un seul dict et le persiste en JSON.

**Résolution du persona :**

| Persona | Domaines couverts |
|---|---|
| Élodie – Spécialiste Méditerranée | Méditerranée, Îles Grecques, Baléares, Croatie/Adriatique, Italie, Espagne, Turquie, Canaries, Corse, Sicile |
| Marc – Expert Caraïbes & Amériques | Caraïbes/Antilles, Bahamas, Cuba, Rép. Dominicaine, Polynésie, Amérique du Sud, Tour du Monde |
| Claire – Spécialiste Europe du Nord & Fjords | Europe du Nord, Fjords, Baltique, Islande, Spitzberg, Groenland, îles Britanniques |
| Thomas – Expert Compagnies & Thématiques | Toutes SL compagnies + SL thématiques (tout inclus, dernière minute, famille, luxe, fluviale) |
| L'équipe ABCroisière | Fallback si aucun match — à éviter |

Matching : extraire le domaine géographique de l'URL slug ou du `--type compagnie`.

Dict final persisté dans `output/<DATE>/<SLUG>/data_assembled.json`.
**À partir de là, Claude Code prend le relai pour la génération.**

---

### Étape 8 — Génération de contenu (Claude Code inline)

Claude Code lit `data_assembled.json` et génère dans cet ordre :

#### 8.1 Title

Structure : `Croisières [Nom] [Année] : [intent] & [promo|itinéraires]`
- Année = année courante (2026) ou courante+1 (2026-2027)
- Prix plancher = `catalogue.low_price` — identique au schema Product
- 50-60 caractères max
- Contraintes marque selon le type de SL
- Voir `reference/sl_anatomy.md` section "Title" + exemples validés

#### 8.2 Meta description

Structure : `[Volume] croisières [keyword] avec [compagnies]. Départs [ports FR]. [Destinations]. Dès [prix]€.`
- 150-160 caractères
- Commencer par chiffre ou entité forte (jamais "Partez", "Découvrez")
- Prix = `catalogue.low_price`, volume = `catalogue.offer_count`
- Pas d'emojis ni caractères HTML décoratifs (☀ ☛ → etc.)
- Voir `reference/sl_anatomy.md` section "Meta description"

#### 8.3 Top content HTML

Format cible : 1-3 `<p>` directement, **sans div wrapper** — le CMS injecte `div.line-clamp-text` automatiquement autour du champ `top_content`.

Règles :
- 1-3 paragraphes `<p>` en prose dense
- Entrée sur entité forte ou "Partez/Découvrez + entité forte + verbe concret"
- Jamais d'accroche creuse ("La Méditerranée vous attend", "Laissez-vous séduire")
- Données réelles : `catalogue.offer_count`, `catalogue.low_price`
- Chaque entité qui a une URL dans `catalogue_urls_latest.json` → linkée en relatif
- Conserver TOUS les liens de `current_content.internal_links_existing`
- Mot-clé principal en `<b>` : 1-2x max
- Pas de H3, pas de listes, pas de `<strong>`, pas de CSS inline
- Longueur selon pattern (Pattern A : 150-300 mots, Pattern B : 100-200 mots, Pattern C : 50-100 mots)
- Voir `reference/sl_anatomy.md` sections "Top content" et "Ce qu'on ne fait pas"

#### 8.4 Destination content HTML

Format cible : contenu H2/H3/P/ul directement, **sans div wrapper** — le CMS injecte `div.kv-blocSEO-wrapper > div.kv-blocSEO` automatiquement autour du champ `destination_content`.

**Pattern A (Costa)** — prose dense :
- Structure : 1+ H2 parent, 3-5 H3 thématiques ou en questions selon fluidité
- Paragraphes de longueur variable (30-300 mots)
- Prose dominante, pas ou peu de listes
- Référent : `reference/examples/costa.md`

**Pattern B (Îles Grecques)** — structuré + listes :
- Structure : 1 H2 parent en question, 3-5 H3 (mix questions + thématiques)
- Listes à puces pour énumérations (escales, compagnies, saisons)
- FAQ microdata en fin si `faq.add_faq: true`
- Référent : `reference/examples/iles_grecques.md`

**Pattern C (Cunard)** — minimal :
- Structure : 1 H2 parent thématique, 2-3 H3 thématiques
- Prose courte (100-200 mots par section)
- Ne pas sur-optimiser — la sobriété est voulue
- Référent : `reference/examples/cunard.md`

**Règles communes :**
- Liens internes partout où pertinent : ports, destinations, compagnies, navires, mois
- Chercher les URLs dans `catalogue_urls_latest.json` (485 URLs, 8 catégories)
- Conserver les liens de `current_content.internal_links_existing`
- Mot-clé principal en `<b>` : 1x par section max
- Pas de `<strong>`, `<em>`, `<h4>`, `<h1>` dans les blocs générés
- Pas de CSS inline (sauf signature auteur)
- Données réelles uniquement : `[À VÉRIFIER - champ]` si manquant
- Voir `reference/sl_anatomy.md` section "Destination content"

#### 8.5 FAQ microdata (si `faq.add_faq: true`)

Les questions FAQ s'intègrent directement en fin de destination content.
Pas de titre H3 "FAQ" séparé — chaque question devient un H3 wrappé en microdata.

```html
<div itemscope itemtype="https://schema.org/FAQPage">
  <div itemscope itemprop="mainEntity" itemtype="https://schema.org/Question">
    <h3 itemprop="name">[Question issue des PAA ou intents transactionnels]</h3>
    <div itemscope itemprop="acceptedAnswer" itemtype="https://schema.org/Answer">
      <div itemprop="text">
        <p>[Réponse 40-80 mots, factuelle, données réelles]</p>
      </div>
    </div>
  </div>
  <!-- Répéter pour chaque question — 4 à 6 max -->
</div>
```

Mix : 2-3 questions issues des PAA (`faq.questions`) + 2-3 questions transactionnelles.
Voir `reference/faq_decision_tree.md` pour le détail.

#### 8.6 Signature auteur

Toujours en fin de destination content, juste avant fermeture de `.kv-blocSEO`.
Format HTML exact depuis `reference/authors.md` :

```html
<p style="margin: 5px 0 0 10px; float: left;">
  <span style="background-image: url('/static/v4/images/pages/lp-navire/sprite.png'); background-position: -28px 0px; background-repeat:no-repeat; width: 25px; float:left; height: 25px;"></span>
  <span style="margin-left: 10px;">[Prénom] – [Titre stable du persona]</span>
</p>
```

Titre stable : "Élodie – Spécialiste Méditerranée" (même sur SL Îles Grecques ou Baléares).

---

### Étape 9 — Validation

#### validator_seo.py (bloquant)

Règles dures — un échec = correction obligatoire avant output :

- [ ] Title : 50-60 caractères
- [ ] Meta : 150-160 caractères
- [ ] Meta : commence par chiffre ou entité forte (pas "Partez", "Découvrez", "Explorez")
- [ ] Meta : aucun emoji ni caractère HTML décoratif
- [ ] Title / meta / schema : prix et volume identiques
- [ ] Année dans le title : courante (2026) ou courante+1 (2026-2027)
- [ ] H1 : présent, contient le keyword, accents corrects
- [ ] Top content : 1-3 `<p>`, pas de H3, pas de listes
- [ ] Top content : >= 5 liens internes
- [ ] Top content : mot-clé principal en `<b>` 1-2x
- [ ] Destination content : H2 parent + 2-5 H3
- [ ] Destination content : >= 10 liens internes
- [ ] Tous les liens internes en relatif (`/fr/...`)
- [ ] Pas de `<strong>`, `<em>`, `<h4>`, `<h1>` (sauf H3 FAQPage microdata)
- [ ] Pas de CSS inline (sauf signature auteur)
- [ ] Contraintes marque respectées (fenêtre 15 mots autour de la marque)
- [ ] Signature auteur présente en fin
- [ ] Liens `current_content.internal_links_existing` tous préservés

**Si un check bloquant échoue** : Claude Code corrige et relance validator_seo (1 seul retry).

#### validator_geo.py (non-bloquant)

Observations de qualité — un échec = warning dans `bilan_geo.md`, pas de blocage :

- [ ] Top content : entrée sur entité forte ou "Partez/Découvrez" + entité
- [ ] Entités nommées denses (~1 / 6-8 mots dans le top content)
- [ ] Chiffres concrets dans le destination content (prix, durées, dates)
- [ ] H3 en questions quand c'est naturel (Pattern B principalement)
- [ ] FAQ microdata présente si conditions remplies
- [ ] Signature auteur présente (double-check)
- [ ] Entity echoing en début de paragraphe si fluide (jamais forcé)

Un run peut passer SEO avec des warnings GEO : c'est normal.
L'inverse (échec SEO avec GEO OK) est bloquant.

---

### Étape 10 — Output formatter

`output_formatter.py` écrit tous les fichiers dans `output/<DATE>/<SLUG>/`.

`metadata.json` doit contenir au minimum :
```json
{
  "url": "...",
  "slug": "...",
  "type": "destination|compagnie",
  "pattern_chosen": "A|B|C",
  "pattern_scores": {"A": 0, "B": 0, "C": 0},
  "pattern_signals": {...},
  "override_used": false,
  "fallback_used": false,
  "persona": "...",
  "faq_added": false,
  "faq_signals": {...},
  "mode_variables": "hardcoded",
  "textguru_guide_id": "...",
  "dataforseo_cost_usd": 0.006,
  "generated_at": "ISO timestamp",
  "anomalies_count": {"HIGH": 0, "MEDIUM": 0, "LOW": 0}
}
```

---

## Gestion des erreurs

| Situation | Comportement |
|---|---|
| Check 5 bis déclenché, pas de `--brief` | Stop + message explicite + demande brief |
| AggregateOffer absent, pas de `--brief` | Stop + message explicite + demande brief |
| Textguru timeout (> 5 min polling) | Warning + continuer sans Textguru (pattern selector sur volume seul) |
| DataForSEO timeout ou erreur | Warning + fallback pattern selector sur volume Textguru |
| DataForSEO 429 rate limit | Attendre 60s + 1 retry |
| Validator SEO échoue | Claude Code corrige + 1 relance validator (pas de boucle infinie) |
| Donnée manquante non critique | `[À VÉRIFIER - nom_du_champ]` dans le HTML + warning dans rapport |
| JSON-LD malformé | Skip silencieux + log `json_ld_malformed` dans diagnostic |

---

## Contraintes non négociables

- Pas d'emojis ni caractères HTML décoratifs dans les metas (☀ ☛ → ✓ etc.)
- Contraintes marque MSC strictes — voir `reference/brand_constraints/msc.md`
- Données réelles uniquement — jamais d'estimation ni d'invention
- Liens internes existants TOUJOURS préservés (liste dans `data_assembled.json`)
- URLs internes toujours en relatif (`/fr/...`)
- `[À VÉRIFIER - champ]` si donnée manquante — jamais de valeur inventée
- Pas de superlatifs marketing ("inoubliable", "paradis", "meilleure expérience")
- FAQ toujours en microdata schema.org/FAQPage si ajoutée — jamais en liste à puces
- `--mode-variables hardcoded` par défaut jusqu'au fix CMS (suivi dans `reference/cms_variables.md`)

---

## SL de test par étape

| SL | URL | Pattern | Ce qu'elle teste |
|---|---|---|---|
| Costa | `/fr/croisieres/croisiere-costa-croisieres/compagnie,7/` | A | Schema fiable, profil compagnie, prose dense |
| Îles Grecques | `/fr/croisieres/croisiere-iles-grecques/destination,53,50/` | B | Schema suspect (check 5 bis), profil destination |
| Cunard | `/fr/croisieres/croisiere-cunard/compagnie,16/` | C | Petit volume, anomalies meta (emojis à bannir), profil compagnie |

---

## Modules runner vs post-génération

**Modules exécutés par le runner (steps 1-7)** — `python runner.py` les appelle
dans l'ordre. Requis pour que le runner tourne :

| Module | Step | Rôle |
|---|---|---|
| `content_fetcher` | 1 | Fetch HTML + parse JSON-LD |
| `diagnostics_runner` | 2 | 10 checks + check 5 bis |
| `textguru_client` | 3 | Brief sémantique + PAA |
| `serp_analyzer` | 4 | SERP DataForSEO |
| `pattern_selector` | 5 | Scoring A/B/C |
| `faq_decision` | 6 | Décision FAQ |
| `data_assembler` | 7 | Dict structuré → data_assembled.json |
| `brief_parser` | — | Parseur brief catalogue (appelé par runner si `--brief`) |

**Modules post-génération** — appelés par Claude Code après avoir produit le
contenu inline. Pas dans le runner, pas bloquants pour les steps 1-7 :

| Module | Rôle |
|---|---|
| `validator_seo` | Validation règles SEO dures (bloquant si échec) |
| `validator_geo` | Validation bonus GEO (non-bloquant) |
| `output_formatter` | Écriture des fichiers output dans `output/<DATE>/<SLUG>/` |

---

## Index des fichiers reference

| Fichier | Rôle |
|---|---|
| `sl_anatomy.md` | Règles éditoriales complètes (document fondateur) |
| `authors.md` | 4 personas EEAT + format HTML signature |
| `pattern_selector.md` | Algorithme scoring A/B/C |
| `faq_decision_tree.md` | Décision FAQ + template microdata H3 |
| `sl_diagnostics.md` | 10 checks + check 5 bis |
| `extraction_selectors.md` | Sélecteurs CSS + parsing JSON-LD |
| `scoring_guidance.md` | Textguru API V2 + règles SOSEO/DSEO |
| `dataforseo_api.md` | DataForSEO SERP endpoint + parsing complet |
| `cms_variables.md` | Variables CMS cassées + tracker migrations |
| `brand_constraints/msc.md` | Termes interdits MSC |
| `concurrents_directs.md` | OTA + armateurs à filtrer dans la SERP |
| `brief_catalogue_format.md` | Format brief catalogue manuel + parsing Python |
| `examples/costa.md` | Référent Pattern A (dense prose) |
| `examples/iles_grecques.md` | Référent Pattern B (structured + lists) |
| `examples/cunard.md` | Référent Pattern C (minimal) |
