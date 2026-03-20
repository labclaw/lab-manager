Feature: Search Advanced
  As a lab user
  I want advanced search capabilities
  So that I can quickly find what I need

  Background:
    Given I am authenticated as "admin"
    And search index is synced

  Scenario: Full-text search across products
    Given products exist:
      | name           | description        |
      | Ethanol 99%    | Pure ethanol       |
      | Ethanol 70%    | Diluted ethanol    |
      | Acetone        | Common solvent     |
    When I search for "ethanol"
    Then I should receive 2 results
    And results should be ordered by relevance

  Scenario: Search with filters
    Given products exist:
      | name      | category    | vendor_id |
      | Product A | chemical    | 1         |
      | Product B | chemical    | 2         |
      | Product C | consumable  | 1         |
    When I search for "product" with filter:
      | field     | value     |
      | category  | chemical  |
    Then I should receive 2 results

  Scenario: Search by catalog number
    Given product with catalog_number "SIG-12345" exists
    When I search for "SIG-12345"
    Then I should find the exact product

  Scenario: Fuzzy search
    Given product "Acetonitrile" exists
    When I search for "acetonitril"
    Then I should find "Acetonitrile"

  Scenario: Search suggestions
    Given products exist:
      | name              |
      | Acetone           |
      | Acetonitrile      |
      | Acetic Acid       |
    When I request search suggestions for "ace"
    Then I should see suggestions:
      | suggestion        |
      | Acetone           |
      | Acetonitrile      |
      | Acetic Acid       |

  Scenario: Search with pagination
    Given 100 products match "reagent"
    When I search for "reagent" page 2
    Then I should receive results 11-20
    And total count should be 100

  Scenario: Search by lot number
    Given inventory with lot_number "LOT-2025-001" exists
    When I search for "LOT-2025-001"
    Then I should find the inventory item

  Scenario: Search across multiple entities
    Given vendor "Sigma" exists
    And product "Sigma Reagent" from vendor "Sigma" exists
    When I search for "Sigma"
    Then I should receive vendor results
    And I should receive product results

  Scenario: Search by date range
    Given orders exist:
      | date       | po_number |
      | 2025-01-15 | PO-001    |
      | 2025-02-20 | PO-002    |
      | 2025-03-10 | PO-003    |
    When I search orders from "2025-02-01" to "2025-02-28"
    Then I should find order "PO-002"

  Scenario: Search with sorting
    Given products exist:
      | name      | created_at  |
      | Product A | 2025-01-01  |
      | Product B | 2025-02-01  |
      | Product C | 2025-03-01  |
    When I search for "Product" sorted by created_at descending
    Then results should be:
      | name      |
      | Product C |
      | Product B |
      | Product A |

  Scenario: Search with wildcards
    Given products exist:
      | name          |
      | Ethanol 70%   |
      | Ethanol 99%   |
      | Methanol      |
    When I search for "Ethanol %"
    Then I should find 2 products

  Scenario: Search highlighting
    Given product "Ethanol Reagent Grade" exists
    When I search for "Ethanol"
    Then result should highlight "Ethanol"

  Scenario: Recent searches
    Given I have searched for "acetone" and "ethanol"
    When I request recent searches
    Then I should see both terms
    And results should be ordered by recency

  Scenario: Search by CAS number
    Given product with cas_number "64-17-5" exists
    When I search for "64-17-5"
    Then I should find the product

  Scenario: Empty search returns all
    When I search with empty query
    Then I should receive all results
    And results should be paginated
