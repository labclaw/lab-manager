# 订单管理 — 采购订单的完整生命周期
Feature: Order Management
  As a lab manager at Shen Lab
  I want to track purchase orders from creation to receipt
  So that I know what has been ordered, received, and is still pending

  Background:
    Given a vendor "Fisher Scientific" exists

  # 创建订单
  Scenario: Create a new purchase order
    When I create an order with po_number "PO-2026-100" for the vendor
    Then the order should be created with status "pending"
    And the order should have po_number "PO-2026-100"

  # 添加订单项
  Scenario: Add items to an order
    Given an order "PO-2026-100" exists
    When I add an item with catalog "21-171-4" description "Oocyte Injector" quantity 3 unit "PK"
    And I add an item with catalog "S7653" description "Sodium Chloride 500g" quantity 2 unit "bottle"
    Then the order should have 2 items
    And the first item should have catalog "21-171-4"

  # 收货
  Scenario: Receive an order creates inventory
    Given an order "PO-2026-100" with 2 items exists
    And a product matching each order item exists
    When I receive the order with received_by "Sylvie"
    Then the order status should be "received"
    And 2 inventory items should be created
    And each inventory item should have status "available"

  # 订单列表与过滤
  Scenario: List orders filtered by vendor
    Given 3 orders for vendor "Fisher Scientific"
    And 2 orders for vendor "Sigma-Aldrich"
    When I list orders for vendor "Fisher Scientific"
    Then I should see 3 orders

  # 订单详情包含项目
  Scenario: Order detail includes items and vendor info
    Given an order with 3 items exists
    When I get the order detail
    Then the response should include vendor name
    And the response should include 3 items with catalog numbers
