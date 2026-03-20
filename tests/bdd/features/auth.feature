# 认证与授权 — 用户认证和权限管理
Feature: Authentication and Authorization
  As a lab system
  I want to authenticate users and control access
  So that only authorized staff can access lab data

  Background:
    Given the system has staff accounts configured

  # 登录流程
  Scenario: Successful login with valid credentials
    Given staff "scientist1" exists with password "validpass"
    When I login with username "scientist1" and password "validpass"
    Then I should receive a session cookie
    And I should be able to access protected endpoints

  Scenario: Login fails with invalid password
    Given staff "scientist1" exists with password "validpass"
    When I login with username "scientist1" and password "wrongpass"
    Then I should receive a 401 error
    And no session cookie should be set

  Scenario: Login fails with non-existent username
    When I login with username "nonexistent" and password "anypass"
    Then I should receive a 401 error

  # 会话管理
  Scenario: Session persists across requests
    Given I am logged in as "scientist1"
    When I make multiple API requests
    Then all requests should succeed without re-authentication

  Scenario: Session expires after timeout
    Given I am logged in as "scientist1"
    And the session has been idle for 25 hours
    When I make an API request
    Then I should receive a 401 error
    And I should be prompted to re-authenticate

  Scenario: Logout clears session
    Given I am logged in as "scientist1"
    When I logout
    Then my session should be invalidated
    And I should not be able to access protected endpoints

  # 权限控制
  Scenario: Regular staff cannot access admin endpoints
    Given I am logged in as "scientist1" with role "staff"
    When I request the admin panel
    Then I should receive a 403 forbidden error

  Scenario: Admin can access all endpoints
    Given I am logged in as "admin1" with role "admin"
    When I request any endpoint
    Then I should receive appropriate access

  # 密码管理
  Scenario: Password meets complexity requirements
    When I create a staff account with password "Str0ng@Pass"
    Then the account should be created successfully

  Scenario: Password fails complexity requirements
    When I create a staff account with password "weak"
    Then I should receive a validation error
    And the error should list password requirements

  # 并发登录
  Scenario: Multiple concurrent sessions allowed
    Given staff "scientist1" exists
    When I login from device A
    And I login from device B
    Then both sessions should be valid
    And logging out from one device should not affect the other

  # 认证白名单
  Scenario: Health endpoint accessible without auth
    Given I am not authenticated
    When I request the health endpoint
    Then I should receive a 200 response

  Scenario: Static assets accessible without auth
    Given I am not authenticated
    When I request a static asset
    Then I should receive the asset

  # 安全
  Scenario: Brute force protection
    Given staff "scientist1" exists
    When I fail login 5 times in a row
    Then further attempts should be rate limited
    And I should see a lockout message

  Scenario: Session cookie is secure
    When I login successfully
    Then the session cookie should have HttpOnly flag
    And the session cookie should have Secure flag
