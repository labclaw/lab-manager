Feature: Alerts Management
  As a lab manager
  I want to receive and manage alerts
  So that important events are not missed

  Background:
    Given the database is clean
    And I am authenticated

  Scenario: Create low stock alert
    Given inventory item with quantity below threshold exists
    When alert check runs
    Then a low stock alert should be created
    And alert priority should be "medium"

  Scenario: Create expiry alert
    Given inventory expiring in 30 days exists
    When alert check runs
    Then an expiry alert should be created
    And alert priority should be "high"

  Scenario: Create critical expiry alert
    Given inventory expiring in 7 days exists
    When alert check runs
    Then a critical expiry alert should be created
    And alert priority should be "urgent"

  Scenario: List all active alerts
    Given 5 active alerts exist
    When I request all alerts
    Then response should contain 5 alerts

  Scenario: List alerts by priority
    Given 3 high priority alerts exist
    And 5 medium priority alerts exist
    When I request alerts with priority "high"
    Then response should contain 3 alerts

  Scenario: List alerts by type
    Given 4 low stock alerts exist
    And 6 expiry alerts exist
    When I request alerts with type "low_stock"
    Then response should contain 4 alerts

  Scenario: Acknowledge alert
    Given alert with ID "alert-123" exists
    When I acknowledge the alert
    Then alert status should be "acknowledged"
    And acknowledged date should be set

  Scenario: Resolve alert
    Given acknowledged alert exists
    When I resolve the alert with notes "Replenished stock"
    Then alert status should be "resolved"
    And resolution notes should be "Replenished stock"

  Scenario: Cannot resolve unacknowledged alert
    Given new alert exists
    When I try to resolve without acknowledging
    Then the response status should be 400

  Scenario: Get alert summary
    Given 10 active alerts exist
    And 5 acknowledged alerts exist
    And 3 resolved alerts exist today
    When I request alert summary
    Then active count should be 10
    And acknowledged count should be 5
    And resolved count should be 3

  Scenario: Alert auto-escalation
    Given high priority alert unacknowledged for 24 hours
    When escalation check runs
    Then alert priority should be escalated to "urgent"

  Scenario: Duplicate alert prevention
    Given low stock alert for item "SKU-123" exists
    When same condition triggers again
    Then no duplicate alert should be created
    And existing alert should be updated

  Scenario: Alert notification delivery
    Given new critical alert is created
    When notification service runs
    Then email should be sent to configured recipients
    And notification record should be created

  Scenario: Alert notification preferences
    Given user has disabled email notifications
    When alert is created
    Then no email should be sent
    And alert should still be visible in system

  Scenario: Alert batch processing
    Given 100 conditions meet alert criteria
    When batch alert check runs
    Then all 100 alerts should be created
    And processing should complete within time limit

  Scenario: Alert with related entity
    Given alert for inventory item exists
    When I request alert details
    Then related inventory item should be included
    And item details should be complete

  Scenario: Alert history
    Given alert with 3 status changes exists
    When I request alert history
    Then all status changes should be returned
    And timestamps should be present

  Scenario: Delete resolved alert
    Given resolved alert older than 30 days exists
    When I delete the alert
    Then alert should be removed
    And audit record should be created

  Scenario: Cannot delete active alert
    Given active alert exists
    When I try to delete the alert
    Then the response status should be 400

  Scenario: Alert search
    Given alerts with various notes exist
    When I search alerts for "restock"
    Then alerts with "restock" in notes should be returned

  Scenario: Alert with suggested action
    Given low stock alert exists
    When I request alert details
    Then suggested action should include "Reorder from vendor"
    And vendor information should be included

  Scenario: Equipment maintenance alert
    Given equipment due for maintenance
    When maintenance check runs
    Then maintenance alert should be created
    And equipment details should be included

  Scenario: Calibration expiry alert
    Given equipment calibration expiring in 14 days
    When calibration check runs
    Then calibration alert should be created

  Scenario: Order delay alert
    Given order not received after expected date
    When order check runs
    Then order delay alert should be created
    And order details should be included

  Scenario: Budget threshold alert
    Given monthly spending approaching budget limit
    When budget check runs
    Then budget alert should be created

  Scenario: Document review queue alert
    Given 10 documents pending review
    When review queue check runs
    Then review queue alert should be created
    And pending count should be included

  Scenario: Alert digest email
    Given 5 new alerts created today
    When digest email is triggered
    Then single email with all 5 alerts should be sent
    And alerts should be grouped by priority

  Scenario: Alert snooze
    Given active alert exists
    When I snooze the alert for 24 hours
    Then alert should not appear in active list
    And alert should reactivate after 24 hours

  Scenario: Alert assignment
    Given alert exists
    When I assign alert to user "john@example.com"
    Then alert should have assignee
    And assignee should receive notification
