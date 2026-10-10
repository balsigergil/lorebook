from django.contrib.postgres.operations import TrigramExtension, UnaccentExtension
from django.db import migrations

# One text search configuration per language, folding accents so that
# "elephant" finds "éléphant".
CONFIGS = {
    "lorebook_fr": "french_stem",
    "lorebook_de": "german_stem",
    "lorebook_it": "italian_stem",
    "lorebook_en": "english_stem",
    "lorebook_es": "spanish_stem",
    "lorebook_pt": "portuguese_stem",
    "lorebook_nl": "dutch_stem",
    "lorebook_simple": "simple",
}


def create_sql():
    statements = []
    for name, dictionary in CONFIGS.items():
        statements.append(f"DROP TEXT SEARCH CONFIGURATION IF EXISTS {name}")
        statements.append(f"CREATE TEXT SEARCH CONFIGURATION {name} (COPY = simple)")
        statements.append(
            f"ALTER TEXT SEARCH CONFIGURATION {name} "
            f"ALTER MAPPING FOR hword, hword_part, word WITH unaccent, {dictionary}"
        )
        statements.append(
            f"ALTER TEXT SEARCH CONFIGURATION {name} "
            f"ALTER MAPPING FOR asciihword, asciiword, hword_asciipart WITH {dictionary}"
        )
    return ";\n".join(statements) + ";"


def drop_sql():
    return ";\n".join(f"DROP TEXT SEARCH CONFIGURATION IF EXISTS {name}" for name in CONFIGS) + ";"


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        TrigramExtension(),
        UnaccentExtension(),
        migrations.RunSQL(create_sql(), drop_sql()),
    ]
