# 库存管理界面 — 查看、消耗、转移、调整、处置
Feature: Inventory Management UI
  As a lab scientist at Shen Lab
  I want to manage reagent inventory through the web interface
  So that I can track what we have, use it, move it, and dispose of expired items

  Background:
    Given I am logged in as a scientist
    And I am on the inventory view

  # 库存列表
  @wip
  Scenario: Inventory list shows items with key fields
    Given 15 inventory items exist across locations
    When the inventory view loads
    Then I should see a table with columns "Product", "Location", "Qty", "Status", "Expiry"
    And each row should show the product name and current quantity

  # 按位置筛选
  @wip
  Scenario: Filter inventory by location
    Given inventory items in "Freezer -80C" and "Fridge 4C"
    When I select location filter "Freezer -80C"
    Then only items in "Freezer -80C" should be displayed

  # 按状态筛选
  @wip
  Scenario: Filter inventory by status
    Given inventory items with statuses "available", "opened", "disposed"
    When I select status filter "available"
    Then only items with status "available" should be displayed

  # 低库存筛选
  @wip
  Scenario: Filter shows low stock items
    Given 3 inventory items are below reorder level
    When I click the "Low Stock" filter
    Then I should see exactly 3 items
    And each item should have a "Low Stock" badge

  # 即将过期筛选
  @wip
  Scenario: Filter shows expiring items
    Given 4 inventory items expire within 30 days
    When I click the "Expiring Soon" filter
    Then I should see exactly 4 items
    And each item should show the expiry date highlighted

  # 搜索库存
  @wip
  Scenario: Search inventory by product name
    Given an inventory item for product "Trypsin-EDTA" exists
    When I type "trypsin" in the inventory search input
    Then only matching items should be displayed

  # 消耗操作
  @wip
  Scenario: Consume inventory item via modal
    Given an inventory item "Anti-GFP Antibody" with quantity 10
    When I click the "Consume" action on that item
    Then a consume modal should appear
    When I enter quantity "3" and reason "Western blot experiment"
    And I click "Confirm"
    Then I should see a success toast "Consumed 3 units"
    And the item quantity should update to 7

  # 消耗超过库存
  @wip
  Scenario: Cannot consume more than available quantity
    Given an inventory item with quantity 5
    When I click the "Consume" action
    And I enter quantity "10" and reason "test"
    And I click "Confirm"
    Then I should see an error toast containing "insufficient"
    And the item quantity should remain 5

  # 转移操作
  @wip
  Scenario: Transfer inventory item to another location
    Given an inventory item in "Freezer -80C"
    And a location "Fridge 4C" exists
    When I click the "Transfer" action on that item
    Then a transfer modal should appear with a location dropdown
    When I select location "Fridge 4C"
    And I click "Confirm"
    Then I should see a success toast "Transferred"
    And the item location should update to "Fridge 4C"

  # 调整库存
  @wip
  Scenario: Adjust inventory quantity after physical count
    Given an inventory item with quantity 10
    When I click the "Adjust" action
    And I enter new quantity "8" with reason "Physical count correction"
    And I click "Confirm"
    Then I should see a success toast "Adjusted"
    And the item quantity should update to 8

  # 处置过期库存
  @wip
  Scenario: Dispose of expired inventory item
    Given an expired inventory item exists
    When I click the "Dispose" action
    And I enter reason "Expired 2026-03-01"
    And I click "Confirm"
    Then I should see a success toast "Disposed"
    And the item status should change to "disposed"
    And the action buttons should be disabled

  # 查看历史记录
  @wip
  Scenario: View consumption history for an item
    Given an inventory item with 3 consumption log entries
    When I click on the inventory item row
    Then the detail panel should show an "Activity History" section
    And I should see 3 log entries with timestamps and actions

  # 已处置项目无操作
  @wip
  Scenario: Disposed items show no action buttons
    Given a disposed inventory item exists
    When I view the disposed item in the list
    Then the row should be visually greyed out
    And no action buttons should be visible for that item

  # 过期标记
  @wip
  Scenario: Expired items show EXPIRED badge
    Given an inventory item with expiry date in the past
    When the inventory view loads
    Then that item should show an "EXPIRED" badge in red

  # 空库存
  @wip
  Scenario: Empty inventory shows helpful message
    Given no inventory items exist
    When the inventory view loads
    Then I should see an empty state message "No inventory items"

  # 零数量禁用消耗
  @wip
  Scenario: Zero quantity items disable consume button
    Given an inventory item with quantity 0
    When I view the item actions
    Then the "Consume" button should be disabled
