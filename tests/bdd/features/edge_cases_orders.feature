Feature: Edge Cases Orders
  As a system
  I want to handle order edge cases
  So that order processing is robust

  Background:
    Given I am authenticated as "admin"

  Scenario: Order with no items
    When I create order without items
    Then order should be rejected
    And order should be created in "draft" status

  Scenario: Order with single item quantity zero
    When I create order with quantity 0
    Then item should be rejected
    And error should indicate invalid quantity

  Scenario: Order exceeding budget
    Given budget limit is $10000
    When I create order for $15000
    Then approval should be required
    And notification should go to budget manager

  Scenario: Order for discontinued product
    Given product is discontinued
    When I add to order
    Then warning should be shown
    And alternative products should be suggested

  Scenario: Order with past delivery date
    When I set delivery date to yesterday
    Then validation should fail
    And error should indicate invalid date

  Scenario: Order delivery date too far
    When I set delivery date 5 years ahead
    Then warning should be shown
    And confirmation should be required

  Scenario: Order to inactive vendor
    Given vendor is marked inactive
    When I create order for vendor
    Then warning should be shown
    And user should confirm

  Scenario: Duplicate PO number
    Given order with PO "PO-001" exists
    When I create order with PO "PO-001"
    Then creation should fail
    And PO should be auto-modified

  Scenario: Order modification after partial receipt
    Given order has 50 of 100 items received
    When I modify unreceived quantities
    Then modification should succeed
    When I modify received quantities
    Then modification should fail

  Scenario: Order cancellation after receipt
    Given order has received items
    When I cancel order
    Then cancellation should be rejected
    And only unreceived items should cancel

  Scenario: Order with items from multiple vendors
    Given order has items from vendor A and B
    When I submit order
    Then it should be split into two orders
    And warning should explain multi-vendor issue

  Scenario: Order total recalculation
    Given order with 3 items
    When I change item 2 price
    Then order total should update
    And history should preserve old total

  Scenario: Order with very large line count
    When I create order with 100 items
    Then order should be created successfully
    And performance should be acceptable

  Scenario: Order item removal with received
    Given item has 50 received of 100 ordered
    When I remove item from order
    Then removal should be blocked
    And error should explain received items

  Scenario: Order approval workflow
    Given order requires approval over $5000
    When I create order for $6000
    Then status should be "pending_approval"
    And approvers should be notified
