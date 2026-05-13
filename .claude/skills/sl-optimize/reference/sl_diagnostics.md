# Diagnostics automatiques des SL

## Principe
Avant de générer du nouveau contenu, le skill effectue un 
audit complet de la SL cible pour détecter les anomalies 
techniques et éditoriales. Ces anomalies sont remontées dans 
un rapport de diagnostic séparé, actionnable par l'équipe dev 
ou SEO.

## Pourquoi c'est important
Les SL ABCroisière ont accumulé des anomalies invisibles à 
l'œil nu mais détectables automatiquement : bugs breadcrumb, 
variables CMS cassées, contraintes marque violées, 
incohérences title/meta/schema. Le skill est donc un outil 
de détection en plus d'un générateur de contenu.

## Checks à exécuter systématiquement

### Check 1 : Cohérence title / meta / schema

Comparer les valeurs chiffrées entre le title, la meta 
description et le schema Product.

Règles :
- Le prix dans le title doit être égal au prix dans la meta 
  doit être égal au lowPrice du schema
- Le volume dans la meta doit être égal au offerCount du 
  schema
- Si divergence → ANOMALIE avec sévérité HIGH

Exemple réel détecté sur SL Costa (24/04/2026) :
- Title dit "dès 159€"
- Meta dit "à partir de 169€"  
- Schema dit lowPrice 169
- Anomalie : title désynchronisé

Code du check (pseudo) :
- Extraire les nombres du title avec regex 
  (matcher "dès X€", "à partir de X€", etc.)
- Extraire les nombres de la meta pareil
- Comparer à schema.product.low_price et 
  schema.product.volume
- Si mismatch → anomalie

### Check 2 : Année obsolète

Regex sur le title et la meta pour matcher les patterns 
de 4 chiffres commençant par 20 : `\b20\d{2}\b`

Règles :
- Année présente = année courante → OK
- Année présente = année courante + 1 → OK
- Année présente = année courante - 1 ou antérieure → 
  ANOMALIE HIGH
- Format "2025-2026" alors qu'on est en 2026 → ANOMALIE 
  HIGH (devrait être "2026" ou "2026-2027")

### Check 3 : H1 valide

Règles :
- H1 présent (non vide)
- H1 contient le keyword principal de la SL (ou au moins 
  la racine "Croisières")
- Accentuation correcte : "Croisières" avec accent, pas 
  "Croisieres"
- Capitalisation : première lettre en majuscule

Si H1 absent → ANOMALIE HIGH bloquante
Si H1 sans accents ou mal capitalisé → ANOMALIE MEDIUM

Exemple réel (SL Costa) : H1 = "Croisieres Costa" 
(sans accent) → ANOMALIE MEDIUM

### Check 4 : Breadcrumb schema

Parser le bloc JSON-LD de type BreadcrumbList.

Pour chaque itemListElement :
- Vérifier que `item.@id` est sur www.abcroisiere.com
- Si URL contient un sous-domaine autre que www 
  (pattern `*.abcroisiere.com` sauf www) → ANOMALIE HIGH 
  `breadcrumb_url_obsolete`
- Vérifier que `item.name` ne viole pas les contraintes 
  marque (voir brand_constraints/)
- Si violation détectée → ANOMALIE HIGH 
  `breadcrumb_brand_violation`

Exemple réel (SL MSC) :
- URL breadcrumb position 2 = `https://msc.abcroisiere.com/` 
  → ANOMALIE (sous-domaine obsolète)
- Nom = "Croisières MSC Croisières pas chères" → ANOMALIE 
  (violation contrainte MSC)

### Check 5 : Variables CMS injectées en dur

Scanner tout le HTML pour détecter si des variables CMS 
apparaissent en dur (pattern `${...}`) sans avoir été 
injectées.

Règles :
- Si `${noResultats}`, `${bestPrix}` ou autre apparaissent 
  littéralement dans le HTML rendu → ANOMALIE HIGH 
  `cms_variable_not_injected`
- Logger la variable et le contexte où elle apparaît

### Check 5 bis : Valeurs schema Product suspectes

Détecter si le schema Product de la SL affiche des valeurs 
génériques par défaut plutôt que des données spécifiques 
à la destination/compagnie.

Heuristique :
- Si `offerCount` = "1 000" ou "1000" (exactement) ET 
  `lowPrice` = "79" → signal de valeurs par défaut 
  probables
- Si la SL est une destination spécifique ou une compagnie 
  spécifique (pas la SL globale Méditerranée qui elle a 
  effectivement ~1000 croisières), ces valeurs sont très 
  probablement génériques

Actions :
- Flag ANOMALIE HIGH : `schema_product_default_values`
- Demander à l'utilisateur de fournir les vraies valeurs 
  catalogue via un brief manuel
- Ne pas utiliser les valeurs schema dans le contenu généré 
  tant que l'utilisateur n'a pas confirmé

