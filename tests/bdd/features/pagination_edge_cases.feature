Feature: Pagination Edge Cases
  As a user
  I want pagination to work correctly in all scenarios
  So that I can navigate large datasets

  Background:
    Given the system is set up
    And I am logged in as "admin@test.com"

  Scenario: Default pagination is applied
    Given 300 documents exist
    When I request the documents list without parameters
    Then the response should contain 20 items
    And page should be 1
    And page_size should be 20
    And total should be 300
    And pages should be 15

  Scenario: Request maximum page size
    Given 300 documents exist
    When I request the documents list with page_size 200
    Then the response should contain 200 items
    And pages should be 2

  Scenario: Request exceeding maximum page size
    Given 300 documents exist
    When I request the documents list with page_size 500
    Then the response should be 422 Unprocessable Entity
    And the error should mention "page_size"

  Scenario: Request negative page
    When I request the documents list with page -1
    Then the response should be 422 Unprocessable Entity

  Scenario: Request page beyond available
    Given 50 documents exist
    When I request the documents list with page 100
    Then the response should contain 0 items
    And total should still be 50

  Scenario: Request page size of 0
    When I request the documents list with page_size 0
    Then the response should be 422 Unprocessable Entity

  Scenario: Page size of 1 works correctly
    Given 10 documents exist
    When I request the documents list with page_size 1
    Then the response should contain 1 item
    And pages should be 10

  Scenario: Pagination preserves filters
    Given 100 documents exist with various statuses
    When I request documents with status "needs_review" and page 2
    Then only documents with status "needs_review" should be returned
    And pagination should reflect filtered count

  Scenario: All list endpoints support pagination
    When I request each list endpoint with pagination
    Then all should return paginated responses
    And all should include total, page, page_size, pages

  Scenario Outline: Pagination works across modules
    Given <count> <resource> exist
    When I request the <resource> list
    Then the response should be paginated
    And page_size should be at most 200

    Examples:
      | resource   | count |
      | vendors    | 50    |
      | products   | 100   |
      | orders     | 75    |
      | inventory  | 200   |
      | documents  | 150   |
      | alerts     | 30    |
