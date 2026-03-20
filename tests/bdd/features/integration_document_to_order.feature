Feature: Integration Document to Order
  As a lab manager
  I want documents to create orders automatically
  So that I can order from packing lists efficiently

  Background:
    Given I am authenticated as "admin"

  Scenario: Extract order from packing list
    Given uploaded packing list document
    And document has been processed
    When I approve the extraction
    Then order should be created
    And order items should match document

  Scenario: Vendor auto-match from document
    Given document shows vendor "Sigma-Aldrich"
    And vendor "Sigma-Aldrich" exists in system
    When I create order from document
    Then order should reference correct vendor

  Scenario: Create new vendor from document
    Given document shows vendor "New Supplier"
    And vendor does not exist in system
    When I create order from document
    Then new vendor should be created
    And order should reference new vendor

  Scenario: Product matching by catalog number
    Given document shows product "CAT-001"
    And product exists with catalog_number "CAT-001"
    When I create order from document
    Then order item should link to existing product

  Scenario: Create new product from document
    Given document shows unknown product
    When I create order from document
    Then new product should be created
    And order should include new product

  Scenario: Quantity extraction with units
    Given document shows "10 bottles of Reagent X"
    When extraction processes document
    Then quantity should be 10
    And unit should be "bottle"

  Scenario: Price extraction validation
    Given document shows price $150.00
    When I review extraction
    Then price should be extractable
    And currency should be identified

  Scenario: Date extraction from invoice
    Given invoice with date "2025-03-15"
    When extraction processes document
    Then date should be extracted
    And order date should be set

  Scenario: Lot number extraction
    Given packing list with lot numbers
    When I receive from document
    Then lot numbers should be extracted
    And inventory should have correct lots

  Scenario: Partial extraction review
    Given extraction found 5 of 7 items
    When I review document
    Then I should see 5 extracted items
    And I should see 2 flagged for review

  Scenario: Multi-page document handling
    Given 5-page packing list
    When extraction processes document
    Then all pages should be processed
    And items should be combined correctly

  Scenario: Document type classification
    Given uploaded document
    When document is processed
    Then type should be classified as one of:
      | type          |
      | packing_list  |
      | invoice       |
      | coa          |
      | shipping_label|

  Scenario: Extraction confidence scoring
    Given extraction with confidence:
      | field        | confidence |
      | vendor_name  | 95%        |
      | product_name | 70%        |
      | quantity     | 90%        |
    When I review extraction
    Then low confidence fields should be highlighted
    And review should focus on uncertain fields
