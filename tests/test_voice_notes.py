"""Tests for voice note endpoints."""

import io

import pytest


def _make_wav_bytes() -> bytes:
    """Return minimal valid WAV bytes (8-bit mono, 8000 Hz, 1 second of silence)."""
    sample_rate = 8000
    num_channels = 1
    bits_per_sample = 8
    num_samples = sample_rate * num_channels
    data_size = num_samples * (bits_per_sample // 8)
    file_size = 36 + data_size

    buf = io.BytesIO()
    # RIFF header
    buf.write(b"RIFF")
    buf.write(file_size.to_bytes(4, "little"))
    buf.write(b"WAVE")
    # fmt chunk
    buf.write(b"fmt ")
    buf.write((16).to_bytes(4, "little"))  # chunk size
    buf.write((1).to_bytes(2, "little"))  # PCM
    buf.write(num_channels.to_bytes(2, "little"))
    buf.write(sample_rate.to_bytes(4, "little"))
    buf.write((sample_rate * num_channels * bits_per_sample // 8).to_bytes(4, "little"))
    buf.write((num_channels * bits_per_sample // 8).to_bytes(2, "little"))
    buf.write(bits_per_sample.to_bytes(2, "little"))
    # data chunk
    buf.write(b"data")
    buf.write(data_size.to_bytes(4, "little"))
    buf.write(b"\x80" * data_size)  # silence
    return buf.getvalue()


@pytest.fixture()
def _seed_staff(db_session):
    """Create a staff member for FK references."""
    from lab_manager.models.staff import Staff

    staff = Staff(name="Test Researcher", email="test@example.com", role="grad_student")
    db_session.add(staff)
    db_session.flush()
    db_session.refresh(staff)
    return staff


class TestCreateVoiceNote:
    def test_upload_audio_success(self, client, _seed_staff):
        wav = _make_wav_bytes()
        resp = client.post(
            "/api/v1/voice-notes/",
            params={"staff_id": _seed_staff.id, "duration_seconds": 5.0},
            files={"file": ("note.wav", wav, "audio/wav")},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["staff_id"] == _seed_staff.id
        assert data["status"] == "pending"
        assert data["duration_seconds"] == 5.0
        assert data["audio_file"] is not None
        assert data["id"] is not None

    def test_upload_with_tags(self, client, _seed_staff):
        wav = _make_wav_bytes()
        resp = client.post(
            "/api/v1/voice-notes/",
            params={"staff_id": _seed_staff.id, "tags": "experiment,meeting"},
            files={"file": ("note.wav", wav, "audio/wav")},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["tags"] == "experiment,meeting"

    def test_upload_rejects_invalid_content_type(self, client, _seed_staff):
        resp = client.post(
            "/api/v1/voice-notes/",
            params={"staff_id": _seed_staff.id},
            files={"file": ("note.txt", b"hello", "text/plain")},
        )
        assert resp.status_code == 400
        assert "not allowed" in resp.json()["detail"]

    def test_upload_rejects_missing_file(self, client, _seed_staff):
        resp = client.post(
            "/api/v1/voice-notes/",
            params={"staff_id": _seed_staff.id},
        )
        assert resp.status_code == 422


class TestListVoiceNotes:
    def test_list_empty(self, client):
        resp = client.get("/api/v1/voice-notes/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["items"] == []

    def test_list_with_filter(self, client, _seed_staff):
        wav = _make_wav_bytes()
        # Create two notes
        client.post(
            "/api/v1/voice-notes/",
            params={"staff_id": _seed_staff.id},
            files={"file": ("a.wav", wav, "audio/wav")},
        )
        client.post(
            "/api/v1/voice-notes/",
            params={"staff_id": _seed_staff.id},
            files={"file": ("b.wav", wav, "audio/wav")},
        )
        # Filter by staff_id
        resp = client.get("/api/v1/voice-notes/", params={"staff_id": _seed_staff.id})
        assert resp.status_code == 200
        assert resp.json()["total"] == 2

        # Filter by status=pending
        resp = client.get("/api/v1/voice-notes/", params={"status": "pending"})
        assert resp.status_code == 200
        assert resp.json()["total"] == 2

        # Filter by non-matching status
        resp = client.get("/api/v1/voice-notes/", params={"status": "archived"})
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    def test_pagination(self, client, _seed_staff):
        wav = _make_wav_bytes()
        for i in range(5):
            client.post(
                "/api/v1/voice-notes/",
                params={"staff_id": _seed_staff.id},
                files={"file": (f"note{i}.wav", wav, "audio/wav")},
            )
        resp = client.get("/api/v1/voice-notes/", params={"page": 1, "page_size": 2})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) == 2
        assert data["total"] == 5
        assert data["pages"] == 3


class TestGetVoiceNote:
    def test_get_existing(self, client, _seed_staff):
        wav = _make_wav_bytes()
        create_resp = client.post(
            "/api/v1/voice-notes/",
            params={"staff_id": _seed_staff.id},
            files={"file": ("note.wav", wav, "audio/wav")},
        )
        note_id = create_resp.json()["id"]
        resp = client.get(f"/api/v1/voice-notes/{note_id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == note_id

    def test_get_not_found(self, client):
        resp = client.get("/api/v1/voice-notes/99999")
        assert resp.status_code == 404


class TestUpdateVoiceNote:
    def test_update_transcript_and_tags(self, client, _seed_staff):
        wav = _make_wav_bytes()
        create_resp = client.post(
            "/api/v1/voice-notes/",
            params={"staff_id": _seed_staff.id},
            files={"file": ("note.wav", wav, "audio/wav")},
        )
        note_id = create_resp.json()["id"]

        resp = client.patch(
            f"/api/v1/voice-notes/{note_id}",
            json={"transcript": "Hello world", "tags": "intro,greeting"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["transcript"] == "Hello world"
        assert data["tags"] == "intro,greeting"

    def test_update_status(self, client, _seed_staff):
        wav = _make_wav_bytes()
        create_resp = client.post(
            "/api/v1/voice-notes/",
            params={"staff_id": _seed_staff.id},
            files={"file": ("note.wav", wav, "audio/wav")},
        )
        note_id = create_resp.json()["id"]

        resp = client.patch(
            f"/api/v1/voice-notes/{note_id}",
            json={"status": "reviewed"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "reviewed"

    def test_update_rejects_invalid_status(self, client, _seed_staff):
        wav = _make_wav_bytes()
        create_resp = client.post(
            "/api/v1/voice-notes/",
            params={"staff_id": _seed_staff.id},
            files={"file": ("note.wav", wav, "audio/wav")},
        )
        note_id = create_resp.json()["id"]

        resp = client.patch(
            f"/api/v1/voice-notes/{note_id}",
            json={"status": "invalid_status"},
        )
        assert resp.status_code == 422


class TestTranscribeVoiceNote:
    def test_transcribe_pending(self, client, _seed_staff):
        wav = _make_wav_bytes()
        create_resp = client.post(
            "/api/v1/voice-notes/",
            params={"staff_id": _seed_staff.id, "duration_seconds": 10.0},
            files={"file": ("note.wav", wav, "audio/wav")},
        )
        note_id = create_resp.json()["id"]

        resp = client.post(f"/api/v1/voice-notes/{note_id}/transcribe")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "transcribed"
        assert data["transcript"] is not None
        assert "Placeholder transcript" in data["transcript"]
        assert "10.0 seconds" in data["transcript"]

    def test_transcribe_already_transcribed(self, client, _seed_staff):
        wav = _make_wav_bytes()
        create_resp = client.post(
            "/api/v1/voice-notes/",
            params={"staff_id": _seed_staff.id},
            files={"file": ("note.wav", wav, "audio/wav")},
        )
        note_id = create_resp.json()["id"]

        # First transcription
        client.post(f"/api/v1/voice-notes/{note_id}/transcribe")
        # Second transcription should also work (re-transcribe allowed)
        resp = client.post(f"/api/v1/voice-notes/{note_id}/transcribe")
        assert resp.status_code == 200

    def test_transcribe_archived_rejected(self, client, _seed_staff):
        wav = _make_wav_bytes()
        create_resp = client.post(
            "/api/v1/voice-notes/",
            params={"staff_id": _seed_staff.id},
            files={"file": ("note.wav", wav, "audio/wav")},
        )
        note_id = create_resp.json()["id"]

        # Archive it first
        client.patch(
            f"/api/v1/voice-notes/{note_id}",
            json={"status": "archived"},
        )

        resp = client.post(f"/api/v1/voice-notes/{note_id}/transcribe")
        assert resp.status_code == 409
