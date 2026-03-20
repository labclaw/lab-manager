# 数据完整性 — 约束和引用一致性
Feature: Data Integrity and Constraints
  As a database administrator
  I want to ensure data integrity constraints
  So that the database remains consistent

  Background:
    Given I am authenticated as staff "admin1"

  # 外键约束
  Scenario: Order must non-existent vendor
    When I create an order referencing non-existent vendor
    Then I should receive a validation error
    And the error should indicate vendor not found

  Scenario: Order items reference valid product
    Given product "P-001" exists
    When I create an order with product "P-001"
    Then the order should be created successfully

  # 唯一约束
  Scenario: Duplicate vendor name
    Given vendor "Sigma" exists
    When I create another vendor "Sigma"
    Then I should receive a conflict error
    And the original vendor should be preserved

  Scenario: Duplicate catalog number
    Given product with catalog number "CAT-001" exists
    When I create product with catalog number "CAT-001"
    Then I should receive a conflict error

  # 级联删除
  Scenario: Delete vendor with orders
    Given vendor "V-001" with 5 orders
    When I delete vendor "V-001"
    Then I should receive a constraint error
    And the vendor should not be deleted

  Scenario: Delete product in inventory
    Given product "P-001" with 10 inventory items
    When I delete product "P-001"
    Then I should receive a constraint error
    And inventory should be deleted first

  # 数值范围
  Scenario: Negative inventory quantity
    When I adjust inventory to -10 units
    Then I should receive a validation error
    And quantity should be rejected

  Scenario: Order quantity exceeds stock
    Given product "P-001" with 5 units in stock
    When I create order for 10 units
    Then I should receive a warning or error
    And insufficient stock should be indicated

  # 并发更新
  Scenario: Concurrent order creation
    Given product "P-001" with 10 units in stock
    When two users try to order 8 units simultaneously
    Then only one order should succeed
    And stock should be updated correctly

  # 事务完整性
  Scenario: Rollback on order failure
    Given product "P-001" with 5 units in stock
    When I create order for 10 units
    Then no partial changes should be saved
    And stock should remain unchanged

  # 数据验证
  Scenario: Invalid email format
    When I create staff with email "invalid-email"
    Then I should receive a validation error
    And valid email format should be suggested

  Scenario: Invalid date range
    When I create order with delivery date in the past
    Then I should receive a validation error
    And date should be required to be future
