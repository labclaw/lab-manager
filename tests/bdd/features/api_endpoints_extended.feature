Feature: API Endpoints Extended
  As an API consumer
  I want complete API coverage
  So that I can integrate with all system features

  Background:
    Given I am authenticated as "admin"

  Scenario: Get all vendors
    Given 10 vendors exist
    When I GET /api/v1/vendors/
    Then I should receive 10 vendors
    And response should include pagination metadata

  Scenario: Create vendor
    When I POST /api/v1/vendors/ with:
      | name    | New Vendor  |
      | website | https://new.com |
    Then vendor should be created
    And response should include location header

  Scenario: Update vendor
    Given vendor "Sigma" exists
    When I PATCH /api/v1/vendors/1 with:
      | name    | Sigma-Aldrich |
    Then vendor should be updated
    And updated_at should change

  Scenario: Delete vendor
    Given vendor without products exists
    When I DELETE /api/v1/vendors/1
    Then vendor should be deleted
    And response should be 204

  Scenario: Get products with filtering
    Given products in categories:
      | category   | count |
      | chemical   | 5     |
      | consumable | 3     |
    When I GET /api/v1/products/?category=chemical
    Then I should receive 5 products

  Scenario: Get products with sorting
    Given products with various prices
    When I GET /api/v1/products/?sort_by=price&sort_dir=desc
    Then products should be sorted by price descending

  Scenario: Create order with items
    Given vendor "Sigma" exists
    When I POST /api/v1/orders/ with items:
      | product_id | quantity |
      | 1          | 10       |
      | 2          | 20       |
    Then order should be created
    And order items should be created

  Scenario: Update order status
    Given order with status "pending"
    When I PATCH /api/v1/orders/1 with:
      | status | approved |
    Then order status should be "approved"

  Scenario: Receive order
    Given order exists with items
    When I POST /api/v1/orders/1/receive
    Then order status should be "received"
    And inventory should be updated

  Scenario: Get inventory with location filter
    Given inventory in locations:
      | location  | count |
      | Freezer A | 5     |
      | Freezer B | 3     |
    When I GET /api/v1/inventory/?location_id=1
    Then I should receive 5 items

  Scenario: Consume inventory
    Given inventory item with quantity 100
    When I POST /api/v1/inventory/1/consume with:
      | quantity | 20 |
    Then inventory should have 80 units

  Scenario: Transfer inventory
    Given inventory in "Lab A"
    When I POST /api/v1/inventory/1/transfer with:
      | to_location_id | 2 |
      | quantity       | 50|
    Then 50 units should be in "Lab B"

  Scenario: Get document stats
    Given documents in various states:
      | status    | count |
      | pending   | 5     |
      | extracted | 3     |
      | approved  | 2     |
    When I GET /api/v1/documents/stats
    Then I should see counts by status

  Scenario: Review document
    Given document in "extracted" status
    When I POST /api/v1/documents/1/review with:
      | action     | approve |
      | reviewed_by| admin   |
    Then document should be "approved"

  Scenario: Search endpoint
    Given indexed data exists
    When I GET /api/search?q=reagent
    Then I should receive matching results
    And results should be ranked by relevance

  Scenario: Ask AI endpoint
    When I POST /api/v1/ask with:
      | question | What is my inventory value? |
    Then I should receive an answer
    And answer should include SQL explanation

  Scenario: Export inventory CSV
    Given inventory exists
    When I GET /api/v1/export/inventory.csv
    Then I should receive CSV file
    And headers should be correct

  Scenario: Health check
    When I GET /api/v1/health
    Then I should receive status 200
    And response should include database status

  Scenario: API versioning
    When I GET /api/v1/vendors/
    Then response should indicate API version
    And deprecated fields should be handled
