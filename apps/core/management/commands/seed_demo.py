"""Fill an empty instance with demo content to try Lorebook out.

uv run manage.py seed_demo --admin-email admin@example.com --admin-password secret
"""

from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.access.models import CollectionRole, Role, User
from apps.content import services as content
from apps.content.markdown import markdown_to_doc
from apps.content.models import Collection
from apps.core.models import SiteSettings
from apps.i18n.models import GlossaryTerm

GUIDE_FR = """# Bien démarrer

Bienvenue dans **Lorebook**, la documentation de votre équipe.

## Installer

1. Téléchargez l'image Docker.
2. Lancez `docker compose up -d`.
3. Ouvrez [le tableau de bord](/edit/).

> [!TIP]
> Les brouillons sont enregistrés automatiquement pendant que vous écrivez.

## Configurer

| Variable | Rôle |
| --- | --- |
| `DB_HOST` | Hôte PostgreSQL |
| `DJANGO_SECRET_KEY` | Clé secrète |

```bash
docker compose exec web python manage.py createsuperuser
```

- [x] Créer une collection
- [ ] Inviter l'équipe
"""

GUIDE_EN = """# Getting started

Welcome to **Lorebook**, your team's documentation.

## Install

1. Pull the Docker image.
2. Run `docker compose up -d`.
3. Open [the dashboard](/edit/).

> [!TIP]
> Drafts are saved automatically while you write.

## Configure

| Variable | Purpose |
| --- | --- |
| `DB_HOST` | PostgreSQL host |
| `DJANGO_SECRET_KEY` | Secret key |

```bash
docker compose exec web python manage.py createsuperuser
```
"""

WRITING_FR = """# Rédiger un article

Chaque article a un **brouillon** et une **version publiée**.

## Publier

Publier remplace la version publiée et crée une révision dans l'historique.

> [!WARNING]
> Publier une version marque les autres langues comme obsolètes, sauf si vous cochez
> « Modification mineure ».

## Traduire

Ouvrez l'onglet d'une langue, partez d'une copie, traduisez puis publiez en déclarant
la version synchronisée.
"""

FAQ_FR = """# Questions fréquentes

## Puis-je importer du Markdown ?

Oui : depuis une collection, choisissez **Importer Markdown**.

## Où sont stockés les fichiers ?

Sur le disque local par défaut, ou dans un stockage compatible S3.
"""

HANDBOOK_FR = """# Manuel de l'équipe

Ce manuel interne n'est visible que des membres connectés.

## Vacances

Annoncez vos absences deux semaines à l'avance.

## Outils

Nous utilisons Lorebook pour toute la documentation.
"""


class Command(BaseCommand):
    help = "Create demo collections, articles, groups and an administrator."

    def add_arguments(self, parser):
        parser.add_argument("--admin-email", default="admin@example.com")
        parser.add_argument("--admin-password", default="")

    @transaction.atomic
    def handle(self, *args, admin_email, admin_password, **options):
        if Collection.objects.exists():
            raise CommandError("This instance already has content.")
        admin = User.objects.filter(email=admin_email).first()
        if admin is None:
            if not admin_password:
                raise CommandError("Pass --admin-password to create the administrator.")
            admin = User.objects.create_superuser(
                admin_email, admin_password, first_name="Ada", last_name="Admin"
            )

        site_settings = SiteSettings.load()
        site_settings.site_name = "Acme Docs"
        site_settings.tagline = "Guides, références et savoir-faire de l'équipe."
        site_settings.save()

        writers = Group.objects.create(name="Rédaction")
        staff = Group.objects.create(name="Équipe")

        docs = Collection.objects.create(
            name="Guide produit",
            slug="guide",
            description="Tout pour installer et utiliser le produit.",
            icon="rocket",
            is_public=True,
            position=0,
        )
        handbook = Collection.objects.create(
            name="Manuel interne",
            slug="manuel",
            description="Processus et règles de l'équipe.",
            icon="people-group",
            position=1,
        )
        CollectionRole.objects.create(collection=docs, group=writers, role=Role.EDITOR)
        CollectionRole.objects.create(collection=handbook, group=writers, role=Role.EDITOR)
        CollectionRole.objects.create(collection=handbook, group=staff, role=Role.READER)

        def add(collection, source, language="fr", parent=None):
            title, doc = markdown_to_doc(source)
            translation = content.create_article(
                collection, title=title, language=language, content=doc, parent=parent, user=admin
            )
            content.publish(translation, user=admin)
            return translation

        guide = add(docs, GUIDE_FR)
        english = content.add_translation(guide.article, "en", user=admin)
        title, doc = markdown_to_doc(GUIDE_EN)
        content.save_draft(english, title=title, content=doc, user=admin)
        content.publish(english, user=admin, kind="sync")
        add(docs, WRITING_FR, parent=guide.article)
        add(docs, FAQ_FR)
        add(handbook, HANDBOOK_FR)

        for terms in [
            {"fr": "tableau de bord", "de": "Dashboard", "it": "cruscotto", "en": "dashboard"},
            {"fr": "brouillon", "de": "Entwurf", "it": "bozza", "en": "draft"},
            {"fr": "collection", "de": "Sammlung", "it": "raccolta", "en": "collection"},
        ]:
            GlossaryTerm.objects.create(translations=terms)

        self.stdout.write(self.style.SUCCESS(f"Demo content created. Sign in as {admin.email}."))
