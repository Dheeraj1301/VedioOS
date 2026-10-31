from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase

from vedioos.database import postgres_database


class DatabaseConfigurationTests(SimpleTestCase):
    def test_encoded_credentials_and_private_schema(self):
        config = postgres_database(
            "postgresql://app.project:synthetic%40pass%23@pooler.example.com:5432/postgres"
        )
        self.assertEqual(config["PASSWORD"], "synthetic@pass#")
        self.assertEqual(config["OPTIONS"]["sslmode"], "verify-full")
        self.assertIn("search_path=vedioos", config["OPTIONS"]["options"])
        self.assertIsNone(config["OPTIONS"]["prepare_threshold"])
        self.assertEqual(config["CONN_MAX_AGE"], 0)

    def test_connection_persistence_requires_an_explicit_value(self):
        config = postgres_database(
            "postgresql://app.project:synthetic@pooler.example.com:5432/postgres",
            conn_max_age=30,
        )
        self.assertEqual(config["CONN_MAX_AGE"], 30)

    def test_encrypted_preview_connection_can_skip_ca_verification_explicitly(self):
        config = postgres_database(
            "postgresql://app.project:synthetic@pooler.example.com:5432/postgres",
            sslmode="require",
        )
        self.assertEqual(config["OPTIONS"]["sslmode"], "require")
        self.assertNotIn("sslrootcert", config["OPTIONS"])

    def test_bad_url_never_leaks_credentials_in_errors(self):
        for url in [
            "postgresql://user:secret@host:secret/db",
            "https://user:secret@host/db",
            "postgresql://user:secret@host/db#secret",
        ]:
            with self.assertRaises(ImproperlyConfigured) as error:
                postgres_database(url)
            self.assertNotIn("secret", str(error.exception))

    def test_unsafe_schema_and_unencrypted_url_rejected(self):
        for schema in ["public", "auth", "storage", "vedioos;drop table users"]:
            with self.assertRaises(ImproperlyConfigured):
                postgres_database("postgresql://user:password@host/db", schema=schema)
        with self.assertRaises(ImproperlyConfigured):
            postgres_database("postgresql://user:password@host/db?sslmode=disable")
