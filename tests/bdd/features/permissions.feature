Feature: Permissions
  As a system administrator
  I want to control user access to features
  So that sensitive operations are protected

  Background:
    Given I am authenticated as "admin"

  Scenario: Admin can access all endpoints
    Given I have role "admin"
    When I access any endpoint
    Then access should be granted

  Scenario: Scientist can view inventory
    Given I have role "scientist"
    When I request inventory list
    Then access should be granted
    When I request to create inventory
    Then access should be granted

  Scenario: Technician cannot delete records
    Given I have role "technician"
    When I request to delete a product
    Then access should be denied with 403

  Scenario: Guest can only read
    Given I have role "guest"
    When I request to view products
    Then access should be granted
    When I request to create a product
    Then access should be denied

  Scenario: Role-based menu visibility
    Given I have role "scientist"
    When I view the dashboard
    Then I should see:
      | menu_item     | visible |
      | Inventory     | true    |
      | Orders        | true    |
      | Staff         | false   |
      | Audit Log     | false   |

  Scenario: Permission inheritance
    Given roles have hierarchy:
      | role      | inherits_from |
      | admin     | -             |
      | scientist | technician    |
      | technician| guest         |
    When technician has permission "read_inventory"
    Then scientist should also have "read_inventory"

  Scenario: Custom role creation
    When I create role "lab_manager" with permissions:
      | permission         |
      | read_inventory     |
      | write_inventory    |
      | read_orders        |
      | write_orders       |
    Then role should be created
    And role should have 4 permissions

  Scenario: Update user role
    Given user "john@lab.com" has role "technician"
    When I update role to "scientist"
    Then user should have role "scientist"
    And audit log should record role change

  Scenario: Remove user access
    Given user "leaving@lab.com" exists
    When I revoke all access
    Then user should not be able to authenticate
    And active sessions should be terminated

  Scenario: API key permissions
    Given API key "integration-key" exists
    And key has permissions:
      | permission       |
      | read_inventory   |
      | write_inventory  |
    When key is used to delete inventory
    Then request should be denied

  Scenario: Permission check on sensitive data
    Given user "scientist" has no "view_costs" permission
    When user requests order details
    Then cost fields should be hidden
    And other fields should be visible

  Scenario: Temporary access grant
    Given user "temp@lab.com" has role "guest"
    When I grant temporary "scientist" access for 24 hours
    Then user should have elevated access
    And after 24 hours access should expire

  Scenario: Permission required fields
    Given I have role "technician"
    When I request inventory with cost data
    Then cost data should be excluded
    And other data should be included

  Scenario: Bulk permission assignment
    Given 5 users have role "guest"
    When I assign "technician" role to all
    Then 5 users should have "technician" role
    And audit log should record bulk assignment

  Scenario: Permission audit trail
    When I change user permissions
    Then change should be logged with:
      | field          |
      | changed_by     |
      | old_permission |
      | new_permission |
      | timestamp      |
