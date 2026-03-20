# 产品管理 — 边界情况和高级场景
Feature: Products Edge Cases and Advanced Scenarios
  As a lab manager
  I want to handle complex product scenarios
  So that the product catalog remains accurate and useful

  Background:
    Given I am authenticated as staff "admin1"

  # 重复产品检测
  Scenario: Detect duplicate product by catalog number
    Given product "Antibody A" with catalog number "AB123" exists
    When I create a product "Antibody B" with catalog number "AB123"
    Then I should receive a duplicate warning
    And the warning should reference the existing product

  Scenario: Detect similar product names
    Given product "DMEM Medium" exists
    When I create a product "DMEM Media"
    Then I should receive a similarity warning
    And I should be prompted to confirm

  # 批量操作
  Scenario: Bulk import products from CSV
    Given a CSV file with 100 valid products
    When I import the products
    Then 100 products should be created
    And the response should include import summary

  Scenario: Bulk import with some invalid rows
    Given a CSV file with 100 products where 5 have invalid data
    When I import the products
    Then 95 products should be created
    And 5 errors should be reported
    And the error report should include row numbers

  # 价格历史
  Scenario: Track price changes over time
    Given product "Reagent X" with price $50
    When the vendor updates price to $55
    Then the price history should be recorded
    And I should be able to query historical prices

  # 供应商变更
  Scenario: Change product vendor
    Given product "Pipette Tips" from vendor "Vendor A"
    And vendor "Vendor B" exists
    When I change the product vendor to "Vendor B"
    Then the product should reference "Vendor B"
    And historical orders from "Vendor A" should be preserved

  # 库存单位管理
  Scenario: Product with multiple units of measure
    Given product "Ethanol" with base unit "mL"
    When I add unit conversion "1 L = 1000 mL"
    Then I can order in liters or milliliters
    And inventory should convert between units correctly

  # 过期跟踪
  Scenario: Track product expiration dates
    Given product "Enzyme Mix" with expiration date "2024-12-31"
    When I query expiring products
    Then "Enzyme Mix" should be listed
    And days until expiration should be shown

  # 危险品标记
  Scenario: Mark hazardous products
    Given product "Ethidium Bromide"
    When I mark it as hazardous with handling instructions
    Then the product should display hazard warnings
    And SDS link should be required

  # 附件管理
  Scenario: Attach product documents
    Given product "Sequencing Kit"
    When I attach a PDF protocol document
    Then the document should be linked to the product
    And users can download the protocol

  # 批次追踪
  Scenario: Track product by lot number
    Given product "FBS" with lot number "LOT123"
    When I receive a new shipment with lot number "LOT456"
    Then both lots should be tracked separately
    And inventory should show quantities per lot

  # 合并产品
  Scenario: Merge duplicate products
    Given product "PBS Buffer A" with 10 units
    And product "PBS Buffer B" (duplicate) with 5 units
    When I merge "PBS Buffer B" into "PBS Buffer A"
    Then "PBS Buffer A" should have 15 units
    And "PBS Buffer B" should be marked as merged
