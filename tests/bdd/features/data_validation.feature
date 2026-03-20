Feature: Data Validation
  As a system
  I want to validate all input data
  So that data integrity is maintained

  Background:
    Given I am authenticated as "admin"

  Scenario: Product name required
    When I create product without name
    Then request should fail with 422
    And error should indicate "name is required"

  Scenario: Product catalog number uniqueness
    Given product with catalog_number "CAT-001" exists
    When I create product with catalog_number "CAT-001"
    Then request should fail with 422
    And error should indicate "catalog_number already exists"

  Scenario: Quantity cannot be negative
    When I create inventory with quantity -5
    Then request should fail with 422
    And error should indicate "quantity must be non-negative"

  Scenario: Valid date format
    When I create order with date "invalid-date"
    Then request should fail with 422
    And error should indicate "invalid date format"

  Scenario: Email format validation
    When I create staff with email "not-an-email"
    Then request should fail with 422
    And error should indicate "invalid email format"

  Scenario: Foreign key validation
    When I create inventory with non-existent product_id 99999
    Then request should fail with 422
    And error should indicate "product_id does not exist"

  Scenario: Enum value validation
    When I create order with status "invalid_status"
    Then request should fail with 422
    And error should indicate "invalid status value"

  Scenario: String length limits
    When I create vendor with name of 500 characters
    Then request should fail with 422
    And error should indicate "name exceeds maximum length"

  Scenario: Numeric range validation
    When I create product with min_stock_level -1
    Then request should fail with 422
    And error should indicate "min_stock_level must be >= 0"

  Scenario: CAS number format
    When I create product with cas_number "invalid"
    Then request should fail with 422
    And error should indicate "invalid CAS number format"

  Scenario: URL format validation
    When I create vendor with website "not-a-url"
    Then request should fail with 422
    And error should indicate "invalid URL format"

  Scenario: Phone format validation
    When I create vendor with phone "abc123"
    Then request should fail with 422
    And error should indicate "invalid phone format"

  Scenario: Lot number format
    When I create inventory with lot_number containing special chars "<script>"
    Then request should fail with 422
    And error should indicate "invalid characters in lot_number"

  Scenario: Bulk validation
    When I import CSV with 3 valid and 2 invalid rows
    Then import should partially succeed
    And 3 items should be created
    And 2 errors should be reported

  Scenario: Cross-field validation
    When I create order with date_from after date_to
    Then request should fail with 422
    And error should indicate "date_from must be before date_to"

  Scenario: Conditional validation
    Given product is marked as hazardous
    When I create product without hazard_info
    Then request should fail with 422
    And error should indicate "hazard_info required for hazardous products"

  Scenario: Update validation preserves required fields
    Given product "Reagent A" exists with name "Reagent A"
    When I update product with empty name
    Then request should fail with 422
    And original name should be preserved
