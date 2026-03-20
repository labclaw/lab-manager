Feature: Inventory Lifecycle Management
  As a lab manager
  I want to manage inventory item lifecycle (consume, transfer, adjust, dispose)
  So that I can track all inventory changes accurately

  Background:
    Given I am authenticated as "admin"
    And a vendor "Sigma-Aldrich" exists
    And a product "PBS Buffer" exists for vendor "Sigma-Aldrich"
    And an inventory item exists for product "PBS Buffer" with quantity 100

  Scenario: Consume inventory item
    Given an inventory item "PBS-001" has quantity 100
    When I consume 20 units of inventory item "PBS-001"
    Then the inventory item quantity should be 80
    And a consumption log entry should exist

  Scenario: Consume more than available quantity
    Given an inventory item "PBS-001" has quantity 10
    When I try to consume 20 units of inventory item "PBS-001"
    Then the request should fail with error "Insufficient quantity"
    And the inventory item quantity should remain 10

  Scenario: Transfer inventory between locations
    Given a location "Freezer A" exists
    And a location "Freezer B" exists
    And an inventory item "PBS-001" is in location "Freezer A"
    When I transfer inventory item "PBS-001" to location "Freezer B"
    Then the inventory item should be in location "Freezer B"
    And a transfer log entry should exist

  Scenario: Transfer to non-existent location
    Given an inventory item "PBS-001" is in location "Freezer A"
    When I try to transfer inventory item "PBS-001" to non-existent location
    Then the request should fail with error "Location not found"

  Scenario: Adjust inventory quantity
    Given an inventory item "PBS-001" has quantity 100
    When I adjust inventory item "PBS-001" quantity to 95 with reason "Broken container"
    Then the inventory item quantity should be 95
    And an adjustment log entry should exist with reason "Broken container"

  Scenario: Dispose inventory item
    Given an inventory item "PBS-001" has quantity 50
    When I dispose inventory item "PBS-001" with reason "Expired"
    Then the inventory item status should be "disposed"
    And a disposal log entry should exist with reason "Expired"

  Scenario: Open sealed inventory item
    Given an inventory item "PBS-001" is sealed
    When I open inventory item "PBS-001"
    Then the inventory item should be marked as opened
    And the opened_at timestamp should be set
    And an open log entry should exist

  Scenario: View consumption history
    Given I consumed 10 units of inventory item "PBS-001" yesterday
    And I consumed 5 units of inventory item "PBS-001" today
    When I view consumption history for inventory item "PBS-001"
    Then I should see 2 consumption entries
    And the entries should be ordered by date descending

  Scenario: Low stock alert after consumption
    Given an inventory item "PBS-001" has quantity 15
    And the low stock threshold is 20
    When I consume 5 units of inventory item "PBS-001"
    Then a low stock alert should be created
    And the alert should reference inventory item "PBS-001"
