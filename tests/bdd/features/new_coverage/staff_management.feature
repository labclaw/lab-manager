Feature: Staff Management
  As a lab administrator
  I want to manage lab staff accounts
  So that access and permissions are properly controlled

  Background:
    Given the database is clean
    And I am authenticated as admin

  Scenario: Create staff account
    When I create staff with:
      | name   | John Doe          |
      | email  | john@example.com  |
      | role   | researcher        |
    Then the response status should be 201
    And staff name should be "John Doe"

  Scenario: Create staff with duplicate email
    Given staff with email "john@example.com" exists
    When I create staff with email "john@example.com"
    Then the response status should be 409

  Scenario: Create staff without email
    When I create staff without email
    Then the response status should be 422

  Scenario: Create staff with invalid email
    When I create staff with email "not-an-email"
    Then the response status should be 422

  Scenario: Get staff by ID
    Given staff with ID "staff-123" exists
    When I request staff "staff-123"
    Then the response status should be 200
    And staff ID should be "staff-123"

  Scenario: Get non-existent staff
    When I request staff "non-existent-id"
    Then the response status should be 404

  Scenario: List all staff
    Given 25 staff members exist
    When I request all staff
    Then the response should contain 25 staff

  Scenario: List staff with pagination
    Given 50 staff members exist
    When I request staff with page 1 and page_size 10
    Then the response should contain 10 staff
    And total count should be 50

  Scenario: Filter staff by role
    Given 10 researchers exist
    And 5 administrators exist
    When I request staff with role "researcher"
    Then the response should contain 10 staff

  Scenario: Filter staff by department
    Given 8 staff in "Biology" exist
    And 12 staff in "Chemistry" exist
    When I request staff in department "Biology"
    Then the response should contain 8 staff

  Scenario: Search staff by name
    Given staff "John Doe", "Jane Smith", "Bob Johnson" exist
    When I search staff for "John"
    Then the response should contain 2 staff

  Scenario: Update staff name
    Given staff with name "Old Name" exists
    When I update staff name to "New Name"
    Then staff name should be "New Name"

  Scenario: Update staff email
    Given staff with email "old@example.com" exists
    When I update staff email to "new@example.com"
    Then staff email should be "new@example.com"

  Scenario: Update staff role
    Given staff with role "researcher" exists
    When I update staff role to "senior_researcher"
    Then staff role should be "senior_researcher"

  Scenario: Deactivate staff account
    Given active staff exists
    When I deactivate staff
    Then staff status should be "inactive"

  Scenario: Reactivate staff account
    Given inactive staff exists
    When I reactivate staff
    Then staff status should be "active"

  Scenario: Delete staff with no orders
    Given staff with no orders exists
    When I delete staff
    Then the response status should be 204
    And the staff should no longer exist

  Scenario: Cannot delete staff with orders
    Given staff with orders exists
    When I try to delete staff
    Then the response status should be 400

  Scenario: Staff permissions
    Given staff with role "researcher" exists
    When I request staff permissions
    Then permissions should include "view_inventory"
    And permissions should include "create_orders"
    And permissions should not include "admin"

  Scenario: Update staff permissions
    Given staff exists
    When I grant permission "manage_users"
    Then staff should have permission "manage_users"

  Scenario: Revoke staff permission
    Given staff with permission "delete_inventory" exists
    When I revoke permission "delete_inventory"
    Then staff should not have permission "delete_inventory"

  Scenario: Staff password reset
    Given staff with email "reset@example.com" exists
    When I request password reset
    Then reset email should be sent
    And reset token should be generated

  Scenario: Staff password update
    Given staff with reset token exists
    When I update password with token and new password
    Then password should be updated
    And reset token should be invalidated

  Scenario: Staff login history
    Given staff with 10 logins exists
    When I request login history
    Then response should contain 10 records
    And records should show timestamps and IPs

  Scenario: Staff activity log
    Given staff with activity exists
    When I request staff activity
    Then recent activities should be listed
    And activities should be timestamped

  Scenario: Staff orders
    Given staff with 15 orders exists
    When I request staff orders
    Then response should contain 15 orders

  Scenario: Staff spending summary
    Given staff with orders totaling $5000 exists
    When I request staff spending
    Then total spending should be $5000

  Scenario: Assign staff to location
    Given staff and location exist
    When I assign staff to location
    Then staff should be assigned to location

  Scenario: Remove staff from location
    Given staff assigned to location exists
    When I remove staff from location
    Then staff should not be assigned to location

  Scenario: Staff certifications
    Given staff exists
    When I add certification "Biosafety Level 2" with expiry "2027-01-01"
    Then staff should have certification

  Scenario: Staff certification expiry
    Given staff with expiring certification exists
    When certification check runs
    Then expiry alert should be created

  Scenario: Staff training records
    Given staff with 5 training records exists
    When I request training history
    Then response should contain 5 records

  Scenario: Bulk import staff
    Given CSV with 20 staff records
    When I import staff from CSV
    Then 20 staff should be created

  Scenario: Export staff list
    Given 30 staff exist
    When I export staff to CSV
    Then the response content type should be "text/csv"

  Scenario: Staff API key generation
    Given staff exists
    When I generate API key
    Then API key should be returned
    And API key should be hashed in database

  Scenario: Staff API key revocation
    Given staff with API key exists
    When I revoke API key
    Then API key should be invalidated

  Scenario: Staff two-factor setup
    Given staff exists
    When I enable two-factor authentication
    Then 2FA should be enabled
    And QR code should be provided

  Scenario: Staff session management
    Given staff with 3 active sessions exists
    When I request active sessions
    Then response should contain 3 sessions

  Scenario: Terminate other sessions
    Given staff with multiple sessions exists
    When I terminate other sessions
    Then only current session should remain
