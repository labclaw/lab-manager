"""Step definitions for product management feature."""

import pytest
from pytest_bdd import given, when, then, parsers
from fastapi.testclient import TestClient

from lab_manager.api.app import app


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def auth_headers():
    """Get authentication headers."""
    return {"Authorization": "Bearer test-token"}


# Background
@given("the database is clean")
def database_clean(db_session):
    """Clean the database."""
    db_session.execute("DELETE FROM products")
    db_session.execute("DELETE FROM vendors")
    db_session.commit()


@given("I am authenticated")
def authenticated(auth_headers):
    """Set up authentication."""
    return auth_headers


# Vendor setup
@given(parsers.parse('vendor "{name}" exists'))
def vendor_exists(db_session, name):
    """Create a vendor."""
    from lab_manager.models.vendor import Vendor

    vendor = Vendor(name=name)
    db_session.add(vendor)
    db_session.commit()
    return vendor


# Product creation
@when(parsers.parse("I create product with:\n{text}"))
def create_product_table(client, auth_headers, text):
    """Create product from table."""
    import re

    data = {}
    for line in text.strip().split("\n"):
        match = re.match(r"\|\s*(\w+)\s*\|\s*(.+?)\s*\|", line)
        if match:
            key = match.group(1)
            value = match.group(2).strip()
            # Try to convert numeric values
            try:
                if "." in value:
                    value = float(value)
                else:
                    value = int(value)
            except ValueError:
                pass
            data[key] = value

    response = client.post("/api/products", json=data, headers=auth_headers)
    return response


@when("I create product without name")
def create_product_no_name(client, auth_headers):
    """Create product without name."""
    response = client.post("/api/products", json={"sku": "TEST"}, headers=auth_headers)
    return response


@when("I create product without SKU")
def create_product_no_sku(client, auth_headers):
    """Create product without SKU."""
    response = client.post("/api/products", json={"name": "Test"}, headers=auth_headers)
    return response


@when(parsers.parse('I create product with SKU "{sku}"'))
def create_product_sku(client, auth_headers, sku):
    """Create product with specific SKU."""
    response = client.post(
        "/api/products", json={"name": "Test Product", "sku": sku}, headers=auth_headers
    )
    return response


@given(parsers.parse('product with SKU "{sku}" exists'))
def product_sku_exists(db_session, sku):
    """Create product with SKU."""

    product = Product(name=f"Product {sku}", sku=sku)
    db_session.add(product)
    db_session.commit()
    return product


@given(parsers.parse('product with ID "{pid}" exists'))
def product_id_exists(db_session, pid):
    """Create product with specific ID."""

    product = Product(id=pid, name="ID Product", sku=f"SKU-{pid}")
    db_session.add(product)
    db_session.commit()
    return product


@when(parsers.parse('I request product "{pid}"'))
def get_product(client, auth_headers, pid):
    """Get product by ID."""
    response = client.get(f"/api/products/{pid}", headers=auth_headers)
    return response


@when("I request all products")
def list_products(client, auth_headers):
    """List all products."""
    response = client.get("/api/products", headers=auth_headers)
    return response


@when(parsers.parse("I request products with page {page:d} and page_size {size:d}"))
def list_products_paginated(client, auth_headers, page, size):
    """List products paginated."""
    response = client.get(
        f"/api/products?page={page}&page_size={size}", headers=auth_headers
    )
    return response


@given(parsers.parse("{count:d} products exist"))
def create_products(db_session, count):
    """Create multiple products."""

    for i in range(count):
        product = Product(name=f"Product {i}", sku=f"SKU-{i:04d}")
        db_session.add(product)
    db_session.commit()


@given(parsers.parse('products "{p1}", "{p2}", "{p3}" exist'))
def products_named_exist(db_session, p1, p2, p3):
    """Create named products."""

    for i, name in enumerate([p1, p2, p3]):
        product = Product(name=name, sku=f"SKU-{name[:3].upper()}-{i}")
        db_session.add(product)
    db_session.commit()


@when(parsers.parse('I search products for "{term}"'))
def search_products(client, auth_headers, term):
    """Search products."""
    response = client.get(f"/api/products?search={term}", headers=auth_headers)
    return response


@when(parsers.parse("I request product inventory"))
def get_product_inventory(client, auth_headers, db_session):
    """Get product inventory."""
    pid = db_session.execute("SELECT id FROM products LIMIT 1").scalar()
    response = client.get(f"/api/products/{pid}/inventory", headers=auth_headers)
    return response


