# Brief Catalogue - Format d'entrée utilisateur

## Objectif

Quand l'utilisateur lance `/sl-optimize` et que le skill détecte 
que les données du schema JSON-LD de la SL sont suspectes (check 5 
bis dans `sl_diagnostics.md`), ou que l'utilisateur veut override 
les valeurs auto-extraites, il fournit un brief catalogue manuel au 
format Markdown.

Le skill parse ce fichier et l'utilise comme source de vérité pour 
les valeurs catalogue (nombre de croisières, prix plancher/plafond, 
etc.).

Les briefs catalogue **ne sont jamais obligatoires**. Par défaut, le 
skill extrait les valeurs du JSON-LD `AggregateOffer` de la SL 
existante. Le brief manuel n'intervient que dans 2 cas :

1. **Schema suspect détecté** : le skill demande un brief à 
   l'utilisateur avant de continuer
2. **Override volontaire** : l'utilisateur fournit `--brief 
   path/to/brief.md` au lancement pour forcer ses propres valeurs

---

## Quand fournir un brief

### Cas 1 : Schema suspect (auto-détecté)

Le skill détecte un schema suspect via `sl_diagnostics.py` check 5 
bis si :
- `offerCount` est une valeur ronde type "1000" ou "500" 
- `lowPrice` est identique sur plusieurs SL différentes
- Écart suspect entre le prix du schema et le prix affiché en 
  meta description

Si suspect → le skill arrête le run et affiche :
[WARNING] Schema AggregateOffer suspect sur cette SL :

offerCount: 1 000 (valeur ronde, probablement générique)
lowPrice: 79 (identique à 8 autres SL testées)

Le skill ne peut pas continuer sans valeurs fiables.
Fournis un brief catalogue au format Markdown :
/sl-optimize --url ... --brief brief_catalogue.md
Template disponible dans :
reference/brief_catalogue_format.md (sections "Template destination"
et "Template compagnie")

### Cas 2 : Override volontaire

L'utilisateur sait que le schema est bon mais veut quand même 
fournir des valeurs custom (ex : inclure de nouveaux ports de départ 
pas encore dans le catalogue, forcer un prix promotionnel, etc.).

```bash
/sl-optimize --url ... --brief brief_custom.md
```

Le brief override toujours les valeurs auto-extraites, sans 
warning.

---

## Format du brief

Le fichier est un Markdown avec des sections nommées via `## Nom de 
section`. L'ordre des sections n'a pas d'importance. Les sections 
manquantes sont considérées comme "utiliser la valeur auto-extraite" 
ou "à compléter au review".

### Règles de parsing

- Une section = un bloc `## Nom` suivi de son contenu jusqu'au 
  prochain `##` ou fin de fichier
- Les lignes commençant par `#` dans le contenu sont ignorées 
  (commentaires markdown)
- Les lignes vides sont ignorées
- Les valeurs peuvent être sur plusieurs lignes (liste à puces ou 
  liste séparée par virgules)
- Les commentaires inline en fin de ligne après `//` ou `#` sont 
  ignorés

### Sections communes (destination ET compagnie)

| Section | Type | Contenu attendu |
|---|---|---|
| `## Prix plancher` | Nombre | Prix le plus bas réel du catalogue, en euros, entier |
| `## Prix plafond` | Nombre | Prix le plus haut du catalogue, en euros, entier |
| `## Nombre de croisières` | Nombre | Entier, sans séparateur de milliers |
| `## Ports de départ FR` | Liste | Ports français, séparés par virgules ou liste à puces |
| `## Ports de départ internationaux` | Liste | Ports internationaux clés |
| `## Saison principale` | Texte | Mois ou période (ex : "avril à octobre") |

### Sections spécifiques SL Destination

| Section | Type | Contenu attendu |
|---|---|---|
| `## Compagnies top content` | Liste | Max 3, les plus volumiques. Pour le paragraphe intro. |
| `## Compagnies complètes` | Liste | Toutes les compagnies présentes dans le catalogue |
| `## Escales incontournables` | Liste | Escales à couvrir dans le destination content |
| `## Durées disponibles` | Liste | Ex : "7 jours, 10 jours, 14 jours" |

### Sections spécifiques SL Compagnie

| Section | Type | Contenu attendu |
|---|---|---|
| `## Nombre de navires` | Nombre | Entier |
| `## Navires phares` | Liste | Max 3, pour top content (les plus récents ou emblématiques) |
| `## Liste complète des navires` | Liste | Toute la flotte présente au catalogue |
| `## Destinations couvertes` | Liste | Bassins principaux (Méditerranée, Caraïbes, etc.) |
| `## Conditions enfants` | Texte | Ex : "Gratuits -12 ans en pension complète" |
| `## Formules disponibles` | Liste | Ex : "Standard, tout inclus, yacht club" |
| `## Départs` | Texte | "Toute l'année" ou "Saisonnier : avril à octobre" |

