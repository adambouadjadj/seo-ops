# authors.md - Signatures auteur par type de SL

## Principe
Chaque SL reçoit en fin de destination content une signature 
"[Prénom] – [Expertise]" comme signal EEAT. Mapping ci-dessous.

## Personas

### Élodie – Spécialiste Méditerranée
Méditerranée, Îles Grecques, Baléares, Croatie/Adriatique, 
Italie, Espagne, Turquie, Canaries/Madère, Sicile, Corse

### Marc – Expert Caraïbes & Amériques
Caraïbes/Antilles, Bahamas, Cuba, République Dominicaine, 
Miami, Amérique du Sud, Polynésie, Tour du Monde

### Claire – Spécialiste Europe du Nord & Fjords
Europe du Nord, Fjords Norvégiens, Baltique, Islande, 
Spitzberg, Groenland, îles Britanniques

### Thomas – Expert Compagnies & Thématiques
Toutes SL compagnies (MSC, Costa, Royal Caribbean, Celebrity, 
Norwegian, Cunard, Croisieurope, Ponant, etc.) + SL 
thématiques (tout inclus, dernière minute, famille, luxe, 
fluviale)

## Fallback
"L'équipe ABCroisière" si aucun matching. À éviter.

## Règle de stabilité
Une fois assigné à une SL, le persona ne change pas.

Le titre d'un persona ne varie JAMAIS selon la SL traitée. 
Élodie reste "Spécialiste Méditerranée" même sur une SL 
Îles Grecques ou Baléares. La règle : un seul titre par 
persona, qui couvre tout son domaine d'expertise.

## Format HTML
<p style="margin: 5px 0 0 10px; float: left;">
  <span style="background-image: url('https://www.abcroisiere.com/static/v4/images/pages/lp-navire/sprite.png'); background-position: -28px 0px; background-repeat:no-repeat; width: 25px; float:left; height: 25px;"></span>
  <span style="margin-left: 10px;">[Prénom] – [Expertise]</span>
</p>

⚠️ URL absolue obligatoire — l'URL relative `/static/...` ne fonctionne pas dans le CMS.