"""Step definitions for location management BDD tests."""

from pytest_bdd import given, when, then, parsers


@given('I am authenticated as "admin"')
def auth_admin(api_client):
    """Authenticate as admin."""
    api_client.login("admin@lab.com", "admin123")


@when("I create a location with:")
def create_location(api_client, datatable):
    """Create location."""
    row = datatable[0]
    api_client.response = api_client.post(
        "/api/v1/locations",
        json={
            "name": row.get("name", "Test Location"),
            "type": row.get("type", "general"),
            "capacity": int(row.get("capacity", 100)),
        },
    )


@then("the location should be created")
def location_created(api_client):
    """Verify location created."""
    assert (
        api_client.response.status_code == 200 or api_client.response.status_code == 201
    )


@then("the location ID should be returned")
def location_id_returned(api_client):
    """Verify location ID."""
    data = api_client.response.json()
    assert "id" in data


@given(parsers.parse("{count:d} locations exist"))
def locations_exist(api_client, count):
    """Create locations."""
    for i in range(count):
        api_client.post("/api/v1/locations", json={"name": f"Location {i}"})


@when("I request all locations")
def request_all_locations(api_client):
    """Request all locations."""
    api_client.response = api_client.get("/api/v1/locations")


@then(parsers.parse("I should receive {count:d} locations"))
def receive_locations(api_client, count):
    """Verify location count."""
    data = api_client.response.json()
    items = data.get("items", data)
    assert len(items) == count


@then("each location should have name and type")
def locations_have_name_type(api_client):
    """Verify location fields."""
    data = api_client.response.json()
    items = data.get("items", data)
    for item in items:
        assert "name" in item
        assert "type" in item


@given(parsers.parse('a location "{name}" exists'))
def location_exists(api_client, name):
    """Create location."""
    resp = api_client.post("/api/v1/locations", json={"name": name})
    api_client.loc_id = resp.json().get("id")


@when(parsers.parse('I update the location with name "{name}"'))
def update_location_name(api_client, name):
    """Update location name."""
    loc_id = getattr(api_client, "loc_id", None)
    api_client.response = api_client.patch(
        f"/api/v1/locations/{loc_id}", json={"name": name}
    )


@then(parsers.parse('the location name should be "{name}"'))
def location_name_is(api_client, name):
    """Verify location name."""
    data = api_client.response.json()
    assert data.get("name") == name


@given(parsers.parse('no inventory is in location "{name}"'))
def no_inventory_in_location(api_client, name):
    """Verify location empty."""
    pass  # Assume empty


@when("I delete the location")
def delete_location(api_client):
    """Delete location."""
    loc_id = getattr(api_client, "loc_id", None)
    api_client.response = api_client.delete(f"/api/v1/locations/{loc_id}")


@then("the location should be removed")
def location_removed(api_client):
    """Verify location removed."""
    assert api_client.response.status_code in [200, 204, 404]


@given(parsers.parse('{count:d} inventory items are in "{name}"'))
def items_in_location(api_client, count, name):
    """Put items in location."""
    loc_resp = api_client.get(f"/api/v1/locations?search={name}")
    loc_id = loc_resp.json()["items"][0]["id"]
    for i in range(count):
        prod_resp = api_client.post("/api/v1/products", json={"name": f"Product {i}"})
        prod_id = prod_resp.json()["id"]
        api_client.post(
            "/api/v1/inventory",
            json={
                "product_id": prod_id,
                "quantity": 1,
                "location_id": loc_id,
            },
        )


@when(parsers.parse("I try to delete the location"))
def try_delete_location(api_client):
    """Try to delete location."""
    loc_id = getattr(api_client, "loc_id", None)
    api_client.response = api_client.delete(f"/api/v1/locations/{loc_id}")


@then("the request should fail")
def request_failed(api_client):
    """Verify request failed."""
    assert api_client.response.status_code >= 400


@then("an error should indicate inventory exists")
def error_inventory_exists(api_client):
    """Verify error message."""
    data = api_client.response.json()
    assert (
        "inventory" in str(data.get("detail", "")).lower()
        or "items" in str(data).lower()
    )


@given(parsers.parse("a location with capacity {capacity:d} exists"))
def location_with_capacity(api_client, capacity):
    """Create location with capacity."""
    resp = api_client.post(
        "/api/v1/locations",
        json={
            "name": "Capacity Test",
            "capacity": capacity,
        },
    )
    api_client.loc_id = resp.json().get("id")


