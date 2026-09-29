from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models


class Author(models.Model):
    name = models.CharField(max_length=255)

    def __str__(self):
        return self.name


class Genre(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name


class Book(models.Model):
    book_id = models.IntegerField(unique=True)

    title = models.CharField(max_length=500)

    original_title = models.CharField(
        max_length=500,
        blank=True,
        null=True
    )

    isbn = models.CharField(
        max_length=20,
        blank=True,
        null=True
    )

    publication_year = models.IntegerField(
        blank=True,
        null=True
    )

    language_code = models.CharField(
        max_length=10,
        blank=True,
        null=True
    )

    image_url = models.URLField(
        blank=True,
        null=True
    )

    authors = models.ManyToManyField(
        Author,
        related_name="books"
    )

    genres = models.ManyToManyField(
        Genre,
        related_name="books",
        blank=True
    )

    def __str__(self):
        return self.title


class Copy(models.Model):
    copy_id = models.IntegerField(unique=True)

    book = models.ForeignKey(
        Book,
        on_delete=models.CASCADE,
        related_name="copies"
    )

    available = models.BooleanField(default=True)

    def __str__(self):
        return f"Copy {self.copy_id}"


class LibraryUser(models.Model):
    user_id = models.IntegerField(unique=True)

    birth_date = models.DateField(
        blank=True,
        null=True
    )

    comment = models.TextField(
        blank=True,
        null=True
    )

    def __str__(self):
        return f"User {self.user_id}"


class Rating(models.Model):
    user = models.ForeignKey(
        LibraryUser,
        on_delete=models.CASCADE,
        related_name="ratings"
    )

    copy = models.ForeignKey(
        Copy,
        on_delete=models.CASCADE,
        related_name="ratings"
    )

    rating = models.IntegerField(
        validators=[
            MinValueValidator(1),
            MaxValueValidator(5),
        ]
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    class Meta:
        unique_together = ("user", "copy")

        indexes = [
            models.Index(fields=["user"]),
            models.Index(fields=["copy"]),
        ]

        constraints = [
            models.CheckConstraint(
                condition=models.Q(
                    rating__gte=1,
                    rating__lte=5
                ),
                name="rating_between_1_and_5"
            )
        ]

    def __str__(self):
        return f"{self.user} - {self.rating}"


class AprioriRun(models.Model):
    started_at = models.DateTimeField(
        auto_now_add=True
    )

    finished_at = models.DateTimeField(
        blank=True,
        null=True
    )

    min_support = models.FloatField(
        validators=[
            MinValueValidator(0),
            MaxValueValidator(1),
        ]
    )

    min_confidence = models.FloatField(
        validators=[
            MinValueValidator(0),
            MaxValueValidator(1),
        ]
    )

    min_lift = models.FloatField(
        validators=[
            MinValueValidator(0),
        ]
    )

    min_rating = models.IntegerField(
        validators=[
            MinValueValidator(1),
            MaxValueValidator(5),
        ]
    )

    max_len = models.IntegerField(
        validators=[
            MinValueValidator(2),
        ]
    )

    is_active = models.BooleanField(
        default=False
    )

    transactions_count = models.IntegerField(
        blank=True,
        null=True,
        validators=[
            MinValueValidator(0),
        ]
    )

    rules_count = models.IntegerField(
        blank=True,
        null=True,
        validators=[
            MinValueValidator(0),
        ]
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["is_active"],
                condition=models.Q(is_active=True),
                name="unique_active_apriori_run"
            ),

            models.CheckConstraint(
                condition=models.Q(
                    min_support__gte=0,
                    min_support__lte=1
                ),
                name="apriori_support_between_0_and_1"
            ),

            models.CheckConstraint(
                condition=models.Q(
                    min_confidence__gte=0,
                    min_confidence__lte=1
                ),
                name="apriori_confidence_between_0_and_1"
            ),

            models.CheckConstraint(
                condition=models.Q(min_lift__gte=0),
                name="apriori_lift_non_negative"
            ),

            models.CheckConstraint(
                condition=models.Q(
                    min_rating__gte=1,
                    min_rating__lte=5
                ),
                name="apriori_rating_between_1_and_5"
            ),

            models.CheckConstraint(
                condition=models.Q(max_len__gte=2),
                name="apriori_max_len_at_least_2"
            ),

            models.CheckConstraint(
                condition=(
                    models.Q(transactions_count__isnull=True)
                    | models.Q(transactions_count__gte=0)
                ),
                name="apriori_transactions_non_negative"
            ),

            models.CheckConstraint(
                condition=(
                    models.Q(rules_count__isnull=True)
                    | models.Q(rules_count__gte=0)
                ),
                name="apriori_rules_non_negative"
            ),
        ]

    def __str__(self):
        return f"Apriori run {self.id}"


class AssociationRule(models.Model):
    run = models.ForeignKey(
        AprioriRun,
        on_delete=models.CASCADE,
        related_name="rules"
    )

    source_book = models.ForeignKey(
        Book,
        on_delete=models.CASCADE,
        related_name="association_rules_as_source"
    )

    support = models.FloatField(
        validators=[
            MinValueValidator(0),
            MaxValueValidator(1),
        ]
    )

    confidence = models.FloatField(
        validators=[
            MinValueValidator(0),
            MaxValueValidator(1),
        ]
    )

    lift = models.FloatField(
        validators=[
            MinValueValidator(0),
        ]
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    class Meta:
        indexes = [
            models.Index(fields=["confidence"]),
            models.Index(fields=["lift"]),
            models.Index(fields=["source_book", "confidence"]),
        ]

        constraints = [
            models.CheckConstraint(
                condition=models.Q(
                    support__gte=0,
                    support__lte=1
                ),
                name="rule_support_between_0_and_1"
            ),

            models.CheckConstraint(
                condition=models.Q(
                    confidence__gte=0,
                    confidence__lte=1
                ),
                name="rule_confidence_between_0_and_1"
            ),

            models.CheckConstraint(
                condition=models.Q(lift__gte=0),
                name="rule_lift_non_negative"
            ),
        ]

    def __str__(self):
        return f"{self.source_book} -> rule {self.id}"


class AssociationRuleTarget(models.Model):
    rule = models.ForeignKey(
        AssociationRule,
        on_delete=models.CASCADE,
        related_name="targets"
    )

    book = models.ForeignKey(
        Book,
        on_delete=models.CASCADE,
        related_name="association_rule_targets"
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["rule", "book"],
                name="unique_book_per_association_rule"
            )
        ]

    def __str__(self):
        return f"{self.rule_id} -> {self.book}"