# Skill : psi-dev-audit

**Description** : Audit PSI détaillé pour produire un ticket dev actionnable sur ABCroisières — diagnostic FCP/LCP/TBT/CLS, scripts tiers par entité (GTM, ContentSquare, Didomi, AppDynamics, TrustPilot, Non attribuable), éléments LCP, ressources bloquantes FCP, répartition thread principal.

**Différence avec le skill `webperf`** : `webperf` = reporting mensuel stakeholders (Sheets + Slides). Ce skill = diagnostic technique ponctuel orienté dev, avec détail par entité et ticket actionnable.

## Trigger

Utiliser ce skill quand l'utilisateur demande :
- Un audit perf orienté dev / technique
- Un ticket web perf détaillé pour les devs
- Une analyse PSI avec détail par entité (GTM, scripts tiers)
- Diagnostic FCP/LCP/TBT avec assets identifiés

Ne pas utiliser pour le reporting mensuel habituel → utiliser le skill `webperf`.

## Workflow

1. **Vérifier PSI_API_KEY** dans `tools/.env` — bloquer si absente
2. **Lancer l'audit** :
   ```
   python .claude/skills/psi-dev-audit/scripts/audit.py .claude/skills/psi-dev-audit/configs/abcroisieres.yaml
   ```
   → Crée 12 JSON bruts dans `runs/YYYY-MM-DD/` (6 pages × mobile + desktop)

3. **Générer le rapport** :
   ```
   python .claude/skills/psi-dev-audit/scripts/report.py .claude/skills/psi-dev-audit/runs/YYYY-MM-DD/
   ```
   → Crée dans `outputs/YYYY-MM-DD/` :
   - `ticket.md` — synthèse tableau + diagnostic détaillé par template×device
   - `outputs/audits.csv` — cumulatif (1 ligne par page×device)
   - `outputs/third_party_scripts.csv` — cumulatif (1 ligne par page×device×entité)

4. **Présenter le ticket.md** à l'utilisateur

## Paramètres modifiables

- Config YAML : `configs/abcroisieres.yaml` (remplacer par `configs/promocroisiere.yaml` pour PMC le moment venu)

## AVERTISSEMENT BUG HISTORIQUE

**Ne JAMAIS utiliser l'audit `unused-javascript`** pour diagnostiquer les scripts tiers.
- `unused-javascript` → retourne des **KB de JS inutilisé** par URL (inutile pour le diagnostic TBT)
- Résultat incorrect : GTM à "62KB" au lieu de "1683ms", Didomi/TrustPilot absents, "Non attribuable" absent

**Toujours utiliser :**
- `third-party-summary` → temps CPU par entité (GTM, ContentSquare, Didomi, etc.)
- `bootup-time` → détail CPU par URL individuelle (complément)

## Audits parsés

| Audit | Champ lighthouse | Usage |
|-------|-----------------|-------|
| Score perf | `categories.performance.score` | Synthèse |
| FCP, LCP, TBT, CLS, SI | `audits[metric].numericValue + score` | Synthèse + couleurs |
| Scripts tiers | `third-party-summary.details.items[]` | TBT par entité |
| CPU par URL | `bootup-time.details.items[]` | Détail scripts |
| Thread principal | `mainthread-work-breakdown.details.items[]` | Répartition CPU |
| Élément LCP | `largest-contentful-paint-element.details.items[]` | Sélecteur + HTML |
| Ressources bloquantes | `render-blocking-resources.details.items[]` | FCP |

Aucun filtre, aucun seuil, aucun top N — tout est extrait, le tri se fait dans le ticket.