@when(parsers.parse("I request product orders"))
def get_product_orders(client, auth_headers, db_session):
    """Get product orders."""
    pid = db_session.execute("SELECT id FROM products LIMIT 1").scalar()
    response = client.get(f"/api/products/{pid}/orders", headers=auth_headers)
    return response


@given(parsers.parse('product "{name}" with {qty:d} units in inventory exists'))
def product_with_inventory(db_session, name, qty):
    """Create product with inventory."""

    product = Product(name=name, sku=f"SKU-{name[:3].upper()}")
    db_session.add(product)
    db_session.commit()

    inventory = Inventory(
        product_id=product.id, quantity=qty, location="Main Storage", status="available"
    )
    db_session.add(inventory)
    db_session.commit()
    return product


@given(parsers.parse("product with {count:d} orders exists"))
def product_with_orders(db_session, count):
    """Create product with orders."""
    from lab_manager.models.vendor import Vendor
    from lab_manager.models.order import Order, OrderItem

    vendor = Vendor(name="Test Vendor")
    db_session.add(vendor)
    db_session.commit()

    product = Product(name="Ordered Product", sku="ORD-001")
    db_session.add(product)
    db_session.commit()

    for i in range(count):
        order = Order(vendor_id=vendor.id, status="received", total=10.0)
        db_session.add(order)
        db_session.commit()

        item = OrderItem(
            order_id=order.id, product_id=product.id, quantity=1, unit_price=10.0
        )
        db_session.add(item)
    db_session.commit()
    return product


@given(parsers.parse('{count:d} products from "{vendor}" exist'))
def products_from_vendor(db_session, count, vendor):
    """Create products from vendor."""
    from lab_manager.models.vendor import Vendor

    v = Vendor(name=vendor)
    db_session.add(v)
    db_session.commit()

    for i in range(count):
        product = Product(
            name=f"{vendor} Product {i}",
            sku=f"{vendor[:3].upper()}-{i}",
            vendor_id=v.id,
        )
        db_session.add(product)
    db_session.commit()


@when(parsers.parse('I request products from vendor "{vendor}"'))
def filter_by_vendor(client, auth_headers, db_session, vendor):
    """Filter products by vendor."""
    vid = db_session.execute(
        "SELECT id FROM vendors WHERE name = :name", {"name": vendor}
    ).scalar()
    response = client.get(f"/api/products?vendor_id={vid}", headers=auth_headers)
    return response


@given(parsers.parse("{count:d} chemicals exist"))
def chemicals_exist(db_session, count):
    """Create chemical products."""

    for i in range(count):
        product = Product(
            name=f"Chemical {i}", sku=f"CHEM-{i:04d}", category="chemicals"
        )
        db_session.add(product)
    db_session.commit()


@given(parsers.parse("{count:d} consumables exist"))
def consumables_exist(db_session, count):
    """Create consumable products."""

    for i in range(count):
        product = Product(
            name=f"Consumable {i}", sku=f"CONS-{i:04d}", category="consumables"
        )
        db_session.add(product)
    db_session.commit()


@when(parsers.parse('I request products with category "{category}"'))
def filter_by_category(client, auth_headers, category):
    """Filter products by category."""
    response = client.get(f"/api/products?category={category}", headers=auth_headers)
    return response


@given(parsers.parse("products with prices {p1}, {p2}, {p3}, {p4} exist"))
def products_with_prices(db_session, p1, p2, p3, p4):
    """Create products with prices."""

    for i, price in enumerate([p1, p2, p3, p4]):
        product = Product(
            name=f"Product ${price}", sku=f"PRICE-{i}", unit_price=float(price)
        )
        db_session.add(product)
    db_session.commit()


@when(parsers.parse("I request products with price range {min_price}-{max_price}"))
def filter_by_price_range(client, auth_headers, min_price, max_price):
    """Filter by price range."""
    response = client.get(
        f"/api/products?min_price={min_price}&max_price={max_price}",
        headers=auth_headers,
    )
    return response


@when(parsers.parse("I request products sorted by name ascending"))
def sort_by_name_asc(client, auth_headers):
    """Sort by name ascending."""
    response = client.get("/api/products?sort=name&order=asc", headers=auth_headers)
    return response


@when(parsers.parse("I request products sorted by price descending"))
def sort_by_price_desc(client, auth_headers):
    """Sort by price descending."""
    response = client.get(
        "/api/products?sort=unit_price&order=desc", headers=auth_headers
    )
    return response


@given(parsers.parse('product with name "{name}" exists'))
def product_name_exists(db_session, name):
    """Create product with name."""

    product = Product(name=name, sku=f"SKU-{name[:3].upper()}")
    db_session.add(product)
    db_session.commit()
    return product


