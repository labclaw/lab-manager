Feature: Edge Cases Vendors
  As a system
  I want to handle vendor edge cases
  So that vendor data is reliable

  Background:
    Given I am authenticated as "admin"

  Scenario: Vendor with very long name
    When I create vendor with 500 character name
    Then creation should fail
    And error should indicate length limit

  Scenario: Vendor with international characters
    When I create vendor "Merck KGaA (德国)"
    Then vendor should be created
    And name should be stored correctly

  Scenario: Vendor with no contact info
    When I create vendor with no email or phone
    Then creation should succeed
    And warning should be shown

  Scenario: Vendor with invalid email
    When I create vendor with email "not-an-email"
    Then creation should fail
    And error should indicate invalid format

  Scenario: Vendor with invalid phone
    When I create vendor with phone "abc123"
    Then creation should fail
    Or phone should be stored as-is

  Scenario: Vendor website validation
    When I create vendor with website "not-a-url"
    Then creation should fail
    And error should indicate invalid URL

  Scenario: Vendor with multiple websites
    When I provide 3 website URLs
    Then primary should be stored
    Or all should be stored

  Scenario: Duplicate vendor name
    Given vendor "Sigma" exists
    When I create vendor "Sigma"
    Then creation should fail
    Or duplicate warning should be shown

  Scenario: Vendor name case sensitivity
    Given vendor "Sigma" exists
    When I create vendor "SIGMA"
    Then should be treated as duplicate
    Or case-insensitive warning

  Scenario: Vendor with special payment terms
    When I set payment terms to "Net 45, 2% discount"
    Then terms should be stored
    And should be displayable

  Scenario: Vendor deletion with products
    Given vendor has 10 products
    When I delete vendor
    Then deletion should be blocked
    And error should list dependent products

  Scenario: Vendor deletion with orders
    Given vendor has order history
    When I delete vendor
    Then deletion should be soft
    And order history should be preserved

  Scenario: Vendor merging
    Given vendors "Sigma" and "Sigma-Aldrich"
    When I merge into "Sigma-Aldrich"
    Then products should be reassigned
    And order history should be combined

  Scenario: Vendor rating update
    Given vendor has rating 4.0
    When 5-star order completes
    Then rating should recalculate
    And update should be incremental

  Scenario: Vendor status history
    Given vendor was active, then inactive
    When I view history
    Then I should see status changes
    And reasons for each change
