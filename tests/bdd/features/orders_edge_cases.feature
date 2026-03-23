# Edge cases and additional scenarios for order management
Feature: Order Edge Cases
  As a lab manager in the lab
  I want robust error handling for order operations
  So that bad data never enters the system

  Background:
    Given an order test vendor "EdgeVendor" exists

  # --- Not found ---

  Scenario: Get non-existent order returns 404
    When I get order with id 99999
    Then the order response status should be 404

  # --- Update ---

  Scenario: Update order status
    Given an order "PO-EDGE-001" exists for edge testing
    When I update the order status to "shipped"
    Then the order should have status "shipped"

  # --- Delete (soft) ---

  Scenario: Delete order soft-deletes
    Given an order "PO-EDGE-DEL" exists for edge testing
    When I delete the order
    Then the order delete response should be 204

  # --- Order items ---

  Scenario: Get non-existent order item returns 404
    Given an order "PO-EDGE-ITEM" exists for edge testing
    When I get order item 99999 from the order
    Then the order response status should be 404

  Scenario: Delete an order item
    Given an order "PO-EDGE-DELITEM" with 1 item exists for edge testing
    When I delete the first order item
    Then the order item delete response should be 204
    And the order should have 0 items

  # --- Pagination ---

  Scenario: List orders with pagination
    Given 5 orders exist for edge testing
    When I list orders with page 1 and page_size 2
    Then I should see 2 orders in the page
    And the total should be 5

  # --- Sorting ---

  Scenario: List orders sorted by po_number descending
    Given 3 orders with sequential POs exist for edge testing
    When I list orders sorted by po_number desc
    Then the first order PO should come last alphabetically
