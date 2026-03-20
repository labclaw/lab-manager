Feature: Edge Cases Inventory
  As a system
  I want to handle inventory edge cases
  So that data remains consistent

  Background:
    Given I am authenticated as "admin"

  Scenario: Zero quantity handling
    Given inventory with quantity 0
    When I attempt to consume
    Then operation should fail
    And error should indicate no stock available

  Scenario: Negative quantity prevention
    When I set inventory to negative quantity
    Then operation should be rejected
    And constraint error should be returned

  Scenario: Very large quantity
    When I set quantity to 999999999999
    Then system should handle gracefully
    And no overflow should occur

  Scenario: Decimal quantities
    Given product measured in "mL"
    When I consume 0.5 mL
    Then inventory should decrease by 0.5
    And precision should be maintained

  Scenario: Unicode in lot number
    When I create inventory with lot "LOT-αβγ-001"
    Then lot number should be stored correctly
    And search should work with unicode

  Scenario: Empty lot number
    When I create inventory without lot number
    Then lot number should be null
    And record should be valid

  Scenario: Duplicate lot number same product
    Given inventory with lot "LOT-001" for product A
    When I create another with lot "LOT-001" for product A
    Then warning should be issued
    Or creation should proceed with warning

  Scenario: Expiration date in past
    When I create inventory expired yesterday
    Then warning should be issued
    And inventory should be flagged as expired

  Scenario: Expiration date very far future
    When I set expiration to year 2099
    Then operation should succeed
    And no premature alerts should trigger

  Scenario: Inventory at multiple locations
    Given product at 3 locations
    When I view total quantity
    Then total should be sum of all locations
    And breakdown by location should be available

  Scenario: Location deletion with inventory
    Given location has 5 inventory items
    When I delete location
    Then operation should be blocked
    Or inventory should be transferred first

  Scenario: Product deletion with inventory
    Given product has active inventory
    When I delete product
    Then operation should be blocked
    And error should explain dependency

  Scenario: Inventory search with special chars
    When I search for lot "LOT/001"
    Then search should work correctly
    And no SQL injection should occur

  Scenario: Inventory import with duplicates
    Given import contains duplicate lot numbers
    When import processes
    Then duplicates should be handled
    And only valid records should import

  Scenario: Inventory snapshot consistency
    Given inventory being updated
    When I take snapshot
    Then snapshot should be point-in-time consistent
    And concurrent updates should not affect snapshot
