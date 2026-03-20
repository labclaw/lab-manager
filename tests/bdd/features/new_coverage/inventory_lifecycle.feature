Feature: Inventory Lifecycle Management
  As a lab manager
  I want to track inventory through its complete lifecycle
  So that materials are properly accounted for

  Background:
    Given the database is clean
    And I am authenticated
    And a product "PBS Buffer" exists with quantity 100
    And a location "Freezer A" exists

  Scenario: Consume inventory reduces quantity
    Given inventory item exists with quantity 50
    When I consume 10 units
    Then the quantity should be 40
    And a consumption record should be created

  Scenario: Consume more than available
    Given inventory item exists with quantity 5
    When I try to consume 10 units
    Then the response status should be 422
    And the error should indicate insufficient quantity

  Scenario: Consume with negative quantity
    Given inventory item exists with quantity 50
    When I try to consume -5 units
    Then the response status should be 422

  Scenario: Consume with zero quantity
    Given inventory item exists with quantity 50
    When I try to consume 0 units
    Then the response status should be 422

  Scenario: Transfer inventory between locations
    Given inventory at location "Freezer A" with quantity 30
    And location "Freezer B" exists
    When I transfer 15 units to "Freezer B"
    Then location "Freezer A" should have 15 units
    And location "Freezer B" should have 15 units
    And a transfer record should be created

  Scenario: Transfer to same location
    Given inventory at location "Freezer A" with quantity 30
    When I try to transfer to same location
    Then the response status should be 400

  Scenario: Transfer more than available
    Given inventory at location "Freezer A" with quantity 10
    When I try to transfer 20 units
    Then the response status should be 422

  Scenario: Adjust inventory upward
    Given inventory item exists with quantity 50
    When I adjust quantity to 60 with reason "Found missing items"
    Then the quantity should be 60
    And an adjustment record should be created
    And adjustment reason should be "Found missing items"

  Scenario: Adjust inventory downward
    Given inventory item exists with quantity 50
    When I adjust quantity to 45 with reason "Damaged items"
    Then the quantity should be 45
    And an adjustment record should be created

  Scenario: Adjust without reason
    Given inventory item exists with quantity 50
    When I adjust quantity without providing reason
    Then the response status should be 422

  Scenario: Dispose of expired inventory
    Given inventory item exists with quantity 20 and status "expired"
    When I dispose of the inventory with reason "Expired"
    Then the inventory status should be "disposed"
    And a disposal record should be created

  Scenario: Dispose of non-expired inventory requires confirmation
    Given inventory item exists with quantity 20 and status "available"
    When I try to dispose without confirmation
    Then the response status should be 400

  Scenario: Dispose with confirmation
    Given inventory item exists with quantity 20 and status "available"
    When I dispose with confirmation and reason "Contaminated"
    Then the inventory status should be "disposed"

  Scenario: Open sealed inventory
    Given sealed inventory item exists with quantity 500
    When I open the container
    Then the container status should be "opened"
    And opened date should be recorded

  Scenario: Track inventory after opening
    Given opened inventory item with remaining 450
    When I consume 100 units
    Then remaining should be 350

  Scenario: Low stock alert trigger
    Given inventory item with minimum threshold 10
    When quantity falls below 10
    Then a low stock alert should be created
    And alert priority should be "medium"

  Scenario: Critical stock alert
    Given inventory item with critical threshold 5
    When quantity falls below 5
    Then a critical stock alert should be created
    And alert priority should be "high"

  Scenario: Inventory expiration check
    Given inventory item expiring in 7 days
    When expiration check runs
    Then an expiring alert should be created

  Scenario: Inventory already expired
    Given inventory item expired 3 days ago
    When I check the item
    Then status should be "expired"
    And item should be flagged for disposal

  Scenario: Get inventory history
    Given inventory item with 5 transactions exists
    When I request inventory history
    Then response should contain 5 transactions
    And transactions should be ordered by date descending

  Scenario: Filter history by transaction type
    Given inventory with 3 consumptions and 2 transfers
    When I request history filtered by "consumption"
    Then response should contain 3 records
    And all records should be type "consumption"

  Scenario: Bulk inventory adjustment
    Given 10 inventory items exist
    When I bulk adjust all quantities by +5
    Then all items should be increased by 5
    And 10 adjustment records should be created

  Scenario: Inventory search by lot number
    Given inventory with lot number "LOT-2026-001" exists
    When I search for lot "LOT-2026-001"
    Then the correct inventory should be returned

  Scenario: Inventory search by expiry date range
    Given inventory expiring at various dates exists
    When I search for items expiring between "2026-01-01" and "2026-03-31"
    Then only items in that range should be returned

  Scenario: Reserve inventory for order
    Given inventory item with quantity 50 exists
    When I reserve 20 units for order "ORD-123"
    Then available quantity should be 30
    And reserved quantity should be 20

  Scenario: Cannot reserve more than available
    Given inventory item with quantity 10 exists
    When I try to reserve 15 units
    Then the response status should be 422

  Scenario: Release reserved inventory
    Given inventory with 20 reserved units for order "ORD-123"
    When I release reservation for order "ORD-123"
    Then reserved quantity should be 0
    And available quantity should increase by 20

  Scenario: Consume from reserved inventory
    Given inventory with 20 reserved units for order "ORD-123"
    When I consume 15 reserved units for order "ORD-123"
    Then reserved quantity should be 5
    And total quantity should be reduced by 15