---

## Template SL Destination

Copier-coller ce template et remplir les valeurs. Laisser une section 
vide ou l'omettre = utiliser la valeur auto-extraite.

```markdown
# Brief catalogue - [Nom de la destination]

## Prix plancher
269

## Prix plafond
4890

## Nombre de croisières
311

## Compagnies top content
MSC, Costa, Royal Caribbean

## Compagnies complètes
MSC, Costa, Royal Caribbean, Celebrity, NCL, Marella, Cunard, 
Princess Cruises, Holland America, Seabourn

## Ports de départ FR
Marseille, Nice, Toulon

## Ports de départ internationaux
Barcelone, Civitavecchia, Gênes, Athènes, Venise, Dubrovnik

## Saison principale
avril à octobre

## Escales incontournables
Mykonos, Santorin, Rhodes, Héraklion, Corfou, Katakolon

## Durées disponibles
3 jours, 7 jours, 10 jours, 14 jours
```

---

## Template SL Compagnie

```markdown
# Brief catalogue - [Nom de la compagnie]

## Prix plancher
169

## Prix plafond
2350

## Nombre de croisières
648

## Nombre de navires
12

## Navires phares
Costa Toscana, Costa Smeralda, Costa Diadema

## Liste complète des navires
Costa Toscana, Costa Smeralda, Costa Diadema, Costa Favolosa, 
Costa Deliziosa, Costa Firenze, Costa Fortuna, Costa Pacifica, 
Costa Fascinosa, Costa Serena, Costa Luminosa, Costa Venezia

## Destinations couvertes
Méditerranée, Europe du Nord, Caraïbes, Émirats, Asie, 
Amérique du Sud

## Ports de départ FR
Marseille, Nice, Le Havre

## Ports de départ internationaux
Barcelone, Gênes, Civitavecchia, Savone, Hambourg, Dubaï, Miami

## Saison principale
toute l'année

## Conditions enfants
Gratuits -18 ans en cabine avec 2 adultes (hors taxes portuaires)

## Formules disponibles
Standard, All Inclusive, My Cruise, Tout Compris

## Départs
toute l'année depuis Marseille et Barcelone, saisonniers ailleurs
```

---

## Exemple d'utilisation avec CLI

### Cas 1 : run normal (pas de brief)

```bash
/sl-optimize --url https://www.abcroisiere.com/fr/croisieres/croisiere-iles-grecques/destination,53,50/
```

Le skill :
1. Fetch la SL
2. Parse le JSON-LD `AggregateOffer`
3. Exécute `sl_diagnostics.py`
4. Si check 5 bis déclenche → arrêt avec message d'erreur (voir 
   Cas 1 plus haut)
5. Sinon → continue le workflow normal

### Cas 2 : run avec brief

```bash
/sl-optimize --url https://www.abcroisiere.com/fr/croisieres/croisiere-iles-grecques/destination,53,50/ --brief briefs/iles_grecques.md
```

Le skill :
1. Lit le fichier `briefs/iles_grecques.md`
2. Parse les sections Markdown
3. Valide : les sections obligatoires sont présentes ? (voir 
   "Sections obligatoires" ci-dessous)
4. Fetch la SL + parse JSON-LD (pour les champs non fournis dans le 
   brief)
5. Merge : valeurs du brief > valeurs auto-extraites
6. Continue le workflow

---

## Sections obligatoires vs optionnelles

### Obligatoires (si brief fourni)

- `## Prix plancher`
- `## Nombre de croisières`

Si l'une de ces sections manque, le skill arrête avec un message 
d'erreur demandant de compléter.

### Optionnelles mais recommandées

Toutes les autres. Si non fournies, le skill :
- Essaie d'auto-extraire depuis le JSON-LD ou le contenu actuel
- Si impossible → place `[À VÉRIFIER]` dans le contenu généré

### Gestion du `[À VÉRIFIER]`

Si une donnée manque après merge brief + auto-extraction :
- Le skill ne génère pas de fausse donnée
- Il place un marqueur `[À VÉRIFIER - nom_du_champ]` dans le 
  contenu produit
- Un warning est ajouté dans le rapport final listant tous les 
  `[À VÉRIFIER]`
- L'utilisateur doit compléter manuellement avant push CMS

Exemple dans le contenu généré :

```html
<p>Plus de 311 croisières Îles Grecques disponibles avec MSC, 
Costa et Royal Caribbean. Départs depuis Marseille, [À VÉRIFIER - 
ports_depart_fr], et Barcelone...</p>
```

