# Alerts — detection, listing, acknowledge, resolve, summary
Feature: Alerts and Monitoring
  As a lab manager at the lab
  I want automatic alerts for expiring reagents, low stock, and pending reviews
  So that nothing falls through the cracks

  # Detect expiring reagents
  Scenario: Detect expiring reagents
    Given an inventory item expiring in 7 days
    When I run the alert check
    Then an expiry alert should be created
    And the alert type should be "expiring_soon"

  # Detect low stock
  Scenario: Detect low stock
    Given a product with min_stock_level 10
    And inventory total quantity is 3
    When I run the alert check
    Then a low stock alert should be created
    And the alert type should be "low_stock"

  # List active alerts
  Scenario: List active alerts
    Given 3 active alerts exist
    And 2 resolved alerts exist
    When I list active alerts
    Then I should see 3 alerts
    And all alerts should be unresolved

  # Acknowledge an alert
  Scenario: Acknowledge an alert
    Given an active alert exists
    When I acknowledge the alert
    Then the alert should be acknowledged

  # Resolve an alert
  Scenario: Resolve an alert
    Given an active alert exists
    When I resolve the alert
    Then the alert should be resolved
    And the alert should also be acknowledged

  # Alert summary
  Scenario: Alert summary counts
    Given 5 inventory items expiring soon
    And 3 products with low stock
    And 2 documents pending review
    When I request the alert summary
    Then the summary should show 10 total active alerts
    And the summary should break down by type

  # Empty state
  Scenario: Alert check on clean database
    When I run the alert check
    Then the check should return 0 new alerts

  # Filter by type
  Scenario: Filter alerts by type
    Given alerts of different types exist
    When I list alerts filtered by type "low_stock"
    Then all returned alerts should have type "low_stock"

  # Filter by severity
  Scenario: Filter alerts by severity
    Given alerts of different severities exist
    When I list alerts filtered by severity "critical"
    Then all returned alerts should have severity "critical"

  # Not found
  Scenario: Acknowledge non-existent alert returns 404
    When I try to acknowledge alert with id 99999
    Then the alert response status should be 404

  Scenario: Resolve non-existent alert returns 404
    When I try to resolve alert with id 99999
    Then the alert response status should be 404
