# Edge cases and additional scenarios for inventory management
Feature: Inventory Edge Cases
  As a lab scientist in the lab
  I want robust error handling for inventory operations
  So that inventory data stays accurate under all conditions

  # --- Not found ---

  Scenario: Get non-existent inventory item returns 404
    When I get inventory item with id 99999
    Then the inventory response status should be 404

  Scenario: Consume from non-existent item returns 404
    When I try to consume 1 from inventory item 99999
    Then the inventory response status should be 404

  # --- Validation ---

  Scenario: Cannot consume zero quantity
    Given an inventory test item with quantity 10 exists
    When I try to consume 0 from the test item
    Then the inventory response status should be 422

  Scenario: Cannot adjust to negative quantity
    Given an inventory test item with quantity 10 exists
    When I try to adjust the test item to -5
    Then the inventory response status should be 422

  Scenario: Cannot open an already-opened item
    Given an inventory test item with quantity 10 exists
    And the test item has been opened
    When I try to open the test item again
    Then the inventory response status should be 422

  Scenario: Cannot consume from disposed item
    Given an inventory test item with quantity 10 exists
    And the test item has been disposed
    When I try to consume 1 from the test item
    Then the inventory response status should be 422

  # --- List and filter ---

  Scenario: List inventory items
    Given 3 inventory test items exist
    When I list all inventory items
    Then I should see at least 3 inventory items

  Scenario: Filter inventory by status
    Given an inventory test item with status available exists
    When I list inventory items with status available
    Then all listed items should have status available

  # --- Low stock endpoint ---

  Scenario: Low stock report
    When I request low stock report
    Then the low stock response should be a list

  # --- Expiring endpoint ---

  Scenario: Expiring items report
    Given an inventory test item expiring in 15 days exists
    When I request items expiring within 30 days
    Then the expiring items list should not be empty

  # --- Soft delete ---

  Scenario: Delete inventory item soft-deletes
    Given an inventory test item with quantity 10 exists
    When I delete the inventory test item
    Then the inventory delete response should be 204

  # --- History on empty item ---

  Scenario: History for item with no actions
    Given an inventory test item with quantity 10 exists
    When I get history for the test item
    Then the history should be a list
