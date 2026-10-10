import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, Group, PermissionsMixin
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, email, password, **extra_fields):
        if not email:
            raise ValueError("An email address is required")
        email = self.normalize_email(email).lower()
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields["is_staff"] = True
        extra_fields["is_superuser"] = True
        return self._create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    """A person who signs in to Lorebook, identified by their email address.

    Superusers are the instance administrators: they manage languages, groups,
    users and site settings, and hold every role on every collection.
    """

    email = models.EmailField(_("email address"), unique=True)
    first_name = models.CharField(_("first name"), max_length=150, blank=True)
    last_name = models.CharField(_("last name"), max_length=150, blank=True)
    is_staff = models.BooleanField(_("staff status"), default=False)
    is_active = models.BooleanField(_("active"), default=True)
    date_joined = models.DateTimeField(_("date joined"), default=timezone.now)
    # Language the user writes in: the editor opens articles in it.
    content_language = models.CharField(_("content language"), max_length=8, blank=True)

    objects = UserManager()

    EMAIL_FIELD = "email"
    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    class Meta:
        verbose_name = _("user")
        verbose_name_plural = _("users")
        ordering = ["first_name", "last_name", "email"]

    def __str__(self):
        return self.full_name or self.email

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()

    @property
    def display_name(self) -> str:
        return self.full_name or self.email

    @property
    def initials(self) -> str:
        if self.first_name or self.last_name:
            return f"{self.first_name[:1]}{self.last_name[:1]}".upper()
        return self.email[:2].upper()

    @property
    def is_instance_admin(self) -> bool:
        return self.is_active and self.is_superuser

    def get_full_name(self):
        return self.full_name

    def get_short_name(self):
        return self.first_name or self.email


class Role(models.TextChoices):
    READER = "reader", _("Reader")
    EDITOR = "editor", _("Editor")
    ADMIN = "admin", _("Admin")


ROLE_RANK = {Role.READER: 1, Role.EDITOR: 2, Role.ADMIN: 3}


class CollectionRole(models.Model):
    """Grants a role on a collection to every member of a group."""

    collection = models.ForeignKey(
        "content.Collection", on_delete=models.CASCADE, related_name="roles"
    )
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name="collection_roles")
    role = models.CharField(_("role"), max_length=16, choices=Role.choices, default=Role.READER)

    class Meta:
        verbose_name = _("collection role")
        verbose_name_plural = _("collection roles")
        constraints = [
            models.UniqueConstraint(fields=["collection", "group"], name="unique_collection_group")
        ]

    def __str__(self):
        return f"{self.group} - {self.get_role_display()} - {self.collection}"


def _invitation_token() -> str:
    return secrets.token_urlsafe(32)


class Invitation(models.Model):
    """An invitation for someone to create a local account."""

    email = models.EmailField(_("email address"))
    token = models.CharField(max_length=64, unique=True, default=_invitation_token)
    groups = models.ManyToManyField(Group, blank=True, verbose_name=_("groups"))
    is_admin = models.BooleanField(_("instance administrator"), default=False)
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    accepted_at = models.DateTimeField(null=True, blank=True)

    VALIDITY_DAYS = 14

    class Meta:
        verbose_name = _("invitation")
        verbose_name_plural = _("invitations")
        ordering = ["-created_at"]

    def __str__(self):
        return self.email

    @property
    def is_expired(self) -> bool:
        return self.created_at + timedelta(days=self.VALIDITY_DAYS) < timezone.now()

    @property
    def is_pending(self) -> bool:
        return self.accepted_at is None and not self.is_expired