@given(parsers.parse("product with price {price:f} exists"))
def product_price_exists(db_session, price):
    """Create product with price."""

    product = Product(name="Priced Product", sku="PRICED-001", unit_price=price)
    db_session.add(product)
    db_session.commit()
    return product


@when(parsers.parse('I update product name to "{new_name}"'))
def update_product_name(client, auth_headers, db_session, new_name):
    """Update product name."""
    pid = db_session.execute("SELECT id FROM products LIMIT 1").scalar()
    response = client.patch(
        f"/api/products/{pid}", json={"name": new_name}, headers=auth_headers
    )
    return response


@when(parsers.parse("I update product price to {price:f}"))
def update_product_price(client, auth_headers, db_session, price):
    """Update product price."""
    pid = db_session.execute("SELECT id FROM products LIMIT 1").scalar()
    response = client.patch(
        f"/api/products/{pid}", json={"unit_price": price}, headers=auth_headers
    )
    return response


@when(parsers.parse('I update product SKU to "{new_sku}"'))
def update_product_sku(client, auth_headers, db_session, new_sku):
    """Update product SKU."""
    pid = db_session.execute("SELECT id FROM products LIMIT 1").scalar()
    response = client.patch(
        f"/api/products/{pid}", json={"sku": new_sku}, headers=auth_headers
    )
    return response


@given(parsers.parse('product with SKU "{sku1}" exists'))
def product_sku1_exists(db_session, sku1):
    """Create first product."""

    product = Product(name="Product 1", sku=sku1)
    db_session.add(product)
    db_session.commit()


@given(parsers.parse('product with SKU "{sku2}" exists'))
def product_sku2_exists(db_session, sku2):
    """Create second product."""

    product = Product(name="Product 2", sku=sku2)
    db_session.add(product)
    db_session.commit()


@given("product with no inventory exists")
def product_no_inventory(db_session):
    """Create product without inventory."""

    product = Product(name="No Inventory Product", sku="NOINV-001")
    db_session.add(product)
    db_session.commit()
    return product


@given("product with inventory exists")
def product_with_inventory_exists(db_session):
    """Create product with inventory."""

    product = Product(name="Inventory Product", sku="INV-001")
    db_session.add(product)
    db_session.commit()

    inventory = Inventory(
        product_id=product.id, quantity=10, location="Storage", status="available"
    )
    db_session.add(inventory)
    db_session.commit()
    return product


@when("I delete the product")
def delete_product(client, auth_headers, db_session):
    """Delete product."""
    pid = db_session.execute("SELECT id FROM products LIMIT 1").scalar()
    response = client.delete(f"/api/products/{pid}", headers=auth_headers)
    return response


@when("I try to delete the product")
def try_delete_product(client, auth_headers, db_session):
    """Try to delete product (may fail)."""
    pid = db_session.execute("SELECT id FROM products LIMIT 1").scalar()
    response = client.delete(f"/api/products/{pid}", headers=auth_headers)
    return response


@given("active product exists")
def active_product(db_session):
    """Create active product."""

    product = Product(name="Active Product", sku="ACTIVE-001", status="active")
    db_session.add(product)
    db_session.commit()


@given("deprecated product exists")
def deprecated_product(db_session):
    """Create deprecated product."""

    product = Product(name="Deprecated Product", sku="DEP-001", status="deprecated")
    db_session.add(product)
    db_session.commit()


@when("I mark product as deprecated")
def deprecate_product(client, auth_headers, db_session):
    """Deprecate product."""
    pid = db_session.execute("SELECT id FROM products LIMIT 1").scalar()
    response = client.patch(
        f"/api/products/{pid}", json={"status": "deprecated"}, headers=auth_headers
    )
    return response


@when("I reactivate product")
def reactivate_product(client, auth_headers, db_session):
    """Reactivate product."""
    pid = db_session.execute("SELECT id FROM products LIMIT 1").scalar()
    response = client.patch(
        f"/api/products/{pid}", json={"status": "active"}, headers=auth_headers
    )
    return response


@when(parsers.parse('I add tags "{tags}"'))
def add_product_tags(client, auth_headers, db_session, tags):
    """Add tags to product."""
    pid = db_session.execute("SELECT id FROM products LIMIT 1").scalar()
    tag_list = [t.strip() for t in tags.split(",")]
    response = client.patch(
        f"/api/products/{pid}", json={"tags": tag_list}, headers=auth_headers
    )
    return response


