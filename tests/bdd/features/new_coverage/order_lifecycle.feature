Feature: Order Lifecycle Management
  As a lab manager
  I want to manage orders through their complete lifecycle
  So that inventory is properly tracked and replenished

  Background:
    Given the database is clean
    And I am authenticated
    And a vendor "Sigma-Aldrich" exists
    And products exist for the vendor

  Scenario: Create order with single item
    When I create an order with:
      | vendor | Sigma-Aldrich |
      | items  | 1             |
    Then the response status should be 201
    And the order status should be "pending"

  Scenario: Create order with multiple items
    When I create an order with 5 items
    Then the response status should be 201
    And the order should have 5 items

  Scenario: Create order with invalid vendor
    When I create an order with vendor "NonExistent"
    Then the response status should be 422

  Scenario: Create order with zero quantity
    When I create an order item with quantity 0
    Then the response status should be 422

  Scenario: Create order with negative quantity
    When I create an order item with quantity -5
    Then the response status should be 422

  Scenario: Update order status to submitted
    Given a pending order exists
    When I update the order status to "submitted"
    Then the order status should be "submitted"

  Scenario: Update order status to received
    Given a submitted order exists
    When I receive the order
    Then the order status should be "received"
    And inventory should be increased

  Scenario: Partial order receipt
    Given an order with 10 items exists
    When I receive 6 items
    Then 6 items should be received
    And 4 items should be pending

  Scenario: Cancel pending order
    Given a pending order exists
    When I cancel the order
    Then the order status should be "cancelled"

  Scenario: Cannot cancel received order
    Given a received order exists
    When I try to cancel the order
    Then the response status should be 400

  Scenario: Get order by ID
    Given an order with ID "order-123" exists
    When I request order "order-123"
    Then the response status should be 200
    And the order ID should be "order-123"

  Scenario: Get non-existent order
    When I request order "non-existent-id"
    Then the response status should be 404

  Scenario: List orders with filtering
    Given 5 pending orders exist
    And 3 received orders exist
    When I request orders with status "pending"
    Then the response should contain 5 orders

  Scenario: List orders with date range
    Given orders exist across multiple months
    When I request orders from "2026-01-01" to "2026-01-31"
    Then only orders in January should be returned

  Scenario: Update order item quantity
    Given an order with items exists
    When I update item quantity to 20
    Then the item quantity should be 20

  Scenario: Remove item from order
    Given an order with 3 items exists
    When I remove 1 item
    Then the order should have 2 items

  Scenario: Add item to existing order
    Given an order with 2 items exists
    When I add a new item
    Then the order should have 3 items

  Scenario: Order total calculation
    Given an order with items at prices 10, 20, 30 exists
    When I request the order
    Then the order total should be 60

  Scenario: Order with special characters in notes
    When I create an order with notes "Urgent: <script>alert('xss')</script>"
    Then the notes should be sanitized

  Scenario: Bulk order creation
    When I create 10 orders at once
    Then all 10 orders should be created
    And each order should have a unique ID

  Scenario: Order history tracking
    Given an order with status changes exists
    When I request order history
    Then all status changes should be recorded
    And timestamps should be present

  Scenario: Order PDF generation
    Given a received order exists
    When I request order PDF
    Then the response should be application/pdf
