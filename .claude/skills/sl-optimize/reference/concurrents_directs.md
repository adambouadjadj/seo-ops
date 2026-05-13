# Concurrents directs - Liste de référence pour l'analyse SERP

## Usage dans le skill
Quand le skill analyse une SERP via DataForSEO :
1. Extraire les URLs du top 10 (ou top 20 si besoin d'élargir)
2. Filtrer sur les domaines listés ci-dessous
3. Analyser UNIQUEMENT ces concurrents pour le benchmark 
   structure / longueur / patterns
4. Ignorer TripAdvisor, routard, Lonely Planet, YouTube, 
   Reddit, Quora, blogs perso

## OTA concurrents directs (analyser à chaque SERP)

| Domaine | URL de référence | Notes |
|---|---|---|
| destockagecroisieres.fr | https://www.destockagecroisieres.fr/ | OTA direct |
| croisieres.fr | https://www.croisieres.fr/ | OTA direct |
| croisieres.com | https://www.croisieres.com/ | OTA direct |
| logitravel.fr | https://www.logitravel.fr/croisieres/ | OTA direct (section croisières) |
| croisierenet.com | https://www.croisierenet.com/ | OTA direct |
| centralcruise.com | https://centralcruise.com/ | OTA direct |
| okcroisiere.fr | https://okcroisiere.fr/ | OTA direct |
| voyages.carrefour.fr | https://voyages.carrefour.fr/accueil/croisiere | OTA direct (section croisières) |
| croisiland.com | https://www.croisiland.com/ | OTA direct |
| croisiere.promovacances.com | https://croisiere.promovacances.com/ | Même groupe (PMVC), concurrent frère, à comparer avec prudence |

## Armateurs (concurrents partiels, analyser selon contexte)

Les armateurs rankent naturellement sur leur propre marque. 
Ne pas essayer de les déloger sur leurs SL brandées. Mais 
analyser leur structure quand on traite une SL compagnie 
correspondante (ex: pour optimiser SL Costa, regarder comment 
costacroisieres.fr structure sa page).

| Compagnie | URL officielle | Notes |
|---|---|---|
| MSC Croisières | https://www.msccroisieres.fr/ | Site officiel FR |
| Costa Croisières | https://www.costacroisieres.fr/ | Site officiel FR |
| Royal Caribbean | https://www.royalcaribbean.com/ | Site international, pas de .fr dédié |
| Celebrity Cruises | https://www.celebritycruises.com/ | Site international |
| Cunard | https://www.cunard-france.fr/ | Site officiel FR |
| Croisieurope | https://www.croisieurope.com/ | Site officiel |
| CFC (Compagnie Française de Croisières) | https://www.cfc-croisieres.fr/ | Site officiel FR |
| Ponant | https://www.ponant.com/ | Site officiel |
| Rivages du Monde | https://www.rivagesdumonde.fr/ | Site officiel |
| Club Med Croisières | https://www.clubmed.fr/l/club-med-croisieres | Section du site Club Med global |

## Sites à exclure de l'analyse SERP

| Domaine | Type |
|---|---|
| tripadvisor.fr | Avis / guide |
| routard.com | Guide voyage |
| lonelyplanet.fr | Guide |
| youtube.com | Vidéos |
| reddit.com | Discussions |
| quora.com | Discussions |
| abcroisiere.com | SOI-MÊME (ne jamais inclure dans l'analyse) |

## Règle de filtrage dans le skill

```python
# Pseudo-code
OTA_DIRECTS = [
    "destockagecroisieres.fr",
    "croisieres.fr",
    "croisieres.com",
    "logitravel.fr/croisieres",
    "croisierenet.com",
    "centralcruise.com",
    "okcroisiere.fr",
    "voyages.carrefour.fr/accueil/croisiere",
    "croisiland.com",
    "croisiere.promovacances.com",
]

ARMATEURS = {
    "msccroisieres.fr": "MSC",
    "costacroisieres.fr": "Costa",
    "royalcaribbean.com": "Royal Caribbean",
    "celebritycruises.com": "Celebrity",
    "cunard-france.fr": "Cunard",
    "croisieurope.com": "Croisieurope",
    "cfc-croisieres.fr": "CFC",
    "ponant.com": "Ponant",
    "rivagesdumonde.fr": "Rivages du Monde",
    "clubmed.fr/l/club-med-croisieres": "Club Med",
}

EXCLUS = [
    "tripadvisor", "routard", "lonelyplanet", "youtube",
    "reddit", "quora", "abcroisiere",
]

serp_results = dataforseo_serp(keyword)

concurrents_directs = [
    r for r in serp_results 
    if any(d in r['url'] for d in OTA_DIRECTS)
]

armateurs_presents = [
    r for r in serp_results 
    if any(d in r['url'] for d in ARMATEURS.keys())
]

# SL compagnie : analyser OTA + l'armateur correspondant
# SL destination : analyser OTA uniquement (les armateurs 
# rankent rarement sur les requêtes destination génériques)
# Si moins de 3 concurrents directs dans top 10 → élargir 
# à top 20
```

## Maintenance
Mettre à jour cette liste quand on découvre de nouveaux 
concurrents (vérification tous les 3 mois via DataForSEO sur 
les SL piliers).

## Note sur les sites internationaux
Royal Caribbean et Celebrity Cruises n'ont pas de site 
officiel FR dédié, ce sont des sites internationaux avec 
détection de langue/géo. Le skill doit matcher sur le domaine 
racine et ne pas s'attendre à un ".fr" systématique.