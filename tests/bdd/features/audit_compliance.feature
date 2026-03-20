Feature: Audit Compliance
  As a compliance officer
  I want complete audit trails
  So that I can demonstrate regulatory compliance

  Background:
    Given I am authenticated as "admin"

  Scenario: View audit log
    Given 50 audit events exist
    When I request audit log
    Then I should receive paginated results
    And each entry should have timestamp and user

  Scenario: Filter audit log by action
    Given audit events exist:
      | action    | count |
      | CREATE    | 10    |
      | UPDATE    | 20    |
      | DELETE    | 5     |
    When I filter by action "UPDATE"
    Then I should receive 20 events

  Scenario: Filter audit log by date range
    Given audit events span 30 days
    When I filter by date range "2025-03-01" to "2025-03-15"
    Then I should only see events in that range

  Scenario: Filter audit log by user
    Given audit events from multiple users:
      | user_id | count |
      | 1       | 15    |
      | 2       | 10    |
    When I filter by user 1
    Then I should receive 15 events

  Scenario: View entity history
    Given product "Reagent A" was created, updated 3 times
    When I view history for product "Reagent A"
    Then I should see 4 events
    And events should show before/after values

  Scenario: Audit log entry detail
    Given an inventory update event exists
    When I view event detail
    Then I should see:
      | field          | value          |
      | timestamp      | present        |
      | user           | present        |
      | action         | UPDATE         |
      | entity_type    | inventory      |
      | entity_id      | present        |
      | old_values     | present        |
      | new_values     | present        |

  Scenario: Audit log immutability
    Given an audit log entry exists
    When I attempt to modify the entry
    Then modification should be denied
    And error should be logged

  Scenario: Export audit log
    Given 100 audit events exist
    When I export audit log to CSV
    Then CSV should contain 100 rows
    And CSV should include all required fields

  Scenario: Audit log retention
    Given audit events older than 7 years exist
    When retention policy runs
    Then old events should be archived
    And archived events should remain accessible

  Scenario: User action attribution
    Given user "scientist@lab.com" performs action
    When action is logged
    Then log should show user email
    And log should show user role at time of action

  Scenario: System action audit
    Given automated process modifies inventory
    When change is logged
    Then actor should be "system"
    And reason should be recorded

  Scenario: Audit log search
    Given audit events exist with various descriptions
    When I search for "lot_number change"
    Then matching events should be returned
    And search should be case-insensitive

  Scenario: Compliance report generation
    Given audit events exist for month
    When I generate compliance report
    Then report should include:
      | section         |
      | total_events    |
      | events_by_type  |
      | events_by_user  |
      | unique_entities |

  Scenario: Failed operation audit
    Given an operation fails due to validation
    When failure occurs
    Then failure should be logged
    And log should include error details
