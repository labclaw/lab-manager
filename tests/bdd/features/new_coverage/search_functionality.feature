Feature: Search Functionality
  As a lab manager
  I want to search across all data types
  So that I can quickly find what I need

  Background:
    Given the database is clean
    And I am authenticated
    And search index is synchronized

  Scenario: Basic search returns results
    Given items matching "antibody" exist
    When I search for "antibody"
    Then results should contain matching items
    And response should include total count

  Scenario: Search with no results
    Given no items matching "xyznonexistent" exist
    When I search for "xyznonexistent"
    Then results should be empty
    And total count should be 0

  Scenario: Search is case insensitive
    Given product "Antibody XYZ" exists
    When I search for "antibody"
    Then "Antibody XYZ" should be in results

  Scenario: Search with partial match
    Given product "Monoclonal Antibody" exists
    When I search for "Monoclon"
    Then "Monoclonal Antibody" should be in results

  Scenario: Search with multiple terms
    Given product "Anti-GFP Antibody" exists
    And product "GFP Plasmid" exists
    And product "RFP Antibody" exists
    When I search for "GFP Antibody"
    Then results should rank "Anti-GFP Antibody" highest

  Scenario: Search with exact phrase
    Given product "Cell Culture Media" exists
    And product "Cell Growth Media" exists
    When I search with exact phrase "Cell Culture"
    Then only "Cell Culture Media" should be returned

  Scenario: Search with filters
    Given 10 products matching "buffer" exist
    And 5 vendors matching "buffer" exist
    When I search for "buffer" with type filter "products"
    Then only products should be returned
    And results should contain 10 items

  Scenario: Search with pagination
    Given 100 items matching "test" exist
    When I search for "test" with page 1 and page_size 20
    Then results should contain 20 items
    And total count should be 100
    And page count should be 5

  Scenario: Search second page
    Given 100 items matching "test" exist
    When I search for "test" with page 2 and page_size 20
    Then results should contain items 21-40

  Scenario: Search sorted by relevance
    Given items with varying relevance to "antibody" exist
    When I search for "antibody"
    Then results should be sorted by relevance score

  Scenario: Search sorted by date
    Given items with different dates exist
    When I search with sort "date_desc"
    Then results should be sorted by date descending

  Scenario: Search with date range filter
    Given items from various dates exist
    When I search with date range "2026-01-01" to "2026-03-31"
    Then only items in date range should be returned

  Scenario: Search suggestions
    Given products "Antibody A", "Antibody B", "Antioxidant" exist
    When I request suggestions for "Anti"
    Then suggestions should include "Antibody A"
    And suggestions should include "Antibody B"
    And suggestions should include "Antioxidant"

  Scenario: Search suggestions limited
    Given 100 products starting with "Test" exist
    When I request suggestions for "Test" with limit 5
    Then only 5 suggestions should be returned

  Scenario: Search with special characters
    Given product "PBS (Phosphate Buffer)" exists
    When I search for "PBS (Phosphate"
    Then "PBS (Phosphate Buffer)" should be in results

  Scenario: Search with wildcards disabled
    Given product "Test*" exists
    When I search for "Test*"
    Then literal "Test*" should be searched
    And wildcards should not expand

  Scenario: Search result highlights
    Given product "Anti-GFP Antibody" exists
    When I search for "GFP" with highlights
    Then "GFP" should be highlighted in results

  Scenario: Search across multiple fields
    Given product with name "GFP Antibody" and description "Green fluorescent" exists
    When I search for "GFP"
    Then product should be found
    And both name and description matches should contribute to score

  Scenario: Search vendor by name
    Given vendor "Sigma-Aldrich" exists
    When I search vendors for "Sigma"
    Then "Sigma-Aldrich" should be returned

  Scenario: Search product by catalog number
    Given product with catalog number "AB-12345" exists
    When I search for "AB-12345"
    Then the product should be found

  Scenario: Search order by order number
    Given order "ORD-2026-001" exists
    When I search for "ORD-2026-001"
    Then the order should be found

  Scenario: Search inventory by lot number
    Given inventory with lot "LOT-2026-ABC" exists
    When I search for "LOT-2026-ABC"
    Then the inventory should be found

  Scenario: Search documents by vendor
    Given documents from "Fisher" and "VWR" exist
    When I search documents for "Fisher"
    Then only Fisher documents should be returned

  Scenario: Search with typo tolerance
    Given product "Antibody" exists
    When I search for "Antibdy"
    Then "Antibody" should still be found via fuzzy matching

  Scenario: Search performance with large dataset
    Given 10000 items exist in search index
    When I search for common term
    Then response time should be under 200ms

  Scenario: Search index synchronization
    Given new product "New Product" is created
    When I wait for index sync
    And I search for "New Product"
    Then the new product should be found

  Scenario: Clear search cache
    Given search cache contains stale results
    When I clear search cache
    Then subsequent search should return fresh results

  Scenario: Search analytics tracking
    Given search tracking is enabled
    When I search for "antibodies"
    Then search query should be logged
    And result count should be recorded

  Scenario: Popular search terms
    Given multiple searches for "antibody" have been performed
    When I request popular search terms
    Then "antibody" should be in the list