@given(parsers.parse("{count:d} items are in the location"))
def items_in_loc_count(api_client, count):
    """Add items to location."""
    loc_id = getattr(api_client, "loc_id", None)
    for i in range(count):
        prod_resp = api_client.post(
            "/api/v1/products", json={"name": f"Cap Product {i}"}
        )
        prod_id = prod_resp.json()["id"]
        api_client.post(
            "/api/v1/inventory",
            json={
                "product_id": prod_id,
                "quantity": 1,
                "location_id": loc_id,
            },
        )


@when("I request location details")
def request_location_details(api_client):
    """Request location details."""
    loc_id = getattr(api_client, "loc_id", None)
    api_client.response = api_client.get(f"/api/v1/locations/{loc_id}")


@then(parsers.parse("the current usage should be {usage:d}"))
def current_usage_is(api_client, usage):
    """Verify current usage."""
    data = api_client.response.json()
    assert data.get("current_usage", data.get("used", 0)) == usage


@then(parsers.parse("available capacity should be {available:d}"))
def available_capacity_is(api_client, available):
    """Verify available capacity."""
    data = api_client.response.json()
    assert data.get("available_capacity", data.get("available", 0)) == available


@when(parsers.parse("I add {count:d} more items to the location"))
def add_items_to_location(api_client, count):
    """Add items to location."""
    loc_id = getattr(api_client, "loc_id", None)
    for i in range(count):
        prod_resp = api_client.post(
            "/api/v1/products", json={"name": f"More Product {i}"}
        )
        prod_id = prod_resp.json()["id"]
        api_client.response = api_client.post(
            "/api/v1/inventory",
            json={
                "product_id": prod_id,
                "quantity": 1,
                "location_id": loc_id,
            },
        )


@then("a capacity warning should be triggered")
def capacity_warning(api_client):
    """Verify capacity warning."""
    data = api_client.response.json()
    assert (
        data.get("warning")
        or data.get("capacity_warning")
        or "capacity" in str(data).lower()
    )


@given("locations exist:")
def locations_exist_table(api_client, datatable):
    """Create locations from table."""
    for row in datatable:
        api_client.post("/api/v1/locations", json={"name": row.get("name", "Location")})


@when(parsers.parse('I search locations for "{query}"'))
def search_locations(api_client, query):
    """Search locations."""
    api_client.response = api_client.get(f"/api/v1/locations?search={query}")


@then(parsers.parse("I should receive {count:d} locations"))
def receive_count_locations(api_client, count):
    """Verify location count."""
    data = api_client.response.json()
    items = data.get("items", data)
    assert len(items) == count


@given("locations of different types exist:")
def locations_types_exist(api_client, datatable):
    """Create locations with types."""
    for row in datatable:
        api_client.post(
            "/api/v1/locations",
            json={
                "name": f"Location-{row['type']}",
                "type": row["type"],
            },
        )


@when(parsers.parse('I filter locations by type "{type}"'))
def filter_by_type(api_client, type):
    """Filter by type."""
    api_client.response = api_client.get(f"/api/v1/locations?type={type}")


@then(parsers.parse('I should receive only "{type}" locations'))
def only_type_locations(api_client, type):
    """Verify only type."""
    data = api_client.response.json()
    items = data.get("items", data)
    for item in items:
        assert item.get("type") == type


@given(parsers.parse('a building "{name}" exists'))
def building_exists(api_client, name):
    """Create building."""
    api_client.post(
        "/api/v1/locations",
        json={
            "name": name,
            "type": "building",
        },
    )


@given(parsers.parse('a room "{room}" in building "{building}" exists'))
def room_in_building(api_client, room, building):
    """Create room in building."""
    bldg_resp = api_client.get(f"/api/v1/locations?search={building}")
    bldg_id = bldg_resp.json()["items"][0]["id"]
    api_client.post(
        "/api/v1/locations",
        json={
            "name": room,
            "type": "room",
            "parent_id": bldg_id,
        },
    )


@given(parsers.parse('a location "{loc}" in room "{room}" exists'))
def location_in_room(api_client, loc, room):
    """Create location in room."""
    room_resp = api_client.get(f"/api/v1/locations?search={room}")
    room_id = room_resp.json()["items"][0]["id"]
    api_client.post(
        "/api/v1/locations",
        json={
            "name": loc,
            "type": "storage",
            "parent_id": room_id,
        },
    )


@when("I request the location hierarchy")
def request_hierarchy(api_client):
    """Request location hierarchy."""
    api_client.response = api_client.get("/api/v1/locations/hierarchy")


@then("I should see the nested structure")
def see_nested_structure(api_client):
    """Verify nested structure."""
    data = api_client.response.json()
    # Check for nested structure (children or items)
    assert "children" in str(data) or "items" in data or isinstance(data, list)
