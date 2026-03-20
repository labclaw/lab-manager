Feature: Error Handling
  As a system
  I want to handle errors gracefully
  So that users receive helpful feedback

  Background:
    Given I am authenticated as "admin"

  Scenario: Database connection error
    Given database is temporarily unavailable
    When I request inventory list
    Then I should receive 503 Service Unavailable
    And error message should indicate temporary issue

  Scenario: Not found error
    When I request product with id 99999
    Then I should receive 404 Not Found
    And error should indicate product does not exist

  Scenario: Validation error with details
    When I create product with invalid data:
      | field   | value |
      | name    |       |
      | price   | -10   |
    Then I should receive 422 Unprocessable Entity
    And error should list all validation failures

  Scenario: Authentication expired
    Given my session has expired
    When I make a request
    Then I should receive 401 Unauthorized
    And I should be redirected to login

  Scenario: Authorization denied
    Given I have role "technician"
    When I delete a product
    Then I should receive 403 Forbidden
    And error should indicate insufficient permissions

  Scenario: Rate limit exceeded
    Given I have made 100 requests in 1 minute
    When I make another request
    Then I should receive 429 Too Many Requests
    And response should include retry-after header

  Scenario: Request timeout
    Given a slow query is running
    When request exceeds 30 second timeout
    Then I should receive 504 Gateway Timeout
    And error should indicate timeout

  Scenario: Malformed JSON
    When I send invalid JSON
    Then I should receive 400 Bad Request
    And error should indicate JSON parsing failed

  Scenario: Request entity too large
    When I upload a file larger than 10MB
    Then I should receive 413 Payload Too Large
    And error should indicate size limit

  Scenario: Duplicate key error
    Given product "CAT-001" exists
    When I create another product with "CAT-001"
    Then I should receive 409 Conflict
    And error should indicate duplicate

  Scenario: Foreign key constraint error
    When I delete vendor with existing products
    Then I should receive 409 Conflict
    And error should indicate related records exist

  Scenario: Internal server error logging
    Given an unexpected error occurs
    When error is handled
    Then error should be logged with stack trace
    And user should receive generic error message
    And request_id should be included

  Scenario: Error response format
    When any error occurs
    Then response should have format:
      | field      |
      | detail     |
      | status     |
      | title      |
      | type       |

  Scenario: Retry on transient error
    Given a transient network error
    When I make request with retry enabled
    Then request should be retried up to 3 times
    And final error should be returned if all fail

  Scenario: Bulk operation partial failure
    When I process 10 items and 3 fail
    Then I should receive 207 Multi-Status
    And response should list successes and failures
