# 批量操作 — 高效数据处理
Feature: Bulk Operations and Batch Processing
  As a lab manager
  I want to perform bulk operations efficiently
  So that I can process large datasets quickly

  Background:
    Given I am authenticated as staff "admin1"

  # 批量导入
  Scenario: Import 100 products from CSV
    Given a CSV file with 100 products
    When I import the CSV
    Then 100 products should be created
    And a summary should show success count

  Scenario: Import with validation errors
    Given a CSV with 50 products, 10 with invalid data
    When I import the CSV
    Then 40 products should be created
    And 10 errors should be reported

  Scenario: Import with duplicate catalog numbers
    Given a CSV with products having duplicate catalog numbers
    When I import the CSV
    Then duplicates should be skipped or reported
    And valid products should be imported

  # 批量更新
  Scenario: Bulk update prices by percentage
    Given 100 products with various prices
    When I increase all prices by 10%
    Then all products should have updated prices
    And price history should be recorded

  Scenario: Bulk update vendor for products
    Given products from vendor "OldVendor"
    And vendor "NewVendor" exists
    When I transfer products to "NewVendor"
    Then products should reference NewVendor
    And historical data should be preserved

  Scenario: Bulk update reorder levels
    Given 50 products without reorder levels
    When I set reorder level to 10 for all
    Then 50 products should have reorder_level 10

  # 批量导出
  Scenario: Export all inventory to CSV
    Given 500 inventory records
    When I export inventory to CSV
    Then a CSV file should be generated
    And 500 rows should be included

  Scenario: Export filtered results
    Given inventory with various products
    When I export low stock items only
    Then CSV should contain only low stock items
    And headers should be included

  # 批量删除
  Scenario: Delete multiple selected products
    Given 20 products are selected
    When I delete selected products
    Then 20 products should be deleted
    And confirmation should be required

  Scenario: Delete with cascading rules
    Given 10 products with inventory
    When I delete with cascade option
    Then products and inventory should be deleted

  # 并发限制
  Scenario: Bulk operation too large
    Given 10000 products to import
    When I import in batches of 100
    Then 100 batches should be processed
    And progress should be reported

  # 事务处理
  Scenario: Rollback on bulk operation failure
    Given 50 products to import
    When 25th product causes an error
    Then no products should be created
    And error should be reported
