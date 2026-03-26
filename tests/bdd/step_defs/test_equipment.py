"""Step definitions for equipment lifecycle BDD scenarios."""

import pytest
from pytest_bdd import given, scenario, then, when, parsers

FEATURE = "../features/equipment.feature"


# --- Scenarios ---


@scenario(FEATURE, "Register new equipment manually")
def test_register():
    pass


@scenario(FEATURE, "List equipment with pagination")
def test_list_pagination():
    pass


@scenario(FEATURE, "Filter equipment by category")
def test_filter_category():
    pass


@scenario(FEATURE, "Filter equipment by status")
def test_filter_status():
    pass


@scenario(FEATURE, "Search equipment by name or manufacturer")
def test_search():
    pass


@scenario(FEATURE, "Update equipment details")
def test_update():
    pass


@scenario(FEATURE, "Change equipment status to maintenance")
def test_maintenance():
    pass


@scenario(FEATURE, "Decommission equipment")
def test_decommission():
    pass


@scenario(FEATURE, "Soft-delete equipment")
def test_soft_delete():
    pass


@scenario(FEATURE, "Get equipment detail by ID")
def test_get_detail():
    pass


@scenario(FEATURE, "Assign equipment to a location")
def test_assign_location():
    pass


@scenario(FEATURE, "Add photos to equipment")
def test_add_photos():
    pass


@scenario(FEATURE, "Store VLM-extracted data with traceability")
def test_vlm_extraction():
    pass


# --- Shared state ---


@pytest.fixture
def ctx():
    """Shared context dict for passing data between steps."""
    return {}


# --- Given steps ---


@given(parsers.parse("{n:d} equipment items exist"), target_fixture="bulk_equipment")
def create_bulk_equipment(api, n):
    items = []
    for i in range(n):
        r = api.post(
            "/api/v1/equipment",
            json={"name": f"Device {i}", "category": "general"},
        )
        assert r.status_code in (200, 201), r.text
        items.append(r.json())
    return items


@given(
    parsers.parse('equipment "{name}" with category "{cat}" exists'),
    target_fixture="test_equipment",
)
def create_equipment_with_cat(api, name, cat):
    r = api.post(
        "/api/v1/equipment",
        json={"name": name, "category": cat},
    )
    assert r.status_code in (200, 201), r.text
    return r.json()


@given(
    parsers.parse('equipment "{name}" with status "{status}" exists'),
    target_fixture="test_equipment",
)
def create_equipment_with_status(api, name, status):
    r = api.post(
        "/api/v1/equipment",
        json={"name": name, "category": "general", "status": status},
    )
    assert r.status_code in (200, 201), r.text
    return r.json()


@given(
    parsers.parse('equipment "{name}" with manufacturer "{mfr}" exists'),
    target_fixture="test_equipment",
)
def create_equipment_with_mfr(api, name, mfr):
    r = api.post(
        "/api/v1/equipment",
        json={"name": name, "manufacturer": mfr},
    )
    assert r.status_code in (200, 201), r.text
    return r.json()


@given(
    parsers.parse('a storage location "{name}" exists'),
    target_fixture="test_location",
)
def create_location(db):
    from lab_manager.models.location import StorageLocation

    loc = StorageLocation(name="Room 6501E")
    db.add(loc)
    db.flush()
    return {"id": loc.id, "name": loc.name}


# --- When steps ---


@when(
    parsers.parse(
        'I create equipment "{name}" with category "{cat}" and manufacturer "{mfr}"'
    ),
    target_fixture="test_equipment",
)
def create_equipment(api, name, cat, mfr):
    r = api.post(
        "/api/v1/equipment",
        json={"name": name, "category": cat, "manufacturer": mfr},
    )
    assert r.status_code in (200, 201), r.text
    return r.json()


@when(
    parsers.parse("I list equipment with page {page:d} and page_size {size:d}"),
    target_fixture="list_response",
)
def list_equipment(api, page, size):
    r = api.get(f"/api/v1/equipment?page={page}&page_size={size}")
    assert r.status_code == 200, r.text
    return r.json()


@when(
    parsers.parse('I filter equipment by category "{cat}"'),
    target_fixture="list_response",
)
def filter_by_category(api, cat):
    r = api.get(f"/api/v1/equipment?category={cat}")
    assert r.status_code == 200, r.text
    return r.json()


@when(
    parsers.parse('I filter equipment by status "{status}"'),
    target_fixture="list_response",
)
def filter_by_status(api, status):
    r = api.get(f"/api/v1/equipment?status={status}")
    assert r.status_code == 200, r.text
    return r.json()


@when(
    parsers.parse('I search equipment for "{query}"'),
    target_fixture="list_response",
)
def search_equipment(api, query):
    r = api.get(f"/api/v1/equipment?search={query}")
    assert r.status_code == 200, r.text
    return r.json()


