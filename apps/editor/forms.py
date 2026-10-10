from django import forms
from django.contrib.auth.models import Group
from django.core.validators import FileExtensionValidator
from django.utils.translation import gettext_lazy as _

from apps.access.models import CollectionRole, Invitation, Role, User
from apps.content import services as content
from apps.content.models import Article, Collection
from apps.core.forms import LoreForm, LoreModelForm
from apps.core.models import SiteSettings
from apps.i18n.models import KNOWN_LANGUAGES, GlossaryTerm, Language
from apps.i18n.services import enabled_languages

RESERVED_SLUGS = {"search", "static", "api", "files", "accounts", "comments", "edit", "internal"}


class CollectionForm(LoreModelForm):
    class Meta:
        model = Collection
        fields = ["name", "slug", "description", "icon", "is_public"]
        widgets = {"description": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["slug"].required = False
        self.fields["slug"].help_text = _("Used in URLs. Generated from the name when empty.")

    def clean_slug(self):
        slug = self.cleaned_data.get("slug") or ""
        if not slug:
            slug = content.unique_slug(
                Collection.objects.all(),
                self.cleaned_data.get("name", ""),
                exclude_pk=self.instance.pk,
            )
        if slug in RESERVED_SLUGS:
            raise forms.ValidationError(_("This slug is reserved."))
        if Collection.objects.filter(slug=slug).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError(_("Another collection already uses this slug."))
        return slug


class CollectionRoleForm(LoreForm):
    submit_label = _("Grant")

    group = forms.ModelChoiceField(label=_("Group"), queryset=Group.objects.all())
    role = forms.ChoiceField(label=_("Role"), choices=Role.choices, initial=Role.READER)

    def __init__(self, *args, collection: Collection, **kwargs):
        self.collection = collection
        super().__init__(*args, **kwargs)

    def save(self) -> CollectionRole:
        role, _created = CollectionRole.objects.update_or_create(
            collection=self.collection,
            group=self.cleaned_data["group"],
            defaults={"role": self.cleaned_data["role"]},
        )
        return role


class ArticleCreateForm(LoreForm):
    """A new article, written in the user's current language."""

    submit_label = _("Create")

    title = forms.CharField(label=_("Title"), max_length=300)
    parent = forms.ModelChoiceField(
        label=_("Parent article"),
        queryset=Article.objects.none(),
        required=False,
        empty_label=_("At the root of the collection"),
    )

    def __init__(self, *args, collection: Collection, **kwargs):
        self.collection = collection
        super().__init__(*args, **kwargs)
        self.fields["parent"].queryset = collection.articles.all()
        self.fields["parent"].label_from_instance = article_label


def article_label(article: Article) -> str:
    translation = article.translations.order_by("-published_at").first()
    title = translation.display_title if translation else article.slug
    depth = len(article.ancestors())
    return f"{'- ' * depth}{title}"


class ArticleSettingsForm(LoreModelForm):
    class Meta:
        model = Article
        fields = ["slug", "parent", "read_groups"]
        widgets = {"read_groups": forms.SelectMultiple()}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        article = self.instance
        excluded = content.descendant_ids(article) | {article.pk}
        self.fields["parent"].queryset = article.collection.articles.exclude(pk__in=excluded)
        self.fields["parent"].label_from_instance = article_label
        self.fields["parent"].empty_label = _("At the root of the collection")
        self.fields["read_groups"].required = False

    def clean_slug(self):
        slug = self.cleaned_data["slug"]
        exists = (
            Article.objects.filter(collection=self.instance.collection, slug=slug)
            .exclude(pk=self.instance.pk)
            .exists()
        )
        if exists:
            raise forms.ValidationError(_("Another article of this collection uses this slug."))
        return slug

    def save(self, commit=True):
        parent_changed = "parent" in self.changed_data
        new_parent = self.cleaned_data.get("parent")
        article = super().save(commit=False)
        if commit:
            article.save(update_fields=["slug", "updated_at"])
            self.save_m2m()
            if parent_changed:
                content.move_article(article, new_parent)
        return article


class PublishForm(LoreForm):
    submit_label = _("Publish")

    kind = forms.ChoiceField(
        label=_("Kind of change"),
        widget=forms.RadioSelect,
        choices=[
            ("update", _("Content update - the other languages become outdated")),
            ("minor", _("Minor change (typo, formatting) - nothing becomes outdated")),
        ],
        initial="update",
    )
    note = forms.CharField(
        label=_("Note"),
        required=False,
        max_length=300,
        help_text=_("Optional, shown in the history."),
    )

    def __init__(self, *args, outdated: bool = False, **kwargs):
        super().__init__(*args, **kwargs)
        if outdated:
            self.fields["kind"].choices = [
                ("sync", _("Translation brought up to date - mark this version as synchronised")),
                *self.fields["kind"].choices,
            ]
            self.fields["kind"].initial = "sync"


class TranslationCreateForm(LoreForm):
    submit_label = _("Create this translation")

    source = forms.ChoiceField(label=_("Start from"), widget=forms.RadioSelect)

    def __init__(self, *args, sources: list, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["source"].choices = [("", _("An empty page"))] + [
            (translation.language, _("A copy of the %(language)s version") % {"language": name})
            for translation, name in sources
        ]
        self.fields["source"].required = False
        self.fields["source"].initial = sources[0][0].language if sources else ""


class MarkdownImportForm(LoreForm):
    submit_label = _("Import")

    file = forms.FileField(
        label=_("Markdown file"),
        validators=[FileExtensionValidator(["md", "markdown", "txt"])],
    )
    parent = forms.ModelChoiceField(
        label=_("Parent article"),
        queryset=Article.objects.none(),
        required=False,
        empty_label=_("At the root of the collection"),
    )
    publish = forms.BooleanField(label=_("Publish right away"), required=False)

    def __init__(self, *args, collection: Collection, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["parent"].queryset = collection.articles.all()
        self.fields["parent"].label_from_instance = article_label

    def clean_file(self):
        upload = self.cleaned_data["file"]
        if upload.size > 2 * 1024 * 1024:
            raise forms.ValidationError(_("The file is too large (2 MB max)."))
        try:
            self.markdown = upload.read().decode("utf-8-sig")
        except UnicodeDecodeError as error:
            raise forms.ValidationError(_("The file must be UTF-8 text.")) from error
        return upload


class GlossaryTermForm(LoreForm):
    submit_label = _("Save")

    note = forms.CharField(
        label=_("Note"), required=False, widget=forms.Textarea(attrs={"rows": 2})
    )

    def __init__(self, *args, instance: GlossaryTerm | None = None, **kwargs):
        self.instance = instance or GlossaryTerm()
        super().__init__(*args, **kwargs)
        fields = {}
        for language in enabled_languages():
            fields[f"term_{language.code}"] = forms.CharField(
                label=language.name,
                required=False,
                max_length=200,
                initial=self.instance.translations.get(language.code, ""),
            )
        self.fields = {**fields, "note": self.fields["note"]}
        self.fields["note"].initial = self.instance.note
        from apps.core.forms.base_forms import style_widget

        for field in self.fields.values():
            style_widget(field)

    def clean(self):
        cleaned = super().clean()
        if not any(value for key, value in cleaned.items() if key.startswith("term_")):
            raise forms.ValidationError(_("Enter the term in at least one language."))
        return cleaned

    def save(self) -> GlossaryTerm:
        translations = dict(self.instance.translations)
        for key, value in self.cleaned_data.items():
            if key.startswith("term_"):
                translations[key.removeprefix("term_")] = value.strip()
        self.instance.translations = translations
        self.instance.note = self.cleaned_data.get("note", "")
        self.instance.save()
        return self.instance


class SiteSettingsForm(LoreModelForm):
    class Meta:
        model = SiteSettings
        fields = ["site_name", "tagline", "main_host", "public_host", "internal_host", "edit_host"]

    def clean(self):
        cleaned = super().clean()
        hosts = {
            name: (cleaned.get(name) or "").strip().lower()
            for name in ("main_host", "public_host", "internal_host", "edit_host")
        }
        portal_hosts = [hosts[name] for name in ("public_host", "internal_host", "edit_host")]
        used = [host for host in portal_hosts if host]
        if len(used) != len(set(used)):
            raise forms.ValidationError(_("Each interface needs a different domain."))
        if hosts["main_host"] and hosts["main_host"] in used:
            raise forms.ValidationError(
                _("The main domain cannot be one of the interface domains.")
            )
        if used and len(used) < 3 and not hosts["main_host"]:
            raise forms.ValidationError(
                _("Set the main domain, which serves the interfaces without their own domain.")
            )
        for name, host in hosts.items():
            if host and ("/" in host or ":" in host or " " in host):
                self.add_error(name, _("Enter a domain name only, e.g. docs.example.com."))
        return cleaned


class LanguageForm(LoreForm):
    submit_label = _("Add")

    code = forms.ChoiceField(label=_("Language"))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        existing = set(Language.objects.values_list("code", flat=True))
        self.fields["code"].choices = [
            (code, name)
            for code, (name, _config) in KNOWN_LANGUAGES.items()
            if code not in existing
        ]

    def save(self) -> Language:
        code = self.cleaned_data["code"]
        position = Language.objects.count()
        return Language.objects.create(code=code, name=KNOWN_LANGUAGES[code][0], position=position)


class GroupForm(LoreModelForm):
    class Meta:
        model = Group
        fields = ["name"]


class GroupMemberForm(LoreForm):
    submit_label = _("Add")

    user = forms.ModelChoiceField(label=_("User"), queryset=User.objects.filter(is_active=True))

    def __init__(self, *args, group: Group, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["user"].queryset = User.objects.filter(is_active=True).exclude(groups=group)


class InvitationForm(LoreModelForm):
    submit_label = _("Send the invitation")

    class Meta:
        model = Invitation
        fields = ["email", "groups", "is_admin"]
        widgets = {"groups": forms.SelectMultiple()}

    def clean_email(self):
        email = self.cleaned_data["email"].lower()
        if User.objects.filter(email__iexact=email, is_active=True).exists():
            raise forms.ValidationError(_("This person already has an account."))
        return email


class UserForm(LoreModelForm):
    class Meta:
        model = User
        fields = ["first_name", "last_name", "email", "groups", "is_superuser", "is_active"]
        labels = {"is_superuser": _("Instance administrator")}
        help_texts = {
            "is_superuser": _(
                "Manages languages, groups, users and settings, and edits everything."
            ),
            "groups": "",
        }
        widgets = {"groups": forms.SelectMultiple()}

    def save(self, commit=True):
        user = super().save(commit=False)
        user.is_staff = user.is_superuser
        if commit:
            user.save()
            self.save_m2m()
        return user


class ProfileForm(LoreModelForm):
    class Meta:
        model = User
        fields = ["first_name", "last_name"]
