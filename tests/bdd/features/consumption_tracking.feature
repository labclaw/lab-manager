Feature: Consumption Tracking
  As a lab manager
  I want to track inventory consumption
  So that I can monitor usage patterns and plan reorders

  Background:
    Given I am authenticated as "admin"
    And an inventory item "PBS Buffer" with quantity 100 exists

  Scenario: Record consumption
    When I consume 10 units of "PBS Buffer"
    Then the quantity should be 90
    And a consumption log should be created

  Scenario: Consumption with project tracking
    Given a project "Project Alpha" exists
    When I consume 5 units of "PBS Buffer" for project "Project Alpha"
    Then the consumption should be attributed to "Project Alpha"

  Scenario: Consumption with notes
    When I consume 5 units of "PBS Buffer" with note "Daily experiment"
    Then the note should be saved with the consumption record

  Scenario: View consumption history
    Given consumption records exist:
      | date       | quantity |
      | 2024-01-10 | 10       |
      | 2024-01-15 | 5        |
      | 2024-01-20 | 8        |
    When I view consumption history for "PBS Buffer"
    Then I should see 3 records
    And records should be ordered by date descending

  Scenario: Consumption by date range
    Given consumption records exist:
      | date       | quantity |
      | 2024-01-10 | 10       |
      | 2024-02-15 | 5        |
      | 2024-03-20 | 8        |
    When I view consumption from "2024-02-01" to "2024-03-31"
    Then I should see 2 records

  Scenario: Consumption by user
    Given users "alice" and "bob" have consumed:
      | user  | quantity |
      | alice | 20       |
      | bob   | 15       |
    When I view consumption by user
    Then I should see user breakdown

  Scenario: Total consumption summary
    Given consumption records total 50 units
    When I request consumption summary
    Then the total should be 50
    And the summary should include time period

  Scenario: Consumption triggers low stock alert
    Given an item with quantity 15 exists
    And the low stock threshold is 10
    When I consume 10 units
    Then a low stock alert should be created

  Scenario: Export consumption report
    Given consumption records exist
    When I export consumption report to CSV
    Then the CSV should contain all consumption records
    And the CSV should have proper headers

  Scenario: Consumption trend analysis
    Given consumption records for 6 months exist
    When I request consumption trends
    Then I should see monthly breakdown
    And I should see trend direction
