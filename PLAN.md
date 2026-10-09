# Lorebook — Document de conception

Oct 9, 2026 · @Gil Balsiger

## Vision

Lorebook est une plateforme de documentation open source et auto-hébergeable, alternative à GitBook, construite en Django. Une même instance sert la base de connaissances interne et la documentation publique.

- **Édition WYSIWYG** : pas de générateur statique Markdown → HTML.
- **Auto-hébergement** : chacun déploie sur ses serveurs et branche ses propres services, dont le modèle d'IA de son choix.
- **Design** moderne et réactif, inspiré du design system actuel de GitBook.
- **Produit autonome** livré en image Docker, pas une app Django réutilisable.
- **Licence AGPL-3.0** : une version modifiée proposée en SaaS doit publier son code.
- **Nom** : Lorebook.

## Interfaces et exposition

Trois interfaces tournent dans une seule instance Django. Elles sont servies par défaut sous un même domaine avec des préfixes de chemin, et l'admin peut assigner un nom d'hôte à chacune.

| Interface | Chemin par défaut | Domaine optionnel (exemple) | Accès |
| --- | --- | --- | --- |
| Portail public | `/` | `docs.exemple.ch` | Anonyme, collections publiques uniquement |
| Portail interne | `/internal` | `kb.exemple.ch` | Connexion + droits de lecture ; donne aussi accès facilement à la doc publique |
| Interface d'édition | `/edit` | `edit.exemple.ch` | Utilisateurs ayant le rôle éditeur ou admin |

Le routage selon le domaine se fait dans un middleware Django, qui choisit l'urlconf du portail.

## Architecture technique

Lorebook est un monolithe Django en ASGI. Toutes les pages sont rendues côté serveur par Django, interface d'édition et administration comprises. Seul l'éditeur de texte Tiptap est un îlot React, et PostgreSQL porte toutes les données : contenu, recherche, vecteurs et file de tâches.

| Domaine | Choix | Raison principale |
| --- | --- | --- |
| Portails, interface d'édition et administration | Templates Django + HTMX + Bloum | SEO, rapidité, simplicité |
| Éditeur de texte uniquement | Composant Tiptap en React, buildé avec Vite et monté dans une page SSR | Écosystème Tiptap le plus riche |
| API interne | Django Ninja (Pydantic, OpenAPI) | Typage, client TypeScript généré pour l'éditeur, base pour la future API publique |
| Base de données | PostgreSQL | Un seul service pour les données, le full-text et la file de tâches |
| Tâches de fond | API Tasks de Django + backend Postgres | Pas de Redis ; le backend reste remplaçable |
| Médias | Disque local par défaut, S3 compatible en option (django-storages) | docker-compose autonome ; contrôle des droits sur les fichiers internes |
| UI | Bloum | Librairie CSS-first pour apps rendues côté serveur, conçue pour HTMX ; theming par les variables --bl-\*, mode sombre natif |
| Runtime | ASGI (Uvicorn ou Granian), une image Docker | Prêt pour le streaming SSE du futur assistant |
| Outillage | uv, ruff, pytest, GitHub Actions | Standards de l'écosystème |

**Point de départ.** Le projet est initialisé avec Vite et Bloum déjà configurés. Bloum s'utilise en classes CSS et en custom elements sans shadow DOM. Documentation pour les agents : [bloum.dev/llms.txt](https://www.bloum.dev/llms.txt), version complète dans [llms-full.txt](https://www.bloum.dev/llms-full.txt).

**Déploiement.** Le docker-compose contient trois services : `web` (ASGI), `worker` (même image, commande différente) et `postgres` (image standard).

**Organisation du code.** Toutes les apps Django sont regroupées dans un dossier apps/ à la racine du projet et découpées par domaine : `content`, `i18n`, `access`, `search`, `media`, `comments`, `analytics`. Une couche de services porte la logique métier et l'ORM est utilisé directement. Les ports et adapters sont réservés aux frontières externes : stockage des médias, recherche.

