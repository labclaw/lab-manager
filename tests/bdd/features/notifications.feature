# Notifications — in-app notification system
Feature: In-app Notifications
  As a lab manager
  I want to receive and manage in-app notifications
  So that I can stay informed about important events

  # List notifications
  Scenario: List notifications for a staff member
    Given a staff member "alice" exists with role "admin"
    And 3 notifications exist for the staff member
    When I request the notification list
    Then the response should contain 3 items
    And the total should be 3

  # Filter unread
  Scenario: Filter notifications to unread only
    Given a staff member "alice" exists with role "admin"
    And 3 notifications exist for the staff member
    And 1 of those notifications are read
    When I request the notification list with unread_only true
    Then the response should contain 2 items

  # Unread count
  Scenario: Get unread notification count
    Given a staff member "alice" exists with role "admin"
    And 2 unread notifications exist for the staff member
    When I request the unread count
    Then the count should be 2

  Scenario: Unread count is zero when no notifications
    Given a staff member "alice" exists with role "admin"
    When I request the unread count
    Then the count should be 0

  # Mark single read
  Scenario: Mark a single notification as read
    Given a staff member "alice" exists with role "admin"
    And an unread notification exists for the staff member
    When I mark the notification as read
    Then the notification should be marked as read

  # Mark all read
  Scenario: Mark all notifications as read
    Given a staff member "alice" exists with role "admin"
    And 3 unread notifications exist for the staff member
    When I mark all notifications as read
    Then the marked count should be 3
    And the unread count should be 0

  # Default preferences
  Scenario: Get default notification preferences
    Given a staff member "alice" exists with role "admin"
    When I request notification preferences
    Then in_app should be true
    And email_weekly should be false

  # Update preferences
  Scenario: Update notification preferences
    Given a staff member "alice" exists with role "admin"
    And notification preferences exist for the staff member
    When I update preferences with email_weekly true and inventory_alerts false
    Then email_weekly should still be true
    And inventory_alerts should still be false

  # Preferences created on first access
  Scenario: Preferences are created on first access
    When I request notification preferences for a new staff member
    Then the response status should be 200
    And in_app should be true for new staff
