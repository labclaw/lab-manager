"""Tests for digital staff fields (staff_type, agent_config, avatar_emoji)."""

from sqlmodel import Session, SQLModel, create_engine, select

from lab_manager.models.staff import Staff


def _make_engine():
    """In-memory SQLite engine for unit tests."""
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine)
    return engine


def test_staff_type_defaults_to_human():
    """New staff members default to staff_type='human'."""
    engine = _make_engine()
    with Session(engine) as session:
        staff = Staff(name="Alice")
        session.add(staff)
        session.commit()
        session.refresh(staff)
        assert staff.staff_type == "human"


def test_create_ai_agent_staff():
    """Staff can be created with staff_type='ai_agent'."""
    engine = _make_engine()
    with Session(engine) as session:
        staff = Staff(
            name="LabBot",
            email="labbot@labclaw.local",
            staff_type="ai_agent",
            avatar_emoji=":robot:",
        )
        session.add(staff)
        session.commit()
        session.refresh(staff)
        assert staff.staff_type == "ai_agent"
        assert staff.avatar_emoji == ":robot:"


def test_agent_config_can_be_none():
    """agent_config is optional and defaults to None."""
    engine = _make_engine()
    with Session(engine) as session:
        staff = Staff(name="Bob", staff_type="human")
        session.add(staff)
        session.commit()
        session.refresh(staff)
        assert staff.agent_config is None


def test_agent_config_stores_and_retrieves_json():
    """agent_config stores a dict and retrieves it intact."""
    engine = _make_engine()
    with Session(engine) as session:
        config = {
            "role": "lab_assistant",
            "capabilities": ["inventory", "documents", "search"],
        }
        staff = Staff(
            name="Lab Assistant",
            email="lab-asst@labclaw.local",
            staff_type="ai_agent",
            avatar_emoji=":test_tube:",
            agent_config=config,
        )
        session.add(staff)
        session.commit()

        result = session.exec(
            select(Staff).where(Staff.email == "lab-asst@labclaw.local")
        ).one()
        assert result.agent_config == config
        assert result.agent_config["role"] == "lab_assistant"
        assert "inventory" in result.agent_config["capabilities"]
