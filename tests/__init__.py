import django

# Now this is ugly.
# The django.db.backend.features that exist changes per version and per db :/
if django.VERSION[:2] == (2, 2):
    has_sufficient_json_support = ('has_jsonb_agg',)
if django.VERSION[:2] == (3, 2):
    # This version of EasyDMP is not using Django's native JSONField
    # implementation, but the deprecated postgres-specific field. When no
    # longer supporting 2.2 this can be "has_native_json_field"
    has_sufficient_json_support = ('is_postgresql_10',)
if django.VERSION[:2] == (4, 0):
    has_sufficient_json_support = ('has_native_json_field',)
