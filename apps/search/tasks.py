from django.tasks import task

from apps.content.models import ArticleTranslation

from .services import get_backend


@task
def index_translation(translation_id: int) -> None:
    translation = ArticleTranslation.objects.filter(pk=translation_id).first()
    if translation is None:
        return
    if translation.is_published:
        get_backend().index(translation)
    else:
        get_backend().remove(translation)


@task
def reindex_all() -> int:
    backend = get_backend()
    count = 0
    for translation in ArticleTranslation.objects.published().only("id"):
        backend.index(translation)
        count += 1
    return count
