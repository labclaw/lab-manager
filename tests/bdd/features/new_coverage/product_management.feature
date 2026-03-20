Feature: Product Management
  As a lab manager
  I want to manage product catalog
  So that I can track all available materials and supplies

  Background:
    Given the database is clean
    And I am authenticated

  Scenario: Create product with all fields
    Given vendor "Sigma" exists
    When I create product with:
      | name          | PBS Buffer     |
      | sku           | PBS-001        |
      | vendor        | Sigma          |
      | unit          | mL             |
      | unit_price    | 25.50          |
    Then the response status should be 201
    And product name should be "PBS Buffer"

  Scenario: Create product with minimal fields
    When I create product with:
      | name | Test Product |
      | sku  | TEST-001     |
    Then the response status should be 201

  Scenario: Create product with duplicate SKU
    Given product with SKU "SKU-001" exists
    When I create product with SKU "SKU-001"
    Then the response status should be 409

  Scenario: Create product without name
    When I create product without name
    Then the response status should be 422

  Scenario: Create product without SKU
    When I create product without SKU
    Then the response status should be 422

  Scenario: Create product with invalid price
    When I create product with:
      | name       | Invalid Price |
      | sku        | INV-001       |
      | unit_price | -10.00        |
    Then the response status should be 422

  Scenario: Get product by ID
    Given product with ID "prod-123" exists
    When I request product "prod-123"
    Then the response status should be 200
    And product ID should be "prod-123"

  Scenario: Get non-existent product
    When I request product "non-existent-id"
    Then the response status should be 404

  Scenario: List all products
    Given 50 products exist
    When I request all products
    Then the response should contain 50 products

  Scenario: List products with pagination
    Given 100 products exist
    When I request products with page 1 and page_size 20
    Then the response should contain 20 products
    And total count should be 100

  Scenario: Search products by name
    Given products "PBS Buffer", "PBS Tablets", "DMEM Media" exist
    When I search products for "PBS"
    Then the response should contain 2 products

  Scenario: Search products by SKU
    Given product with SKU "ABC-123-XYZ" exists
    When I search products for "ABC-123"
    Then the product should be in results

  Scenario: Filter products by vendor
    Given 10 products from "Sigma" exist
    And 15 products from "Fisher" exist
    When I request products from vendor "Sigma"
    Then the response should contain 10 products

  Scenario: Filter products by category
    Given 20 chemicals exist
    And 30 consumables exist
    When I request products with category "chemicals"
    Then the response should contain 20 products

  Scenario: Filter products by price range
    Given products with prices 10, 25, 50, 100 exist
    When I request products with price range 20-60
    Then the response should contain 2 products

  Scenario: Sort products by name
    Given products "Zinc", "Alpha", "Beta" exist
    When I request products sorted by name ascending
    Then products should be ordered Alpha, Beta, Zinc

  Scenario: Sort products by price
    Given products with prices 100, 25, 75 exist
    When I request products sorted by price descending
    Then products should be ordered 100, 75, 25

  Scenario: Update product name
    Given product with name "Old Name" exists
    When I update product name to "New Name"
    Then product name should be "New Name"

  Scenario: Update product price
    Given product with price 10.00 exists
    When I update product price to 15.00
    Then product price should be 15.00

  Scenario: Update product SKU
    Given product with SKU "OLD-001" exists
    When I update product SKU to "NEW-001"
    Then product SKU should be "NEW-001"

  Scenario: Cannot update to duplicate SKU
    Given product with SKU "SKU-001" exists
    And product with SKU "SKU-002" exists
    When I update product SKU to "SKU-001"
    Then the response status should be 409

  Scenario: Delete product with no inventory
    Given product with no inventory exists
    When I delete the product
    Then the response status should be 204
    And the product should no longer exist

  Scenario: Cannot delete product with inventory
    Given product with inventory exists
    When I try to delete the product
    Then the response status should be 400

  Scenario: Get product inventory
    Given product "PBS" with 50 units in inventory exists
    When I request product inventory
    Then the response should show 50 units

  Scenario: Get product orders
    Given product with 10 orders exists
    When I request product orders
    Then the response should contain 10 orders

  Scenario: Product with catalog number
    When I create product with:
      | name            | Antibody     |
      | sku             | AB-001       |
      | catalog_number  | CAT-12345   |
    Then catalog number should be "CAT-12345"

  Scenario: Product with CAS number
    When I create product with:
      | name        | Ethanol     |
      | sku         | ETH-001     |
      | cas_number  | 64-17-5     |
    Then CAS number should be "64-17-5"

  Scenario: Product with storage requirements
    When I create product with:
      | name              | Enzyme      |
      | sku               | ENZ-001     |
      | storage_temp_min  | -20         |
      | storage_temp_max  | -15         |
    Then storage requirements should be recorded

  Scenario: Product with hazard information
    When I create product with:
      | name           | Acetone     |
      | sku            | ACE-001     |
      | hazard_class   | Flammable   |
    Then hazard class should be "Flammable"

  Scenario: Bulk import products
    Given CSV with 50 products
    When I import products from CSV
    Then 50 products should be created
    And import report should show success

  Scenario: Bulk import with errors
    Given CSV with 10 valid and 3 invalid products
    When I import products from CSV
    Then 10 products should be created
    And 3 errors should be reported

  Scenario: Export products
    Given 75 products exist
    When I export products to CSV
    Then the response content type should be "text/csv"
    And CSV should have 76 rows

  Scenario: Product image upload
    Given product exists
    When I upload product image "product.jpg"
    Then the response status should be 201
    And product should have image

  Scenario: Product image deletion
    Given product with image exists
    When I delete product image
    Then the response status should be 204
    And product should not have image

  Scenario: Product alternative suggestions
    Given product "PBS" exists
    And product "PBS Alternative" exists
    When I request alternatives for "PBS"
    Then "PBS Alternative" should be suggested

  Scenario: Product usage statistics
    Given product used in 20 orders exists
    When I request product statistics
    Then total orders should be 20
    And total spent should be calculated

  Scenario: Mark product as deprecated
    Given active product exists
    When I mark product as deprecated
    Then product status should be "deprecated"
    And product should not appear in search

  Scenario: Reactivate deprecated product
    Given deprecated product exists
    When I reactivate product
    Then product status should be "active"
    And product should appear in search

  Scenario: Product tags
    Given product exists
    When I add tags "antibody, primary, rabbit"
    Then product should have 3 tags

  Scenario: Search by tag
    Given product with tag "antibody" exists
    And product with tag "buffer" exists
    When I search products with tag "antibody"
    Then only tagged products should be returned

  Scenario: Product notes
    Given product exists
    When I add note "Requires cold chain shipping"
    Then product note should be recorded

  Scenario: Product clone
    Given product "PBS" exists
    When I clone product "PBS"
    Then a new product should be created
    And new product should have same properties
    And new product should have different SKU

  Scenario: Product minimum order quantity
    When I create product with:
      | name                   | Bulk Chemical |
      | sku                    | BULK-001      |
      | minimum_order_quantity | 10            |
    Then minimum order quantity should be 10

  Scenario: Product lead time
    When I create product with:
      | name       | Custom Reagent |
      | sku        | CUST-001       |
      | lead_days  | 14             |
    Then lead time should be 14 days
