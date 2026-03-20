Feature: Edge Cases Products
  As a system
  I want to handle product edge cases
  So that product data is reliable

  Background:
    Given I am authenticated as "admin"

  Scenario: Product with very long name
    When I create product with 500 character name
    Then creation should fail
    And error should indicate length limit

  Scenario: Product with special characters
    When I create product "Reagent α & β (99.9%)"
    Then product should be created
    And name should be stored correctly

  Scenario: Product catalog number with spaces
    When I create product with catalog "CAT 001"
    Then spaces should be handled
    Or trimmed automatically

  Scenario: Duplicate catalog number different vendor
    Given product "CAT-001" for vendor A
    When I create product "CAT-001" for vendor B
    Then creation should succeed
    Or warning should be shown about cross-vendor duplicates

  Scenario: Product with no vendor
    When I create product without vendor
    Then creation should fail
    Or product should be "unassigned"

  Scenario: Product price as zero
    When I create product with price 0
    Then creation should succeed
    And warning about free product should show

  Scenario: Product with negative price
    When I create product with price -10
    Then creation should fail
    And error should indicate invalid price

  Scenario: Product with extremely high price
    When I create product with price $9999999.99
    Then creation should succeed
    And no overflow should occur

  Scenario: Product CAS number format variations
    When I create products with CAS:
      | cas_number |
      | 64-17-5    |
      | 0064-17-05 |
      | 64175      |
    Then valid formats should be normalized
    And invalid formats should be rejected

  Scenario: Product with multiple categories
    When I assign product to 2 categories
    Then assignment should be handled per schema
    And category should be queryable

  Scenario: Product image upload
    When I upload product image
    Then image should be stored
    And thumbnail should be generated

  Scenario: Product image too large
    When I upload 50MB image
    Then upload should be rejected
    And size limit should be indicated

  Scenario: Product document attachment
    When I attach SDS document to product
    Then document should be linked
    And document should be downloadable

  Scenario: Product deletion with order history
    Given product has historical orders
    When I delete product
    Then deletion should be soft
    And order history should be preserved

  Scenario: Product archive and restore
    Given product is archived
    When I restore product
    Then product should be active
    And historical data should be intact
