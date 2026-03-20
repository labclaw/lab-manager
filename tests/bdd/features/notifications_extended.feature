Feature: Notifications Extended
  As a lab user
  I want comprehensive notification management
  So that I stay informed about all relevant events

  Background:
    Given I am authenticated as "admin"

  Scenario: Email notification for critical events
    Given email notifications are enabled
    When critical alert is triggered
    Then email should be sent to configured recipients
    And email should include event details

  Scenario: In-app notification badge
    Given 5 unread notifications exist
    When I view the application
    Then notification badge should show 5
    And badge should update in real-time

  Scenario: Notification grouping
    Given 10 low_stock notifications exist
    When I view notifications
    Then notifications should be grouped by type
    And count should show for each group

  Scenario: Notification priority levels
    Given notifications with priorities:
      | priority | message     |
      | critical | Safety alert|
      | high     | Low stock   |
      | low      | Info update |
    When I view notification list
    Then critical should appear first
    And ordering should be by priority

  Scenario: Notification expiry
    Given notification is 30 days old
    When cleanup runs
    Then old notification should be archived
    And active list should only show recent

  Scenario: Notification actions
    Given order approval notification exists
    When I view notification
    Then I should see action buttons:
      | action    |
      | Approve   |
      | Reject    |
      | View      |

  Scenario: Notification forwarding
    Given I am on vacation
    And forwarding is configured to "colleague@lab.com"
    When notification arrives for me
    Then notification should be forwarded
    And original recipient should be cc'd

  Scenario: Notification digest
    Given digest mode is enabled daily
    And 50 notifications occurred today
    When daily digest time arrives
    Then one summary email should be sent
    And email should group by type

  Scenario: Notification mute
    Given I mute "low_stock" notifications
    When low_stock event occurs
    Then no notification should be created for me
    And other users should still receive

  Scenario: Notification search
    Given 100 notifications exist
    When I search for "order"
    Then matching notifications should be returned
    And search should be fast

  Scenario: Notification export
    Given notifications for compliance period
    When I export notifications
    Then export should include all fields
    And format should be audit-ready

  Scenario: Push notification for mobile
    Given mobile app is installed
    When urgent alert occurs
    Then push notification should be sent
    And notification should be actionable from lock screen

  Scenario: Notification templates
    Given custom notification template exists
    When notification is sent
    Then template should be applied
    And placeholders should be filled correctly
