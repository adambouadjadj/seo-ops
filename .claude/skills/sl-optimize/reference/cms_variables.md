# Variables CMS - Statut et gestion

## Date de mise à jour
24/04/2026 (statut à vérifier au fil des fix dev)

## Statut actuel : variables NON FIABLES

Les variables CMS `${noResultats}`, `${bestPrix}` et potentiellement 
d'autres sont injectées par le CMS au rendu mais retournent des 
valeurs incorrectes en production.

**Exemples de bugs observés :**
- Meta description SL Méditerranée : "131 croisières dès 319€" 
  au lieu de "1 000 croisières dès 79€" (valeurs vérifiées 
  dans le schema JSON-LD AggregateOffer)
- Divergence entre les valeurs du HTML visible et celles du 
  schema JSON-LD (les données backend sont correctes, c'est le 
  template HTML qui est cassé)

Un ticket dev est en attente, fix annoncé d'ici 2-3 semaines 
(à partir du 23/04/2026).

## Règle en vigueur : hardcoder les valeurs

Jusqu'au fix confirmé, le skill doit :
1. **Ne jamais injecter `${noResultats}`, `${bestPrix}` ou 
   autre variable non fiable** dans le contenu généré
2. **Utiliser les valeurs issues du schema JSON-LD** de la page 
   (parsing `AggregateOffer.offerCount` pour le volume et 
   `AggregateOffer.lowPrice` pour le prix plancher) en priorité
3. **Fallback sur les valeurs du brief catalogue** si le schema 
   n'est pas accessible

## Inventaire des variables

| Variable | Contenu théorique | Statut | Usage skill |
|---|---|---|---|
| `${destination}` | Nom de la destination | OK | Utilisable |
| `${annee}` | Année en cours | OK | Utilisable (vérifier que la valeur retournée = année courante) |
| `${mois}` | Mois en cours | OK | Utilisable |
| `${noResultats}` | Nombre d'offres catalogue | NON FIABLE | **Hardcoder** depuis schema |
| `${bestPrix}` | Prix le plus bas catalogue | NON FIABLE | **Hardcoder** depuis schema |
| `${topPrix}` | Prix plafond | Non confirmé | Ne pas utiliser |
| `${anneeSuivante}` | Année + 1 | Non confirmé | Ne pas utiliser, calculer à partir de `${annee}` |
| `${nbCompagnies}` | Nb de compagnies | Non confirmé | Ne pas utiliser |
| `${topPortsDepart}` | Top ports de départ | Non confirmé | Ne pas utiliser |

## Flag skill : --mode-variables

Le skill accepte un flag `--mode-variables` avec deux valeurs :

- `hardcoded` (défaut actuel) : les valeurs chiffrées sont 
  insérées en dur dans le HTML généré (ex: "1 000 croisières", 
  "dès 79€")
- `dynamic` (à activer post fix) : les variables CMS sont 
  insérées directement (`${noResultats}`, `${bestPrix}`, etc.)

Tant que le statut est "NON FIABLES", **ne jamais lancer le 
skill en mode dynamic en production**.

## Source des valeurs hardcodées

Ordre de priorité :

1. **Schema JSON-LD de la page cible** (plus fiable, toujours 
   à jour)
   - `AggregateOffer.offerCount` → volume
   - `AggregateOffer.lowPrice` → prix plancher
2. **Brief catalogue** fourni en input du skill (si schema 
   indisponible ou incomplet)
3. **Valeurs par défaut** → AUCUNE. Si aucune source n'est 
   disponible, le skill stop et demande un override manuel 
   à l'utilisateur.

## Tracker des SL à migrer post-fix

Quand le fix dev des variables CMS sera déployé, repasser sur 
chaque SL de cette liste pour re-générer le contenu en mode 
dynamic.

| SL | Date push hardcoded | Valeurs hardcodées | Schema lowPrice réel |
|---|---|---|---|
| SL Méditerranée | 23/03/2026 + correctif 24/04/2026 | 1 000 croisières, 79€ | 79€ |
| SL MSC | 23/03/2026 | 1 000 croisières, 79€ | 79€ |
| SL Caraïbes | 02/04/2026 | [à vérifier] | [à vérifier] |
| SL Europe du Nord | 02/04/2026 | [à vérifier] | [à vérifier] |
| SL Costa | [à traiter] | 650 croisières, 169€ | 169€ |
| SL Îles Grecques | Non modifiée | Non concerné | [à vérifier] |

**À mettre à jour au fil des SL traitées par le skill.**

## Workflow post-fix

Le jour où le fix CMS est déployé :
1. Vérifier sur 2-3 SL de test que `${noResultats}` et 
   `${bestPrix}` retournent les bonnes valeurs
2. Mettre à jour ce fichier (statut → OK - Utilisable)
3. Re-lancer le skill en mode dynamic sur toutes les SL du 
   tracker ci-dessus
4. Push en prod les nouvelles versions
5. Mettre à jour le défaut du flag `--mode-variables` à `dynamic`