# Arbre de décision FAQ

## Principe
La FAQ est ajoutée **par défaut** sur les SL compagnie et les
SL destination en Pattern A ou B. Les signaux DataForSEO servent
à choisir les questions, pas à décider si la FAQ existe.

**Règle de défaut par type de SL :**

| Type | Pattern | Décision par défaut |
|---|---|---|
| Compagnie (MSC, Costa, Cunard…) | A/B/C | **FAQ oui** |
| Destination principale (Méditerranée, Îles Grecques…) | A ou B | **FAQ oui** |
| Destination secondaire / thématique | C | FAQ optionnelle |

**Pourquoi les SL compagnie retournent souvent 0 PAA DataForSEO :**
Google affiche peu de PAA sur les requêtes navigationnelles/marque.
Ce n'est pas un signal d'absence d'utilité FAQ — c'est la nature
de ces requêtes. Ne jamais conditionner la décision FAQ sur le
seul retour PAA DataForSEO pour une SL compagnie.

**Override possible :** `--no-faq` pour forcer l'absence de FAQ.

## Quand ajouter une FAQ

Pour les cas optionnels (Pattern C destination), ajouter une FAQ 
si **au moins UN** des signaux suivants est détecté :

### Signal 1 : PAA présents (signal le plus fort)
- 3+ "People Also Ask" visibles sur la requête principale
- Les questions PAA seront réutilisées quasi-textuellement 
  dans la FAQ générée

**Note importante** : les PAA sont générés par Google, parfois 
via "question expansion" (questions inventées, pas réellement 
posées). Dans le doute, croiser avec le signal 2 ou 3 pour 
confirmer.

### Signal 2 : Featured snippet question/réponse
- Google affiche un featured snippet de type question/réponse 
  sur la requête
- Signal fort que Google valorise le format FAQ sur ce sujet

### Signal 3 : Guides/informationnels dans le top 10
- Au moins 2 URLs de type guide/blog/magazine dans le top 10 
  (TripAdvisor, routard, Lonely Planet, magazines voyage)
- Signal que Google juge l'intent partiellement informationnel
- Une FAQ permet de capter cette dimension sans casser le 
  focus transactionnel

### Signal 4 : Pattern interrogatif dans le keyword
- Le keyword principal contient un mot interrogatif : 
  "comment", "quand", "quelle", "quels", "où", "pourquoi", 
  "combien"
- Exemples : "quand partir en croisière Méditerranée", 
  "comment choisir sa croisière"
- Signal explicite d'un intent informationnel

## Quand ne PAS ajouter de FAQ

Ne pas ajouter si **TOUS** les signaux ci-dessus sont absents :
- 0-2 PAA seulement (ou PAA non pertinents)
- Pas de featured snippet question/réponse
- Moins de 2 guides dans le top 10
- Keyword purement transactionnel ("croisière dernière minute", 
  "croisière MSC août", "croisière pas cher")

## Format obligatoire

**Toujours en microdata HTML** avec schema.org/FAQPage 
(itemscope + itemtype + itemprop). Jamais en simple liste à 
puces même si les questions/réponses sont présentes.

**Note structurelle importante** : Les questions FAQ 
s'intègrent dans la structure H3 existante du destination 
content, pas dans un bloc FAQ séparé avec un titre "FAQ". 
Chaque question devient un H3 en fin de destination content, 
wrappé dans le microdata FAQPage. Pas de H3 "FAQ – Vos 
questions fréquentes" en chapeau.

Structure HTML à générer :

<div itemscope itemtype="https://schema.org/FAQPage">
  <div itemscope itemprop="mainEntity" itemtype="https://schema.org/Question">
    <h3 itemprop="name">Quelle est la meilleure période pour une croisière en Méditerranée ?</h3>
    <div itemscope itemprop="acceptedAnswer" itemtype="https://schema.org/Answer">
      <div itemprop="text">
        <p>Mai, juin et septembre offrent le meilleur compromis entre météo agréable et fréquentation modérée.</p>
      </div>
    </div>
  </div>
  
  <!-- Répéter le bloc Question pour chaque question -->
  
</div>

## Contenu de la FAQ

### Nombre de questions
- **4 à 6 questions maximum**
- Moins de 4 = pas la peine
- Plus de 6 = dilution, Google peut ignorer certaines

### Mix des questions
- **2 à 3 questions issues des PAA** de la SERP (reprises 
  quasi-textuellement, légère reformulation si nécessaire)
- **2 à 3 questions issues du brief Textguru** ou des intents 
  transactionnels principaux (prix, départ, saison, compagnies, 
  formules)

### Longueur des réponses
- **40 à 80 mots par réponse**
- Factuelles, basées sur les données du brief catalogue ou du 
  schema JSON-LD
- Pas de superlatifs marketing
- Contraintes marque respectées (voir brand_constraints/)
- Inclure des chiffres concrets quand pertinent (prix, durées, 
  nombre de navires, etc.)

## Placement dans le destination content

La FAQ est placée **en fin de destination content**, juste 
avant la signature auteur.

## Check automatique dans le skill

1. Analyser la SERP DataForSEO et compter les signaux
2. Si ≥ 1 signal → décision "FAQ à ajouter"
3. Générer le bloc FAQ en microdata
4. Valider la structure HTML (tous les itemprop présents, 
   schema.org/FAQPage correctement balisé)
5. Logger la décision dans metadata.json avec les signaux 
   qui ont déclenché (pour traçabilité)

## Exemples de décisions

| SL | Volume | PAA | Guides top 10 | Pattern interrogatif | Décision |
|---|---|---|---|---|---|
| Croisière Méditerranée | 40 500 | 5+ | 3 | Non | FAQ |
| Quand partir en Méditerranée | 1 900 | 4 | 4 | Oui | FAQ |
| Croisière MSC dernière minute | 880 | 1 | 0 | Non | Pas de FAQ |
| Croisière Cunard | 390 | 0 | 0 | Non | Pas de FAQ |
| Croisière îles grecques | 2 400 | 3+ | 2+ | Non | FAQ |