# Edge cases for alert management
Feature: Alert Edge Cases
  As a lab manager in the lab
  I want robust alert handling
  So that no alerts are lost or mishandled

  # --- Not found ---

  Scenario: Acknowledge non-existent alert returns 404
    When I try to acknowledge alert with id 99999
    Then the alert response status should be 404

  Scenario: Resolve non-existent alert returns 404
    When I try to resolve alert with id 99999
    Then the alert response status should be 404

  # --- Filter by type ---

  Scenario: Filter alerts by type
    Given alerts of type "expiring_soon" and "low_stock" exist
    When I list alerts with type "low_stock"
    Then all listed alerts should have type "low_stock"

  # --- Filter by severity ---

  Scenario: Filter alerts by severity
    Given alerts with severity "warning" and "critical" exist
    When I list alerts with severity "critical"
    Then all listed alerts should have severity "critical"

  # --- Resolve auto-acknowledges ---

  Scenario: Resolving an unacknowledged alert also acknowledges it
    Given an unacknowledged alert exists
    When I resolve the unacknowledged alert
    Then the alert should be both acknowledged and resolved

  # --- Empty state ---

  Scenario: Alert summary on empty database
    When I request alert summary
    Then the summary total should be 0

  Scenario: Alert check on empty database
    When I run alert check
    Then the check should return 0 new alerts
