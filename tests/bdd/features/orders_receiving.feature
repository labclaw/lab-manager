Feature: Order Receiving and Inventory Creation
  As a lab manager
  I want to receive orders and automatically create inventory
  So that incoming shipments are tracked and inventory is updated

  Background:
    Given I am authenticated as "admin"
    And a vendor "Fisher Scientific" exists
    And a product "Pipette Tips 1000uL" exists for vendor "Fisher Scientific"
    And a product "Microcentrifuge Tubes" exists for vendor "Fisher Scientific"

  Scenario: Receive order creates inventory items
    Given an order exists with status "shipped"
    And the order contains:
      | product                | quantity | lot_number  |
      | Pipette Tips 1000uL   | 10       | LOT-2024-01 |
      | Microcentrifuge Tubes | 20       | LOT-2024-02 |
    When I receive the order
    Then the order status should be "received"
    And 2 inventory items should be created
    And inventory item for "Pipette Tips 1000uL" should have quantity 10
    And inventory item for "Microcentrifuge Tubes" should have quantity 20
    And inventory items should have lot numbers preserved

  Scenario: Receive order with missing lot numbers
    Given an order exists with status "shipped"
    And the order contains:
      | product                | quantity |
      | Pipette Tips 1000uL   | 5        |
    When I receive the order
    Then the order should be received
    And inventory items should be created without lot numbers

  Scenario: Receive already received order
    Given an order exists with status "received"
    When I try to receive the order
    Then the request should fail with error "Order already received"

  Scenario: Receive order updates inventory value
    Given an order exists with status "shipped"
    And the order contains:
      | product              | quantity | unit_price |
      | Pipette Tips 1000uL | 10       | 25.00      |
    When I receive the order
    Then the total inventory value should increase by 250.00

  Scenario: Partial order receiving
    Given an order exists with status "shipped"
    And the order contains:
      | product                | quantity |
      | Pipette Tips 1000uL   | 10       |
      | Microcentrifuge Tubes | 20       |
    When I partially receive the order with:
      | product              | received_quantity |
      | Pipette Tips 1000uL | 10                |
    Then the order status should be "partially_received"
    And 1 inventory item should be created
    And 1 order item should remain pending

  Scenario: Receive order with custom location
    Given an order exists with status "shipped"
    And a location "Shelf A-1" exists
    And the order contains:
      | product              | quantity |
      | Pipette Tips 1000uL | 10       |
    When I receive the order to location "Shelf A-1"
    Then the inventory item should be in location "Shelf A-1"

  Scenario: Receive order with expiration dates
    Given an order exists with status "shipped"
    And the order contains:
      | product              | quantity | expiration_date |
      | Pipette Tips 1000uL | 10       | 2025-12-31      |
    When I receive the order
    Then the inventory item should have expiration date "2025-12-31"

  Scenario: Receive order creates alert for expiring items
    Given an order exists with status "shipped"
    And the order contains:
      | product              | quantity | expiration_date |
      | Pipette Tips 1000uL | 10       | 2024-04-01      |
    When I receive the order
    Then an expiring soon alert should be created
    And the alert should reference the inventory item
