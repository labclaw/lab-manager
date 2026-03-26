# One-click deploy — full flow from fresh instance to usable lab
Feature: One-Click Lab Setup
  As a scientist deploying Lab Manager for the first time
  I want to complete setup through a browser wizard
  So that I can start managing my lab without any CLI knowledge

  # === Fresh deployment: initial state ===

  Scenario: Fresh deployment indicates setup is needed
    Given a fresh Lab Manager instance with no users
    When I check the setup status
    Then the response should indicate setup is needed

  Scenario: Setup status endpoint requires no authentication
    Given a fresh Lab Manager instance with no users
    When I check the setup status without any credentials
    Then I should not receive a 401 unauthorized error

  Scenario: Config endpoint requires no authentication
    Given a fresh Lab Manager instance with no users
    When I request the lab configuration without any credentials
    Then I should not receive a 401 unauthorized error

  # === Lab branding configuration ===

  Scenario: Lab config returns configured branding
    Given a Lab Manager instance with name "My Lab" and subtitle "Neuroscience Department"
    When I request the lab configuration
    Then the lab name should be "My Lab"
    And the lab subtitle should be "Neuroscience Department"

  Scenario: Lab config returns defaults when not configured
    Given a Lab Manager instance with default settings
    When I request the lab configuration
    Then the lab name should be "My Lab"
    And the lab subtitle should be empty

  # === Admin account creation ===

  Scenario: Create admin account via setup wizard
    Given a fresh Lab Manager instance with no users
    When I complete setup with name "Dr. Chen" email "chen@mgh.harvard.edu" and password "neuroscience2026"
    Then the setup should succeed
    And the setup status should no longer indicate setup is needed

  Scenario: Setup endpoint requires no authentication
    Given a fresh Lab Manager instance with no users
    When I complete setup with name "Dr. Chen" email "chen@mgh.harvard.edu" and password "neuroscience2026"
    Then I should not receive a 401 unauthorized error

  # === Input validation ===

  Scenario: Invalid email is rejected
    Given a fresh Lab Manager instance with no users
    When I complete setup with name "Dr. Chen" email "notanemail" and password "neuroscience2026"
    Then the setup should fail with status 422
    And the error should mention "Invalid email"

  Scenario: Empty name is rejected
    Given a fresh Lab Manager instance with no users
    When I complete setup with name "   " email "chen@mgh.harvard.edu" and password "neuroscience2026"
    Then the setup should fail with status 422
    And the error should mention "Name must be"

  Scenario: Password too short is rejected
    Given a fresh Lab Manager instance with no users
    When I complete setup with name "Dr. Chen" email "chen@mgh.harvard.edu" and password "short"
    Then the setup should fail with status 422
    And the error should mention "at least 8 characters"

  Scenario: Password exceeding bcrypt 72-byte limit is rejected
    Given a fresh Lab Manager instance with no users
    When I complete setup with a 73-byte password
    Then the setup should fail with status 422
    And the error should mention "72 bytes"

  # === Security: prevent duplicate setup ===

  Scenario: Setup blocked after first admin is created
    Given a Lab Manager instance where setup was already completed
    When I try to complete setup again with name "Hacker" email "hack@evil.com" and password "hackpass123"
    Then the setup should fail with status 409
    And the error should mention "already completed"

  Scenario: Setup status shows false after admin exists
    Given a Lab Manager instance where setup was already completed
    When I check the setup status
    Then the response should indicate setup is not needed

  # === Login flow ===

  Scenario: Login works immediately after setup
    Given a Lab Manager instance where setup was completed by "Dr. Chen" with email "chen@mgh.harvard.edu" and password "neuroscience2026"
    When I log in with email "chen@mgh.harvard.edu" and password "neuroscience2026"
    Then the login should succeed
    And the logged-in user name should be "Dr. Chen"

  Scenario: Login with wrong password fails
    Given a Lab Manager instance where setup was completed by "Dr. Chen" with email "chen@mgh.harvard.edu" and password "neuroscience2026"
    When I log in with email "chen@mgh.harvard.edu" and password "wrongpassword"
    Then the login should fail with status 401

  Scenario: Session cookie is set after login
    Given a Lab Manager instance where setup was completed by "Dr. Chen" with email "chen@mgh.harvard.edu" and password "neuroscience2026"
    When I log in with email "chen@mgh.harvard.edu" and password "neuroscience2026"
    Then a session cookie should be set

  Scenario: Authenticated user can access protected endpoints
    Given a Lab Manager instance where setup was completed by "Dr. Chen" with email "chen@mgh.harvard.edu" and password "neuroscience2026"
    And I am logged in as "chen@mgh.harvard.edu" with password "neuroscience2026"
    When I check my auth status
    Then I should be recognized as "Dr. Chen"

  # === Logout ===

  Scenario: Logout clears session
    Given a Lab Manager instance where setup was completed by "Dr. Chen" with email "chen@mgh.harvard.edu" and password "neuroscience2026"
    And I am logged in as "chen@mgh.harvard.edu" with password "neuroscience2026"
    When I log out
    Then the logout should succeed
    And checking my auth status should return 401
