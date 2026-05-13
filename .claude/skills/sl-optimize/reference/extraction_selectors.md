# Sélecteurs d'extraction - Parsing HTML et JSON-LD

## Objectif
Définir comment le skill extrait les données d'une SL cible 
depuis le HTML frontend et le JSON-LD, sans dépendre d'APIs 
externes pour les données catalogue.

## Sources de données

### 1. HTML frontend (fetch de l'URL)
Le skill fait un HTTP GET sur l'URL de la SL et parse le HTML 
avec BeautifulSoup (ou équivalent Python).

Le contenu est rendu côté serveur, donc le HTML initial 
contient déjà les éléments visibles. Pas besoin de rendu JS.

### 2. JSON-LD embarqué dans le HTML
Plusieurs balises script type="application/ld+json" sont 
présentes dans le HTML. Chacune contient un schema distinct 
(Organization, BreadcrumbList, Product, Event).

## Sélecteurs CSS à utiliser

### Title et meta description
- title : balise `<title>`
- meta description : `meta[name="description"]` attribut 
  `content`

### H1 principal
- Sélecteur : `h1.kv-products-search-list-headTitle`
- Classe : `kv-products-search-list-headTitle`

### Top content (paragraphes intro)
- Chemin : `div.kv-products-search-list-headSubtitle` 
  contient `div.line-clamp-text` qui contient 1 à 3 
  balises `<p>`
- Le skill récupère le HTML complet du container 
  `div.line-clamp-text` (inner HTML)
- Le skill compte le nombre de paragraphes pour info 
  diagnostic

### Destination content (blocs H3 + paragraphes du bas)
- Chemin : `div.kv-blocSEO-wrapper` contient `div.kv-blocSEO`
- Le container `div.kv-blocSEO` contient :
  - H2 parent
  - H3 multiples
  - Paragraphes
  - Listes (ul/li) en pattern B
  - Signature auteur en fin

### Signature auteur (si présente)
- La signature n'a pas de classe dédiée, elle est 
  identifiable par sa structure : `<p>` contenant un 
  `<span>` avec attribut style incluant `sprite.png`
- Le texte de la signature est dans un second `<span>` 
  avec le format `[Prénom] – [Expertise]`

## Parsing JSON-LD

### Extraction de tous les blocs JSON-LD
1. Sélectionner toutes les balises `script[type="application/ld+json"]`
2. Pour chaque balise, parser le contenu JSON
3. Gérer les erreurs de parsing (JSON malformé) 
   silencieusement : skip le bloc, continuer avec les autres

### Identification par @type

Les blocs JSON-LD à identifier :
- `@type: "Organization"` : infos organisation
- `@type: "BreadcrumbList"` : breadcrumb (check anomalies)
- `@type: "Product"` : données catalogue (critique)
- `@type: "Event"` : croisières individuelles

### Extraction des données catalogue depuis Product

Si Product existe et contient "offers" :
- Si `offers.@type == "AggregateOffer"` :
  - `offerCount` : volume de croisières (ex: "1 000" ou 1000)
  - `lowPrice` : prix plancher (ex: "79")
  - `highPrice` : prix plafond (parfois présent)
  - `priceCurrency` : devise (ex: "EUR")

**Attention format** : `offerCount` et `lowPrice` peuvent 
être en string ("1 000" avec espace insécable) ou en int. 
Le skill doit normaliser en int :
- Enlever espaces, espaces insécables (\u00a0), virgules
- Convertir en int
- Si échec → None

### Extraction des infos depuis Events

Les Events représentent les croisières individuelles du 
catalogue. Le skill peut en extraire :
- Ports de départ : `location.address.addressLocality` 
  (mettre en set pour dédupliquer)
- Destinations mentionnées : parser le champ `name` qui 
  contient souvent une liste de pays séparés par virgules 
  ("Italie, Espagne, France")

**Note** : les Events sont souvent nombreux (20-50 par SL). 
Le skill ne les utilise qu'en lecture pour extraire les 
ports et destinations, pas pour générer du contenu 
individuel.

### Détection d'anomalies dans BreadcrumbList

Pour chaque item de `itemListElement` :
- Récupérer `item.@id` (URL) et `item.name` (nom affiché)
- Check URL : doit commencer par `https://www.abcroisiere.com` 
  ou être un path relatif
  - Si URL contient un sous-domaine autre que www 
    (ex: `msc.abcroisiere.com`) → ANOMALIE 
    `breadcrumb_url_obsolete`
- Check nom : scanner pour termes interdits selon 
  `brand_constraints/` (ex: "pas chères" avec MSC → 
  ANOMALIE `breadcrumb_brand_violation`)

## Gestion des erreurs

### Cas : le container n'existe pas
Certaines SL peuvent ne pas avoir de top content ou de 
destination content. Le skill doit gérer gracieusement :
- Logger `top_content_missing` ou `destination_content_missing`
- Le skill continue mais signale dans le diagnostic
- Pas de crash

### Cas : JSON-LD malformé
Skip silencieusement le bloc fautif, continuer avec les 
autres blocs. Ne pas crasher. Logger 
`json_ld_malformed` dans le rapport.

### Cas : AggregateOffer absent
Si le schema Product n'existe pas ou n'a pas 
d'AggregateOffer, fallback sur le brief catalogue fourni 
en input par l'utilisateur. Si pas de brief non plus → 
ERREUR bloquante, stop de l'exécution du skill.

## Fetch de l'URL

Utiliser `requests` avec un User-Agent réaliste pour éviter 
les blocages :

User-Agent recommandé : 
Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 
(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36

Timeout : 15 secondes
Gérer les codes HTTP 4xx et 5xx proprement (log + stop).

### Alternative : MCP Chrome DevTools
Si disponible dans le projet (mentionné dans la mémoire CC), 
utiliser le MCP Chrome DevTools peut être plus fiable pour 
les pages qui bloquent le scraping basique. À évaluer selon 
les résultats des premiers tests sur 2-3 SL. Si `requests` 
suffit, on reste dessus pour la simplicité.

## Output attendu après extraction

Le module `content_fetcher.py` doit retourner un dict 
structuré contenant :

- url : URL fetchée
- fetched_at : timestamp ISO
- title : contenu de la balise title
- meta_description : contenu de la meta description
- h1 : texte du H1
- top_content_html : HTML complet du top content
- top_content_paragraphs_count : nombre de `<p>` comptés
- destination_content_html : HTML complet du destination 
  content
- destination_content_h3_count : nombre de H3 comptés
- author_signature : texte de la signature si présente, 
  null sinon
- schema : dict avec organization, breadcrumb, product 
  (volume, low_price, currency), events_count, 
  ports_depart (liste), destinations_mentionnees (liste)
- anomalies_detected : liste des anomalies trouvées pendant 
  l'extraction

Ce dict est consommé par les autres modules du skill 
(pattern_selector, content_generator, validator, etc.).

## Cache

Le skill devrait cacher les résultats d'extraction pendant 
la durée d'une même session (éviter de re-fetcher 3x la 
même URL si plusieurs étapes du skill en ont besoin). 
Cache simple en mémoire suffit, pas besoin de persistance 
sur disque.