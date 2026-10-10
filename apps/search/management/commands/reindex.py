from django.core.management.base import BaseCommand

from apps.search.tasks import reindex_all


class Command(BaseCommand):
    help = "Rebuild the full-text index of every published article."

    def handle(self, *args, **options):
        count = reindex_all.call()
        self.stdout.write(self.style.SUCCESS(f"{count} translations indexed."))
