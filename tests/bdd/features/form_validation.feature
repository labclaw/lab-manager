Feature: Form Validation
  As a user
  I want clear validation feedback
  So that I can correct errors easily

  Background:
    Given the system is set up
    And I am logged in as "admin@test.com"

  Scenario: Login requires email
    When I submit login with empty email
    Then I should receive a 422 error
    And the error should mention "email"

  Scenario: Login requires password
    When I submit login with empty password
    Then I should receive a 401 error

  Scenario: Email must be valid format
    When I submit login with email "invalid-email"
    Then I should receive a validation error

  Scenario: Password minimum length
    When I submit setup with password "short"
    Then I should receive a validation error
    And the error should mention password requirements

  Scenario: Document review requires action
    Given a document with id 1 exists
    When I submit review without action
    Then I should receive a 422 error
    And the error should mention "action"

  Scenario: Document review action must be valid
    Given a document with id 1 exists
    When I submit review with action "invalid"
    Then I should receive a 422 error

  Scenario: Inventory consume requires quantity
    Given an inventory item with id 1 exists
    When I consume inventory without quantity
    Then I should receive a 422 error

  Scenario: Inventory quantity must be positive
    Given an inventory item with id 1 exists
    When I consume inventory with quantity -5
    Then I should receive a 422 error

  Scenario: Order receive requires items
    Given an order with id 1 exists
    When I receive order without items
    Then I should receive a 422 error

  Scenario: API returns consistent error format
    When I make various invalid requests
    Then all errors should have consistent structure
    And should include "detail" field

  Scenario: Validation errors are human readable
    When I submit invalid data
    Then error messages should be clear
    And should not expose internal details

  Scenario: Special characters are handled safely
    When I submit data with SQL injection attempt
    Then the request should be handled safely
    And no SQL error should be returned

  Scenario: XSS attempts are sanitized
    When I submit data with script tags
    Then the data should be sanitized
    And scripts should not execute