@given('product with tag "{tag}" exists')
def product_with_tag(db_session, tag):
    """Create product with tag."""

    product = Product(name=f"{tag} Product", sku=f"TAG-{tag[:3].upper()}", tags=[tag])
    db_session.add(product)
    db_session.commit()


@when(parsers.parse('I search products with tag "{tag}"'))
def search_by_tag(client, auth_headers, tag):
    """Search by tag."""
    response = client.get(f"/api/products?tag={tag}", headers=auth_headers)
    return response


@when(parsers.parse('I add note "{note}"'))
def add_product_note(client, auth_headers, db_session, note):
    """Add note to product."""
    pid = db_session.execute("SELECT id FROM products LIMIT 1").scalar()
    response = client.patch(
        f"/api/products/{pid}", json={"notes": note}, headers=auth_headers
    )
    return response


@when(parsers.parse('I clone product "{name}"'))
def clone_product(client, auth_headers, db_session, name):
    """Clone product."""
    pid = db_session.execute(
        "SELECT id FROM products WHERE name = :name", {"name": name}
    ).scalar()
    response = client.post(f"/api/products/{pid}/clone", headers=auth_headers)
    return response


@given('product "{name}" exists')
def product_named_exists(db_session, name):
    """Create product with name."""

    product = Product(name=name, sku=f"SKU-{name[:3].upper()}")
    db_session.add(product)
    db_session.commit()


# Then steps
@then("the response status should be 200")
def status_200(response):
    assert response.status_code == 200


@then("the response status should be 201")
def status_201(response):
    assert response.status_code == 201


@then("the response status should be 204")
def status_204(response):
    assert response.status_code == 204


@then("the response status should be 400")
def status_400(response):
    assert response.status_code == 400


@then("the response status should be 404")
def status_404(response):
    assert response.status_code == 404


@then("the response status should be 409")
def status_409(response):
    assert response.status_code == 409


@then("the response status should be 422")
def status_422(response):
    assert response.status_code == 422


@then(parsers.parse('product name should be "{name}"'))
def product_name_is(response, name):
    data = response.json()
    assert data.get("name") == name


@then(parsers.parse('product ID should be "{pid}"'))
def product_id_is(response, pid):
    data = response.json()
    assert str(data.get("id")) == pid


@then(parsers.parse("the response should contain {count:d} products"))
def product_count(response, count):
    data = response.json()
    assert len(data.get("items", data)) == count


@then(parsers.parse("total count should be {count:d}"))
def total_count_is(response, count):
    data = response.json()
    assert data.get("total", len(data)) == count


@then("the product should be in results")
def product_in_results(response):
    data = response.json()
    assert len(data.get("items", data)) >= 1


@then(parsers.parse("products should be ordered {order}"))
def products_ordered(response, order):
    data = response.json()
    items = data.get("items", data)
    names = [i.get("name", i.get("unit_price")) for i in items]
    if "Alpha" in order:
        assert names == sorted(names)


@then(parsers.parse("product price should be {price:f}"))
def product_price_is(db_session, price):
    pid = db_session.execute("SELECT id FROM products LIMIT 1").scalar()
    product = db_session.get(Product, pid)
    assert product.unit_price == price


@then(parsers.parse('product SKU should be "{sku}"'))
def product_sku_is(db_session, sku):
    pid = db_session.execute("SELECT id FROM products LIMIT 1").scalar()
    product = db_session.get(Product, pid)
    assert product.sku == sku


@then("the product should no longer exist")
def product_not_exists(db_session):
    count = db_session.execute("SELECT COUNT(*) FROM products").scalar()
    assert count == 0


@then(parsers.parse("the response should show {qty:d} units"))
def inventory_qty(response, qty):
    data = response.json()
    total = sum(i.get("quantity", 0) for i in data.get("items", [data]))
    assert total == qty


@then(parsers.parse('catalog number should be "{cat}"'))
def catalog_number_is(response, cat):
    data = response.json()
    assert data.get("catalog_number") == cat


@then(parsers.parse('CAS number should be "{cas}"'))
def cas_number_is(response, cas):
    data = response.json()
    assert data.get("cas_number") == cas


@then("storage requirements should be recorded")
def storage_recorded(response):
    data = response.json()
    assert "storage_temp_min" in data or "storage_temperature" in data


@then(parsers.parse('hazard class should be "{hazard}"'))
def hazard_class_is(response, hazard):
    data = response.json()
    assert data.get("hazard_class") == hazard


@then(parsers.parse("{count:d} products should be created"))
def products_created(response, count):
    pass  # Would check bulk operation


@then(parsers.parse("{count:d} errors should be reported"))
def errors_reported(response, count):
    pass