**Formulaires.** Toute saisie hors éditeur de texte passe par les formulaires Django, et chaque formulaire hérite de LoreForm ou de LoreModelForm. Responsabilités attendues de ces classes :

- Deux classes de base déjà créées, `LoreForm` et `LoreModelForm`, dans `apps/core/forms/base_forms.py`.
- Le rendu via les templates de formulaire et de champ de Django (`template_name`, `FORM_RENDERER`), écrits avec les composants Bloum (Form Field, Input, Textarea, Checkbox, Switch, Combobox…) : aucun HTML de formulaire écrit à la main dans les pages.
- La prise en charge d'HTMX : en cas d'erreur de validation, seul le fragment du formulaire est renvoyé et réinjecté, sans rechargement de page.
- Un affichage homogène des erreurs de champ et des erreurs globales, et des attributs de widgets uniformes.
- Tout nouveau formulaire du projet en hérite.

&#91;embedded content: Architecture · conteneurs web et worker, PostgreSQL, services externes\]

Les trois clients passent tous par le conteneur web Django. Le worker partage la même base PostgreSQL pour la file de tâches ; le fournisseur d'IA n'arrivera qu'après la v1.

## Modèle de contenu et cycle d'édition

Le contenu est stocké en JSON Tiptap/ProseMirror, et chaque version linguistique d'un article suit un cycle brouillon → publication.

**Organisation**

- Pas de catégories : les articles forment un arbre parent/enfant, et un article peut servir de catégorie (modèle Notion).
- Les articles appartiennent à des collections, et le caractère public ou privé se règle au niveau de la collection.

**Format**

- Source de vérité en JSON Tiptap : la structure reste fidèle à l'éditeur et les blocs sont adressables.
- Django rend le HTML avec un renderer Python maison, mis en cache. Le texte brut est dérivé pour la recherche et les embeddings.
- Markdown sert uniquement à l'import et à l'export. Il n'y a pas d'import GitBook, Notion ou Confluence en v1.
- Blocs simples uniquement en v1 : ni onglets ni accordéons.

**Cycle d'édition**

1. Chaque version linguistique d'un article a un brouillon, sauvegardé automatiquement.
2. « Publier » remplace la version publiée et crée une révision dans l'historique.
3. Les lecteurs ne voient jamais un état en cours d'écriture.
4. L'historique permet de consulter et de restaurer une révision.

Pas de workflow de relecture en v1.

## Multilingue et traductions

Il n'y a pas de langue source globale. Un article peut être écrit dans n'importe quelle langue activée puis traduit dans les autres, et publier une version marque les autres versions comme obsolètes.

**Langues**

- Les langues sont activées globalement dans l'administration, pour toutes les collections.
- Un besoin de documentations avec des langues différentes se règle en déployant plusieurs instances.
- Cas d'usage visé : français, allemand, italien et anglais.

**Statut des versions**

- Publier une version linguistique marque les autres comme **obsolètes**.
- Exception : l'auteur coche « Modification mineure » (coquille, mise en forme), et rien n'est marqué.
- Une version obsolète redevient à jour quand on la publie en la déclarant synchronisée.
- La traduction travaille sur l'article complet. Il n'y a pas de suivi bloc par bloc.

**Traduction**

- Manuelle en v1 : l'éditeur rédige la version dans la langue cible, puis la publie.
- Un glossaire global à l'instance (une colonne par langue activée, termes saisis manuellement) sert de référence aux traducteurs.
- La traduction assistée par IA est reportée après la v1.

**Affichage côté lecteur**

| Situation | Version affichée | Bandeau |
| --- | --- | --- |
| Version à jour dans la langue du lecteur | Celle-ci | Aucun |
| Version obsolète dans la langue du lecteur | Celle-ci | « Cette version n'est pas à jour », avec un lien vers la version la plus récente |
| Aucune version dans la langue du lecteur | La version la plus récemment modifiée | « Pas encore disponible en \[langue\] » |

