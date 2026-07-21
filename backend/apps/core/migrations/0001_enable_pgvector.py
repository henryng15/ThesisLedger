from django.db import migrations
from pgvector.django import VectorExtension


class Migration(migrations.Migration):
    """Enable the pgvector extension so Chunk.embedding can use vector columns."""

    initial = True

    dependencies = []

    operations = [VectorExtension()]