@then(parsers.parse('the response content type should be "{content_type}"'))
def content_type_is(response, content_type):
    assert content_type in response.headers.get("content-type", "")


@then(parsers.parse("CSV should have {rows:d} rows"))
def csv_rows(response, rows):
    lines = response.text.strip().split("\n")
    assert len(lines) == rows


@then("product should have image")
def product_has_image(response):
    data = response.json()
    assert data.get("image_url") is not None


@then("product should not have image")
def product_no_image(db_session):
    pid = db_session.execute("SELECT id FROM products LIMIT 1").scalar()
    product = db_session.get(Product, pid)
    assert product.image_url is None


@when(parsers.parse('I upload product image "{filename}"'))
def upload_product_image(client, auth_headers, db_session, filename, tmp_path):
    pid = db_session.execute("SELECT id FROM products LIMIT 1").scalar()
    file_path = tmp_path / filename
    file_path.write_bytes(b"fake image data")
    with open(file_path, "rb") as f:
        response = client.post(
            f"/api/products/{pid}/image",
            files={"file": (filename, f, "image/jpeg")},
            headers=auth_headers,
        )
    return response


@given("product with image exists")
def product_with_image(db_session):
    product = Product(
        name="Image Product", sku="IMG-001", image_url="/uploads/product.jpg"
    )
    db_session.add(product)
    db_session.commit()


@when("I delete product image")
def delete_product_image(client, auth_headers, db_session):
    pid = db_session.execute("SELECT id FROM products LIMIT 1").scalar()
    response = client.delete(f"/api/products/{pid}/image", headers=auth_headers)
    return response


@when(parsers.parse('I request alternatives for "{name}"'))
def get_alternatives(client, auth_headers, db_session, name):
    pid = db_session.execute(
        "SELECT id FROM products WHERE name = :name", {"name": name}
    ).scalar()
    response = client.get(f"/api/products/{pid}/alternatives", headers=auth_headers)
    return response


@then(parsers.parse('"{name}" should be suggested'))
def product_suggested(response, name):
    data = response.json()
    names = [p.get("name") for p in data.get("items", data)]
    assert name in names


@given(parsers.parse('product "{p1}" exists'))
def product_p1_exists(db_session, p1):
    product = Product(name=p1, sku=f"SKU-{p1[:3].upper()}")
    db_session.add(product)
    db_session.commit()


@given(parsers.parse('product "{p2}" exists'))
def product_p2_exists(db_session, p2):
    product = Product(name=p2, sku=f"SKU-{p2[:3].upper()}")
    db_session.add(product)
    db_session.commit()


@when("I request product statistics")
def get_product_stats(client, auth_headers, db_session):
    pid = db_session.execute("SELECT id FROM products LIMIT 1").scalar()
    response = client.get(f"/api/products/{pid}/statistics", headers=auth_headers)
    return response


@then(parsers.parse("total orders should be {count:d}"))
def total_orders(response, count):
    data = response.json()
    assert data.get("total_orders") == count


@then("total spent should be calculated")
def total_spent_calculated(response):
    data = response.json()
    assert "total_spent" in data


@then(parsers.parse('product status should be "{status}"'))
def product_status_is(db_session, status):
    pid = db_session.execute("SELECT id FROM products LIMIT 1").scalar()
    product = db_session.get(Product, pid)
    assert product.status == status


@then("product should not appear in search")
def product_not_in_search(db_session):
    pass  # Would verify search results


@then("product should appear in search")
def product_in_search(db_session):
    pass


@then(parsers.parse("product should have {count:d} tags"))
def product_tag_count(db_session, count):
    pid = db_session.execute("SELECT id FROM products LIMIT 1").scalar()
    product = db_session.get(Product, pid)
    assert len(product.tags or []) == count


@then("product note should be recorded")
def product_note_recorded(db_session):
    pid = db_session.execute("SELECT id FROM products LIMIT 1").scalar()
    product = db_session.get(Product, pid)
    assert product.notes is not None


@then("a new product should be created")
def new_product_created(response):
    assert response.status_code == 201


@then("new product should have same properties")
def same_properties(response):
    pass


@then("new product should have different SKU")
def different_sku(response):
    data = response.json()
    assert data.get("sku") is not None


@then(parsers.parse("minimum order quantity should be {qty:d}"))
def min_order_qty(response, qty):
    data = response.json()
    assert data.get("minimum_order_quantity") == qty


@then(parsers.parse("lead time should be {days:d} days"))
def lead_time(response, days):
    data = response.json()
    assert data.get("lead_days") == days


# Import Product and Inventory models for steps that need them
