# DEBUG_NOTES — psi-dev-audit

## Contexte

Skill psi-dev-audit créé le 2026-04-20. Premier run effectué sur les 6 pages ABC (mobile + desktop). Le ticket.md généré présente plusieurs anomalies qui invalident son utilisation en l'état pour un ticket dev. À investiguer.

---

## Anomalies détectées sur le run du 2026-04-20

### 1. TBT mobile anormalement bas sur toutes les pages

| Page | TBT mobile | TBT desktop |
|------|-----------|------------|
| Fiche Produit | 0.0s | ok |
| Homepage | 0.0s | 0.6s |
| Page Navire | 0.1s | ok |
| Page Thématique | 0.0s | ok |
| SL MSC | 0.0s | ok |
| SL Méditerranée | 0.0s | ok |

Incohérent : en mobile émulé par Lighthouse (CPU throttling x4), on s'attend à du TBT plusieurs fois supérieur au desktop. Homepage desktop = 0.6s → mobile devrait être entre 2s et 4s.

---

### 2. Scripts tiers mobile quasi-vides

- Mobile ne montre qu'AppDynamics et JSDelivr CDN sur toutes les pages
- Desktop montre correctement GTM (848ms sur homepage), ContentSquare, Didomi, AppDynamics, TrustPilot
- GTM, ContentSquare, Didomi totalement absents des rapports mobile

---

### 3. Thread principal mobile anormalement bas

- Script Evaluation mobile : 0.1s à 0.3s selon les pages
- Script Evaluation desktop : 1.6s à 6.2s
- Rapport inversé par rapport à ce qu'on attend (mobile > desktop)

---

### 4. Élément LCP mobile suspect

Sur Fiche Produit, Page Navire Costa Toscana, Page Thématique, SL MSC, SL Méditerranée : l'élément LCP identifié est `body > img` avec :
```
<img fetchpriority="high" alt="." width="99999" height="99999" style="pointer-events: none; position: absolute; top: 0px
```
Ressemble à un pixel de tracking invisible, pas à un vrai élément LCP.

À vérifier : est-ce ce que l'API renvoie vraiment, ou est-ce que le parser prend le mauvais item dans `lcp-breakdown-insight.details.items[]` ?

---

### 5. Champ blockingTime vide partout

Dans tous les tableaux "TBT — Scripts tiers", la colonne "Blocking (ms)" affiche "—".
Le champ `blockingTime` existe dans la structure `third-party-summary` de l'API Lighthouse.
Soit le parser ne l'extrait pas, soit il est mal mappé.

---

### 6. Bruit dans les tableaux scripts tiers

`service-voyages.com` apparaît avec toutes ses images listées à 0ms CPU (des .jpg, .svg).
`JSDelivr CDN` apparaît avec des .css listés comme scripts.
Ces entrées ne devraient pas figurer dans un tableau "scripts tiers / temps CPU".

**Fix prévu** : filtrer — n'inclure que les entités avec `mainThreadTime > 0` OU ressource de type JS.

---

### 7. Output incomplet (à confirmer)

La spec prévoyait `audits.csv` et `third_party_scripts.csv` cumulatifs.
À vérifier : ces CSV ont-ils été générés dans `outputs/` ? Si oui, pas de bug, l'utilisateur ne les a pas partagés.

---

## Plan de debug — à faire dans l'ordre

### Étape 1 — Diagnostiquer : bug API ou bug parser ?

Ouvrir `runs/2026-04-20/homepage_mobile.json` et inspecter :

- `lighthouseResult.audits['total-blocking-time'].numericValue`
- `lighthouseResult.audits['third-party-summary'].details.items[]` (liste complète)
- `lighthouseResult.audits['mainthread-work-breakdown'].displayValue`
- `lighthouseResult.audits['largest-contentful-paint-element'].details.items[0].items[]`
- `lighthouseResult.audits['total-blocking-time'].score`
- `lighthouseResult.configSettings` (throttlingMethod, formFactor, screenEmulation)

**Cas A** : le JSON brut contient des valeurs mobile cohérentes (TBT > 1000ms, GTM présent) → bug dans `report.py`. Probable cause : indexation en dur, filtre qui exclut des entités, ou mauvaise clé d'audit (nouveau nom Lighthouse 12).

**Cas B** : le JSON brut contient réellement des valeurs basses / vides → l'API PSI a mal répondu. Causes possibles :
- `configSettings.formFactor` indique desktop au lieu de mobile (param `strategy=mobile` mal transmis)
- Throttling non appliqué (CPU non ralenti → TBT faible)
- Appels mobile en timeout partiel (résultat tronqué mais pas en erreur)
- Rate limiting Google qui dégrade silencieusement la qualité du run

### Étape 2 — Corriger selon le diagnostic

- **Cas A** : fixer `report.py` (parsing third-party-summary, LCP element selection, blockingTime, filtre scripts tiers non-JS)
- **Cas B** : fixer `audit.py` (vérifier query string, augmenter timeout à 90s, délai inter-appels de 2s → 5s, ajouter retry avec validation cohérence réponse)

### Étape 3 — Vérifier les CSV

Confirmer que `outputs/audits.csv` et `outputs/third_party_scripts.csv` existent et sont bien formés.

### Étape 4 — Relancer un run complet et valider contre l'UI PSI

- Homepage mobile : TBT doit être cohérent avec ce que PSI UI affiche
- Homepage mobile : GTM doit apparaître avec un temps CPU proche de l'UI

---

## Note importante

Le bug historique du premier script était d'utiliser `unused-javascript` (KB) au lieu de `third-party-summary` (ms CPU). Le nouveau skill utilise bien `third-parties-insight` côté desktop — les données desktop sont cohérentes. Le problème mobile est différent. Ne pas refaire la même hypothèse.
