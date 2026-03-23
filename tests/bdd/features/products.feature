# Product CRUD, validation, and relationship management
Feature: Product Management
  As a lab manager in the lab
  I want to manage products through the full CRUD lifecycle
  So that I can track reagents, their vendors, and ordering history

  # --- Create ---

  Scenario: Create a product with required fields
    Given a vendor "Thermo Fisher" exists for products
    When I create a product with name "Trypsin 0.25%" catalog "25200056"
    Then the product should be created successfully
    And the product name should be "Trypsin 0.25%"
    And the product catalog_number should be "25200056"

  Scenario: Create a product with CAS number
    Given a vendor "Sigma-Aldrich" exists for products
    When I create a product with name "Sodium Chloride" catalog "S7653" and CAS "7647-14-5"
    Then the product should be created successfully
    And the product cas_number should be "7647-14-5"

  Scenario: Reject product with invalid CAS number format
    Given a vendor "Sigma-Aldrich" exists for products
    When I try to create a product with invalid CAS "INVALID-CAS"
    Then the product create response status should be 422

  Scenario: Reject product with empty name
    Given a vendor "Sigma-Aldrich" exists for products
    When I try to create a product with empty name
    Then the product create response status should be 422

  # --- Read ---

  Scenario: Get product by id
    Given a vendor "Fisher" exists for products
    And a product "DMEM Medium" with catalog "11965092" exists
    When I get the product by id
    Then the product detail name should be "DMEM Medium"

  Scenario: Get non-existent product returns 404
    When I get product with id 99999
    Then the product response status should be 404

  # --- List and filter ---

  Scenario: List products with vendor filter
    Given a vendor "VendorA" exists for products
    And a vendor "VendorB" exists for products
    And 3 products exist for "VendorA"
    And 2 products exist for "VendorB"
    When I list products for vendor "VendorA"
    Then I should see 3 products in the product list

  Scenario: Search products by name
    Given a vendor "SearchVendor" exists for products
    And the following products exist for search:
      | name               | catalog    |
      | Trypsin-EDTA 0.25% | 25200056   |
      | Trypan Blue Stain  | T8154      |
      | DMEM Medium        | 11965092   |
    When I search products with query "tryp"
    Then I should see 2 products in the product list

  # --- Update ---

  Scenario: Update product name
    Given a vendor "UpdateVendor" exists for products
    And a product "Old Product Name" with catalog "UPD-001" exists
    When I update the product name to "New Product Name"
    Then the product detail name should be "New Product Name"

  # --- Delete ---

  Scenario: Delete a product
    Given a vendor "DelVendor" exists for products
    And a product "Disposable Product" with catalog "DEL-001" exists
    When I delete the product
    Then the product delete response should be 204

  # --- Linked resources ---

  Scenario: List inventory for a product
    Given a vendor "InvVendor" exists for products
    And a product "Inventory Product" with catalog "INV-001" exists
    And 2 inventory items exist for the product
    When I list inventory for the product
    Then I should see 2 items in the product inventory

  Scenario: List order items for a product
    Given a vendor "OrdVendor" exists for products
    And a product "Ordered Product" with catalog "ORD-001" exists
    And 3 order items reference the product
    When I list orders for the product
    Then I should see 3 items in the product orders

  # --- Edge cases ---

  Scenario: Product with max length name
    Given a vendor "EdgeVendor" exists for products
    When I create a product with a 500-character name
    Then the product should be created successfully

  Scenario: List products when none exist for vendor
    Given a vendor "EmptyVendor" exists for products
    When I list products for vendor "EmptyVendor"
    Then I should see 0 products in the product list
