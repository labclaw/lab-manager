Feature: Integration Order to Inventory
  As a lab manager
  I want orders to automatically create inventory
  So that I can track received goods

  Background:
    Given I am authenticated as "admin"
    And vendor "Sigma" exists
    And product "Reagent A" exists with catalog_number "CAT-001"

  Scenario: Receive order creates inventory
    Given an order exists with items:
      | product_id | quantity | unit_price |
      | 1          | 100      | 10.00      |
    When I receive the order
    Then inventory should be created for product 1
    And quantity should be 100
    And audit log should show receipt

  Scenario: Partial receipt updates inventory
    Given an order exists with item:
      | product_id | quantity |
      | 1          | 100      |
    When I receive 50 units
    Then inventory should have 50 units
    And order should show 50 received
    And order status should be "partial"

  Scenario: Receipt with lot number assignment
    Given an order exists with item:
      | product_id | quantity |
      | 1          | 50       |
    When I receive with lot_number "LOT-2025-001"
    Then inventory should have lot_number "LOT-2025-001"
    And lot_number should be unique

  Scenario: Receipt with expiration date
    Given an order exists with item:
      | product_id | quantity |
      | 1          | 50       |
    When I receive with expiration "2025-12-31"
    Then inventory should expire on 2025-12-31
    And expiring_soon alert should not be created

  Scenario: Receipt creates alert for expiring items
    Given an order exists with item:
      | product_id | quantity |
      | 1          | 50       |
    When I receive with expiration in 30 days
    Then expiring_soon alert should be created

  Scenario: Multiple receipts for same order
    Given an order exists with item:
      | product_id | quantity |
      | 1          | 100      |
    When I receive 30 units on 2025-03-01
    And I receive 70 units on 2025-03-05
    Then 2 inventory records should exist
    And order should show all receipts

  Scenario: Receipt updates order total cost
    Given an order exists with items totaling $1000
    When I receive all items
    Then order total should be $1000
    And spending analytics should be updated

  Scenario: Cancel unreceived order
    Given an order exists with status "pending"
    When I cancel the order
    Then order status should be "cancelled"
    And no inventory should be created

  Scenario: Cancel partially received order
    Given an order with 50 of 100 items received
    When I cancel remaining items
    Then order should show 50 received
    And 50 should be cancelled

  Scenario: Receipt validates product match
    Given an order for product "Reagent A"
    When I try to receive product "Reagent B"
    Then receipt should be rejected
    And error should indicate product mismatch

  Scenario: Receipt validates quantity
    Given an order for 100 units
    When I try to receive 150 units
    Then receipt should be rejected
    And error should indicate quantity exceeded

  Scenario: Order item updates after receipt
    Given an order item with quantity 100
    When I receive 40 units
    Then item received_quantity should be 40
    And item pending_quantity should be 60

  Scenario: Auto-complete order when fully received
    Given an order for 100 units
    When I receive 100 units
    Then order status should be "received"
    And received_at should be set