## Droits et authentification

Les droits passent par des groupes qui reçoivent un rôle par collection. Un article peut en plus restreindre sa lecture, et cette restriction s'hérite dans le sous-arbre.

**Rôles par collection**

| Rôle | Peut |
| --- | --- |
| Lecteur | Lire les articles de la collection sur le portail interne, commenter |
| Éditeur | Ce que fait le lecteur, plus créer, modifier, publier, traduire et restaurer des révisions |
| Admin | Ce que fait l'éditeur, plus gérer les droits de la collection et sa visibilité publique ou privée |

**Restrictions de lecture**

- Un article peut limiter sa lecture à certains groupes, et ses enfants héritent de la restriction.
- Les droits d'édition se gèrent uniquement au niveau de la collection.
- Les collections publiques sont lisibles par tous sur le portail public.

**Connexion (v1)**

- Via django-allauth : comptes locaux (email et mot de passe, invitations) et OIDC générique (Google Workspace, Microsoft Entra, Keycloak…).
- SAML, SCIM et liens de partage temporaires sont reportés.

## Recherche

La recherche de la v1 est un full-text PostgreSQL, sans aucune IA.

- Une configuration full-text par langue (français, allemand, italien, anglais), avec pg\_trgm pour tolérer les fautes de frappe.
- L'index est mis à jour à chaque publication.
- Les résultats sont toujours filtrés par les droits de lecture de l'utilisateur.

**Après la v1 :** recherche sémantique (pgvector), assistant IA avec widget embarquable et traduction assistée. Ils passeront par des ports « LLM » et « Embeddings », avec un adapter compatible OpenAI en premier.

## Commentaires et statistiques

Les commentaires sont des fils de discussion au niveau de l'article, réservés aux utilisateurs internes. Les lectures sont comptées côté serveur, sans cookie.

**Commentaires**

- Fils de discussion avec réponses et statut « résolu », rattachés à une version linguistique de l'article.
- Tout utilisateur connecté qui peut lire l'article peut commenter, depuis le portail interne ou l'éditeur.
- Jamais affichés sur le portail public, même pour un article public.
- L'ancrage sur une sélection de texte est reporté.

**Statistiques de lecture**

- Compteur côté Django, sans cookie ni traceur tiers : aucun bandeau cookies, compatible nLPD/RGPD.
- Agrégation par article, langue, portail et jour.
- Dédoublonnage par un hash anonymisé et rotatif, et filtrage des bots.
- Alimente la liste des « articles les plus lus » en v1. Les statistiques avancées sont reportées.

## Périmètre v1 et versions futures

La v1 garde la vision complète définie, sans élagage supplémentaire. Le reste est explicitement reporté.

| Dans la v1 | Reporté |
| --- | --- |
| Éditeur WYSIWYG, blocs simples | Onglets, accordéons et blocs avancés |
| Portails public et interne, interface d'édition | Versionnement de la documentation (v1, v2 d'un produit) |
| Brouillon, publication, historique et restauration | Workflow de relecture |
| Multilingue, statut obsolète, glossaire, traduction manuelle | Édition en temps réel |
| Groupes, rôles par collection, restrictions héritées | SSO SAML, SCIM, liens de partage temporaires |
| Comptes locaux + OIDC | Notifications |
| Recherche full-text PostgreSQL | Toute l'IA : assistant et widget, traduction assistée, recherche sémantique |
| Commentaires au niveau de l'article | Commentaires ancrés sur le texte |
| Articles les plus lus | Journal d'audit, statistiques avancées |
| Import et export Markdown | Webhooks, plugins, thèmes |
|  | Import GitBook, Notion, Confluence ; API REST publique |

Le mode sombre n'est pas en v1 (jugé moins lisible pour de la doc), mais les tokens CSS doivent permettre de l'ajouter plus tard.
