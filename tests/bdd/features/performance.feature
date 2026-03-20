Feature: Performance
  As a user
  I want the system to be responsive
  So that I can work efficiently

  Background:
    Given I am authenticated as "admin"

  Scenario: List page response time
    Given 1000 products exist
    When I request product list
    Then response should be under 200ms
    And pagination should work efficiently

  Scenario: Search response time
    Given 10000 products exist
    When I search for "reagent"
    Then response should be under 500ms
    And results should be accurate

  Scenario: Dashboard load time
    Given extensive data exists
    When I load dashboard
    Then initial load should be under 1 second
    And lazy loading should fill in details

  Scenario: Large dataset export
    Given 5000 inventory items exist
    When I export to CSV
    Then export should complete under 30 seconds
    And streaming should start immediately

  Scenario: Bulk import performance
    When I import 1000 products
    Then import should complete under 60 seconds
    And progress should be reported

  Scenario: Database query optimization
    Given 10000 orders with items
    When I request order list with items
    Then query should use efficient joins
    And N+1 queries should not occur

  Scenario: Caching effectiveness
    Given popular product is frequently accessed
    When I access product 10 times
    Then subsequent accesses should be cached
    And cache hit rate should be high

  Scenario: API rate limiting
    When I make 100 requests in 1 minute
    Then rate limiting should activate
    And legitimate traffic should not be blocked

  Scenario: Memory usage stability
    When system runs for 24 hours
    Then memory usage should remain stable
    And no memory leaks should occur

  Scenario: Concurrent request handling
    When 50 users make simultaneous requests
    Then all requests should complete
    And average response time under 500ms

  Scenario: Large file upload
    When I upload 5MB document
    Then upload should complete under 10 seconds
    And progress should be shown

  Scenario: Pagination efficiency
    Given 10000 records exist
    When I page through results
    Then each page should load under 100ms
    And count query should be efficient
