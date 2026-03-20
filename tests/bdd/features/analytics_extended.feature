Feature: Extended Analytics Endpoints
  As a lab manager
  I want to access detailed analytics
  So that I can make informed decisions about inventory and spending

  Background:
    Given I am authenticated as "admin"

  Scenario: Get inventory value summary
    Given 5 inventory items exist with total value 5000.00
    When I request inventory value summary
    Then the response should contain total value 5000.00
    And the response should include item count 5

  Scenario: Get inventory value by category
    Given inventory items exist:
      | category    | value   |
      | Chemicals   | 2000.00 |
      | Consumables | 1500.00 |
      | Equipment   | 1500.00 |
    When I request inventory value by category
    Then the response should contain category breakdown
    And "Chemicals" value should be 2000.00
    And "Consumables" value should be 1500.00

  Scenario: Get top products by consumption
    Given consumption records exist:
      | product          | total_consumed |
      | PBS Buffer       | 500            |
      | Ethanol          | 300            |
      | Pipette Tips     | 200            |
    When I request top products with limit 3
    Then the response should contain 3 products
    And products should be ordered by consumption descending
    And "PBS Buffer" should be first

  Scenario: Get order history with date range
    Given orders exist:
      | date       | total   |
      | 2024-01-15 | 1500.00 |
      | 2024-02-20 | 2300.00 |
      | 2024-03-10 | 1800.00 |
    When I request order history from "2024-02-01" to "2024-03-31"
    Then the response should contain 2 orders
    And orders should be within the date range

  Scenario: Get spending by vendor
    Given orders exist:
      | vendor           | total   |
      | Fisher Scientific| 3000.00 |
      | Sigma-Aldrich    | 2000.00 |
      | Bio-Rad          | 1500.00 |
    When I request spending by vendor
    Then the response should contain vendor breakdown
    And "Fisher Scientific" spending should be 3000.00

  Scenario: Get staff activity summary
    Given activity records exist:
      | user     | actions |
      | admin    | 50      |
      | scientist| 30      |
      | tech     | 20      |
    When I request staff activity summary
    Then the response should contain activity per user
    And users should be ordered by activity descending

  Scenario: Get vendor summary
    Given a vendor "Sigma-Aldrich" exists
    And 5 orders exist for vendor "Sigma-Aldrich"
    And 10 products exist for vendor "Sigma-Aldrich"
    When I request vendor summary for "Sigma-Aldrich"
    Then the response should contain order count 5
    And the response should contain product count 10

  Scenario: Get document processing statistics
    Given documents exist:
      | status    | count |
      | pending   | 5     |
      | processing| 2     |
      | reviewed  | 20    |
      | rejected  | 3     |
    When I request document stats
    Then the response should contain status breakdown
    And "reviewed" count should be 20
    And "pending" count should be 5

  Scenario: Get spending by month
    Given orders exist:
      | month    | total   |
      | 2024-01  | 5000.00 |
      | 2024-02  | 4500.00 |
      | 2024-03  | 6000.00 |
    When I request spending by month
    Then the response should contain monthly breakdown
    And each month should have total spending

  Scenario: Analytics with no data
    Given no inventory items exist
    And no orders exist
    When I request dashboard analytics
    Then the response should contain zero values
    And the response should not error
