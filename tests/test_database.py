"""Tests for database engine and session management."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import lab_manager.database as db_mod


class TestGetEngine:
    def setup_method(self):
        # Reset module globals
        db_mod._engine = None
        db_mod._session_factory = None
        db_mod._readonly_engine = None

    def teardown_method(self):
        db_mod._engine = None
        db_mod._session_factory = None
        db_mod._readonly_engine = None

    @patch("lab_manager.database.get_settings")
    @patch("lab_manager.database.create_engine")
    def test_get_engine_sqlite(self, mock_create, mock_settings):
        mock_settings.return_value.database_url = "sqlite:///test.db"
        engine = db_mod.get_engine()
        mock_create.assert_called_once_with("sqlite:///test.db", echo=False)
        assert engine is mock_create.return_value

    @patch("lab_manager.database.get_settings")
    @patch("lab_manager.database.create_engine")
    def test_get_engine_postgres(self, mock_create, mock_settings):
        mock_settings.return_value.database_url = (
            "postgresql+psycopg://user:pw@localhost/db"
        )
        engine = db_mod.get_engine()
        mock_create.assert_called_once_with(
            "postgresql+psycopg://user:pw@localhost/db",
            echo=False,
            pool_size=10,
            max_overflow=20,
            pool_pre_ping=True,
            pool_recycle=1800,
            connect_args={"options": "-c search_path=labmanager,public"},
        )
        assert engine is mock_create.return_value

    @patch("lab_manager.database.get_settings")
    @patch("lab_manager.database.create_engine")
    def test_get_engine_caches(self, mock_create, mock_settings):
        mock_settings.return_value.database_url = "sqlite://"
        e1 = db_mod.get_engine()
        e2 = db_mod.get_engine()
        assert e1 is e2
        assert mock_create.call_count == 1


class TestGetReadonlyEngine:
    def setup_method(self):
        db_mod._engine = None
        db_mod._readonly_engine = None
        db_mod._session_factory = None

    def teardown_method(self):
        db_mod._engine = None
        db_mod._readonly_engine = None
        db_mod._session_factory = None

    @patch("lab_manager.database.get_engine")
    @patch("lab_manager.database.get_settings")
    def test_no_readonly_url_falls_back(self, mock_settings, mock_get_engine):
        mock_settings.return_value.database_readonly_url = ""
        mock_main = MagicMock()
        mock_get_engine.return_value = mock_main
        engine = db_mod.get_readonly_engine()
        assert engine is mock_main

    @patch("lab_manager.database.create_engine")
    @patch("lab_manager.database.get_settings")
    def test_readonly_url_creates_engine(self, mock_settings, mock_create):
        mock_settings.return_value.database_readonly_url = (
            "postgresql+psycopg://ro:pw@localhost/db"
        )
        engine = db_mod.get_readonly_engine()
        mock_create.assert_called_once()
        assert engine is mock_create.return_value

    @patch("lab_manager.database.create_engine")
    @patch("lab_manager.database.get_engine")
    @patch("lab_manager.database.get_settings")
    def test_readonly_creation_failure_falls_back(
        self, mock_settings, mock_get_engine, mock_create
    ):
        mock_settings.return_value.database_readonly_url = (
            "postgresql+psycopg://fail@localhost/db"
        )
        mock_create.side_effect = Exception("connection failed")
        mock_main = MagicMock()
        mock_get_engine.return_value = mock_main
        engine = db_mod.get_readonly_engine()
        assert engine is mock_main


class TestGetSessionFactory:
    def setup_method(self):
        db_mod._engine = None
        db_mod._session_factory = None
        db_mod._readonly_engine = None

    def teardown_method(self):
        db_mod._engine = None
        db_mod._session_factory = None
        db_mod._readonly_engine = None

    @patch("lab_manager.database.sessionmaker")
    @patch("lab_manager.database.get_engine")
    def test_creates_factory(self, mock_get_engine, mock_sessionmaker):
        factory = db_mod.get_session_factory()
        assert factory is mock_sessionmaker.return_value

    @patch("lab_manager.database.sessionmaker")
    @patch("lab_manager.database.get_engine")
    def test_caches_factory(self, mock_get_engine, mock_sessionmaker):
        f1 = db_mod.get_session_factory()
        f2 = db_mod.get_session_factory()
        assert f1 is f2
        assert mock_sessionmaker.call_count == 1


class TestGetDb:
    def test_yields_and_commits(self):
        mock_session = MagicMock()
        mock_factory = MagicMock(return_value=mock_session)
        with patch(
            "lab_manager.database.get_session_factory", return_value=mock_factory
        ):
            gen = db_mod.get_db()
            session = next(gen)
            assert session is mock_session
            try:
                gen.send(None)
            except StopIteration:
                pass
            mock_session.commit.assert_called_once()
            mock_session.close.assert_called_once()

    def test_rollback_on_exception(self):
        mock_session = MagicMock()
        mock_factory = MagicMock(return_value=mock_session)
        with patch(
            "lab_manager.database.get_session_factory", return_value=mock_factory
        ):
            gen = db_mod.get_db()
            next(gen)
            try:
                gen.throw(RuntimeError("boom"))
            except RuntimeError:
                pass
            mock_session.rollback.assert_called_once()
            mock_session.close.assert_called_once()


class TestGetDbSession:
    def test_context_manager(self):
        mock_session = MagicMock()
        mock_factory = MagicMock(return_value=mock_session)
        with patch(
            "lab_manager.database.get_session_factory", return_value=mock_factory
        ):
            with db_mod.get_db_session() as session:
                assert session is mock_session
            mock_session.close.assert_called_once()
