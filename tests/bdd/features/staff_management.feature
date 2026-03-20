# 员工管理 — 完整生命周期测试
Feature: Staff Management Lifecycle
  As a lab administrator
  I want to manage staff accounts and permissions
  So that lab access is properly controlled

  Background:
    Given I am authenticated as staff "admin1" with admin role

  # 创建员工
  Scenario: Create new staff member
    When I create a staff member with:
      | name | email | role |
      | John Doe | john@example.com | staff |
    Then the staff member should be created
    And the staff should have a unique ID

  Scenario: Create staff with duplicate email
    Given staff "john@example.com" already exists
    When I create a staff member with email "john@example.com"
    Then I should receive a conflict error
    And the error should indicate email already in use

  Scenario: Create staff without required fields
    When I create a staff member without a name
    Then I should receive a validation error
    And the error should list missing fields

  # 更新员工
  Scenario: Update staff name
    Given staff "scientist1" exists
    When I update staff "scientist1" name to "Dr. Scientist"
    Then the name should be updated
    And the update should be logged in audit trail

  Scenario: Update staff role
    Given staff "scientist1" with role "staff"
    When I change role to "admin"
    Then the role should be updated
    And the staff should have new permissions

  Scenario: Update last active timestamp
    Given staff "scientist1" last active 2 days ago
    When staff "scientist1" makes an API request
    Then last_active should be updated
    And the timestamp should be recent

  # 停用/激活
  Scenario: Deactivate staff member
    Given staff "scientist1" is active
    When I deactivate the staff account
    Then the account should be inactive
    And the staff should not be able to login

  Scenario: Reactivate staff member
    Given staff "scientist1" is inactive
    When I reactivate the staff account
    Then the account should be active
    And the staff should be able to login

  Scenario: Deactivate staff with active sessions
    Given staff "scientist1" has 3 active sessions
    When I deactivate the staff account
    Then all sessions should be invalidated
    And the staff should be logged out

  # 权限
  Scenario: Staff with staff role cannot access admin endpoints
    Given I am authenticated as staff with role "staff"
    When I try to access admin panel
    Then I should receive 403 Forbidden

  Scenario: Admin can access all endpoints
    Given I am authenticated as staff with role "admin"
    When I access any endpoint
    Then I should have appropriate access

  # 搜索
  Scenario: Search staff by name
    Given staff "John Doe" and "Jane Smith" exist
    When I search for staff "John"
    Then I should find "John Doe"
    And I should not find "Jane Smith"

  Scenario: Filter staff by role
    Given 3 admin staff and 7 regular staff
    When I filter by role "admin"
    Then I should see 3 staff members

  # 统计
  Scenario: Get staff activity statistics
    Given staff have various activity levels
    When I request staff activity report
    Then each staff should have action counts
    And the report should be sorted by activity

  # 边界情况
  Scenario: List staff with pagination
    Given 50 staff members exist
    When I request staff list page 2 with size 10
    Then I should see staff 11-20
    And total count should be 50

  Scenario: Delete staff who created orders
    Given staff "olduser" created 10 orders
    When I delete staff "olduser"
    Then orders should be reassigned or marked
    And deletion should be logged

  # 密码重置
  Scenario: Request password reset
    Given staff "scientist1" exists with email "sci@example.com"
    When I request password reset for "sci@example.com"
    Then a reset link should be generated
    And an email should be queued

  Scenario: Use expired reset token
    Given reset token "expired-token" expired 2 hours ago
    When I try to reset password with "expired-token"
    Then I should receive an error
    And the error should indicate token expired
