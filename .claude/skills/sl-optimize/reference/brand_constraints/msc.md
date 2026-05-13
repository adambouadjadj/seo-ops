# Contraintes marque MSC Croisières

## Source
Demande directe de MSC Croisières transmise à ABCroisière. 
Document exact à retrouver et archiver quand disponible.

## Principe
MSC impose des restrictions sur la façon dont sa marque peut 
être associée à certains termes commerciaux et marketing. Ces 
contraintes sont strictes et doivent être appliquées **partout** 
dans le contenu : title, meta description, H1, H2, H3, corps 
de texte, ancres de liens, attributs title, breadcrumbs, 
microdata, et tout élément visible par un utilisateur ou par 
Google.

## Termes INTERDITS en association avec MSC

Ne jamais associer la marque MSC avec :
- promo
- promotion
- pas cher / pas chère
- low cost
- bon plan
- discount
- petit prix
- budget
- tarifs réduits
- bradé / bradées
- dégriffé / dégriffées

## Formulations à éviter

- "Croisière MSC pas chère" → INTERDIT
- "MSC en promo" → INTERDIT
- "MSC à petit prix" → INTERDIT
- "Tarifs réduits MSC" → INTERDIT
- "MSC accessible" → à éviter (connotation bas de gamme)
- "MSC discount" → INTERDIT

## Formulations AUTORISÉES

Le skill peut et doit utiliser des formulations factuelles 
basées sur les données du catalogue :

- "à partir de 79€" / "dès 79€" / "cabine standard dès 79€"
- "Offres dernière minute" (factuel, pas connoté discount)
- "Formules tout inclus" (factuel)
- "Enfants de moins de 12 ans gratuits en pension complète" 
  (factuel)
- "Croisière MSC en formule tout compris"
- "Départs MSC dès 79€"
- "Disponibilités MSC en Méditerranée"

## Vocabulaire alternatif recommandé

Quand une formulation contient un terme interdit, remplacer par :

| À la place de | Utiliser |
|---|---|
| "accessible" | "adaptée" (pour les familles, couples, etc.) |
| "tarifs réduits" | "disponibilités" ou "offres" |
| "promo" | formulation factuelle avec prix réel ("dès 79€") |
| "pas cher" | "à partir de [prix]€" |
| "bon plan" | "offre" |
| "petit prix" | prix factuel du catalogue |

## Check automatique dans le skill

Le skill exécute une vérification automatique avant output :

1. Scanner tout le contenu généré (title, meta, H1, tout le HTML)
2. Pour chaque mention de "MSC" ou "msc" (case insensitive), 
   vérifier qu'aucun terme interdit n'apparaît dans une fenêtre 
   de 15 mots autour
3. Si violation détectée → **ERREUR bloquante**, stop de la 
   génération, rapport d'erreur avec la phrase exacte contenant 
   la violation

## Violations détectées dans la prod actuelle (à corriger)

**Breadcrumb schema SL MSC** :
```json
{
  "@type": "ListItem",
  "position": 2,
  "item": {
    "@id": "https://msc.abcroisiere.com/",
    "name": "Croisières MSC Croisières pas chères"  ← VIOLATION
  }
}
```
Ticket dev ouvert pour fixer ce breadcrumb. Le skill doit 
détecter ce type d'anomalie dans ses diagnostics.

## Autres compagnies avec contraintes

Pour l'instant, seul MSC a communiqué des contraintes formelles. 
D'autres armateurs pourraient suivre. Quand une nouvelle 
contrainte est signalée, créer un fichier 
`brand_constraints/[compagnie].md` sur le même modèle.