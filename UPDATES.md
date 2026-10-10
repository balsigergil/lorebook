# Updates

Liste des modifications à apporter.

- Les commentaires sont uniquement pour la rédaction des articles. Ils ne doivent jamais apparaître dans les articles rendus, même interne.
- Editeur: implémente une recherche d'articles globale (toutes les collections accessibles par l'utilisateur connecté). Recherche juste par le nom de l'article.
- Editeur: ajoute la possibilité de supprimer un commentaire qu'on a écrit. Seul l'auteur du commentaire peut le supprimer. L'administrateur peut aussi le supprimer.
- Ajoute la possibilité de supprimer une langue, pas juste de la désactiver. Garde la désactivation, mais ajoute la possibilité de supprimer. Lors de la suppression, les articles de cette langue sont supprimés également.
- La langue courante doit être globale et définie par l'utilisateur. Ainsi, l'éditeur affiche les articles de la langue courante par défaut. La langue courante est modifiable dans la sidebar. On ne permet pas de choisir la langue par article, c'est la langue courante globale de l'utilisateur qui dit dans quelle langue l'article est édité.
- Editeur: Garde la possibilité de voir les langues depuis la liste des articles dans une collection. Cliquer sur la langue change la langue courante globale de l'utilisateur et affiche l'éditeur de l'article dans cette langue (comportement actuel).
- Editeur: Ajoute la possibilité de créer un article depuis un autre dans le tableau, c'est plus pratique que de devoir toujours cliquer sur le bouton "Nouvel article" puis choisir l'article parent. Garde cependant le bouton "Nouvel article". Ajoute juste un petit "+" à droite de chaque article dans le tableau et ça ouvre la même modale avec juste l'article parent déjà sélectionné.
- Remplace tous les em dashes dans la base de code selon la règle indiquée dans CLAUDE.md

Modification de l'interface utilisateur :

- Tableau de bord: le bouton "Nouvelle collection" a la police noir, elle devrait être en blanche.
- Sidebar: déplace Glossaire dans la section administration
- Collection: le badge "Publique" / "Interne" n'est pas correctement centré verticalement
- Historique dans l'éditeur: le header manque un padding bottom, la bordure basse est collée au texte.
- Editeur d'un article: le menu déroulant avec les options de réglages de l'article, export, etc. -> le texte est parfois centré horizontalement, parfois positionné à gauche. ça doit être toujours positionné à gauche.
- Glossaire: bouton "modifier" en taille sm, pas xs
- Glossaire, modifier un terme: mets le bouton "Supprimer ce terme" dans la carte, positionne le bouton à gauche avec le style outline, pas ghost.