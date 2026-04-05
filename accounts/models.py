from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    class Role(models.TextChoices):
        VIEWER = "viewer", "Viewer"
        ANALYST = "analyst", "Analyst"
        ADMIN = "admin", "Admin"

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        INACTIVE = "inactive", "Inactive"

    username = None
    email = models.EmailField("email address", unique=True)
    name = models.CharField(max_length=150)
    role = models.CharField(max_length=20, choices=Role.choices)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    def __str__(self):
        return self.email

    def save(self, *args, **kwargs):
        self.is_active = self.status == self.Status.ACTIVE
        super().save(*args, **kwargs)
