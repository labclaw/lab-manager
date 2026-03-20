Feature: Staff Management
  As a lab administrator
  I want to manage lab staff accounts
  So that team members can access the system appropriately

  Background:
    Given I am authenticated as "admin"

  Scenario: Create staff account
    When I create a staff member with:
      | email    | scientist@lab.com |
      | name     | Dr. Jane Smith    |
      | role     | scientist         |
    Then the staff account should be created
    And a welcome email should be sent

  Scenario: List staff members
    Given 5 staff members exist
    When I request all staff
    Then I should receive 5 staff members

  Scenario: Update staff role
    Given a staff member "tech@lab.com" with role "technician" exists
    When I update the role to "scientist"
    Then the role should be updated

  Scenario: Deactivate staff account
    Given a staff member "leaving@lab.com" exists
    When I deactivate the account
    Then the account status should be "inactive"
    And the user should not be able to login

  Scenario: Reactivate staff account
    Given an inactive staff account exists
    When I reactivate the account
    Then the account status should be "active"
    And the user should be able to login

  Scenario: Staff activity report
    Given staff members have activity:
      | email              | actions |
      | active@lab.com     | 50      |
      | moderate@lab.com   | 20      |
      | inactive@lab.com   | 5       |
    When I request staff activity report
    Then I should see activity counts per staff member
    And staff should be ordered by activity

  Scenario: Role-based permissions
    Given staff with roles:
      | role      | can_manage_users | can_delete_data |
      | admin     | true             | true            |
      | scientist | false            | false           |
    When I check permissions
    Then each role should have appropriate permissions

  Scenario: Staff profile update
    Given a staff member exists
    When the staff member updates their profile
    Then the profile should be updated
    And email changes should require verification

  Scenario: Password reset
    Given a staff member "forgot@lab.com" exists
    When I request password reset
    Then a reset link should be sent
    And the link should expire after 24 hours

  Scenario: Staff search
    Given staff members exist:
      | name        |
      | John Smith  |
      | Jane Doe    |
      | Bob Johnson |
    When I search staff for "John"
    Then I should receive 2 staff members
