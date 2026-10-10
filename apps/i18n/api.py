from ninja import Router, Schema

from .models import GlossaryTerm
from .services import enabled_codes

router = Router(tags=["i18n"])


class GlossaryTermOut(Schema):
    id: int
    translations: dict[str, str]
    note: str


@router.get("/glossary", response=list[GlossaryTermOut])
def glossary(request):
    codes = enabled_codes()
    return [
        GlossaryTermOut(
            id=term.pk,
            translations={code: term.translations.get(code, "") for code in codes},
            note=term.note,
        )
        for term in GlossaryTerm.objects.all()
    ]
