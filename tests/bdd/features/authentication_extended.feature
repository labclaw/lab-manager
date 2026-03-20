Feature: Extended Authentication
  As a system administrator
  I want robust authentication mechanisms
  So that the system is secure and users can access appropriately

  Background:
    Given the system is configured with admin credentials

  Scenario: Login with valid credentials
    Given a user exists with email "admin@lab.com" and password "secure123"
    When I login with email "admin@lab.com" and password "secure123"
    Then I should receive a session cookie
    And the response should contain user information

  Scenario: Login with invalid password
    Given a user exists with email "admin@lab.com" and password "secure123"
    When I login with email "admin@lab.com" and password "wrongpassword"
    Then the response should be 401 Unauthorized
    And no session cookie should be set

  Scenario: Login with non-existent email
    When I login with email "nobody@lab.com" and password "anypassword"
    Then the response should be 401 Unauthorized
    And the error message should not reveal user existence

  Scenario: Session validation
    Given I am logged in as "admin"
    When I access a protected endpoint
    Then the request should succeed
    And the user context should be available

  Scenario: Session expiration
    Given I have an expired session
    When I access a protected endpoint
    Then the response should be 401 Unauthorized
    And I should be redirected to login

  Scenario: Logout clears session
    Given I am logged in as "admin"
    When I logout
    Then the session cookie should be cleared
    And subsequent requests should be unauthorized

  Scenario: Rate limiting on login attempts
    Given I have failed login 5 times in the last minute
    When I attempt to login again
    Then the response should be 429 Too Many Requests
    And I should wait before retrying

  Scenario: API key authentication
    Given a valid API key exists
    When I make a request with the API key header
    Then the request should be authenticated
    And the response should succeed

  Scenario: Invalid API key
    When I make a request with an invalid API key
    Then the response should be 401 Unauthorized

  Scenario: Deactivated user cannot login
    Given a user exists with status "inactive"
    When I login with that user's credentials
    Then the response should be 401 Unauthorized
    And the error should indicate account is disabled

  Scenario: Cookie security attributes
    Given I login successfully
    When I receive the session cookie
    Then the cookie should have HttpOnly flag
    And the cookie should have SameSite attribute

  Scenario: CSRF protection
    Given I am logged in
    When I make a POST request without CSRF token
    Then the request should be rejected

  Scenario: Password comparison timing attack prevention
    Given a user exists
    When I login with wrong password
    Then the response time should be consistent
    And timing should not reveal password correctness