Exemple détecté (Îles Grecques, 24/04/2026) :
- Schema : offerCount "1 000", lowPrice "79"
- Réalité catalogue : 311 croisières, 309€
- Divergence critique, valeurs schema non exploitables

Cette détection s'ajoute au check 1 (cohérence 
title/meta/schema) : même si title/meta/schema sont 
cohérents entre eux sur les valeurs suspectes, le check 
5 bis détecte que les valeurs sont fausses à la racine.

### Check 6 : URLs internes en relatif

Scanner toutes les balises `<a href=...>` du top content 
et du destination content.

Règles :
- Toutes les URLs internes (pointant vers abcroisiere.com) 
  doivent être en relatif (`/fr/croisieres/...`)
- Si URL absolue détectée (`https://www.abcroisiere.com/...`) 
  → ANOMALIE MEDIUM `internal_url_absolute`
- Les URLs externes restent absolues, pas d'anomalie

### Check 7 : Longueurs title et meta

Règles :
- Title : entre 30 et 60 caractères
- Meta description : entre 120 et 160 caractères

Si hors limites → ANOMALIE LOW (non bloquant)
- Title < 30 : trop court
- Title > 60 : Google tronque
- Meta < 120 : sous-exploité
- Meta > 160 : Google tronque

### Check 8 : Contraintes marque dans tout le contenu

Scanner le HTML complet (top content + destination content 
+ title + meta + H1) pour détecter les violations de 
contraintes marque.

Pour chaque marque listée dans brand_constraints/ :
- Chercher les mentions de la marque (case insensitive)
- Pour chaque mention, vérifier qu'aucun terme interdit 
  n'apparaît dans une fenêtre de 15 mots autour
- Si violation → ANOMALIE HIGH `brand_constraint_violation`

### Check 9 : Signature auteur présente

Règle :
- Si la SL a été optimisée par le skill (donc devrait avoir 
  une signature), vérifier qu'elle est présente en fin de 
  destination content
- Si absente → ANOMALIE LOW `author_signature_missing`

Pour les SL pas encore optimisées, pas d'anomalie (la 
signature sera ajoutée par le skill).

### Check 10 : Balisage HTML conforme

Scanner le HTML généré pour détecter :
- Balises interdites : `<strong>`, `<em>`, `<h1>` (dans 
  destination content), `<h4>`
- CSS inline (attribut `style=...`) sauf pour la signature 
  auteur qui garde son style historique
- Classes CSS arbitraires
- Attributs data-*

Si balise interdite ou style inline → ANOMALIE MEDIUM

## Sévérités

- **HIGH** : bug critique qui impacte le SEO ou viole une 
  contrainte (marque, cohérence données)
- **MEDIUM** : qualité dégradée mais impact limité 
  (accentuation, longueur meta)
- **LOW** : best practice non respectée, non urgent

## Output du module de diagnostic

Le module `diagnostics_runner.py` retourne une liste 
structurée d'anomalies :

Pour chaque anomalie :
- check_id : identifiant unique du check (ex: "check_4_breadcrumb")
- severity : "HIGH", "MEDIUM" ou "LOW"
- code : code court de l'anomalie (ex: "breadcrumb_url_obsolete")
- description : phrase lisible pour humain
- details : dict avec contexte (valeurs divergentes, URL 
  concernée, phrase contenant la violation, etc.)
- suggested_fix : suggestion d'action corrective

Exemple :
- check_id : "check_1_consistency"
- severity : "HIGH"
- code : "title_meta_mismatch_price"
- description : "Le prix dans le title (159€) diffère du 
  prix dans la meta et le schema (169€)"
- details : {title_price: 159, meta_price: 169, 
  schema_price: 169}
- suggested_fix : "Mettre à jour le title pour afficher 169€"

## Rapport de diagnostic

Le skill génère un fichier `diagnostic_report.md` dans 
l'output, avec :
- Nombre total d'anomalies par sévérité (HIGH / MEDIUM / LOW)
- Liste détaillée par check
- Suggestions de fix priorisées
- URL et métadonnées de la SL analysée

Ce rapport est **indépendant du contenu généré**. Il peut 
être utilisé pour ouvrir des tickets dev (ex: fix breadcrumb 
MSC) sans attendre que le skill soit lancé sur toutes les 
SL.

## Usage du diagnostic dans le flow du skill

1. Fetch de la SL (via extraction_selectors)
2. Run des 10 checks de diagnostic
3. Si anomalies HIGH détectées → logger, continuer la 
   génération, remonter en fin
4. Si anomalies MEDIUM ou LOW → logger, continuer 
   normalement
5. Le contenu généré par le skill **ne doit pas reproduire** 
   les anomalies détectées (ex: si le title actuel a une 
   année obsolète, le nouveau title doit avoir l'année 
   courante)

## Mode dry-run

Flag `--dry-run` : le skill exécute uniquement les 
diagnostics sans générer de nouveau contenu. Utile pour 
auditer rapidement une SL ou un batch de SL avant de 
décider quoi prioriser.