---

## Organisation des briefs dans le repo

Recommandation : stocker les briefs dans le skill sous :
.claude/skills/sl-optimize/
├── briefs/
│   ├── iles_grecques.md
│   ├── mediterranee.md
│   ├── costa.md
│   ├── msc.md
│   └── ...

Nommer les fichiers en snake_case du nom de la destination ou 
compagnie, sans accents.

Ces briefs sont **réutilisables** : tant que le catalogue ABCroisière 
ne bouge pas drastiquement, un brief peut servir plusieurs runs sur 
la même SL (après monitoring J+14 par exemple, pour une V2 du 
contenu).

À actualiser quand :
- Le catalogue change significativement (ajout/retrait de navires, 
  nouvelle destination couverte)
- Les prix bougent de plus de 10%
- Un nouveau port de départ est ajouté
- Une compagnie est ajoutée ou retirée

---

## Parsing Python (pseudocode)

```python
import re
from pathlib import Path

def parse_brief(brief_path: Path) -> dict:
    content = brief_path.read_text(encoding="utf-8")
    
    # Split sur les headers ##
    sections = {}
    current_section = None
    current_content = []
    
    for line in content.split("\n"):
        # Nouveau header ##
        if line.startswith("## "):
            if current_section:
                sections[current_section] = "\n".join(current_content).strip()
            current_section = line[3:].strip()
            current_content = []
        elif line.startswith("#"):
            # Header # (titre du doc) ou commentaire, on ignore
            continue
        else:
            current_content.append(line)
    
    # Dernière section
    if current_section:
        sections[current_section] = "\n".join(current_content).strip()
    
    # Validation obligatoires
    if "Prix plancher" not in sections or "Nombre de croisières" not in sections:
        raise ValueError(
            "Brief incomplet : 'Prix plancher' et "
            "'Nombre de croisières' sont obligatoires"
        )
    
    # Parsing des valeurs selon le type attendu
    parsed = {}
    for key, value in sections.items():
        parsed[normalize_key(key)] = parse_value(key, value)
    
    return parsed


def normalize_key(key: str) -> str:
    """'Prix plancher' → 'prix_plancher'"""
    return key.lower().replace(" ", "_").replace("é", "e").replace("è", "e")


def parse_value(key: str, value: str):
    """Parse la valeur selon le type attendu pour cette clé"""
    numeric_keys = ["Prix plancher", "Prix plafond", 
                    "Nombre de croisières", "Nombre de navires"]
    list_keys = ["Compagnies top content", "Compagnies complètes",
                 "Ports de départ FR", "Ports de départ internationaux",
                 "Escales incontournables", "Navires phares",
                 "Liste complète des navires", "Destinations couvertes",
                 "Formules disponibles", "Durées disponibles"]
    
    if key in numeric_keys:
        # Extraire le premier nombre trouvé
        match = re.search(r"\d+", value.replace(" ", "").replace(",", ""))
        return int(match.group()) if match else None
    
    elif key in list_keys:
        # Liste : soit virgules, soit puces
        if "\n-" in value or "\n*" in value:
            # Liste à puces
            return [line.lstrip("-* ").strip() 
                    for line in value.split("\n") 
                    if line.strip().startswith(("-", "*"))]
        else:
            # Séparé par virgules
            return [item.strip() for item in value.split(",") if item.strip()]
    
    else:
        # Texte libre
        return value.strip()
```

---

## Exemple complet d'exécution

### Brief fichier (`briefs/iles_grecques.md`)

```markdown
# Brief catalogue - Îles Grecques

## Prix plancher
269

## Nombre de croisières
311

## Compagnies top content
MSC, Costa, Celestyal Cruises

## Ports de départ FR
Marseille

## Saison principale
avril à octobre
```

### Run

```bash
/sl-optimize \
  --url https://www.abcroisiere.com/fr/croisieres/croisiere-iles-grecques/destination,53,50/ \
  --type destination \
  --brief briefs/iles_grecques.md
```

### Merge dans le skill

1. Fetch la SL → JSON-LD dit 1000 croisières, 79€
2. Check 5 bis → suspect détecté
3. Merge avec brief : prix 269€, 311 croisières, compagnies [MSC, 
   Costa, Celestyal], port FR [Marseille]
4. Valeurs non fournies dans le brief → auto-extraites du contenu 
   actuel ou marquées `[À VÉRIFIER]` :
   - Prix plafond : auto-extrait depuis contenu actuel ou 
     `[À VÉRIFIER - prix_plafond]`
   - Compagnies complètes : `[À VÉRIFIER - compagnies_completes]`
   - Escales : auto-extrait si listées dans le contenu actuel
5. Continue le workflow avec ces valeurs