@when(
    parsers.parse('I update the equipment name to "{name}"'),
    target_fixture="test_equipment",
)
def update_name(api, test_equipment, name):
    r = api.patch(
        f"/api/v1/equipment/{test_equipment['id']}",
        json={"name": name},
    )
    assert r.status_code == 200, r.text
    return r.json()


@when(
    parsers.parse('I update the equipment status to "{status}"'),
    target_fixture="test_equipment",
)
def update_status(api, test_equipment, status):
    r = api.patch(
        f"/api/v1/equipment/{test_equipment['id']}",
        json={"status": status},
    )
    assert r.status_code == 200, r.text
    return r.json()


@when("I delete the equipment", target_fixture="test_equipment")
def delete_equipment(api, test_equipment):
    r = api.delete(f"/api/v1/equipment/{test_equipment['id']}")
    assert r.status_code == 200, r.text
    return r.json()


@when(
    parsers.parse(
        'I create equipment "{name}" with category "{cat}" and location "{loc_name}"'
    ),
    target_fixture="test_equipment",
)
def create_equipment_with_location(api, test_location, name, cat, loc_name):
    r = api.post(
        "/api/v1/equipment",
        json={
            "name": name,
            "category": cat,
            "location_id": test_location["id"],
        },
    )
    assert r.status_code in (200, 201), r.text
    return r.json()


@when(
    "I update the equipment photos with 2 photo paths", target_fixture="test_equipment"
)
def update_photos(api, test_equipment):
    r = api.patch(
        f"/api/v1/equipment/{test_equipment['id']}",
        json={
            "photos": [
                "/data/devices/IMG_3308.jpg",
                "/data/devices/IMG_3309.jpg",
            ]
        },
    )
    assert r.status_code == 200, r.text
    return r.json()


@when(
    parsers.parse('I create equipment "{name}" with extracted data from VLM'),
    target_fixture="test_equipment",
)
def create_with_vlm_data(api, name):
    r = api.post(
        "/api/v1/equipment",
        json={
            "name": name,
            "category": "two-photon",
            "manufacturer": "Bruker",
            "extracted_data": {
                "source_model": "gemini-3.1-flash-preview",
                "extraction_timestamp": "2026-03-17T09:00:00Z",
                "source_photo": "/data/devices/IMG_3488.jpg",
                "raw_fields": {
                    "system_id": "#5010",
                    "manufacturer": "Bruker",
                },
                "confidence": 0.95,
            },
        },
    )
    assert r.status_code in (200, 201), r.text
    return r.json()


# --- Then steps ---


@then(parsers.parse('the equipment should be created with status "{status}"'))
def check_created_status(test_equipment, status):
    assert test_equipment["status"] == status


@then(parsers.parse('the equipment name should be "{name}"'))
def check_name(test_equipment, name):
    assert test_equipment["name"] == name


@then(parsers.parse('the equipment manufacturer should be "{mfr}"'))
def check_manufacturer(test_equipment, mfr):
    assert test_equipment["manufacturer"] == mfr


@then(parsers.parse("I should get {n:d} equipment items"))
def check_count(list_response, n):
    assert len(list_response["items"]) == n


@then(parsers.parse("the total count should be {n:d}"))
def check_total(list_response, n):
    assert list_response["total"] == n


@then(parsers.parse("the page count should be {n:d}"))
def check_pages(list_response, n):
    assert list_response["pages"] == n


@then(parsers.parse('the equipment status should be "{status}"'))
def check_status(test_equipment, status):
    assert test_equipment["status"] == status


@then("I can retrieve the equipment by ID")
def check_get_by_id(api, test_equipment):
    r = api.get(f"/api/v1/equipment/{test_equipment['id']}")
    assert r.status_code == 200
    assert r.json()["id"] == test_equipment["id"]


@then("the equipment should have created_at and updated_at timestamps")
def check_timestamps(api, test_equipment):
    r = api.get(f"/api/v1/equipment/{test_equipment['id']}")
    data = r.json()
    assert data["created_at"] is not None
    assert data["updated_at"] is not None


@then("the equipment location_id should match the location")
def check_location(test_equipment, test_location):
    assert test_equipment["location_id"] == test_location["id"]


@then(parsers.parse("the equipment should have {n:d} photos"))
def check_photos(test_equipment, n):
    assert len(test_equipment["photos"]) == n


@then("the equipment extracted_data should contain the source model")
def check_extracted_model(test_equipment):
    assert "source_model" in test_equipment["extracted_data"]
    assert (
        test_equipment["extracted_data"]["source_model"] == "gemini-3.1-flash-preview"
    )


@then("the equipment extracted_data should contain the extraction timestamp")
def check_extracted_timestamp(test_equipment):
    assert "extraction_timestamp" in test_equipment["extracted_data"]


@then("the equipment extracted_data should contain the source photo path")
def check_extracted_photo(test_equipment):
    assert "source_photo" in test_equipment["extracted_data"]
